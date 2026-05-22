import streamlit as st
import pandas as pd
import gspread

from io import BytesIO
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

# ==================================================
# 頁面設定
# ==================================================

st.set_page_config(
    page_title="宿舍管理系統",
    layout="wide"
)

st.title("宿舍管理系統")

# ==================================================
# Google API Scope
# ==================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ==================================================
# Google 驗證
# ==================================================

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

# ==================================================
# Google Sheets URL
# ==================================================

# 點名總表
ROLLCALL_SHEET_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit"

# 上學期外宿晚歸
UPPER_GATE_URL = "https://docs.google.com/spreadsheets/d/1Pr1fQYH35KgXMkl6igxqc-3jnZ5ufi0QgWtgp3782Lo/edit"

# 下學期外宿晚歸
LOWER_GATE_URL = "https://docs.google.com/spreadsheets/d/1ivjA_-voyNAUGbvbc5o5BULu_MgU2AqbNokvQJ5dfe4/edit"

# ==================================================
# 開啟 Google Sheet
# ==================================================

@st.cache_resource
def open_spreadsheet(url):

    return client.open_by_url(url)

try:

    rollcall_spreadsheet = open_spreadsheet(
        ROLLCALL_SHEET_URL
    )

    upper_gate_spreadsheet = open_spreadsheet(
        UPPER_GATE_URL
    )

    lower_gate_spreadsheet = open_spreadsheet(
        LOWER_GATE_URL
    )

    st.success("成功開啟 Google Sheets")

except Exception as e:

    st.error("Google Sheet 開啟失敗")
    st.code(str(e))
    st.stop()

# ==================================================
# 讀取指定 Sheet
# ==================================================

def load_sheet_df(spreadsheet, sheet_name):

    try:

        ws = spreadsheet.worksheet(sheet_name)

        data = ws.get_all_records()

        df = pd.DataFrame(data)

        df.columns = df.columns.str.strip()

        return df

    except:

        return pd.DataFrame()

# ==================================================
# 讀取點名資料（24小時快取）
# ==================================================

@st.cache_data(ttl=86400)
def load_rollcall_data():

    worksheets = rollcall_spreadsheet.worksheets()

    date_sheets = []

    for ws in worksheets:

        try:

            datetime.strptime(
                ws.title,
                "%Y-%m-%d"
            )

            date_sheets.append(ws)

        except:
            pass

    # 日期排序（新 → 舊）
    date_sheets = sorted(
        date_sheets,
        key=lambda x: datetime.strptime(
            x.title,
            "%Y-%m-%d"
        ),
        reverse=True
    )

    all_data = {}

    for ws in date_sheets:

        try:

            values = ws.get_all_values()

            if len(values) <= 1:
                continue

            headers = [
                h.strip()
                for h in values[0]
            ]

            rows = values[1:]

            df = pd.DataFrame(
                rows,
                columns=headers
            )

            df.columns = (
                df.columns.str.strip()
            )

            if "姓名" in df.columns:

                df = df[
                    df["姓名"]
                    .astype(str)
                    .str.strip() != ""
                ]

            all_data[ws.title] = df

        except:
            continue

    return date_sheets, all_data

# ==================================================
# 門禁分析
# ==================================================

