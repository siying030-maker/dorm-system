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

st.title("🏠 宿舍管理系統")

# ==================================================
# 自動更新設定
# ==================================================

CACHE_TTL = 86400  # 24小時

now = datetime.now()

# 每天 00:30 自動刷新 cache
if now.hour == 0 and now.minute >= 30:
    st.cache_data.clear()

# ==================================================
# Google API
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

    st.success("✅ Google 驗證成功")

except Exception as e:

    st.error("❌ Google 驗證失敗")
    st.code(str(e))
    st.stop()

# ==================================================
# API 防爆
# ==================================================

_last_call = 0

def rate_limit():

    global _last_call

    now_time = time.time()

    if now_time - _last_call < 0.3:
        time.sleep(0.3)

    _last_call = time.time()

# ==================================================
# Sheet URL
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

                wait_time = (i + 1) * 5

                time.sleep(wait_time)

            else:

                raise e

    raise Exception("Google API 過載")

try:

    rollcall_ss = open_sheet(ROLLCALL_SHEET_URL)

    upper_ss = open_sheet(UPPER_GATE_URL)

    lower_ss = open_sheet(LOWER_GATE_URL)

    st.success("✅ Google Sheet 連線成功")

except Exception as e:

    st.error("❌ Google Sheet 開啟失敗")
    st.code(str(e))
    st.stop()

# ==================================================
# 載入點名資料
# ==================================================

@st.cache_data(ttl=CACHE_TTL)
def load_rollcall_cache():

    worksheets = rollcall_ss.worksheets()

    data = {}

    for ws in worksheets:

        try:

            # 只抓 YYYY-MM-DD
            datetime.strptime(ws.title, "%Y-%m-%d")

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
# 載入指定 sheet
# ==================================================

