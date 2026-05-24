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
# open sheet
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
    raise Exception("Google API 過載")

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
# session
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

    st.subheader("登入")

    role = st.selectbox("身分", ["舍監", "行政", "樓長"])

    # 樓長：新增宿舍別
    dorm = None
    if role == "樓長":
        dorm = st.selectbox("宿舍別", ["A棟", "B棟", "總樓"])

    df = load_users(role)

    if df.empty:
        st.error("無帳號")
        st.stop()

    user = st.selectbox("使用者", df.iloc[:, 1].astype(str).tolist())
    pwd = st.text_input("密碼", type="password")

    if st.button("登入"):

        ok = df[
            (df.iloc[:, 1].astype(str).str.strip() == user) &
            (df.iloc[:, 2].astype(str).str.strip() == pwd)
        ]

        if not ok.empty:
            st.session_state.login = True
            st.session_state.role = role
            st.session_state.user = user

            # 判斷總樓
            if role == "樓長":
                st.session_state.is_main = (dorm == "總樓")

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
# 讀 rollcall
# ==================================================
@st.cache_data(ttl=CACHE_TTL)
def load_rollcall():
    data = {}
    for ws in rollcall_ss.worksheets():
        try:
            datetime.strptime(ws.title, "%Y-%m-%d")
            df = pd.DataFrame(ws.get_all_values()[1:], columns=ws.get_all_values()[0])
            df.columns = df.columns.str.strip()
            data[ws.title] = df
        except:
            continue
    return data

data = load_rollcall()
dates = sorted(data.keys(), reverse=True)

# ==================================================
# 搜尋 + 月份
# ==================================================
month = st.selectbox("月份", ["全部"] + sorted(list({d[:7] for d in dates}), reverse=True))
search = st.text_input("搜尋學號 / 姓名")

def filter_by_month(d):
    if month == "全部":
        return True
    return d.startswith(month)

# ==================================================
# 門禁（完全保留你原版）
# ==================================================
def load_sheet_df(ss, name):
    try:
        ws = ss.worksheet(name)
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame()

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

    df = df.sort_values(by=["姓名", "日期", "刷卡時間"])

    selected = []
    threshold = timedelta(minutes=60)

    for (name, date), g in df.groupby(["姓名", "日期"]):
        last = None
        for idx, row in g.iterrows():
            if last is None or row["刷卡時間"] - last > threshold:
                selected.append(idx)
            last = row["刷卡時間"]

    df = df.loc[selected].copy()

    leave = load_sheet_df(semester_url, "外宿申請")
    long_leave = load_sheet_df(semester_url, "長期外宿")
    late = load_sheet_df(semester_url, "長期晚歸")

    status = []

    weekday_map = {0:"一",1:"二",2:"三",3:"四",4:"五",5:"六",6:"日"}

    for _, r in df.iterrows():

        sid = str(r["學號"])
        d = pd.to_datetime(r["日期"])
        t = r["刷卡時間"]

        s = "未申請"

        if not leave.empty:
            m = leave[(leave["學號"].astype(str) == sid)]
            if not m.empty:
                s = "外宿"

        if not long_leave.empty:
            s = "長期外宿"

        if not late.empty:
            s = "晚歸"

        status.append(s)

    df["狀態判斷"] = status

    return df, df.head(), df.tail()

# ==================================================
# TAB控制（修復 None bug）
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

ui_tabs = st.tabs(tabs)

# ==================================================
# 缺席
# ==================================================
if "每日缺席名單" in tabs:

    i = tabs.index("每日缺席名單")

    with ui_tabs[i]:

        for d in dates:

            if not filter_by_month(d):
                continue

            df = data[d]
            miss = df[df["狀態"] == "缺"]

            if search:
                miss = miss[
                    miss["學號"].str.contains(search) |
                    miss["姓名"].str.contains(search)
                ]

            st.subheader(d)
            st.dataframe(miss[["房號","學號","姓名"]])

# ==================================================
# 連三天
# ==================================================
if "連三天不假外宿" in tabs:

    i = tabs.index("連三天不假外宿")

    with ui_tabs[i]:

        found = False

        for i2 in range(len(dates)-2):

            g = dates[i2:i2+3]

            if not all(filter_by_month(x) for x in g):
                continue

            all_m = []

            for d in g:
                df = data[d]
                all_m.append(df[df["狀態"] == "缺"])

            res = pd.concat(all_m)

            res = res.groupby(["房號","學號","姓名"]).size().reset_index(name="count")
            res = res[res["count"] == 3]

            if search:
                res = res[
                    res["學號"].str.contains(search) |
                    res["姓名"].str.contains(search)
                ]

            if not res.empty:
                st.subheader(f"{g[0]} ~ {g[2]}")
                st.dataframe(res)
                found = True

        if not found:
            st.info("無連續三天不假外宿")

# ==================================================
# 門禁
# ==================================================
if "上學期門禁" in tabs:

    i = tabs.index("上學期門禁")

    with ui_tabs[i]:
        f = st.file_uploader("Excel")

        if f:
            r, c, n = analyze_gate(f, upper_ss)
            st.dataframe(n)
            st.dataframe(c)

if "下學期門禁" in tabs:

    i = tabs.index("下學期門禁")

    with ui_tabs[i]:
        f = st.file_uploader("Excel")

        if f:
            r, c, n = analyze_gate(f, lower_ss)
            st.dataframe(n)
            st.dataframe(c)

# ==================================================
# 整潔（總樓）
# ==================================================
if "整潔比賽" in tabs:

    i = tabs.index("整潔比賽")

    with ui_tabs[i]:
        st.title("總樓整潔比賽")