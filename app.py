import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# =========================
# 頁面設定
# =========================
st.set_page_config(
    page_title="宿舍不假外宿名單",
    layout="wide"
)

st.title("宿舍不假外宿名單")

# =========================
# Google API Scope
# =========================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# =========================
# Google 驗證
# =========================
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

# =========================
# Sheet URL
# =========================
SHEET_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit"

# =========================
# ⭐ cache resource（只連一次）
# =========================
@st.cache_resource
def get_spreadsheet(_client):
    return _client.open_by_url(SHEET_URL)

spreadsheet = get_spreadsheet(client)

@st.cache_resource
def get_worksheets(_spreadsheet):
    return _spreadsheet.worksheets()

worksheets = get_worksheets(spreadsheet)

# =========================
# 日期 sheets（新 → 舊）
# =========================
date_sheets = []

for ws in worksheets:
    try:
        datetime.strptime(ws.title, "%Y-%m-%d")
        date_sheets.append(ws)
    except:
        pass

# 🔥 改成新到舊
date_sheets = sorted(
    date_sheets,
    key=lambda x: datetime.strptime(x.title, "%Y-%m-%d"),
    reverse=True
)

st.write("找到日期 Sheets：")
st.write([ws.title for ws in date_sheets])

# =========================
# ⭐ 24h cache（資料）
# =========================
@st.cache_data(ttl=86400)
def load_all_sheets(_worksheets):
    all_data = {}

    for ws in _worksheets:
        try:
            values = ws.get_all_values()

            if len(values) <= 1:
                continue

            headers = [h.strip() for h in values[0]]
            rows = values[1:]

            df = pd.DataFrame(rows, columns=headers)
            df.columns = df.columns.str.strip()

            if "姓名" in df.columns:
                df = df[df["姓名"].astype(str).str.strip() != ""]

            all_data[ws.title] = df

        except:
            continue

    return all_data

all_sheet_data = load_all_sheets(worksheets)

# =========================
# Tabs
# =========================
tab1, tab2 = st.tabs([
    "連三天不假外宿",
    "每天點名不到名單"
])

# ==================================================
# TAB 1
# ==================================================
with tab1:
    st.header("連三天不假外宿")

    groups = [
        date_sheets[i:i+3]
        for i in range(0, len(date_sheets), 3)
    ]

    for group in groups:
        if len(group) < 3:
            continue

        group_dates = [ws.title for ws in group]
        st.subheader(f"{group_dates[0]} ~ {group_dates[-1]}")

        all_data = []

        for ws in group:
            df = all_sheet_data.get(ws.title)
            if df is None:
                continue

            required = ["狀態", "房號", "姓名"]
            if not all(c in df.columns for c in required):
                continue

            temp = df[df["狀態"].astype(str).str.strip() == "缺"].copy()
            temp["日期"] = ws.title
            all_data.append(temp)

        if not all_data:
            st.warning("此組沒有資料")
            continue

        full_df = pd.concat(all_data, ignore_index=True)

        result = (
            full_df.groupby(["房號", "姓名"])["日期"]
            .nunique()
            .reset_index()
        )

        result = result[result["日期"] == 3]

        if result.empty:
            st.success("沒有連三天缺席")
        else:
            result["日期"] = f"{group_dates[0]} ~ {group_dates[-1]}"
            st.dataframe(result, use_container_width=True)

# ==================================================
# TAB 2
# ==================================================
with tab2:
    st.header("每天點名不到名單")

    all_missing_records = []

    for ws in date_sheets:
        df = all_sheet_data.get(ws.title)
        if df is None:
            continue

        required = ["狀態", "房號", "姓名"]
        if not all(c in df.columns for c in required):
            continue

        result = df[df["狀態"].astype(str).str.strip() == "缺"]

        if result.empty:
            continue

        st.subheader(ws.title)

        show_df = result[["房號", "姓名"]].reset_index(drop=True)
        show_df.insert(0, "日期", ws.title)

        st.dataframe(show_df, use_container_width=True)

        all_missing_records.append(show_df)

    # =========================
    # ⭐ 常缺席統計（紅字）
    # =========================
    if all_missing_records:

        st.divider()
        st.subheader("🔥 常缺席名單（紅字 ≥ 3 次）")

        summary = pd.concat(all_missing_records)

        freq = summary.groupby(["房號", "姓名"]).size().reset_index(name="缺席次數")

        def color_red(val):
            return "color: red" if val >= 3 else ""

        st.dataframe(
            freq.style.applymap(color_red, subset=["缺席次數"]),
            use_container_width=True
        )

# =========================
# Footer
# =========================
st.divider()

st.caption(
    f"最後更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)