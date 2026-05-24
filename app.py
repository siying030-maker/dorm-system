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
# Sheet URLs
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
    try:
        ws = admin_ss.worksheet(role)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

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
# 登入頁面（樓長改版）
# ==================================================
if not st.session_state.login:

    st.subheader("登入系統")

    role = st.selectbox("選擇身分", ["舍監", "行政", "樓長"])

    df_users = load_users(role)

    if role != "樓長":

        if df_users.empty:
            st.error("無資料")
            st.stop()

        user_col = df_users.columns[0]
        pass_col = df_users.columns[1]

        user = st.selectbox("使用者", df_users[user_col].tolist(), key="user_login")
        pwd = st.text_input("密碼", type="password", key="pwd_login")

        if st.button("登入"):
            ok = df_users[
                (df_users[user_col].astype(str) == user) &
                (df_users[pass_col].astype(str) == pwd)
            ]
            if not ok.empty:
                st.session_state.login = True
                st.session_state.role = role
                st.session_state.user = user
                st.rerun()
            else:
                st.error("密碼錯誤")

        st.stop()

    # =========================
    # 樓長登入（新版）
    # =========================
    else:

        if df_users.empty:
            st.error("樓長資料錯誤")
            st.stop()

        dorm_col = df_users.columns[0]   # A 宿舍別
        user_col = df_users.columns[1]   # B 使用者
        pass_col = df_users.columns[2]   # C 密碼
        main_col = df_users.columns[3]   # D 總樓

        dorm = st.selectbox("宿舍別", df_users[dorm_col].unique(), key="dorm_login")

        sub = df_users[df_users[dorm_col] == dorm]

        user = st.selectbox("使用者", sub[user_col].tolist(), key="user_login2")

        pwd = st.text_input("密碼", type="password", key="pwd_login2")

        if st.button("登入"):
            ok = sub[
                (sub[user_col].astype(str) == user) &
                (sub[pass_col].astype(str) == pwd)
            ]

            if not ok.empty:
                st.session_state.login = True
                st.session_state.role = role
                st.session_state.user = user

                st.session_state.is_main = (
                    str(ok.iloc[0][main_col]) == "總樓"
                )

                st.rerun()
            else:
                st.error("密碼錯誤")

        st.stop()

# ==================================================
# 登入成功
# ==================================================
st.success(f"{st.session_state.role} / {st.session_state.user}")

# ==================================================
# 登出（置頂）
# ==================================================
if st.button("登出"):
    st.session_state.clear()
    st.rerun()

st.divider()

# ==================================================
# 月份篩選（預設當月）
# ==================================================
all_dates = [ws.title for ws in rollcall_ss.worksheets()]

valid_dates = []
for d in all_dates:
    try:
        datetime.strptime(d, "%Y-%m-%d")
        valid_dates.append(d)
    except:
        pass

valid_dates = sorted(valid_dates)

month_list = sorted(list(set([d[:7] for d in valid_dates])))

current_month = datetime.now().strftime("%Y-%m")

selected_month = st.selectbox(
    "月份",
    month_list,
    index=month_list.index(current_month) if current_month in month_list else 0,
    key="month_select"
)

dates = [d for d in valid_dates if d.startswith(selected_month)]

# ==================================================
# 搜尋（只給兩個頁面用）
# ==================================================
search = st.text_input("搜尋學號 / 姓名", key="global_search")

# ==================================================
# rollcall data
# ==================================================
@st.cache_data(ttl=CACHE_TTL)
def load_rollcall():
    data = {}
    for ws in rollcall_ss.worksheets():
        if ws.title in dates:
            df = pd.DataFrame(ws.get_all_values()[1:], columns=ws.get_all_values()[0])
            df.columns = df.columns.str.strip()
            data[ws.title] = df
    return data

data = load_rollcall()

# ==================================================
# 門禁分析（完全保留你版本）
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

    weekday_map = {0:"一",1:"二",2:"三",3:"四",4:"五",5:"六",6:"日"}

    for _, r in df.iterrows():

        sid = str(r["學號"]).strip()
        d = pd.to_datetime(r["日期"])
        t = r["刷卡時間"]

        s = "未申請"

        if not leave.empty:
            m = leave[
                (leave["學號"].astype(str) == sid) &
                (pd.to_datetime(leave["申請日期"]) <= d) &
                (pd.to_datetime(leave["結束日期"]) >= d)
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
                s = "晚歸正常" if t.time() <= limit else "晚歸超時"

        status.append(s)

    df["狀態判斷"] = status

    return df, df[[]], df[[]]

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
# tabs（無重複修正）
# ==================================================
tabs = st.tabs([
    "連三天不假外宿",
    "每日缺席名單",
    "門禁系統",
    "整潔比賽" if st.session_state.role == "樓長" and st.session_state.get("is_main") else None
])

tabs = [t for t in tabs if t is not None]

# ==================================================
# TAB1
# ==================================================
with tabs[0]:
    st.subheader("連三天不假外宿")

    for d in dates:
        df = data.get(d)
        if df is None:
            continue

        miss = df[df["狀態"].astype(str) == "缺"]

        show = miss[["房號","學號","姓名"]]

        if search:
            show = show[
                show["學號"].astype(str).str.contains(search) |
                show["姓名"].astype(str).str.contains(search)
            ]

        st.write(d)
        st.dataframe(show)

# ==================================================
# TAB2
# ==================================================
with tabs[1]:
    st.subheader("每日缺席名單")

    for d in dates:
        df = data.get(d)
        if df is None:
            continue

        miss = df[df["狀態"].astype(str) == "缺"]

        show = miss[["房號","學號","姓名"]]

        if search:
            show = show[
                show["學號"].astype(str).str.contains(search) |
                show["姓名"].astype(str).str.contains(search)
            ]

        st.write(d)
        st.dataframe(show)

# ==================================================
# TAB3
# ==================================================
with tabs[2]:
    st.subheader("門禁系統")
    f = st.file_uploader("Excel", key="gate_upload")

    if f:
        r, c, n = analyze_gate(f, upper_ss)
        st.dataframe(n)
        st.dataframe(c)

# ==================================================
# TAB4（整潔比賽）
# ==================================================
if len(tabs) == 4:
    with tabs[3]:
        st.subheader("整潔比賽名次（總樓）")
        st.info("此功能僅總樓可見")