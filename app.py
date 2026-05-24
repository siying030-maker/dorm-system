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
st.set_page_config(
    page_title="宿舍管理系統",
    layout="wide"
)

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
# API 防爆
# ==================================================
_last_call = 0

def rate_limit():
    global _last_call
    now = time.time()
    if now - _last_call < 0.3:
        time.sleep(0.3)
    _last_call = time.time()

# ==================================================
# Google Sheet URL
# ==================================================
ROLLCALL_SHEET_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit"
UPPER_GATE_URL = "https://docs.google.com/spreadsheets/d/1Pr1fQYH35KgXMkl6igxqc-3jnZ5ufi0QgWtgp3782Lo/edit"
LOWER_GATE_URL = "https://docs.google.com/spreadsheets/d/1ivjA_-voyNAUGbvbc5o5BULu_MgU2AqbNokvQJ5dfe4/edit"
ADMIN_SHEET_URL = "https://docs.google.com/spreadsheets/d/1eZgdlelXQWcO3ZRxeXRjXNTI1g1I6RUZPGtJoC9iRes/edit"

# ==================================================
# open sheet
# ==================================================
@st.cache_resource(ttl=CACHE_TTL)
def open_sheet(url):
    return client.open_by_url(url)

rollcall_ss = open_sheet(ROLLCALL_SHEET_URL)
upper_ss = open_sheet(UPPER_GATE_URL)
lower_ss = open_sheet(LOWER_GATE_URL)
admin_ss = open_sheet(ADMIN_SHEET_URL)

# ==================================================
# 登入資料
# ==================================================
@st.cache_data(ttl=300)
def load_users(role):
    ws = admin_ss.worksheet(role)
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip()
    return df

# ==================================================
# Session
# ==================================================
if "login" not in st.session_state:
    st.session_state.login = False

if "role" not in st.session_state:
    st.session_state.role = ""

if "user" not in st.session_state:
    st.session_state.user = ""

# ==================================================
# 登入
# ==================================================
if not st.session_state.login:

    st.subheader("登入系統")

    role = st.selectbox("身分", ["舍監", "行政", "樓長"])
    user_df = load_users(role)

    if user_df.empty:
        st.error("無帳號資料")
        st.stop()

    user_col = user_df.columns[0]
    pass_col = user_df.columns[1]

    username = st.selectbox("使用者", user_df[user_col].tolist())
    password = st.text_input("密碼", type="password")

    if st.button("登入"):

        match = user_df[
            (user_df[user_col].astype(str) == username) &
            (user_df[pass_col].astype(str) == password)
        ]

        if not match.empty:
            st.session_state.login = True
            st.session_state.role = role
            st.session_state.user = username
            st.rerun()
        else:
            st.error("登入失敗")

    st.stop()

# ==================================================
# 登入成功
# ==================================================
st.success(f"登入：{st.session_state.role} / {st.session_state.user}")

# ==================================================
# 點名資料
# ==================================================
@st.cache_data(ttl=CACHE_TTL)
def load_rollcall():
    data = {}
    for ws in rollcall_ss.worksheets():
        try:
            datetime.strptime(ws.title, "%Y-%m-%d")
            rate_limit()
            values = ws.get_all_values()

            if len(values) <= 1:
                continue

            df = pd.DataFrame(values[1:], columns=values[0])
            df.columns = df.columns.str.strip()

            data[ws.title] = df
        except:
            continue
    return data

# ==================================================
# sheet讀取
# ==================================================
def load_sheet(ss, name):
    try:
        ws = ss.worksheet(name)
        rate_limit()
        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

