import streamlit as st
import pandas as pd
import gspread
import time

from io import BytesIO
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

# ==================================================
# 基本設定
# ==================================================
st.set_page_config(page_title="宿舍管理系統", layout="wide")
st.title("宿舍管理系統")

CACHE_TTL = 86400

# ==================================================
# Google API
# ==================================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["google"],
    scopes=SCOPES
)

client = gspread.authorize(creds)

# ==================================================
# Sheet URL
# ==================================================
ROLLCALL_SHEET_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit"
UPPER_GATE_URL = "https://docs.google.com/spreadsheets/d/1Pr1fQYH35KgXMkl6igxqc-3jnZ5ufi0QgWtgp3782Lo/edit"
LOWER_GATE_URL = "https://docs.google.com/spreadsheets/d/1ivjA_-voyNAUGbvbc5o5BULu_MgU2AqbNokvQJ5dfe4/edit"
ADMIN_SHEET_URL = "https://docs.google.com/spreadsheets/d/1eZgdlelXQWcO3ZRxeXRjXNTI1g1I6RUZPGtJoC9iRes/edit"

# ==================================================
# 防爆
# ==================================================
_last_call = 0

def rate_limit():
    global _last_call
    now = time.time()
    if now - _last_call < 0.3:
        time.sleep(0.3)
    _last_call = time.time()

# ==================================================
# open sheet
# ==================================================
@st.cache_resource(ttl=CACHE_TTL)
def open_sheet(url):
    for i in range(5):
        try:
            rate_limit()
            return client.open_by_url(url)
        except:
            time.sleep(2)
    raise Exception("Sheet open failed")

rollcall_ss = open_sheet(ROLLCALL_SHEET_URL)
upper_ss = open_sheet(UPPER_GATE_URL)
lower_ss = open_sheet(LOWER_GATE_URL)
admin_ss = open_sheet(ADMIN_SHEET_URL)

# ==================================================
# USERS
# ==================================================
@st.cache_data(ttl=300)
def load_users(role):
    ws = admin_ss.worksheet(role)
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip()
    return df

# ==================================================
# SESSION
# ==================================================
if "login" not in st.session_state:
    st.session_state.login = False

if "role" not in st.session_state:
    st.session_state.role = ""

if "user" not in st.session_state:
    st.session_state.user = ""

if "dorm" not in st.session_state:
    st.session_state.dorm = ""

# ==================================================
# LOGIN
# ==================================================
if not st.session_state.login:

    st.subheader("登入")

    role = st.selectbox("身分", ["舍監", "行政", "樓長"], key="role_select")

    user_df = load_users(role)

    if role == "樓長":
        dorm_list = user_df["A宿舍別"].dropna().unique().tolist()
        dorm = st.selectbox("宿舍別", dorm_list, key="dorm_select")

        filtered = user_df[user_df["A宿舍別"] == dorm]

        user = st.selectbox("使用者", filtered["B使用者"].tolist(), key="user_select")

        pw = st.text_input("密碼", type="password", key="pw1")

        if st.button("登入", key="login_btn"):

            ok = filtered[
                (filtered["B使用者"] == user) &
                (filtered["C密碼"].astype(str) == pw)
            ]

            if not ok.empty:
                st.session_state.login = True
                st.session_state.role = role
                st.session_state.user = user
                st.session_state.dorm = dorm
                st.rerun()
            else:
                st.error("密碼錯誤")

    else:

        user = st.selectbox("使用者", user_df.iloc[:,0].tolist(), key="user_select2")
        pw = st.text_input("密碼", type="password", key="pw2")

        if st.button("登入", key="login_btn2"):

            ok = user_df[
                (user_df.iloc[:,0] == user) &
                (user_df.iloc[:,1].astype(str) == pw)
            ]

            if not ok.empty:
                st.session_state.login = True
                st.session_state.role = role
                st.session_state.user = user
                st.rerun()
            else:
                st.error("密碼錯誤")

    st.stop()

# ==================================================
# TOP BAR (登出)
# ==================================================
col1, col2 = st.columns([8,1])
with col2:
    if st.button("登出", key="logout"):
        st.session_state.clear()
        st.rerun()

st.success(f"{st.session_state.role} / {st.session_state.user}")

# ==================================================
# DATA
# ==================================================
@st.cache_data(ttl=CACHE_TTL)
def load_rollcall():
    data = {}
    for ws in rollcall_ss.worksheets():
        try:
            df = pd.DataFrame(ws.get_all_records())
            df.columns = df.columns.str.strip()
            if "姓名" in df.columns:
                df = df[df["姓名"].astype(str).str.strip() != ""]
            data[ws.title] = df
        except:
            continue
    return data

data = load_rollcall()