def analyze_gate(uploaded_file, semester_spreadsheet):

    if uploaded_file is None:

        return None, None, None

    # ==================================================
    # 讀取 Excel
    # ==================================================

    df = pd.read_excel(uploaded_file)

    df.columns = df.columns.str.strip()

    # ==================================================
    # 時間欄位處理
    # ==================================================

    df["刷卡時間"] = pd.to_datetime(
        df["刷卡時間"],
        errors="coerce"
    )

    df["時間"] = df["刷卡時間"].dt.time

    df["日期"] = df["刷卡時間"].dt.date

    # ==================================================
    # 篩選 00:00 ~ 06:00
    # ==================================================

    df = df[
        (df["刷卡時間"].dt.hour >= 0) &
        (df["刷卡時間"].dt.hour < 6)
    ].copy()

    # ==================================================
    # 移除 LHU / Y 開頭
    # ==================================================

    df["姓名"] = df["姓名"].astype(str)

    df = df[
        ~df["姓名"]
        .fillna("")
        .str.upper()
        .str.startswith(("LHU", "Y"))
    ]

    # ==================================================
    # 排序
    # ==================================================

    df = df.sort_values(
        by=["姓名", "日期", "刷卡時間"]
    ).copy()

    # ==================================================
    # 時間差 > 60 分鐘才保留
    # ==================================================

    selected_rows = []

    time_threshold = 60

    for (name, date), group in df.groupby(
        ["姓名", "日期"]
    ):

        last_time = None

        for idx, row in group.iterrows():

            if last_time is None:

                selected_rows.append(idx)

                last_time = row["刷卡時間"]

            else:

                diff = (
                    row["刷卡時間"] - last_time
                )

                if diff > timedelta(
                    minutes=time_threshold
                ):

                    selected_rows.append(idx)

                last_time = row["刷卡時間"]

    # ==================================================
    # 保留結果
    # ==================================================

    df_result = df.loc[selected_rows]

    df_result = df_result.sort_values(
        by=["日期", "刷卡時間"],
        ascending=False
    )

    # ==================================================
    # 讀取 Sheet
    # ==================================================

    leave_df = load_sheet_df(
        semester_spreadsheet,
        "外宿申請"
    )

    long_leave_df = load_sheet_df(
        semester_spreadsheet,
        "長期外宿"
    )

    late_df = load_sheet_df(
        semester_spreadsheet,
        "長期晚歸"
    )

    # ==================================================
    # 日期格式
    # ==================================================

    if not leave_df.empty:

        leave_df["申請日期"] = pd.to_datetime(
            leave_df["申請日期"],
            errors="coerce"
        )

        leave_df["結束日期"] = pd.to_datetime(
            leave_df["結束日期"],
            errors="coerce"
        )

    # ==================================================
    # 星期對照
    # ==================================================

    weekday_map = {
        1: "一",
        2: "二",
        3: "三",
        4: "四",
        5: "五",
        6: "六",
        7: "日"
    }

    status_list = []

    # ==================================================
    # 判斷
    # ==================================================

    for _, row in df_result.iterrows():

        student_id = str(
            row["學號"]
        ).strip()

        gate_date = pd.to_datetime(
            row["日期"]
        )

        gate_time = row["刷卡時間"]

        status = "未申請"

        # ==================================================
        # 外宿申請
        # ==================================================

        if not leave_df.empty:

            leave_match = leave_df[
                (leave_df["學號"].astype(str) == student_id) &
                (leave_df["申請日期"] <= gate_date) &
                (leave_df["結束日期"] >= gate_date)
            ]

            if not leave_match.empty:

                status = "已申請外宿（凌晨回宿）"

        # ==================================================
        # 長期外宿
        # ==================================================

        if not long_leave_df.empty:

            weekday = weekday_map[
                gate_date.weekday()
            ]

            long_match = long_leave_df[
                (long_leave_df["學號"].astype(str) == student_id) &
                (
                    long_leave_df["星期"]
                    .astype(str)
                    .str.contains(weekday)
                )
            ]

            if not long_match.empty:

                status = "長期外宿（凌晨回宿）"

        # ==================================================
        # 長期晚歸
        # ==================================================

        if not late_df.empty:

            late_match = late_df[
                late_df["學號"].astype(str) == student_id
            ]

            if not late_match.empty:

                try:

                    limit_time = pd.to_datetime(
                        late_match.iloc[0]["返回時間"]
                    ).time()

                    if gate_time.time() <= limit_time:

                        status = "晚歸正常"

                    else:

                        status = "晚歸超時"

                except:
                    pass

        status_list.append(status)

    df_result["狀態判斷"] = status_list

    # ==================================================
    # 白卡
    # ==================================================

    df_C = df_result[
        df_result["姓名"]
        .str.upper()
        .str.startswith("C")
    ]

    df_nonC = df_result[
        ~df_result["姓名"]
        .str.upper()
        .str.startswith("C")
    ]

    return df_result, df_C, df_nonC

# ==================================================
# Excel 匯出
# ==================================================

def to_excel(df):

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False
        )

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
# TAB1：連三天不假外宿
# ==================================================

