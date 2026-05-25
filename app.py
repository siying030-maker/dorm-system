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
# Sheets
# ==================================================

ROLLCALL_SHEET_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit"
UPPER_GATE_URL = "https://docs.google.com/spreadsheets/d/1Pr1fQYH35KgXMkl6igxqc-3jnZ5ufi0QgWtgp3782Lo/edit"
LOWER_GATE_URL = "https://docs.google.com/spreadsheets/d/1ivjA_-voyNAUGbvbc5o5BULu_MgU2AqbNokvQJ5dfe4/edit"
ADMIN_SHEET_URL = "https://docs.google.com/spreadsheets/d/1eZgdlelXQWcO3ZRxeXRjXNTI1g1I6RUZPGtJoC9iRes/edit"

# ==================================================
# 整潔比賽 Sheets
# ==================================================

CLEAN_SHEETS = {
    "上學期": {
        "男一": "https://docs.google.com/spreadsheets/d/1S2axgu2BWP8HnEs0RJdDcccdD1bvPdH26qrx3c4DeWo/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1RcRTslmv4s_C_7AH-WuqtLrty9l0A7YECvaGJETnpis/edit",
        "女ㄧ": "https://docs.google.com/spreadsheets/d/1U9bdg8CWASheYE7XxLt5p-otLDxKiotju4s72Car9rk/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1jNbe--UINl7NS6dpBU82AZJuT6wQ9VwVAlglyG7infQ/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1Vrst2-bqPE7flCIXeAI-lyN51Os9QwStx388DWx11w8/edit",
    },
    "下學期": {
        "男一": "https://docs.google.com/spreadsheets/d/1JSJx0cLdUxfIeYoe6dldeBe3Xeewm3uuIYrJkeYi_A8/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1KpqeWBWIR0g6RxZ_oFUFXbn34PbH7r18UI9NBsfWIPY/edit",
        "女ㄧ": "https://docs.google.com/spreadsheets/d/1Nf7U106SxRZUu1pb35Fu2xrN2BTV80lit43BcgE6GnA/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1NVt6M8SVc64zmRmxh268NlZqzT3JLpcGwuRBlkCe8oE/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1y2YB118Xg2Mq8w6NeabTXgZ-n1gN56kCalyJ5KlMk1I/edit",
    }
}

# ==================================================
# open sheet
# ==================================================

@st.cache_resource(ttl=CACHE_TTL)
def open_sheet(url):
    return client.open_by_url(url)

def load_sheet_df(url):
    try:
        ws = open_sheet(url).sheet1
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame()

# ==================================================
# 登入
# ==================================================

def load_users(sheet_url, sheet_name):
    try:
        ws = open_sheet(sheet_url).worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        return df
    except:
        return pd.DataFrame()

if "login" not in st.session_state:
    st.session_state.login = False
    st.session_state.role = ""
    st.session_state.user = ""
    st.session_state.is_main = False

# ==================================================
# 登入頁面
# ==================================================

if not st.session_state.login:

    st.subheader("登入系統")

    role = st.selectbox("選擇身分", ["舍監", "行政", "樓長"], key="role_select")

    if role == "舍監":
        df = load_users(ADMIN_SHEET_URL, "舍監")
        user_col, pass_col = "使用者", "密碼"
        house_col = None

    elif role == "行政":
        df = load_users(ADMIN_SHEET_URL, "行政")
        user_col, pass_col = "使用者", "密碼"
        house_col = None

    else:
        df = load_users(ADMIN_SHEET_URL, "樓長")
        house_col, user_col, pass_col, main_col = "宿舍別", "使用者", "密碼", "總樓"

    if df.empty:
        st.error("帳號資料錯誤")
        st.stop()

    if role == "樓長":
        house = st.selectbox("宿舍別", df[house_col].dropna().unique(), key="house")
        df = df[df[house_col] == house]

    user = st.selectbox("使用者", df[user_col].astype(str).tolist(), key="user")
    pw = st.text_input("密碼", type="password", key="pw")

    if st.button("登入"):

        match = df[
            (df[user_col].astype(str) == user) &
            (df[pass_col].astype(str) == pw)
        ]

        if not match.empty:
            st.session_state.login = True
            st.session_state.role = role
            st.session_state.user = user

            if role == "樓長":
                st.session_state.is_main = str(match.iloc[0].get(main_col, "")) == "是"
            else:
                st.session_state.is_main = False

            st.rerun()

        else:
            st.error("帳號或密碼錯誤")

    st.stop()

# ==================================================
# 登出（置頂）
# ==================================================

col1, col2 = st.columns([9,1])