# ==================================================
# MONTH FILTER
# ==================================================
months = sorted(list(set([d[:7] for d in data.keys() if len(d) >= 7])))
today_month = datetime.now().strftime("%Y-%m")

selected_month = st.selectbox(
    "月份",
    ["全部"] + months,
    index=0,
    key="month_select"
)

search = st.text_input("搜尋學號 / 姓名", key="search")

# ==================================================
# FILTER DATA BY MONTH
# ==================================================
def filter_by_month(df_dict):
    if selected_month == "全部":
        return df_dict
    return {k:v for k,v in df_dict.items() if k.startswith(selected_month)}

data = filter_by_month(data)
dates = sorted(data.keys(), reverse=True)

# ==================================================
# TAB CONTROL
# ==================================================
tabs = []

if st.session_state.role in ["舍監", "行政"]:
    tabs += ["連三天不假外宿", "每日缺席名單"]

if st.session_state.role == "行政":
    tabs += ["上學期門禁", "下學期門禁"]

if st.session_state.role == "樓長":
    tabs += ["每日缺席名單"]

# ==================================================
# TAB 1
# ==================================================
if "連三天不假外宿" in tabs:

    i = tabs.index("連三天不假外宿")
    with st.tabs(tabs)[i]:

        st.subheader("連三天不假外宿")

        if len(dates) < 3:
            st.info("資料不足")
        else:
            groups = [dates[i:i+3] for i in range(0, len(dates), 3)]

            found = False

            for g in groups:
                if len(g) < 3:
                    continue

                all_d = []
                for d in g:
                    df = data.get(d)
                    if df is None:
                        continue

                    tmp = df[df["狀態"].astype(str) == "缺"].copy()
                    tmp["日期"] = d
                    all_d.append(tmp)

                if not all_d:
                    continue

                df_all = pd.concat(all_d)

                res = df_all.groupby(["房號","學號","姓名"])["日期"].nunique().reset_index()
                res = res[res["日期"] == 3]

                if search:
                    res = res[
                        res["學號"].astype(str).str.contains(search) |
                        res["姓名"].astype(str).str.contains(search)
                    ]

                if not res.empty:
                    found = True
                    st.write(f"{g[0]} ~ {g[-1]}")
                    st.dataframe(res[["房號","學號","姓名"]])

            if not found:
                st.info("無連續三天不假外宿")

# ==================================================
# TAB 2
# ==================================================
if "每日缺席名單" in tabs:

    i = tabs.index("每日缺席名單")
    with st.tabs(tabs)[i]:

        st.subheader("每日缺席名單")

        found = False

        for d in dates:
            df = data.get(d)
            if df is None:
                continue

            miss = df[df["狀態"].astype(str) == "缺"]

            if search:
                miss = miss[
                    miss["學號"].astype(str).str.contains(search) |
                    miss["姓名"].astype(str).str.contains(search)
                ]

            if not miss.empty:
                found = True
                st.write(d)
                st.dataframe(miss[["房號","學號","姓名"]])

        if not found:
            st.info("無缺席資料")

# ==================================================
# TAB 3 & 4 (門禁保留)
# ==================================================
def analyze_gate(file, semester_url):

    if file is None:
        return None, None, None

    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()

    df["刷卡時間"] = pd.to_datetime(df["刷卡時間"], errors="coerce")
    df["日期"] = df["刷卡時間"].dt.date

    df = df[(df["刷卡時間"].dt.hour >= 0) & (df["刷卡時間"].dt.hour < 6)]

    df["姓名"] = df["姓名"].astype(str)
    df = df[~df["姓名"].str.upper().str.startswith(("LHU","Y"))]

    df = df.sort_values(["姓名","日期","刷卡時間"])

    selected = []
    for (n,d),g in df.groupby(["姓名","日期"]):
        last=None
        for i,r in g.iterrows():
            if last is None or r["刷卡時間"]-last>timedelta(minutes=60):
                selected.append(i)
            last=r["刷卡時間"]

    df = df.loc[selected]

    return df, df, df

if "上學期門禁" in tabs:
    i = tabs.index("上學期門禁")
    with st.tabs(tabs)[i]:
        f = st.file_uploader("上學期門禁", key="up_gate")
        if f:
            _,_,df = analyze_gate(f, upper_ss)
            st.dataframe(df[["房號","學號","姓名"]])

if "下學期門禁" in tabs:
    i = tabs.index("下學期門禁")
    with st.tabs(tabs)[i]:
        f = st.file_uploader("下學期門禁", key="low_gate")
        if f:
            _,_,df = analyze_gate(f, lower_ss)
            st.dataframe(df[["房號","學號","姓名"]])

# ==================================================
# 主管整潔（D總樓）
# ==================================================
if st.session_state.dorm == "D總樓":
    st.subheader("🏆 整潔比賽名次")
    st.info("此功能可自行接 ranking sheet")