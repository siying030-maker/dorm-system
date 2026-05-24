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

CACHE_TTL = 86400

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

except Exception as e:

    st.error("Google 驗證失敗")
    st.code(str(e))
    st.stop()

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
# Google Sheet URLs
# ==================================================

ROLLCALL_SHEET_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit"

UPPER_GATE_URL = "https://docs.google.com/spreadsheets/d/1Pr1fQYH35KgXMkl6igxqc-3jnZ5ufi0QgWtgp3782Lo/edit"

LOWER_GATE_URL = "https://docs.google.com/spreadsheets/d/1ivjA_-voyNAUGbvbc5o5BULu_MgU2AqbNokvQJ5dfe4/edit"

ADMIN_SHEET_URL = "https://docs.google.com/spreadsheets/d/1eZgdlelXQWcO3ZRxeXRjXNTI1g1I6RUZPGtJoC9iRes/edit"

# ==================================================
# 開啟 Google Sheet
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

    rollcall_ss = open_sheet(
        ROLLCALL_SHEET_URL
    )

    upper_ss = open_sheet(
        UPPER_GATE_URL
    )

    lower_ss = open_sheet(
        LOWER_GATE_URL
    )

    admin_ss = open_sheet(
        ADMIN_SHEET_URL
    )

except Exception as e:

    st.error("Google Sheet 開啟失敗")
    st.code(str(e))
    st.stop()

# ==================================================
# 讀取管理者資料
# ==================================================

@st.cache_data(ttl=300)
def load_admin_data():

    try:

        ws = admin_ss.get_worksheet(0)

        rate_limit()

        data = ws.get_all_records()

        df = pd.DataFrame(data)

        df.columns = df.columns.str.strip()

        return df

    except:

        return pd.DataFrame()

admin_df = load_admin_data()

# ==================================================
# 登入系統
# ==================================================

st.sidebar.title("管理者登入")

role = st.sidebar.selectbox(
    "選擇身分",
    ["舍監", "行政", "樓長"]
)

role_df = admin_df[
    admin_df["身分"].astype(str).str.strip() == role
]

name_list = role_df["姓名"].astype(str).tolist()

selected_name = st.sidebar.selectbox(
    "選擇姓名",
    name_list if name_list else ["無資料"]
)

password = st.sidebar.text_input(
    "輸入密碼",
    type="password"
)

login_btn = st.sidebar.button("登入")

# ==================================================
# Session State
# ==================================================

if "login_success" not in st.session_state:

    st.session_state.login_success = False

if "user_role" not in st.session_state:

    st.session_state.user_role = ""

if "user_name" not in st.session_state:

    st.session_state.user_name = ""

# ==================================================
# 登入驗證
# ==================================================

if login_btn:

    match = role_df[
        (role_df["姓名"].astype(str) == selected_name) &
        (role_df["密碼"].astype(str) == password)
    ]

    if not match.empty:

        st.session_state.login_success = True
        st.session_state.user_role = role
        st.session_state.user_name = selected_name

        st.sidebar.success("登入成功")

    else:

        st.sidebar.error("帳號或密碼錯誤")

# ==================================================
# 未登入
# ==================================================

if not st.session_state.login_success:

    st.warning("請先登入")
    st.stop()

# ==================================================
# 顯示登入資訊
# ==================================================

st.success(
    f"目前登入："
    f"{st.session_state.user_role} / "
    f"{st.session_state.user_name}"
)

# ==================================================
# 讀取點名資料
# ==================================================

@st.cache_data(ttl=CACHE_TTL)
def load_rollcall_cache():

    worksheets = rollcall_ss.worksheets()

    data = {}

    for ws in worksheets:

        try:

            datetime.strptime(
                ws.title,
                "%Y-%m-%d"
            )

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
# 讀取指定 Sheet
# ==================================================

