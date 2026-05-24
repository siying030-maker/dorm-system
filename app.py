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
# rate limit
# ==================================================

_last_call = 0

def rate_limit():
    global _last_call
    now = time.time()
    if now - _last_call < 0.3:
        time.sleep(0.3)
    _last_call = time.time()

# ==================================================
# Sheets
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
# USERS (修正版：不再 KeyError)
# ==================================================

@st.cache_data(ttl=300)
def load_users(role):

    ws = admin_ss.worksheet(role)
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip()

    # 強制標準欄位
    df = df.rename(columns={
        df.columns[0]: "使用者",
        df.columns[1]: "密碼"
    })

    df["使用者"] = df["使用者"].astype(str).str.strip()
    df["密碼"] = df["密碼"].astype(str).str.strip()

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

# ==================================================
# LOGIN
# ==================================================

if not st.session_state.login:

    st.subheader("登入系統")

    role = st.selectbox("身分", ["舍監", "行政", "樓長"])

    df_user = load_users(role)

    user = st.selectbox("使用者", df_user["使用者"].tolist())
    pwd = st.text_input("密碼", type="password")

    if st.button("登入"):

        match = df_user[
            (df_user["使用者"] == user) &
            (df_user["密碼"] == pwd)
        ]

        if not match.empty:
            st.session_state.login = True
            st.session_state.role = role
            st.session_state.user = user
            st.rerun()
        else:
            st.error("帳號或密碼錯誤")

    st.stop()

# ==================================================
# 登出（置頂）
# ==================================================

col1, col2 = st.columns([9, 1])
with col2:
    if st.button("登出"):
        st.session_state.clear()
        st.rerun()

st.success(f"{st.session_state.role} / {st.session_state.user}")

# ==================================================
# 月份 + 搜尋
# ==================================================

month_now = datetime.now().strftime("%m")

month = st.selectbox(
    "月份",
    ["全部"] + [f"{i:02d}" for i in range(1,13)],
    index=0
)

search = st.text_input("搜尋學號 / 姓名")

# ==================================================
# 讀取點名
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
dates = sorted(data.keys(), reverse=True)

# ==================================================
# 權限
# ==================================================

role = st.session_state.role

tabs_list = []

if role in ["舍監", "行政"]:
    tabs_list += ["連三天不假外宿", "每日缺席"]

if role == "樓長":
    tabs_list += ["每日缺席"]

if role == "行政":
    tabs_list += ["上學期門禁", "下學期門禁"]

tabs = st.tabs(tabs_list)

# ==================================================
# TAB1 連三天
# ==================================================

if "連三天不假外宿" in tabs_list:

    i = tabs_list.index("連三天不假外宿")

    with tabs[i]:

        found = False

        groups = [dates[i:i+3] for i in range(0, len(dates), 3)]

        for g in groups:

            if len(g) < 3:
                continue

            rows = []

            for d in g:

                if month != "全部" and f"-{month}-" not in d:
                    continue

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

            res = all_df.groupby(["房號","學號","姓名"]).nunique().reset_index()
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
# TAB2 每日缺席
# ==================================================

if "每日缺席" in tabs_list:

    i = tabs_list.index("每日缺席")

    with tabs[i]:

        found = False

        for d in dates:

            if month != "全部" and f"-{month}-" not in d:
                continue

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

            if miss.empty:
                continue

            found = True
            st.write(d)
            st.dataframe(miss)

        if not found:
            st.info("無缺席資料")

# ==================================================
# 門禁（完整保留你原本）
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

    selected=[]
    threshold=timedelta(minutes=60)

    for (name,date),g in df.groupby(["姓名","日期"]):

        last=None
        for idx,row in g.iterrows():

            if last is None:
                selected.append(idx)
            else:
                if row["刷卡時間"]-last>threshold:
                    selected.append(idx)

            last=row["刷卡時間"]

    df=df.loc[selected].copy()

    leave=load_sheet_df(semester_url,"外宿申請")
    long_leave=load_sheet_df(semester_url,"長期外宿")
    late=load_sheet_df(semester_url,"長期晚歸")

    status=[]
    weekday_map={0:"一",1:"二",2:"三",3:"四",4:"五",5:"六",6:"日"}

    for _,r in df.iterrows():

        sid=str(r["學號"]).strip()
        d=pd.to_datetime(r["日期"])
        t=r["刷卡時間"]

        s="未申請"

        if not leave.empty:
            leave["申請日期"]=pd.to_datetime(leave["申請日期"],errors="coerce")
            leave["結束日期"]=pd.to_datetime(leave["結束日期"],errors="coerce")

            m=leave[(leave["學號"].astype(str)==sid)&(leave["申請日期"]<=d)&(leave["結束日期"]>=d)]
            if not m.empty:
                s="外宿"

        if not long_leave.empty:
            weekday=weekday_map[d.weekday()]
            m=long_leave[(long_leave["學號"].astype(str)==sid)&(long_leave["星期"].astype(str).str.contains(weekday))]
            if not m.empty:
                s="長期外宿"

        if not late.empty:
            m=late[late["學號"].astype(str)==sid]
            if not m.empty:
                limit=pd.to_datetime(m.iloc[0]["返回時間"]).time()
                s="晚歸正常" if t.time()<=limit else "晚歸超時"

        status.append(s)

    df["狀態判斷"]=status

    return df,df,df

# ==================================================
# TAB3 / TAB4
# ==================================================

if "上學期門禁" in tabs_list:

    i=tabs_list.index("上學期門禁")

    with tabs[i]:
        f=st.file_uploader("上學期Excel",key="up")
        if f:
            df,c,n=analyze_gate(f,upper_ss)
            st.dataframe(n[["房號","學號","姓名"]])

if "下學期門禁" in tabs_list:

    i=tabs_list.index("下學期門禁")

    with tabs[i]:
        f=st.file_uploader("下學期Excel",key="low")
        if f:
            df,c,n=analyze_gate(f,lower_ss)
            st.dataframe(n[["房號","學號","姓名"]])

# ==================================================
# footer
# ==================================================

st.divider()
st.caption(f"更新時間 {datetime.now()}")