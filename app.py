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

CACHE_TTL = 86400  # 24小時快取

# ==================================================
# Google API
# ==================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    creds = Credentials.from_service_account_info(
        st.secrets["google"],
        scopes=SCOPES
    )
    client = gspread.authorize(creds)

except Exception as e:
    st.error("Google 驗證失敗")
    st.code(str(e))
    st.stop()

# ==================================================
# API 防爆控制
# ==================================================

_last_call = 0

def rate_limit():
    global _last_call
    now = time.time()
    if now - _last_call < 0.3:
        time.sleep(0.3)
    _last_call = time.time()

# ==================================================
# Sheet URL
# ==================================================

ROLLCALL_SHEET_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit"
UPPER_GATE_URL = "https://docs.google.com/spreadsheets/d/1Pr1fQYH35KgXMkl6igxqc-3jnZ5ufi0QgWtgp3782Lo/edit"
LOWER_GATE_URL = "https://docs.google.com/spreadsheets/d/1ivjA_-voyNAUGbvbc5o5BULu_MgU2AqbNokvQJ5dfe4/edit"

# ==================================================
# 安全開啟 Sheet（防 429）
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

# ==================================================
# 點名資料 cache（最重要：避免 API 爆炸）
# ==================================================

@st.cache_data(ttl=CACHE_TTL)
def load_rollcall_cache():

    worksheets = rollcall_ss.worksheets()

    data = {}

    for ws in worksheets:
        try:
            rate_limit()
            values = ws.get_all_values()

            if len(values) <= 1:
                continue

            df = pd.DataFrame(values[1:], columns=values[0])
            df.columns = df.columns.str.strip()

            if "姓名" in df.columns:
                df = df[df["姓名"].astype(str).str.strip() != ""]

            data[ws.title] = df

        except:
            continue

    return data


# ==================================================
# 讀 Sheet function
# ==================================================

def load_sheet_df(ss, name):
    try:
        ws = ss.worksheet(name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

# ==================================================
# 門禁分析
# ==================================================

def analyze_gate(file, semester_ss):

    if file is None:
        return None, None, None

    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()

    df["刷卡時間"] = pd.to_datetime(df["刷卡時間"], errors="coerce")
    df["日期"] = df["刷卡時間"].dt.date

    # 00~06
    df = df[(df["刷卡時間"].dt.hour >= 0) & (df["刷卡時間"].dt.hour < 6)]

    # LHU / Y 排除
    df["姓名"] = df["姓名"].astype(str)
    df = df[~df["姓名"].str.upper().str.startswith(("LHU", "Y"))]

    df = df.sort_values(["姓名", "日期", "刷卡時間"])

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

    df = df.loc[selected].sort_values(["日期", "刷卡時間"], ascending=False)

    leave = load_sheet_df(semester_ss, "外宿申請")
    long_leave = load_sheet_df(semester_ss, "長期外宿")
    late = load_sheet_df(semester_ss, "長期晚歸")

    status = []

    weekday_map = {0:"一",1:"二",2:"三",3:"四",4:"五",5:"六",6:"日"}

    for _, r in df.iterrows():

        sid = str(r["學號"])
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
            w = weekday_map[d.weekday()]
            m = long_leave[
                (long_leave["學號"].astype(str) == sid) &
                (long_leave["星期"].astype(str).str.contains(w))
            ]
            if not m.empty:
                s = "長期外宿"

        if not late.empty:
            m = late[late["學號"].astype(str) == sid]
            if not m.empty:
                limit = pd.to_datetime(m.iloc[0]["返回時間"]).time()
                s = "晚歸正常" if t.time() <= limit else "晚歸超時"

        status.append(s)

    df["狀態"] = status

    return df, df[df["姓名"].str.upper().str.startswith("C")], df[~df["姓名"].str.upper().str.startswith("C")]

# ==================================================
# Excel export
# ==================================================

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return output.getvalue()

# ==================================================
# Tabs
# ==================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "連三天不假外宿",
    "每天點名不到名單",
    "上學期門禁",
    "下學期門禁"
])

# ==================================================
# TAB1
# ==================================================

with tab1:

    data = load_rollcall_cache()
    dates = sorted(data.keys(), reverse=True)

    groups = [dates[i:i+3] for i in range(0, len(dates), 3)]

    for g in groups:

        if len(g) < 3:
            continue

        all_d = []

        for d in g:
            df = data.get(d)
            if df is None:
                continue

            if "狀態" not in df.columns:
                continue

            tmp = df[df["狀態"].astype(str).str.strip() == "缺"].copy()
            tmp["日期"] = d
            all_d.append(tmp)

        if not all_d:
            continue

        df_all = pd.concat(all_d)

        res = df_all.groupby(["房號","學號","姓名"])["日期"].nunique().reset_index()
        res = res[res["日期"] == 3]

        st.subheader(f"{g[0]} ~ {g[-1]}")
        st.dataframe(res)

# ==================================================
# TAB2
# ==================================================

with tab2:

    data = load_rollcall_cache()
    dates = sorted(data.keys(), reverse=True)

    all_miss = []

    for d in dates:

        df = data.get(d)
        if df is None:
            continue

        if "狀態" not in df.columns:
            continue

        miss = df[df["狀態"].str.strip() == "缺"]

        if miss.empty:
            continue

        st.subheader(d)

        show = miss[["房號","學號","姓名"]]
        st.dataframe(show)

        all_miss.append(show)

    if all_miss:

        total = pd.concat(all_miss)

        freq = total.groupby(["房號","學號","姓名"]).size().reset_index(name="缺席次數")

        freq["🔥"] = freq["缺席次數"].apply(lambda x: "🔴" if x >= 3 else "")

        st.dataframe(freq.sort_values("缺席次數", ascending=False))

# ==================================================
# TAB3
# ==================================================

with tab3:

    f = st.file_uploader("上學期門禁")

    if f:
        df, c, n = analyze_gate(f, upper_ss)

        st.dataframe(n)
        st.dataframe(c)

        st.download_button("一般", to_excel(n), "normal.xlsx")
        st.download_button("白卡", to_excel(c), "white.xlsx")

# ==================================================
# TAB4
# ==================================================

with tab4:

    f = st.file_uploader("下學期門禁")

    if f:
        df, c, n = analyze_gate(f, lower_ss)

        st.dataframe(n)
        st.dataframe(c)

        st.download_button("一般", to_excel(n), "normal.xlsx")
        st.download_button("白卡", to_excel(c), "white.xlsx")

# ==================================================
# footer
# ==================================================

st.caption(f"更新時間 {datetime.now()}")