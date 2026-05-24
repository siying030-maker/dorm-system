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
# Sheets URL
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
# 登入
# ==================================================

@st.cache_data(ttl=300)
def load_users(role):
    ws = admin_ss.worksheet(role)
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip()
    return df

if "login" not in st.session_state:
    st.session_state.login = False
if "role" not in st.session_state:
    st.session_state.role = ""
if "user" not in st.session_state:
    st.session_state.user = ""

# ==================================================
# 登入畫面
# ==================================================

if not st.session_state.login:

    st.subheader("登入系統")

    role = st.selectbox("身分", ["舍監", "行政", "樓長"])
    df_user = load_users(role)

    user_col = df_user.columns[0]
    pass_col = df_user.columns[1]

    user = st.selectbox("使用者", df_user[user_col].tolist())
    pwd = st.text_input("密碼", type="password")

    if st.button("登入"):
        ok = df_user[
            (df_user[user_col].astype(str) == user) &
            (df_user[pass_col].astype(str) == pwd)
        ]

        if not ok.empty:
            st.session_state.login = True
            st.session_state.role = role
            st.session_state.user = user
            st.rerun()
        else:
            st.error("登入失敗")

    st.stop()

# ==================================================
# 登出（置頂）
# ==================================================

col1, col2 = st.columns([8, 1])
with col2:
    if st.button("登出"):
        st.session_state.clear()
        st.rerun()

st.success(f"{st.session_state.role} / {st.session_state.user}")

# ==================================================
# 月份 + 搜尋
# ==================================================

month = st.selectbox(
    "月份",
    ["全部"] + [f"{i:02d}" for i in range(1, 13)],
    index=0
)

search = st.text_input("搜尋學號 / 姓名")

# ==================================================
# 點名資料
# ==================================================

@st.cache_data(ttl=CACHE_TTL)
def load_rollcall():
    data = {}
    for ws in rollcall_ss.worksheets():
        try:
            if "-" not in ws.title:
                continue

            values = ws.get_all_values()
            df = pd.DataFrame(values[1:], columns=values[0])
            df.columns = df.columns.str.strip()

            if "姓名" in df.columns:
                df = df[df["姓名"].astype(str).str.strip() != ""]

            data[ws.title] = df
        except:
            continue
    return data

data = load_rollcall()
dates = sorted(data.keys(), reverse=True)

# ==================================================
# 門禁分析（你提供完整版）
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

    df = df.sort_values(by=["姓名", "日期", "刷卡時間"])

    selected = []
    threshold = timedelta(minutes=60)

    for (name, date), g in df.groupby(["姓名", "日期"]):

        last = None
        for idx, row in g.iterrows():
            if last is None:
                selected.append(idx)
            else:
                if row["刷卡時間"] - last > threshold:
                    selected.append(idx)
            last = row["刷卡時間"]

    df = df.loc[selected].copy()

    leave = load_sheet_df(semester_url, "外宿申請")
    long_leave = load_sheet_df(semester_url, "長期外宿")
    late = load_sheet_df(semester_url, "長期晚歸")

    status = []

    weekday_map = {1:"一",2:"二",3:"三",4:"四",5:"五",6:"六",7:"日"}

    for _, r in df.iterrows():

        sid = str(r["學號"]).strip()
        d = pd.to_datetime(r["日期"])
        t = r["刷卡時間"]

        s = "未申請"

        if not leave.empty:
            leave["申請日期"] = pd.to_datetime(leave["申請日期"], errors="coerce")
            leave["結束日期"] = pd.to_datetime(leave["結束日期"], errors="coerce")

            m = leave[
                (leave["學號"].astype(str) == sid) &
                (leave["申請日期"] <= d) &
                (leave["結束日期"] >= d)
            ]

            if not m.empty:
                s = "外宿"

        if not long_leave.empty:
            weekday = weekday_map[d.weekday()]

            m = long_leave[
                (long_leave["學號"].astype(str) == sid) &
                (long_leave["星期"].astype(str).str.contains(weekday))
            ]

            if not m.empty:
                s = "長期外宿"

        if not late.empty:
            m = late[late["學號"].astype(str) == sid]

            if not m.empty:
                limit = pd.to_datetime(m.iloc[0]["返回時間"]).time()

                if t.time() <= limit:
                    s = "晚歸正常"
                else:
                    s = "晚歸超時"

        status.append(s)

    df["狀態判斷"] = status

    show = ["房號","學號","姓名"]

    df_C = df[df["姓名"].str.upper().str.startswith("C")][show]
    df_N = df[~df["姓名"].str.upper().str.startswith("C")][show]

    return df, df_C, df_N

# ==================================================
# sheet helper
# ==================================================

def load_sheet_df(ss, name):
    try:
        ws = ss.worksheet(name)
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame()

# ==================================================
# Tabs
# ==================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "連三天不假外宿",
    "每日缺席名單",
    "上學期門禁",
    "下學期門禁"
])

# ==================================================
# TAB1
# ==================================================

with tab1:

    st.subheader("連三天不假外宿")

    found = False

    groups = [dates[i:i+3] for i in range(0, len(dates), 3)]

    for g in groups:

        if len(g) < 3:
            continue

        rows = []

        for d in g:
            df = data.get(d)
            if df is None:
                continue

            miss = df[df["狀態"].astype(str).str.strip() == "缺"]
            miss = miss[["房號","學號","姓名"]].copy()
            miss["日期"] = d
            rows.append(miss)

        if not rows:
            continue

        all_df = pd.concat(rows)
        res = all_df.groupby(["房號","學號","姓名"]).nunique("日期").reset_index()
        res = res[res["日期"] == 3][["房號","學號","姓名"]]

        if search:
            res = res[
                res["學號"].astype(str).str.contains(search) |
                res["姓名"].astype(str).str.contains(search)
            ]

        if not res.empty:
            found = True
            st.write(f"{g[0]} ~ {g[-1]}")
            st.dataframe(res)

    if not found:
        st.info("無連續三天不假外宿")

# ==================================================
# TAB2
# ==================================================

with tab2:

    st.subheader("每日缺席名單")

    found = False

    for d in dates:

        df = data.get(d)
        if df is None:
            continue

        miss = df[df["狀態"].astype(str).str.strip() == "缺"]
        miss = miss[["房號","學號","姓名"]]

        if search:
            miss = miss[
                miss["學號"].astype(str).str.contains(search) |
                miss["姓名"].astype(str).str.contains(search)
            ]

        if month != "全部" and not d.startswith(f"2026-{month}"):
            continue

        if miss.empty:
            continue

        found = True
        st.write(d)
        st.dataframe(miss)

    if not found:
        st.info("無缺席資料")

# ==================================================
# TAB3
# ==================================================

with tab3:

    st.subheader("上學期門禁")

    f = st.file_uploader("Excel上傳", key="upper")

    if f:
        df, c, n = analyze_gate(f, upper_ss)
        st.dataframe(n[["房號","學號","姓名"]])
        st.dataframe(c[["房號","學號","姓名"]])

# ==================================================
# TAB4
# ==================================================

with tab4:

    st.subheader("下學期門禁")

    f = st.file_uploader("Excel上傳", key="lower")

    if f:
        df, c, n = analyze_gate(f, lower_ss)
        st.dataframe(n[["房號","學號","姓名"]])
        st.dataframe(c[["房號","學號","姓名"]])

# ==================================================
# footer
# ==================================================

st.divider()
st.caption(f"更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")