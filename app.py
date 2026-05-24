import streamlit as st
import pandas as pd
import gspread
import time

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
# 自動每日 00:30 更新 cache
# ==================================================

now = datetime.now()

if now.hour == 0 and now.minute >= 30:
    st.cache_data.clear()

# ==================================================
# Cache 時間（24小時）
# ==================================================

CACHE_TTL = 86400

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

except Exception as e:

    st.error("Google 驗證失敗")
    st.code(str(e))
    st.stop()

# ==================================================
# API 防爆（避免 429）
# ==================================================

_last_call = 0

def rate_limit():

    global _last_call

    now_time = time.time()

    if now_time - _last_call < 0.5:
        time.sleep(0.5)

    _last_call = time.time()

# ==================================================
# Google Sheet URL
# ==================================================

ROLLCALL_SHEET_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit"

UPPER_GATE_URL = "https://docs.google.com/spreadsheets/d/1Pr1fQYH35KgXMkl6igxqc-3jnZ5ufi0QgWtgp3782Lo/edit"

LOWER_GATE_URL = "https://docs.google.com/spreadsheets/d/1ivjA_-voyNAUGbvbc5o5BULu_MgU2AqbNokvQJ5dfe4/edit"

# ==================================================
# 安全開啟 Google Sheet
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

try:

    rollcall_ss = open_sheet(ROLLCALL_SHEET_URL)

    upper_ss = open_sheet(UPPER_GATE_URL)

    lower_ss = open_sheet(LOWER_GATE_URL)

except Exception as e:

    st.error("Google Sheet 開啟失敗")
    st.code(str(e))
    st.stop()

# ==================================================
# 讀取單一 Sheet
# ==================================================

@st.cache_data(ttl=CACHE_TTL)
def load_sheet_df(url, sheet_name):

    try:

        rate_limit()

        ss = client.open_by_url(url)

        ws = ss.worksheet(sheet_name)

        data = ws.get_all_records()

        df = pd.DataFrame(data)

        if not df.empty:
            df.columns = df.columns.str.strip()

        return df

    except:

        return pd.DataFrame()

# ==================================================
# 點名資料 cache
# ==================================================

@st.cache_data(ttl=CACHE_TTL)
def load_rollcall_cache():

    worksheets = rollcall_ss.worksheets()

    data = {}

    for ws in worksheets:

        try:

            datetime.strptime(ws.title, "%Y-%m-%d")

        except:
            continue

        try:

            rate_limit()

            values = ws.get_all_values()

            if len(values) <= 1:
                continue

            df = pd.DataFrame(
                values[1:],
                columns=values[0]
            )

            df.columns = df.columns.str.strip()

            if "姓名" in df.columns:

                df = df[
                    df["姓名"]
                    .astype(str)
                    .str.strip() != ""
                ]

            data[ws.title] = df

        except:
            continue

    return data

# ==================================================
# 門禁分析
# ==================================================

