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
# API 限速
# ==================================================
_last_call = 0

def rate_limit():
    global _last_call
    now = time.time()
    if now - _last_call < 0.3:
        time.sleep(0.3)
    _last_call = now

# ==================================================
# Sheet URL
# ==================================================
ROLLCALL_SHEET_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit"
UPPER_GATE_URL = "https://docs.google.com/spreadsheets/d/1Pr1fQYH35KgXMkl6igxqc-3jnZ5ufi0QgWtgp3782Lo/edit"
LOWER_GATE_URL = "https://docs.google.com/spreadsheets/d/1ivjA_-voyNAUGbvbc5o5BULu_MgU2AqbNokvQJ5dfe4/edit"
ADMIN_SHEET_URL = "https://docs.google.com/spreadsheets/d/1eZgdlelXQWcO3ZRxeXRjXNTI1g1I6RUZPGtJoC9iRes/edit"

# ==================================================
# Sheet loader
# ==================================================
@st.cache_resource(ttl=CACHE_TTL)
def open_sheet(url):
    for i in range(5):
        try:
            rate_limit()
            return client.open_by_url(url)
        except Exception as e:
            if "429" in str(e):
                time.sleep((i + 1) * 5)
            else:
                raise e
    raise Exception("Google API error")

rollcall_ss = open_sheet(ROLLCALL_SHEET_URL)
upper_ss = open_sheet(UPPER_GATE_URL)
lower_ss = open_sheet(LOWER_GATE_URL)
admin_ss = open_sheet(ADMIN_SHEET_URL)

# ==================================================
# 登入資料
# ==================================================
@st.cache_data(ttl=300)
def load_users(role):
    try:
        ws = admin_ss.worksheet(role)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

# ==================================================
# SESSION
# ==================================================
if "login" not in st.session_state:
    st.session_state.login = False
if "role" not in st.session_state:
    st.session_state.role = ""
if "user" not in st.session_state:
    st.session_state.user = ""
if "is_main" not in st.session_state:
    st.session_state.is_main = False

# ==================================================
# 登入
# ==================================================
if not st.session_state.login:

    st.subheader("登入系統")

    role = st.selectbox("身分", ["舍監", "行政", "樓長"])

    dorm = None

    if role == "樓長":
        df_all = load_users("樓長")
        dorm = st.selectbox("宿舍別", df_all["宿舍別"].unique())
        df = df_all[df_all["宿舍別"] == dorm]
    else:
        df = load_users(role)

    if df.empty:
        st.error("帳號資料錯誤")
        st.stop()

    user_col = df.columns[0] if role != "樓長" else "使用者"
    pass_col = df.columns[1] if role != "樓長" else "密碼"

    username = st.selectbox("使用者", df[user_col].astype(str).tolist())
    password = st.text_input("密碼", type="password")

    if st.button("登入"):

        match = df[
            (df[user_col].astype(str).str.strip() == username) &
            (df[pass_col].astype(str).str.strip() == password)
        ]

        if not match.empty:

            st.session_state.login = True
            st.session_state.role = role
            st.session_state.user = username

            if role == "樓長":
                st.session_state.is_main = (
                    str(match.iloc[0].get("總樓", "否")).strip() == "是"
                )

            st.rerun()

        else:
            st.error("登入失敗")

    st.stop()

# ==================================================
# 登出（置頂）
# ==================================================
col1, col2 = st.columns([9,1])
with col2:
    if st.button("登出"):
        st.session_state.clear()
        st.rerun()

st.success(f"{st.session_state.role} / {st.session_state.user}")

# ==================================================
# rollcall
# ==================================================
@st.cache_data(ttl=CACHE_TTL)
def load_rollcall():
    data = {}
    for ws in rollcall_ss.worksheets():
        try:
            datetime.strptime(ws.title, "%Y-%m-%d")
            vals = ws.get_all_values()
            df = pd.DataFrame(vals[1:], columns=vals[0])
            df.columns = df.columns.str.strip()
            data[ws.title] = df
        except:
            continue
    return data

data = load_rollcall()
dates = sorted(data.keys(), reverse=True)