with col1:
    st.success(f"{st.session_state.role} / {st.session_state.user}")

with col2:
    if st.button("登出"):
        st.session_state.clear()
        st.rerun()

# ==================================================
# 月份
# ==================================================

month = st.selectbox(
    "月份",
    ["全部"] + [f"2026-{i:02d}" for i in range(1, 13)],
    index=1
)

# ==================================================
# 權限頁面
# ==================================================

role = st.session_state.role

tabs = []

if role in ["舍監", "行政"]:
    tabs += ["連三天不假外宿", "每日缺席名單"]

if role == "行政":
    tabs += ["上學期門禁", "下學期門禁", "整潔比賽(檢視)"]

if role == "樓長":
    tabs += ["每日缺席名單"]

if role == "樓長" and st.session_state.is_main:
    tabs += ["整潔比賽"]

tab = st.tabs(tabs)

# ==================================================
# 模擬點名資料
# ==================================================

def get_mock_data():
    return {
        "2026-05-01": pd.DataFrame([{"房號":"A101","學號":"001","姓名":"王小明","狀態":"缺"}]),
        "2026-05-02": pd.DataFrame([{"房號":"A101","學號":"001","姓名":"王小明","狀態":"缺"}]),
        "2026-05-03": pd.DataFrame([{"房號":"A101","學號":"001","姓名":"王小明","狀態":"缺"}]),
    }

data = get_mock_data()

# ==================================================
# TAB 1 連三天
# ==================================================

if "連三天不假外宿" in tabs:

    i = tabs.index("連三天不假外宿")

    with tab[i]:

        st.subheader("連三天不假外宿")

        search = st.text_input("搜尋學號/姓名", key="s1")

        dates = sorted(data.keys())

        groups = [dates[i:i+3] for i in range(0, len(dates), 3)]

        found = False

        for g in groups:
            if len(g) < 3:
                continue

            tmp = []
            for d in g:
                df = data[d]
                df = df[df["狀態"] == "缺"].copy()
                df["日期"] = d
                tmp.append(df)

            if not tmp:
                continue

            df_all = pd.concat(tmp)

            res = df_all.groupby(["房號","學號","姓名"]).size().reset_index(name="天數")
            res = res[res["天數"] == 3]

            if search:
                res = res[
                    res["學號"].astype(str).str.contains(search) |
                    res["姓名"].astype(str).str.contains(search)
                ]

            if not res.empty:
                found = True
                st.dataframe(res[["房號","學號","姓名"]])

        if not found:
            st.info("無連續三天不假外宿")

# ==================================================
# TAB 2 缺席
# ==================================================

if "每日缺席名單" in tabs:

    i = tabs.index("每日缺席名單")

    with tab[i]:

        st.subheader("每日缺席名單")

        search = st.text_input("搜尋", key="s2")

        found = False

        for d, df in data.items():

            miss = df[df["狀態"] == "缺"]

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
# TAB 3 門禁（保留結構）
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

    df = df.sort_values(by=["姓名","日期","刷卡時間"])

    selected = []
    threshold = timedelta(minutes=60)

    for (name,date), g in df.groupby(["姓名","日期"]):
        last=None
        for i,row in g.iterrows():
            if last is None:
                selected.append(i)
            elif row["刷卡時間"]-last>threshold:
                selected.append(i)
            last=row["刷卡時間"]

    df = df.loc[selected].copy()

    return df, df, df

# ==================================================
# TAB 4 門禁
# ==================================================

if "上學期門禁" in tabs:

    i = tabs.index("上學期門禁")

    with tab[i]:
        st.subheader("上學期門禁")

if "下學期門禁" in tabs:

    i = tabs.index("下學期門禁")

    with tab[i]:
        st.subheader("下學期門禁")

# ==================================================
# TAB 5 整潔比賽
# ==================================================

if "整潔比賽(檢視)" in tabs:

    i = tabs.index("整潔比賽(檢視)")

    with tab[i]:
        st.subheader("行政檢視（只讀）")

if "整潔比賽" in tabs:

    i = tabs.index("整潔比賽")

    with tab[i]:

        st.subheader("整潔比賽填寫")

        sem = st.selectbox("學期", ["上學期","下學期"])
        round_ = st.selectbox("次數", ["第一次","第二次","第三次"])
        rank = st.selectbox("名次", ["第一名","第二名","第三名"])

        dorm = st.selectbox("宿舍", list(CLEAN_SHEETS[sem].keys()))

        df = load_sheet_df(CLEAN_SHEETS[sem][dorm])

        st.dataframe(df)

# ==================================================
# END
# ==================================================