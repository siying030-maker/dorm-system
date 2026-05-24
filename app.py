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
ADMIN_URL = "https://docs.google.com/spreadsheets/d/1eZgdlelXQWcO3ZRxeXRjXNTI1g1I6RUZPGtJoC9iRes/edit"
ROLLCALL_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit"
UPPER_URL = "https://docs.google.com/spreadsheets/d/1Pr1fQH35KgXMkl6igxqc-3jnZ5ufi0QgWtgp3782Lo/edit"
LOWER_URL = "https://docs.google.com/spreadsheets/d/1ivjA_-voyNAUGbvbc5o5BULu_MgU2AqbNokvQJ5dfe4/edit"

# ==================================================
# 防 API 爆炸
# ==================================================
_last = 0

def rate_limit():
    global _last
    now = time.time()
    if now - _last < 0.3:
        time.sleep(0.3)
    _last = time.time()

# ==================================================
# 開啟 Sheet（安全版）
# ==================================================
@st.cache_resource(ttl=CACHE_TTL)
def open_sheet(url):
    return client.open_by_url(url)

admin_ss = open_sheet(ADMIN_URL)
rollcall_ss = open_sheet(ROLLCALL_URL)
upper_ss = open_sheet(UPPER_URL)
lower_ss = open_sheet(LOWER_URL)

# ==================================================
# 登入資料（3個sheet）
# ==================================================
@st.cache_data(ttl=CACHE_TTL)
def load_admin():

    roles = ["舍監", "行政", "樓長"]
    data = {}

    for r in roles:
        ws = admin_ss.worksheet(r)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()
        data[r] = df

    return data

admin_data = load_admin()

# ==================================================
# 登入系統
# ==================================================
if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:

    st.subheader("🔐 登入")

    role = st.selectbox("身分", ["舍監", "行政", "樓長"])
    user = st.text_input("帳號")
    pwd = st.text_input("密碼", type="password")

    if st.button("登入"):

        df = admin_data[role]

        ok = df[
            (df.iloc[:, 0].astype(str) == user) &
            (df.iloc[:, 1].astype(str) == pwd)
        ]

        if not ok.empty:
            st.session_state.login = True
            st.session_state.role = role
            st.rerun()
        else:
            st.error("登入失敗")

    st.stop()

# ==================================================
# 登出
# ==================================================
col1, col2 = st.columns([8,1])
with col2:
    if st.button("🚪 登出"):
        st.session_state.login = False
        st.rerun()

st.write(f"👤 身分：{st.session_state.role}")

role = st.session_state.role

# ==================================================
# 點名資料
# ==================================================
@st.cache_data(ttl=CACHE_TTL)
def load_rollcall():

    data = {}
    sheets = rollcall_ss.worksheets()

    for ws in sheets:
        try:
            datetime.strptime(ws.title, "%Y-%m-%d")
            df = pd.DataFrame(ws.get_all_values()[1:], columns=ws.get_all_values()[0])
            df.columns = df.columns.str.strip()
            data[ws.title] = df
        except:
            continue

    return data

rollcall = load_rollcall()

# ==================================================
# 門禁分析（完整）
# ==================================================
def analyze_gate(file, ss):

    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()

    df["刷卡時間"] = pd.to_datetime(df["刷卡時間"], errors="coerce")
    df["日期"] = df["刷卡時間"].dt.date

    df = df[(df["刷卡時間"].dt.hour >= 0) & (df["刷卡時間"].dt.hour < 6)]
    df = df[~df["姓名"].astype(str).str.upper().str.startswith(("LHU", "Y"))]

    df = df.sort_values(["姓名","日期","刷卡時間"])

    keep = []
    last_gap = timedelta(minutes=60)

    for (n,d), g in df.groupby(["姓名","日期"]):
        last = None
        for i,r in g.iterrows():
            if last is None or r["刷卡時間"] - last > last_gap:
                keep.append(i)
            last = r["刷卡時間"]

    df = df.loc[keep]

    leave = pd.DataFrame(ss.worksheet("外宿申請").get_all_records())
    long = pd.DataFrame(ss.worksheet("長期外宿").get_all_records())
    late = pd.DataFrame(ss.worksheet("長期晚歸").get_all_records())

    status = []

    for _, r in df.iterrows():

        sid = str(r["學號"])
        d = pd.to_datetime(r["日期"])
        t = r["刷卡時間"]

        s = "未申請"

        # 外宿
        if not leave.empty:
            m = leave[leave["學號"].astype(str) == sid]
            if not m.empty:
                s = "外宿"

        # 長期外宿
        if not long.empty:
            if sid in long["學號"].astype(str).values:
                s = "長期外宿"

        # 晚歸
        if not late.empty:
            m = late[late["學號"].astype(str) == sid]
            if not m.empty:
                limit = pd.to_datetime(m.iloc[0]["返回時間"]).time()
                s = "晚歸正常" if t.time() <= limit else "晚歸超時"

        status.append(s)

    df["狀態"] = status

    return df

# ==================================================
# TAB
# ==================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "連三天不假外宿",
    "每天點名不到名單",
    "上學期門禁",
    "下學期門禁"
])

# ==================================================
# 月份
# ==================================================
dates = sorted(rollcall.keys(), reverse=True)
months = sorted(list(set([d[:7] for d in dates])))

default = datetime.now().strftime("%Y-%m")

month = st.selectbox(
    "月份查詢（預設當月）",
    months,
    index=months.index(default) if default in months else 0
)

# ==================================================
# TAB1
# ==================================================
with tab1:

    st.header("連三天不假外宿")

    groups = [dates[i:i+3] for i in range(0,len(dates),3)]

    found = False

    for g in groups:

        if len(g) < 3:
            continue

        all_d = []

        for d in g:
            df = rollcall[d]
            tmp = df[df["狀態"]=="缺"].copy()
            tmp["日期"] = d
            all_d.append(tmp)

        if not all_d:
            continue

        df_all = pd.concat(all_d)

        res = df_all.groupby(["房號","學號","姓名"])["日期"].nunique().reset_index()
        res = res[res["日期"]==3]

        st.subheader(f"{g[0]} ~ {g[-1]}")

        if res.empty:
            st.info(f"{g[0]} ~ {g[-1]} 無連三天不假外宿")
        else:
            found = True
            st.dataframe(res)

# ==================================================
# TAB2
# ==================================================
with tab2:

    st.header("每天點名不到名單")

    all_miss = []

    for d in dates:

        if not d.startswith(month):
            continue

        df = rollcall.get(d)
        if df is None:
            continue

        miss = df[df["狀態"]=="缺"]

        if miss.empty:
            continue

        st.subheader(d)
        st.dataframe(miss[["房號","學號","姓名"]])

        all_miss.append(miss[["房號","學號","姓名"]])

    if all_miss:

        total = pd.concat(all_miss)

        freq = total.groupby(["房號","學號","姓名"]).size().reset_index(name="缺席次數")

        st.dataframe(freq.sort_values("缺席次數", ascending=False))

# ==================================================
# TAB3 / TAB4
# ==================================================
with tab3:

    if role in ["舍監","行政"]:

        f = st.file_uploader("上學期門禁")

        if f:
            df = analyze_gate(f, upper_ss)
            st.dataframe(df[["房號","學號","姓名"]])

with tab4:

    if role in ["行政"]:

        f = st.file_uploader("下學期門禁")

        if f:
            df = analyze_gate(f, lower_ss)
            st.dataframe(df[["房號","學號","姓名"]])

# ==================================================
# footer
# ==================================================
st.caption(f"更新時間 {datetime.now()}")