@st.cache_data(ttl=CACHE_TTL)
def load_sheet_df(url, sheet_name):

    try:

        ss = client.open_by_url(url)

        ws = ss.worksheet(sheet_name)

        rate_limit()

        data = ws.get_all_records()

        df = pd.DataFrame(data)

        df.columns = df.columns.str.strip()

        return df

    except:

        return pd.DataFrame()

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
    # 時間欄位
    # ==================================================

    df["刷卡時間"] = pd.to_datetime(
        df["刷卡時間"],
        errors="coerce"
    )

    df["日期"] = df["刷卡時間"].dt.date

    # ==================================================
    # 篩選凌晨
    # ==================================================

    df = df[
        (df["刷卡時間"].dt.hour >= 0) &
        (df["刷卡時間"].dt.hour < 6)
    ].copy()

    # ==================================================
    # 移除 LHU / Y
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
    # 時差過濾
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
    # 讀取 Sheet
    # ==================================================

    leave = load_sheet_df(
        semester_url,
        "外宿申請"
    )

    long_leave = load_sheet_df(
        semester_url,
        "長期外宿"
    )

    late = load_sheet_df(
        semester_url,
        "長期晚歸"
    )

    # ==================================================
    # 判斷
    # ==================================================

    status = []

    weekday_map = {
        1: "一",
        2: "二",
        3: "三",
        4: "四",
        5: "五",
        6: "六",
        7: "日"
    }

    for _, r in df.iterrows():

        sid = str(r["學號"]).strip()

        d = pd.to_datetime(r["日期"])

        t = r["刷卡時間"]

        s = "未申請"

        # ==================================================
        # 外宿
        # ==================================================

        if not leave.empty:

            m = leave[
                (leave["學號"].astype(str) == sid) &
                (
                    pd.to_datetime(
                        leave["申請日期"]
                    ) <= d
                ) &
                (
                    pd.to_datetime(
                        leave["結束日期"]
                    ) >= d
                )
            ]

            if not m.empty:

                s = "外宿凌晨回宿"

        # ==================================================
        # 長期外宿
        # ==================================================

        if not long_leave.empty:

            weekday = weekday_map[d.weekday()]

            m = long_leave[
                (long_leave["學號"].astype(str) == sid) &
                (
                    long_leave["星期"]
                    .astype(str)
                    .str.contains(weekday)
                )
            ]

            if not m.empty:

                s = "長期外宿凌晨回宿"

        # ==================================================
        # 晚歸
        # ==================================================

        if not late.empty:

            m = late[
                late["學號"].astype(str) == sid
            ]

            if not m.empty:

                try:

                    limit = pd.to_datetime(
                        m.iloc[0]["返回時間"]
                    ).time()

                    if t.time() <= limit:

                        s = "晚歸正常"

                    else:

                        s = "晚歸超時"

                except:
                    pass

        status.append(s)

    df["狀態判斷"] = status

    # ==================================================
    # 白卡分流
    # ==================================================

    df_C = df[
        df["姓名"]
        .str.upper()
        .str.startswith("C")
    ]

    df_nonC = df[
        ~df["姓名"]
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
# 點名資料
# ==================================================

data = load_rollcall_cache()

dates = sorted(
    data.keys(),
    reverse=True
)

# ==================================================
# 月份查詢
# ==================================================

month_options = sorted(
    list(set([
        d[:7]
        for d in dates
    ])),
    reverse=True
)

default_month = datetime.now().strftime("%Y-%m")

# ==================================================
# TAB1
# ==================================================

with tab1:

    st.header("連三天不假外宿")

    col1, col2 = st.columns(2)

    with col1:

        selected_month = st.selectbox(
            "選擇月份",
            month_options,
            index=0
        )

    with col2:

        keyword = st.text_input(
            "搜尋學號 / 姓名"
        )

    filtered_dates = [
        d for d in dates
        if d.startswith(selected_month)
    ]

    groups = [
        filtered_dates[i:i+3]
        for i in range(
            0,
            len(filtered_dates),
            3
        )
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

            continue

        full_df = pd.concat(all_d)

        res = (
            full_df.groupby(
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
                res,
                use_container_width=True
            )

# ==================================================
# TAB2
# ==================================================

with tab2:

    st.header("每天點名不到名單")

    col1, col2 = st.columns(2)

    with col1:

        selected_month = st.selectbox(
            "選擇月份 ",
            month_options,
            index=0
        )

    with col2:

        keyword = st.text_input(
            "搜尋學號 / 姓名 "
        )

    filtered_dates = [
        d for d in dates
        if d.startswith(selected_month)
    ]

    all_miss = []

    for d in filtered_dates:

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

        if miss.empty:
            continue

        st.subheader(d)

        show = miss[
            ["房號", "學號", "姓名"]
        ]

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
            "🔥 常缺席名單"
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

    file = st.file_uploader(
        "上傳上學期門禁 Excel",
        type=["xlsx"],
        key="upper"
    )

    if file:

        result, c, n = analyze_gate(
            file,
            UPPER_GATE_URL
        )

        st.subheader("一般刷卡資料")

        st.dataframe(
            n,
            use_container_width=True
        )

        st.subheader("白卡刷卡資料")

        st.dataframe(
            c,
            use_container_width=True
        )

        st.download_button(
            "下載刷卡資料.xlsx",
            to_excel(n),
            "刷卡資料.xlsx"
        )

        st.download_button(
            "下載白卡刷卡資料.xlsx",
            to_excel(c),
            "白卡刷卡資料.xlsx"
        )

# ==================================================
# TAB4
# ==================================================

with tab4:

    st.header("下學期門禁")

    file = st.file_uploader(
        "上傳下學期門禁 Excel",
        type=["xlsx"],
        key="lower"
    )

    if file:

        result, c, n = analyze_gate(
            file,
            LOWER_GATE_URL
        )

        st.subheader("一般刷卡資料")

        st.dataframe(
            n,
            use_container_width=True
        )

        st.subheader("白卡刷卡資料")

        st.dataframe(
            c,
            use_container_width=True
        )

        st.download_button(
            "下載刷卡資料.xlsx",
            to_excel(n),
            "刷卡資料.xlsx"
        )

        st.download_button(
            "下載白卡刷卡資料.xlsx",
            to_excel(c),
            "白卡刷卡資料.xlsx"
        )

# ==================================================
# Footer
# ==================================================

st.divider()

st.caption(
    f"最後更新時間："
    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)