# ==================================================
# 門禁分析
# ==================================================
def analyze_gate(file, ss):

    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()

    df["刷卡時間"] = pd.to_datetime(df["刷卡時間"], errors="coerce")
    df["日期"] = df["刷卡時間"].dt.date

    df = df[(df["刷卡時間"].dt.hour < 6)]
    df["姓名"] = df["姓名"].astype(str)

    df = df[~df["姓名"].str.upper().str.startswith(("LHU","Y"))]

    df = df.sort_values(["姓名","日期","刷卡時間"])

    selected = []
    th = timedelta(minutes=60)

    for (n,d), g in df.groupby(["姓名","日期"]):
        last = None
        for i,r in g.iterrows():
            if last is None or r["刷卡時間"] - last > th:
                selected.append(i)
            last = r["刷卡時間"]

    df = df.loc[selected]

    leave = load_sheet(ss,"外宿申請")
    long = load_sheet(ss,"長期外宿")
    late = load_sheet(ss,"長期晚歸")

    status = []

    for _,r in df.iterrows():

        sid = str(r["學號"])
        d = pd.to_datetime(r["日期"])
        t = r["刷卡時間"]

        s = "未申請"

        if not leave.empty:
            leave["申請日期"] = pd.to_datetime(leave["申請日期"], errors="coerce")
            leave["結束日期"] = pd.to_datetime(leave["結束日期"], errors="coerce")

            if not leave[
                (leave["學號"].astype(str)==sid) &
                (leave["申請日期"]<=d) &
                (leave["結束日期"]>=d)
            ].empty:
                s = "外宿"

        if not long.empty:
            w = str(d.weekday())
            if not long[
                (long["學號"].astype(str)==sid) &
                (long["星期"].astype(str).str.contains(w))
            ].empty:
                s = "長期外宿"

        if not late.empty:
            m = late[late["學號"].astype(str)==sid]
            if not m.empty:
                limit = pd.to_datetime(m.iloc[0]["返回時間"]).time()
                s = "晚歸正常" if t.time()<=limit else "晚歸超時"

        status.append(s)

    df["狀態"] = status

    show = ["房號","學號","姓名"]

    return df, df[df["姓名"].str.startswith("C")][show], df[~df["姓名"].str.startswith("C")][show]

# ==================================================
# export
# ==================================================
def to_excel(df):
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return out.getvalue()

# ==================================================
# 權限
# ==================================================
role = st.session_state.role

tabs_list = []

if role in ["舍監","行政"]:
    tabs_list += ["連三天不假外宿","每天點名不到名單"]

if role == "行政":
    tabs_list += ["上學期門禁","下學期門禁"]

if role == "樓長":
    tabs_list += ["每天點名不到名單"]

tabs = st.tabs(tabs_list)

data = load_rollcall()
dates = sorted(data.keys(), reverse=True)

# ==================================================
# TAB1
# ==================================================
if "連三天不假外宿" in tabs_list:

    i = tabs_list.index("連三天不假外宿")
    with tabs[i]:

        st.header("連三天不假外宿")

        search = st.text_input("搜尋")

        for i in range(0,len(dates),3):

            g = dates[i:i+3]
            if len(g)<3: continue

            all_d = []

            for d in g:
                df = data.get(d)
                if df is None: continue

                tmp = df[df["狀態"]=="缺"].copy()
                tmp["日期"]=d
                all_d.append(tmp)

            st.subheader(f"{g[0]}~{g[-1]}")

            if not all_d:
                st.info("此三天無人連三天不假外宿")
                continue

            df_all = pd.concat(all_d)

            res = df_all.groupby(["房號","學號","姓名"])["日期"].nunique().reset_index()

            res = res[res["日期"]==3]

            if search:
                res = res[
                    res["學號"].astype(str).str.contains(search) |
                    res["姓名"].astype(str).str.contains(search)
                ]

            st.dataframe(res[["房號","學號","姓名"]])

# ==================================================
# TAB2
# ==================================================
if "每天點名不到名單" in tabs_list:

    i = tabs_list.index("每天點名不到名單")
    with tabs[i]:

        st.header("缺席名單")

        search = st.text_input("搜尋")

        all_miss = []

        for d in dates:

            df = data.get(d)
            if df is None: continue

            miss = df[df["狀態"]=="缺"]

            if miss.empty: continue

            show = miss[["房號","學號","姓名"]]

            if search:
                show = show[
                    show["學號"].astype(str).str.contains(search) |
                    show["姓名"].astype(str).str.contains(search)
                ]

            st.subheader(d)
            st.dataframe(show)

            all_miss.append(show)

# ==================================================
# TAB3/4
# ==================================================
def gate_tab(title, ss, key):

    with st.container():

        f = st.file_uploader(title, type=["xlsx"], key=key)

        if f:
            df,c,n = analyze_gate(f,ss)

            st.dataframe(n)
            st.dataframe(c)

            st.download_button("一般",to_excel(n),"n.xlsx")
            st.download_button("白卡",to_excel(c),"c.xlsx")

if "上學期門禁" in tabs_list:
    i=tabs_list.index("上學期門禁")
    with tabs[i]:
        gate_tab("上學期門禁",upper_ss,"up")

if "下學期門禁" in tabs_list:
    i=tabs_list.index("下學期門禁")
    with tabs[i]:
        gate_tab("下學期門禁",lower_ss,"low")

# ==================================================
# 登出
# ==================================================
if st.button("登出"):
    st.session_state.login=False
    st.rerun()

st.divider()
st.caption(f"更新時間 {datetime.now()}")