with tab1:

    st.header("連三天不假外宿")

    date_sheets, all_sheet_data = (
        load_rollcall_data()
    )

    groups = [
        date_sheets[i:i+3]
        for i in range(
            0,
            len(date_sheets),
            3
        )
    ]

    for group in groups:

        if len(group) < 3:
            continue

        group_dates = [
            ws.title
            for ws in group
        ]

        st.subheader(
            f"{group_dates[0]} ~ {group_dates[-1]}"
        )

        all_data = []

        for ws in group:

            df = all_sheet_data.get(
                ws.title
            )

            if df is None:
                continue

            required = [
                "狀態",
                "房號",
                "學號",
                "姓名"
            ]

            if not all(
                c in df.columns
                for c in required
            ):
                continue

            temp = df[
                df["狀態"]
                .astype(str)
                .str.strip() == "缺"
            ].copy()

            temp["日期"] = ws.title

            all_data.append(temp)

        if not all_data:

            st.warning("此組沒有資料")

            continue

        full_df = pd.concat(
            all_data,
            ignore_index=True
        )

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
# TAB2：每天點名不到名單
# ==================================================

with tab2:

    st.header("每天點名不到名單")

    all_missing_records = []

    for ws in date_sheets:

        df = all_sheet_data.get(
            ws.title
        )

        if df is None:
            continue

        required = [
            "狀態",
            "房號",
            "學號",
            "姓名"
        ]

        if not all(
            c in df.columns
            for c in required
        ):
            continue

        result = df[
            df["狀態"]
            .astype(str)
            .str.strip() == "缺"
        ].copy()

        if result.empty:
            continue

        # 日期標題
        st.subheader(ws.title)

        # 顯示表格
        show_df = result[
            ["房號", "學號", "姓名"]
        ].reset_index(drop=True)

        st.dataframe(
            show_df,
            use_container_width=True
        )

        all_missing_records.append(
            show_df
        )

    # ==================================================
    # 常缺席統計
    # ==================================================

    if all_missing_records:

        st.divider()

        st.subheader(
            "🔥 常缺席名單（缺席 ≥ 3 次）"
        )

        summary = pd.concat(
            all_missing_records
        )

        freq = (
            summary.groupby(
                ["房號", "學號", "姓名"]
            )
            .size()
            .reset_index(name="缺席次數")
        )

        freq["狀態"] = freq[
            "缺席次數"
        ].apply(
            lambda x:
            "🔴 常缺席"
            if x >= 3
            else ""
        )

        freq = freq.sort_values(
            by="缺席次數",
            ascending=False
        )

        st.dataframe(
            freq,
            use_container_width=True
        )

# ==================================================
# TAB3：上學期門禁
# ==================================================

with tab3:

    st.header("上學期門禁")

    uploaded_upper = st.file_uploader(
        "上傳上學期門禁 Excel",
        type=["xlsx"],
        key="upper"
    )

    if uploaded_upper:

        result, df_C, df_nonC = analyze_gate(
            uploaded_upper,
            upper_gate_spreadsheet
        )

        st.subheader("一般刷卡資料")

        st.dataframe(
            df_nonC,
            use_container_width=True
        )

        st.subheader("白卡刷卡資料")

        st.dataframe(
            df_C,
            use_container_width=True
        )

        # 下載
        normal_excel = to_excel(df_nonC)

        white_excel = to_excel(df_C)

        st.download_button(
            label="下載刷卡資料.xlsx",
            data=normal_excel,
            file_name="刷卡資料.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.download_button(
            label="下載白卡刷卡資料.xlsx",
            data=white_excel,
            file_name="白卡刷卡資料.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ==================================================
# TAB4：下學期門禁
# ==================================================

with tab4:

    st.header("下學期門禁")

    uploaded_lower = st.file_uploader(
        "上傳下學期門禁 Excel",
        type=["xlsx"],
        key="lower"
    )

    if uploaded_lower:

        result, df_C, df_nonC = analyze_gate(
            uploaded_lower,
            lower_gate_spreadsheet
        )

        st.subheader("一般刷卡資料")

        st.dataframe(
            df_nonC,
            use_container_width=True
        )

        st.subheader("白卡刷卡資料")

        st.dataframe(
            df_C,
            use_container_width=True
        )

        # 下載
        normal_excel = to_excel(df_nonC)

        white_excel = to_excel(df_C)

        st.download_button(
            label="下載刷卡資料.xlsx",
            data=normal_excel,
            file_name="刷卡資料.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.download_button(
            label="下載白卡刷卡資料.xlsx",
            data=white_excel,
            file_name="白卡刷卡資料.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ==================================================
# Footer
# ==================================================

st.divider()

st.caption(
    f"最後更新時間："
    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)