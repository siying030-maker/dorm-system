import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# =========================
# 頁面設定
# =========================

st.set_page_config(
    page_title="宿舍點名分析系統",
    layout="wide"
)

st.title("宿舍點名分析系統")

# =========================
# Google API
# =========================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# =========================
# Google 驗證
# =========================

try:

    creds = Credentials.from_service_account_file(
        "service_account.json",
        scopes=SCOPES
    )

    client = gspread.authorize(creds)

    st.success("Google 驗證成功")

except Exception as e:

    st.error("Google 驗證失敗")
    st.code(str(e))
    st.stop()

# =========================
# Google Sheet 網址
# =========================

SHEET_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit?gid=1847984024#gid=1847984024"

# 範例：
# SHEET_URL = "https://docs.google.com/spreadsheets/d/xxxxxxxx/edit#gid=0"

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
# 取得所有 Sheets
# =========================

worksheets = spreadsheet.worksheets()

# =========================
# 篩選日期格式 Sheets
# =========================

date_sheets = []

for ws in worksheets:

    try:

        datetime.strptime(ws.title, "%Y-%m-%d")

        date_sheets.append(ws)

    except:
        pass

# 日期排序
date_sheets = sorted(
    date_sheets,
    key=lambda x: datetime.strptime(x.title, "%Y-%m-%d")
)

st.write("找到日期 Sheets：")

st.write([ws.title for ws in date_sheets])

# =========================
# 快取讀取 Google Sheet
# =========================

@st.cache_data(ttl=300)
def load_all_sheets():

    all_sheet_data = {}

    for ws in date_sheets:

        try:

            values = ws.get_all_values()

            # 空 Sheet
            if len(values) <= 1:
                continue

            headers = [h.strip() for h in values[0]]

            rows = values[1:]

            df = pd.DataFrame(rows, columns=headers)

            # 清除欄位空白
            df.columns = df.columns.str.strip()

            # 去除空白列
            if "姓名" in df.columns:

                df = df[
                    df["姓名"].astype(str).str.strip() != ""
                ]

            all_sheet_data[ws.title] = df

        except Exception as e:

            st.error(f"{ws.title} 讀取失敗")
            st.code(str(e))

    return all_sheet_data

# =========================
# 只讀一次 Google
# =========================

all_sheet_data = load_all_sheets()

# =========================
# 分頁
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

    # 每三個 Sheet 為一組
    groups = [
        date_sheets[i:i+3]
        for i in range(0, len(date_sheets), 3)
    ]

    for idx, group in enumerate(groups):

        # 不足三天跳過
        if len(group) < 3:
            continue

        group_dates = [ws.title for ws in group]

        st.subheader(
            f"{group_dates[0]} ~ {group_dates[-1]}"
        )

        all_data = []

        for ws in group:

            try:

                df = all_sheet_data.get(ws.title)

                if df is None:
                    continue

                # 必要欄位
                required_cols = [
                    "狀態",
                    "房號",
                    "姓名"
                ]

                missing = [
                    c for c in required_cols
                    if c not in df.columns
                ]

                if missing:
                    continue

                # 只保留 狀態=缺
                temp_df = df[
                    df["狀態"].astype(str).str.strip() == "缺"
                ].copy()

                # 加入日期
                temp_df["日期"] = ws.title

                all_data.append(temp_df)

            except Exception as e:

                st.error(f"{ws.title} 分析失敗")
                st.code(str(e))

        # 沒有資料
        if len(all_data) == 0:

            st.warning("此組沒有資料")

            continue

        # 合併
        full_df = pd.concat(all_data, ignore_index=True)

        # 三天都缺
        result = (
            full_df.groupby(["房號", "姓名"])["日期"]
            .nunique()
            .reset_index()
        )

        result = result[
            result["日期"] == 3
        ]

        # 顯示結果
        if result.empty:

            st.success("沒有連三天缺席")

        else:

            result["日期"] = (
                f"{group_dates[0]} ~ {group_dates[-1]}"
            )

            result = result[
                ["日期", "房號", "姓名"]
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

    for ws in date_sheets:

        try:

            df = all_sheet_data.get(ws.title)

            if df is None:
                continue

            # 必要欄位
            required_cols = [
                "狀態",
                "房號",
                "姓名"
            ]

            missing = [
                c for c in required_cols
                if c not in df.columns
            ]

            if missing:
                continue

            # 只抓 狀態=缺
            result = df[
                df["狀態"].astype(str).str.strip() == "缺"
            ].copy()

            # 無資料
            if result.empty:
                continue

            st.subheader(ws.title)

            result = result[
                ["房號", "姓名"]
            ].reset_index(drop=True)

            result.insert(0, "日期", ws.title)

            st.dataframe(
                result,
                use_container_width=True
            )

        except Exception as e:

            st.error(f"{ws.title} 分析失敗")
            st.code(str(e))

# =========================
# 更新時間
# =========================

st.divider()

st.caption(
    f"最後更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)