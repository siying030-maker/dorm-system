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

    st.success("Google 驗證成功")

except Exception as e:

    st.error("Google 驗證失敗")
    st.code(str(e))
    st.stop()

# =========================
# Google Sheet URL
# =========================
SHEET_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit"

# =========================
# 開啟 Google Sheet
# =========================
try:

    spreadsheet = client.open_by_url(SHEET_URL)

    st.success("成功開啟 Google Sheet")

except Exception as e:

    st.error("Google Sheet 開啟失敗")
    st.code(str(e))
    st.stop()

# =========================
# 取得 worksheets
# =========================
worksheets = spreadsheet.worksheets()

# =========================
# 篩選日期 sheets
# =========================
date_sheets = []

for ws in worksheets:

    try:

        datetime.strptime(ws.title, "%Y-%m-%d")

        date_sheets.append(ws)

    except:
        pass

# =========================
# 日期排序（新 → 舊）
# =========================
date_sheets = sorted(
    date_sheets,
    key=lambda x: datetime.strptime(x.title, "%Y-%m-%d"),
    reverse=True
)

st.write("找到日期 Sheets：")

st.write([ws.title for ws in date_sheets])

# =========================
# 快取讀取（24小時）
# =========================
@st.cache_data(ttl=86400)
def load_all_sheets():

    all_data = {}

    for ws in date_sheets:

        try:

            values = ws.get_all_values()

            # 空 sheet
            if len(values) <= 1:
                continue

            headers = [h.strip() for h in values[0]]

            rows = values[1:]

            df = pd.DataFrame(rows, columns=headers)

            # 清除欄位空白
            df.columns = df.columns.str.strip()

            # 移除空姓名
            if "姓名" in df.columns:

                df = df[
                    df["姓名"].astype(str).str.strip() != ""
                ]

            all_data[ws.title] = df

        except:
            continue

    return all_data

# =========================
# 讀取資料
# =========================
all_sheet_data = load_all_sheets()

# =========================
# Tabs
# =========================
tab1, tab2 = st.tabs([
    "連三天不假外宿",
    "每天點名不到名單"
])

# ==================================================
# TAB 1：連三天不假外宿
# ==================================================
with tab1:

    st.header("連三天不假外宿")

    # 每三天一組
    groups = [
        date_sheets[i:i+3]
        for i in range(0, len(date_sheets), 3)
    ]

    for group in groups:

        # 不足三天跳過
        if len(group) < 3:
            continue

        group_dates = [ws.title for ws in group]

        st.subheader(
            f"{group_dates[0]} ~ {group_dates[-1]}"
        )

        all_data = []

        for ws in group:

            df = all_sheet_data.get(ws.title)

            if df is None:
                continue

            required = [
                "狀態",
                "房號",
                "學號",
                "姓名"
            ]

            if not all(c in df.columns for c in required):
                continue

            # 只抓 缺
            temp = df[
                df["狀態"].astype(str).str.strip() == "缺"
            ].copy()

            temp["日期"] = ws.title

            all_data.append(temp)

        # 沒資料
        if not all_data:

            st.warning("此組沒有資料")

            continue

        # 合併
        full_df = pd.concat(
            all_data,
            ignore_index=True
        )

        # 三天都缺
        result = (
            full_df.groupby(
                ["房號", "學號", "姓名"]
            )["日期"]
            .nunique()
            .reset_index()
        )

        result = result[
            result["日期"] == 3
        ]

        # 顯示
        if result.empty:

            st.success("沒有連三天缺席")

        else:

            result["日期區間"] = (
                f"{group_dates[0]} ~ {group_dates[-1]}"
            )

            result = result[
                [
                    "日期區間",
                    "房號",
                    "學號",
                    "姓名"
                ]
            ]

            st.dataframe(
                result,
                use_container_width=True
            )

# ==================================================
# TAB 2：每天點名不到名單
# ==================================================
with tab2:

    st.header("每天點名不到名單")

    all_missing_records = []

    for ws in date_sheets:

        df = all_sheet_data.get(ws.title)

        if df is None:
            continue

        # 必要欄位
        required = [
            "狀態",
            "房號",
            "學號",
            "姓名"
        ]

        if not all(c in df.columns for c in required):
            continue

        # 只抓 缺
        result = df[
            df["狀態"].astype(str).str.strip() == "缺"
        ].copy()

        # 無資料
        if result.empty:
            continue

        # =========================
        # 日期標題
        # =========================
        st.subheader(ws.title)

        # =========================
        # 顯示欄位
        # =========================
        show_df = result[
            ["房號", "學號", "姓名"]
        ].reset_index(drop=True)

        # 顯示表格
        st.dataframe(
            show_df,
            use_container_width=True
        )

        # 加入統計
        all_missing_records.append(show_df)

    # =========================
    # 常缺席統計
    # =========================
    if all_missing_records:

        st.divider()

        st.subheader("🔥 常缺席名單（缺席 ≥ 3 次）")

        summary = pd.concat(all_missing_records)

        freq = (
            summary.groupby(
                ["房號", "學號", "姓名"]
            )
            .size()
            .reset_index(name="缺席次數")
        )

        # 🔴 標記
        freq["狀態"] = freq["缺席次數"].apply(
            lambda x: "🔴 常缺席" if x >= 3 else ""
        )

        # 排序（高→低）
        freq = freq.sort_values(
            by="缺席次數",
            ascending=False
        )

        st.dataframe(
            freq,
            use_container_width=True
        )

# =========================
# Footer
# =========================
st.divider()

st.caption(
    f"最後更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)