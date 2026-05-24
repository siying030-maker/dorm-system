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

CACHE_TTL = 86400

st.title("宿舍管理系統")

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
# 開啟 Sheet
# ==================================================

@st.cache_resource(ttl=CACHE_TTL)
def open_sheet(url):
    for i in range(5):
        try:
            rate_limit()
            return client.open_by_url(url)
        except:
            time.sleep((i + 1) * 5)
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
    st.session_state.role = ""
    st.session_state.user = ""

# ==================================================
# 登入頁
# ==================================================

if not st.session_state.login:

    st.subheader("登入系統")

    role = st.selectbox("身分", ["舍監", "行政", "樓長"])

    df_user = load_users(role)

    username = st.selectbox("使用者", df_user.iloc[:,0].tolist())
    password = st.text_input("密碼", type="password")

    if st.button("登入"):
        check = df_user[
            (df_user.iloc[:,0].astype(str) == username) &
            (df_user.iloc[:,1].astype(str) == password)
        ]

        if not check.empty:
            st.session_state.login = True
            st.session_state.role = role
            st.session_state.user = username
            st.rerun()
        else:
            st.error("錯誤")

    st.stop()

# ==================================================
# 登出（移到最上面）
# ==================================================

col1, col2 = st.columns([8, 1])
with col2:
    if st.button("登出"):
        st.session_state.login = False
        st.session_state.role = ""
        st.session_state.user = ""
        st.rerun()

st.success(f"{st.session_state.role} / {st.session_state.user}")

st.divider()

# ==================================================
# 月份 + 搜尋（新增）
# ==================================================

@st.cache_data(ttl=CACHE_TTL)
def load_rollcall():
    data = {}
    for ws in rollcall_ss.worksheets():
        try:
            if "-" not in ws.title:
                continue

            df = pd.DataFrame(ws.get_all_values()[1:], columns=ws.get_all_values()[0])
            df.columns = df.columns.str.strip()

            data[ws.title] = df
        except:
            pass
    return data

data = load_rollcall()

months = sorted(list(set([k[:7] for k in data.keys()])), reverse=True)

selected_month = st.selectbox("月份", ["全部"] + months)

search_global = st.text_input("搜尋學號 / 姓名")

if selected_month != "全部":
    data = {k:v for k,v in data.items() if k.startswith(selected_month)}

dates = sorted(data.keys(), reverse=True)

# ==================================================
# 權限 Tabs
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
# TAB1
# ==================================================

if "連三天不假外宿" in tabs_list:

    with tabs[tabs_list.index("連三天不假外宿")]:

        st.header("連三天不假外宿")

        search = st.text_input("搜尋", key="t1")

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

            key = search or search_global
            if key:
                res = res[
                    res["學號"].astype(str).str.contains(key) |
                    res["姓名"].astype(str).str.contains(key)
                ]

            if res.empty:
                st.info("無連續三天不假外宿")
            else:
                st.dataframe(res, use_container_width=True)

# ==================================================
# TAB2
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

            key = search or search_global
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
            st.subheader("🔥 常缺席")
            total = pd.concat(all_miss)

            freq = total.groupby(["房號","學號","姓名"]).size().reset_index(name="次數")
            st.dataframe(freq)

# ==================================================
# TAB3
# ==================================================

if "上學期門禁" in tabs_list:

    with tabs[tabs_list.index("上學期門禁")]:

        st.header("上學期門禁")
        f = st.file_uploader("Excel")

        if f:
            df = pd.read_excel(f)
            st.dataframe(df)

# ==================================================
# TAB4
# ==================================================

if "下學期門禁" in tabs_list:

    with tabs[tabs_list.index("下學期門禁")]:

        st.header("下學期門禁")
        f = st.file_uploader("Excel")

        if f:
            df = pd.read_excel(f)
            st.dataframe(df)

# ==================================================
# footer
# ==================================================

st.divider()
st.caption(f"更新時間：{datetime.now()}")