def load_sheet_df(ss, name):

    try:

        rate_limit()

        ws = ss.worksheet(name)

        data = ws.get_all_records()

        df = pd.DataFrame(data)

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

    # ==================================================
    # 讀 Excel
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
        ["姓名", "日期", "刷卡時間"]
    )

    # ==================================================
    # 60分鐘過濾
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
    # 讀取外宿資料
    # ==================================================

    leave_df = load_sheet_df(
        semester_ss,
        "外宿申請"
    )

    long_leave_df = load_sheet_df(
        semester_ss,
        "長期外宿"
    )

    late_df = load_sheet_df(
        semester_ss,
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

    for _, row in df.iterrows():

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

                status = "外宿"

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

                status = "長期外宿"

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

    df["狀態判斷"] = status_list

    # ==================================================
    # 顯示欄位
    # ==================================================

    show_cols = [
        c for c in [
            "房號",
            "學號",
            "姓名",
            "狀態判斷"
        ]
        if c in df.columns
    ]

    df = df[show_cols]

    # ==================================================
    # 白卡分類
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
# 載入點名資料
# ==================================================

data = load_rollcall_cache()

dates = sorted(
    data.keys(),
    reverse=True
)

# ==================================================
# 權限 Tabs
# ==================================================

role = st.session_state.user_role

if role == "舍監":

    tabs = st.tabs([
        "連三天不假外宿",
        "每天點名不到名單"
    ])

elif role == "行政":

    tabs = st.tabs([
        "連三天不假外宿",
        "每天點名不到名單",
        "上學期門禁",
        "下學期門禁"
    ])

elif role == "樓長":

    tabs = st.tabs([
        "每天點名不到名單"
    ])

# ==================================================
# TAB1：連三天不假外宿
# ==================================================

if role in ["舍監", "行政"]:

    with tabs[0]:

        st.header("連三天不假外宿")

        groups = [
            dates[i:i+3]
            for i in range(
                0,
                len(dates),
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

            st.subheader(
                f"{g[0]} ~ {g[-1]}"
            )

            if not all_d:

                st.warning(
                    f"{g[0]} ~ {g[-1]} "
                    "此三天無人連三天不假外宿"
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

            if res.empty:

                st.warning(
                    f"{g[0]} ~ {g[-1]} "
                    "此三天無人連三天不假外宿"
                )

            else:

                show_df = res[
                    ["房號", "學號", "姓名"]
                ]

                st.dataframe(
                    show_df,
                    use_container_width=True
                )

# ==================================================
# TAB2：每天點名不到名單
# ==================================================

if role == "舍監":

    tab_index = 1

elif role == "行政":

    tab_index = 1

elif role == "樓長":

    tab_index = 0

with tabs[tab_index]:

    st.header("每天點名不到名單")

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
    # 常缺席統計
    # ==================================================

    if all_miss:

        st.divider()

        st.subheader("🔥 常缺席名單")

        total = pd.concat(all_miss)

        freq = (
            total.groupby(
                ["房號", "學號", "姓名"]
            )
            .size()
            .reset_index(name="缺席次數")
        )

        freq = freq.sort_values(
            "缺席次數",
            ascending=False
        )

        st.dataframe(
            freq,
            use_container_width=True
        )

# ==================================================
# TAB3：上學期門禁
# ==================================================

if role == "行政":

    with tabs[2]:

        st.header("上學期門禁")

        f = st.file_uploader(
            "上傳上學期門禁 Excel",
            type=["xlsx"],
            key="upper"
        )

        if f:

            df, c, n = analyze_gate(
                f,
                upper_ss
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
# TAB4：下學期門禁
# ==================================================

if role == "行政":

    with tabs[3]:

        st.header("下學期門禁")

        f = st.file_uploader(
            "上傳下學期門禁 Excel",
            type=["xlsx"],
            key="lower"
        )

        if f:

            df, c, n = analyze_gate(
                f,
                lower_ss
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