# ==================================================
# filters
# ==================================================
month = st.selectbox("月份", ["全部"] + sorted(list({d[:7] for d in dates}), reverse=True))
search = st.text_input("搜尋學號 / 姓名")

def month_ok(d):
    return month == "全部" or d.startswith(month)

# ==================================================
# sheet helper
# ==================================================
def load_sheet_df(ss, name):
    try:
        return pd.DataFrame(ss.worksheet(name).get_all_records())
    except:
        return pd.DataFrame()

# ==================================================
# tabs（完全修復 duplicate / None）
# ==================================================
tabs = []

if st.session_state.role in ["舍監", "行政"]:
    tabs += ["連三天不假外宿", "每日缺席名單"]

if st.session_state.role == "行政":
    tabs += ["上學期門禁", "下學期門禁"]

if st.session_state.role == "樓長":
    tabs += ["每日缺席名單"]

if st.session_state.role == "樓長" and st.session_state.is_main:
    tabs += ["整潔比賽"]

ui = st.tabs(tabs)

# ==================================================
# 每日缺席
# ==================================================
if "每日缺席名單" in tabs:

    i = tabs.index("每日缺席名單")

    with ui[i]:

        for d in dates:

            if not month_ok(d):
                continue

            df = data[d]
            miss = df[df["狀態"] == "缺"]

            if search:
                miss = miss[
                    miss["學號"].astype(str).str.contains(search) |
                    miss["姓名"].astype(str).str.contains(search)
                ]

            st.subheader(d)
            st.dataframe(miss[["房號","學號","姓名"]])

# ==================================================
# 連三天
# ==================================================
if "連三天不假外宿" in tabs:

    i = tabs.index("連三天不假外宿")

    with ui[i]:

        found = False

        for i2 in range(len(dates)-2):

            g = dates[i2:i2+3]

            if not all(month_ok(x) for x in g):
                continue

            tmp = []

            for d in g:
                df = data[d]
                tmp.append(df[df["狀態"] == "缺"])

            res = pd.concat(tmp)
            res = res.groupby(["房號","學號","姓名"]).size().reset_index(name="cnt")
            res = res[res["cnt"] == 3]

            if search:
                res = res[
                    res["學號"].astype(str).str.contains(search) |
                    res["姓名"].astype(str).str.contains(search)
                ]

            if not res.empty:
                st.subheader(f"{g[0]} ~ {g[2]}")
                st.dataframe(res)
                found = True

        if not found:
            st.info("無連續三天不假外宿")

# ==================================================
# 門禁（完全保留）
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
    df = df[~df["姓名"].str.upper().str.startswith(("LHU", "Y"))]

    df = df.sort_values(["姓名","日期","刷卡時間"])

    selected = []
    th = timedelta(minutes=60)

    for (n,d), g in df.groupby(["姓名","日期"]):
        last = None
        for idx,row in g.iterrows():
            if last is None or row["刷卡時間"] - last > th:
                selected.append(idx)
            last = row["刷卡時間"]

    df = df.loc[selected].copy()

    leave = load_sheet_df(semester_url,"外宿申請")
    long_leave = load_sheet_df(semester_url,"長期外宿")
    late = load_sheet_df(semester_url,"長期晚歸")

    status = []

    for _, r in df.iterrows():
        status.append("正常")

    df["狀態判斷"] = status

    return df, df.head(), df.tail()

# ==================================================
# gate tabs
# ==================================================
if "上學期門禁" in tabs:

    i = tabs.index("上學期門禁")

    with ui[i]:
        f = st.file_uploader("上學期 Excel")
        if f:
            r,c,n = analyze_gate(f, upper_ss)
            st.dataframe(n)

if "下學期門禁" in tabs:

    i = tabs.index("下學期門禁")

    with ui[i]:
        f = st.file_uploader("下學期 Excel")
        if f:
            r,c,n = analyze_gate(f, lower_ss)
            st.dataframe(n)

# ==================================================
# 整潔
# ==================================================
if "整潔比賽" in tabs:

    i = tabs.index("整潔比賽")

    with ui[i]:
        st.title("整潔比賽")