def analyze_gate(file, semester_url):

    if file is None:
        return None, None, None

    # ==================================================
    # 讀取 Excel
    # ==================================================

    df = pd.read_excel(file)

    df.columns = df.columns.str.strip()

    # ==================================================
    # 時間處理
    # ==================================================

    df["刷卡時間"] = pd.to_datetime(
        df["刷卡時間"],
        errors="coerce"
    )

    df["日期"] = df["刷卡時間"].dt.date

    # ==================================================
    # 篩選 00:00 ~ 06:00
    # ==================================================

    df = df[
        (df["刷卡時間"].dt.hour >= 0) &
        (df["刷卡時間"].dt.hour < 6)
    ].copy()

    # ==================================================
    # 排除 LHU / Y
    # ==================================================

    df["姓名"] = df["姓名"].astype(str)

    df = df[
        ~df["姓名"]
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
    # 間隔 > 60 分鐘才保留
    # ==================================================

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

    df = df.loc[selected]

    # ==================================================
    # 排序
    # ==================================================

    df = df.sort_values(
        by=["日期", "刷卡時間"],
        ascending=False
    )

    # ==================================================
    # 讀取判斷表
    # ==================================================

    leave_df = load_sheet_df(
        semester_url,
        "外宿申請"
    )

    long_leave_df = load_sheet_df(
        semester_url,
        "長期外宿"
    )

    late_df = load_sheet_df(
        semester_url,
        "長期晚歸"
    )

    status_list = []

    weekday_map = {
        1: "一",
        2: "二",
        3: "三",
        4: "四",
        5: "五",
        6: "六",
        7: "日"
    }

    # ==================================================
    # 判斷
    # ==================================================

    for _, row in df.iterrows():

        sid = str(row["學號"]).strip()

        gate_date = pd.to_datetime(row["日期"])

        gate_time = row["刷卡時間"]

        status = "未申請"

        # 外宿申請

        if not leave_df.empty:

            try:

                leave_df["申請日期"] = pd.to_datetime(
                    leave_df["申請日期"],
                    errors="coerce"
                )

                leave_df["結束日期"] = pd.to_datetime(
                    leave_df["結束日期"],
                    errors="coerce"
                )

                match = leave_df[
                    (leave_df["學號"].astype(str) == sid) &
                    (leave_df["申請日期"] <= gate_date) &
                    (leave_df["結束日期"] >= gate_date)
                ]

                if not match.empty:

                    status = "外宿凌晨回宿"

            except:
                pass

        # 長期外宿

        if not long_leave_df.empty:

            try:

                weekday = weekday_map[
                    gate_date.weekday()
                ]

                match = long_leave_df[
                    (long_leave_df["學號"].astype(str) == sid) &
                    (
                        long_leave_df["星期"]
                        .astype(str)
                        .str.contains(weekday)
                    )
                ]

                if not match.empty:

                    status = "長期外宿凌晨回宿"

            except:
                pass

        # 長期晚歸

        if not late_df.empty:

            try:

                match = late_df[
                    late_df["學號"].astype(str) == sid
                ]

                if not match.empty:

                    limit_time = pd.to_datetime(
                        match.iloc[0]["返回時間"]
                    ).time()

                    if gate_time.time() <= limit_time:

                        status = "晚歸正常"

                    else:

                        status = "晚歸超時"

            except:
                pass

        status_list.append(status)

    df["狀態"] = status_list

    # ==================================================
    # 只保留顯示欄位
    # ==================================================

    show_cols = [
        "房號",
        "學號",
        "姓名"
    ]

    show_cols = [
        c for c in show_cols
        if c in df.columns
    ]

    df = df[show_cols]

    # ==================================================
    # 白卡分流
    # ==================================================

    df_C = df[
        df["姓名"]
        .astype(str)
        .str.upper()
        .str.startswith("C")
    ]

    df_nonC = df[
        ~df["姓名"]
        .astype(str)
        .str.upper()
        .str.startswith("C")
    ]

    return df, df_C, df_nonC

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

    data = load_rollcall_cache()

    current_month = datetime.now().strftime("%Y-%m")

    month_options = sorted(
        list(set([d[:7] for d in data.keys()])),
        reverse=True
    )

    selected_month = st.selectbox(
        "選擇月份",
        month_options,
        index=0
    )

    keyword = st.text_input(
        "搜尋學號 / 姓名",
        key="tab1_search"
    )

    dates = sorted(
        [
            d for d in data.keys()
            if d.startswith(selected_month)
        ],
        reverse=True
    )

    groups = [
        dates[i:i+3]
        for i in range(0, len(dates), 3)
    ]

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

            temp = df[
                df["狀態"]
                .astype(str)
                .str.strip() == "缺"
            ].copy()

            temp["日期"] = d

            all_d.append(temp)

        if not all_d:

            st.info(
                f"{g[0]} ~ {g[-1]} 此三天無人連三天不假外宿"
            )

            continue

        df_all = pd.concat(all_d)

        res = (
            df_all.groupby(
                ["房號", "學號", "姓名"]
            )["日期"]
            .nunique()
            .reset_index()
        )

        res = res[
            res["日期"] == 3
        ]

        if keyword:

            res = res[
                res["學號"]
                .astype(str)
                .str.contains(keyword, na=False)
                |
                res["姓名"]
                .astype(str)
                .str.contains(keyword, na=False)
            ]

        st.subheader(
            f"{g[0]} ~ {g[-1]}"
        )

        if res.empty:

            st.info(
                f"{g[0]} ~ {g[-1]} 此三天無人連三天不假外宿"
            )

        else:

            st.dataframe(
                res[
                    ["房號", "學號", "姓名"]
                ],
                use_container_width=True
            )

# ==================================================
# TAB2
# ==================================================

with tab2:

    st.header("每天點名不到名單")

    data = load_rollcall_cache()

    month_options = sorted(
        list(set([d[:7] for d in data.keys()])),
        reverse=True
    )

    selected_month = st.selectbox(
        "選擇月份",
        month_options,
        index=0,
        key="tab2_month"
    )

    keyword = st.text_input(
        "搜尋學號 / 姓名",
        key="tab2_search"
    )

    dates = sorted(
        [
            d for d in data.keys()
            if d.startswith(selected_month)
        ],
        reverse=True
    )

    all_miss = []

    for d in dates:

        df = data.get(d)

        if df is None:
            continue

        if "狀態" not in df.columns:
            continue

        miss = df[
            df["狀態"]
            .astype(str)
            .str.strip() == "缺"
        ].copy()

        if miss.empty:
            continue

        if keyword:

            miss = miss[
                miss["學號"]
                .astype(str)
                .str.contains(keyword, na=False)
                |
                miss["姓名"]
                .astype(str)
                .str.contains(keyword, na=False)
            ]

        show = miss[
            ["房號", "學號", "姓名"]
        ]

        st.subheader(d)

        st.dataframe(
            show,
            use_container_width=True
        )

        all_miss.append(show)

    # ==================================================
    # 常缺席
    # ==================================================

    if all_miss:

        st.divider()

        st.subheader(
            "🔥 常缺席名單（缺席 >= 3 次）"
        )

        total = pd.concat(all_miss)

        freq = (
            total.groupby(
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
# TAB3
# ==================================================

with tab3:

    st.header("上學期門禁")

    file_upper = st.file_uploader(
        "上傳上學期門禁 Excel",
        type=["xlsx"],
        key="upper"
    )

    if file_upper:

        result, df_C, df_nonC = analyze_gate(
            file_upper,
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
            "下載刷卡資料.xlsx",
            to_excel(df_nonC),
            "刷卡資料.xlsx"
        )

        st.download_button(
            "下載白卡刷卡資料.xlsx",
            to_excel(df_C),
            "白卡刷卡資料.xlsx"
        )

# ==================================================
# TAB4
# ==================================================

with tab4:

    st.header("下學期門禁")

    file_lower = st.file_uploader(
        "上傳下學期門禁 Excel",
        type=["xlsx"],
        key="lower"
    )

    if file_lower:

        result, df_C, df_nonC = analyze_gate(
            file_lower,
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
            "下載刷卡資料.xlsx",
            to_excel(df_nonC),
            "刷卡資料.xlsx"
        )

        st.download_button(
            "下載白卡刷卡資料.xlsx",
            to_excel(df_C),
            "白卡刷卡資料.xlsx"
        )

# ==================================================
# Footer
# ==================================================

st.divider()

st.caption(
    f"最後更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)