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

@st.cache_resource
def get_gspread_client():

    creds = Credentials.from_service_account_info(
        st.secrets["google"],
        scopes=SCOPES
    )

    return gspread.authorize(creds)

try:

    client = get_gspread_client()

except Exception as e:

    st.error("Google 驗證失敗")
    st.code(str(e))
    st.stop()

# ==================================================
# Google Sheets URL
# ==================================================

# 點名總表
ROLLCALL_SHEET_URL = "你的點名總表"

# 上學期外宿晚歸
UPPER_GATE_URL = "你的上學期Sheet"

# 下學期外宿晚歸
LOWER_GATE_URL = "你的下學期Sheet"

# ==================================================
# 開啟 Spreadsheet
# ==================================================

@st.cache_resource
def get_spreadsheet(url):

    return client.open_by_url(url)

try:

    rollcall_spreadsheet = get_spreadsheet(
        ROLLCALL_SHEET_URL
    )

    upper_gate_spreadsheet = get_spreadsheet(
        UPPER_GATE_URL
    )

    lower_gate_spreadsheet = get_spreadsheet(
        LOWER_GATE_URL
    )

except Exception as e:

    st.error("Google Sheet 開啟失敗")
    st.code(str(e))
    st.stop()

# ==================================================
# 讀取指定 Sheet（24hr cache）
# ==================================================

@st.cache_data(ttl=86400)
def load_sheet_df(sheet_url, sheet_name):

    try:

        spreadsheet = client.open_by_url(
            sheet_url
        )

        ws = spreadsheet.worksheet(
            sheet_name
        )

        data = ws.get()

        if len(data) <= 1:

            return pd.DataFrame()

        headers = data[0]

        rows = data[1:]

        df = pd.DataFrame(
            rows,
            columns=headers
        )

        df.columns = (
            df.columns.str.strip()
        )

        return df

    except:

        return pd.DataFrame()

# ==================================================
# 讀取點名資料
# ==================================================

@st.cache_data(ttl=86400)
def load_rollcall_data():

    worksheets = (
        rollcall_spreadsheet.worksheets()
    )

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

    # 新 → 舊
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

            data = ws.get()

            if len(data) <= 1:
                continue

            headers = [
                h.strip()
                for h in data[0]
            ]

            rows = data[1:]

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

def analyze_gate(
    uploaded_file,
    semester_sheet_url
):

    if uploaded_file is None:

        return None, None, None

    # ==================================================
    # 讀取 Excel
    # ==================================================

    try:

        df = pd.read_excel(
            uploaded_file
        )

    except Exception as e:

        st.error("Excel 讀取失敗")
        st.code(str(e))

        return None, None, None

    df.columns = (
        df.columns.str.strip()
    )

    # ==================================================
    # 必要欄位
    # ==================================================

    required_cols = [
        "學號",
        "姓名",
        "刷卡時間"
    ]

    missing = [
        c for c in required_cols
        if c not in df.columns
    ]

    if missing:

        st.error(
            f"缺少欄位：{missing}"
        )

        return None, None, None

    # ==================================================
    # 時間欄位
    # ==================================================

    df["刷卡時間"] = pd.to_datetime(
        df["刷卡時間"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["刷卡時間"]
    )

    df["日期"] = (
        df["刷卡時間"].dt.date
    )

    # ==================================================
    # 00:00 ~ 06:00
    # ==================================================

    df = df[
        (df["刷卡時間"].dt.hour >= 0) &
        (df["刷卡時間"].dt.hour < 6)
    ].copy()

    # ==================================================
    # 移除 LHU / Y
    # ==================================================

    df["姓名"] = (
        df["姓名"].astype(str)
    )

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
    )

    # ==================================================
    # 間隔 > 60分鐘
    # ==================================================

    selected_rows = []

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
                    row["刷卡時間"]
                    - last_time
                )

                if diff > timedelta(
                    minutes=60
                ):

                    selected_rows.append(idx)

                last_time = row["刷卡時間"]

    df_result = df.loc[selected_rows]

    # ==================================================
    # 日期排序
    # ==================================================

    df_result = df_result.sort_values(
        by=["日期", "刷卡時間"],
        ascending=False
    )

    # ==================================================
    # 讀取 Sheet
    # ==================================================

    leave_df = load_sheet_df(
        semester_sheet_url,
        "外宿申請"
    )

    long_leave_df = load_sheet_df(
        semester_sheet_url,
        "長期外宿"
    )

    late_df = load_sheet_df(
        semester_sheet_url,
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
    # 星期 mapping
    # ==================================================

    weekday_map = {
        0: "一",
        1: "二",
        2: "三",
        3: "四",
        4: "五",
        5: "六",
        6: "日"
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

        elif not long_leave_df.empty:

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

        elif not late_df.empty:

            late_match = late_df[
                late_df["學號"].astype(str)
                == student_id
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
    # 白卡分類
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
# TAB1
# ==================================================

with tab1:

    st.header("連三天不假外宿")

# ==================================================
# TAB2
# ==================================================

with tab2:

    st.header("每天點名不到名單")

# ==================================================
# TAB3
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
            UPPER_GATE_URL
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

        st.download_button(
            label="下載刷卡資料.xlsx",
            data=to_excel(df_nonC),
            file_name="刷卡資料.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.download_button(
            label="下載白卡刷卡資料.xlsx",
            data=to_excel(df_C),
            file_name="白卡刷卡資料.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ==================================================
# TAB4
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
            LOWER_GATE_URL
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

        st.download_button(
            label="下載刷卡資料.xlsx",
            data=to_excel(df_nonC),
            file_name="刷卡資料.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.download_button(
            label="下載白卡刷卡資料.xlsx",
            data=to_excel(df_C),
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