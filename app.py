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
# Open Sheet
# ==================================================

@st.cache_resource(ttl=CACHE_TTL)
def open_sheet(url):
    for i in range(5):
        try:
            rate_limit()
            return client.open_by_url(url)
        except:
            time.sleep((i + 1) * 5)
    raise Exception("Google API error")

rollcall_ss = open_sheet(ROLLCALL_SHEET_URL)
upper_ss = open_sheet(UPPER_GATE_URL)
lower_ss = open_sheet(LOWER_GATE_URL)
admin_ss = open_sheet(ADMIN_SHEET_URL)

# ==================================================
# 登入系統
# ==================================================

@st.cache_data(ttl=300)
def load_users(role):
    ws = admin_ss.worksheet(role)
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip()
    return df

if "login" not in st.session_state:
    st.session_state.login = False
    st.session_state.role = ""
    st.session_state.user = ""

# ==================================================
# 登入頁
# ==================================================

if not st.session_state.login:

    st.subheader("登入系統")

    role = st.selectbox("身分", ["舍監", "行政", "樓長"])

    users = load_users(role)

    username = st.selectbox("使用者", users.iloc[:, 0].tolist(), key="login_user")
    password = st.text_input("密碼", type="password", key="login_pass")

    if st.button("登入", key="login_btn"):

        ok = users[
            (users.iloc[:,0].astype(str) == username) &
            (users.iloc[:,1].astype(str) == password)
        ]

        if not ok.empty:
            st.session_state.login = True
            st.session_state.role = role
            st.session_state.user = username
            st.rerun()
        else:
            st.error("登入失敗")

    st.stop()

# ==================================================
# 登出（置頂）
# ==================================================

col1, col2 = st.columns([8,1])
with col2:
    if st.button("登出", key="logout"):
        st.session_state.login = False
        st.session_state.role = ""
        st.session_state.user = ""
        st.rerun()

st.success(f"{st.session_state.role} / {st.session_state.user}")
st.divider()

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
            data[ws.title] = df
        except:
            pass
    return data

data = load_rollcall()

# ==================================================
# 月份 + 搜尋（全域）
# ==================================================

months = sorted(list(set([k[:7] for k in data.keys()])), reverse=True)

month = st.selectbox("月份", ["全部"] + months, key="month_select")
global_search = st.text_input("搜尋學號 / 姓名", key="global_search")

if month != "全部":
    data = {k:v for k,v in data.items() if k.startswith(month)}

dates = sorted(data.keys(), reverse=True)

# ==================================================
# Tabs 權限
# ==================================================

role = st.session_state.role

tabs_list = []

if role in ["舍監", "行政"]:
    tabs_list += ["連三天不假外宿", "每天點名不到名單"]

if role == "行政":
    tabs_list += ["上學期門禁", "下學期門禁"]

if role == "樓長":
    tabs_list += ["每天點名不到名單"]

tabs = st.tabs(tabs_list)

# ==================================================
# TAB1：三天外宿
# ==================================================

if "連三天不假外宿" in tabs_list:

    with tabs[tabs_list.index("連三天不假外宿")]:

        st.header("連三天不假外宿")

        search = st.text_input("搜尋", key="t1")

        found = False

        groups = [dates[i:i+3] for i in range(0, len(dates), 3)]

        for g in groups:

            if len(g) < 3:
                continue

            all_d = []

            for d in g:
                df = data.get(d)
                if df is None or "狀態" not in df.columns:
                    continue

                tmp = df[df["狀態"] == "缺"].copy()
                tmp["日期"] = d
                all_d.append(tmp)

            st.subheader(f"{g[0]} ~ {g[-1]}")

            if not all_d:
                st.info("無連續三天不假外宿")
                continue

            df_all = pd.concat(all_d)

            res = df_all.groupby(["房號","學號","姓名"])["日期"].nunique().reset_index()
            res = res[res["日期"] == 3]

            key = search or global_search
            if key:
                res = res[
                    res["學號"].astype(str).str.contains(key) |
                    res["姓名"].astype(str).str.contains(key)
                ]

            if res.empty:
                st.info("無連續三天不假外宿")
            else:
                found = True
                st.dataframe(res, use_container_width=True)

        if not found:
            st.warning("本月無連續三天不假外宿")

# ==================================================
# TAB2：每日缺席
# ==================================================

if "每天點名不到名單" in tabs_list:

    with tabs[tabs_list.index("每天點名不到名單")]:

        st.header("每天點名不到名單")

        search = st.text_input("搜尋", key="t2")

        all_miss = []

        for d in dates:

            df = data.get(d)
            if df is None or "狀態" not in df.columns:
                continue

            miss = df[df["狀態"] == "缺"]

            if miss.empty:
                continue

            show = miss[["房號","學號","姓名"]]

            key = search or global_search
            if key:
                show = show[
                    show["學號"].astype(str).str.contains(key) |
                    show["姓名"].astype(str).str.contains(key)
                ]

            st.subheader(d)
            st.dataframe(show, use_container_width=True)

            all_miss.append(show)

        if all_miss:
            st.divider()
            st.subheader("🔥 常缺席排行")

            total = pd.concat(all_miss)

            freq = total.groupby(["房號","學號","姓名"]).size().reset_index(name="次數")

            st.dataframe(freq, use_container_width=True)

# ==================================================
# TAB3
# ==================================================

if "上學期門禁" in tabs_list:

    with tabs[tabs_list.index("上學期門禁")]:

        st.header("上學期門禁")

        f = st.file_uploader(
            "上學期門禁 Excel",
            type=["xlsx"],
            key="upper_file"
        )

        if f:
            df = pd.read_excel(f)
            st.dataframe(df)

# ==================================================
# TAB4
# ==================================================

if "下學期門禁" in tabs_list:

    with tabs[tabs_list.index("下學期門禁")]:

        st.header("下學期門禁")

        f = st.file_uploader(
            "下學期門禁 Excel",
            type=["xlsx"],
            key="lower_file"
        )

        if f:
            df = pd.read_excel(f)
            st.dataframe(df)

# ==================================================
# footer
# ==================================================

st.divider()
st.caption(f"更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")