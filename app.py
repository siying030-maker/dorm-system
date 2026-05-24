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
# Google Sheets URL
# ==================================================

# 點名總表
ROLLCALL_SHEET_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit"

# 上學期外宿 / 晚歸
UPPER_GATE_URL = "https://docs.google.com/spreadsheets/d/1Pr1fQYH35KgXMkl6igxqc-3jnZ5ufi0QgWtgp3782Lo/edit"

# 下學期外宿 / 晚歸
LOWER_GATE_URL = "https://docs.google.com/spreadsheets/d/1ivjA_-voyNAUGbvbc5o5BULu_MgU2AqbNokvQJ5dfe4/edit"

# 管理者帳號
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
# 登入資料
# ==================================================

@st.cache_data(ttl=300)
def load_users(role):

    try:

        ws = admin_ss.worksheet(role)

        data = ws.get_all_records()

        df = pd.DataFrame(data)

        df.columns = df.columns.str.strip()

        return df

    except:

        return pd.DataFrame()

# ==================================================
# Session
# ==================================================

if "login" not in st.session_state:
    st.session_state.login = False

if "role" not in st.session_state:
    st.session_state.role = ""

if "user" not in st.session_state:
    st.session_state.user = ""

# ==================================================
# 登入頁面
# ==================================================

if not st.session_state.login:

    st.subheader("登入系統")

    role = st.selectbox(
        "選擇身分",
        ["舍監", "行政", "樓長"]
    )

    user_df = load_users(role)

    if user_df.empty:

        st.error(f"{role} Sheet 無資料")

        st.stop()

    user_col = user_df.columns[0]
    pass_col = user_df.columns[1]

    username = st.selectbox(
        "選擇使用者",
        user_df[user_col].astype(str).tolist()
    )

    password = st.text_input(
        "輸入密碼",
        type="password"
    )

    if st.button("登入"):

        match = user_df[
            (
                user_df[user_col]
                .astype(str)
                .str.strip()
                == username
            )
            &
            (
                user_df[pass_col]
                .astype(str)
                .str.strip()
                == password
            )
        ]

        if not match.empty:

            st.session_state.login = True
            st.session_state.role = role
            st.session_state.user = username

            st.rerun()

        else:

            st.error("帳號或密碼錯誤")

    st.stop()

# ==================================================
# 登入成功
# ==================================================

st.success(
    f"登入成功：{st.session_state.role} - {st.session_state.user}"
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

            df.columns = (
                df.columns.str.strip()
            )

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
# 讀取 Sheet
# ==================================================

def load_sheet_df(ss, name):

    try:

        ws = ss.worksheet(name)

        rate_limit()

        df = pd.DataFrame(
            ws.get_all_records()
        )

        df.columns = (
            df.columns.str.strip()
        )

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

    df.columns = (
        df.columns.str.strip()
    )

    # ==================================================
    # 時間
    # ==================================================

    df["刷卡時間"] = pd.to_datetime(
        df["刷卡時間"],
        errors="coerce"
    )

    df["日期"] = (
        df["刷卡時間"].dt.date
    )

    # ==================================================
    # 00:00 ~ 06:00
    # ==================================================

    df = df[
        (
            df["刷卡時間"].dt.hour >= 0
        )
        &
        (
            df["刷卡時間"].dt.hour < 6
        )
    ]

    # ==================================================
    # 排除 LHU / Y
    # ==================================================

    df["姓名"] = (
        df["姓名"].astype(str)
    )

    df = df[
        ~df["姓名"]
        .str.upper()
        .str.startswith(("LHU", "Y"))
    ]

    # ==================================================
    # 排序
    # ==================================================

    df = df.sort_values(
        [
            "姓名",
            "日期",
            "刷卡時間"
        ]
    )

    # ==================================================
    # 間隔 > 60分鐘
    # ==================================================

    selected = []

    threshold = timedelta(minutes=60)

    for (name, date), g in df.groupby(
        ["姓名", "日期"]
    ):

        last = None

        for idx, row in g.iterrows():

            if last is None:

                selected.append(idx)

            else:

                if (
                    row["刷卡時間"] - last
                    > threshold
                ):

                    selected.append(idx)

            last = row["刷卡時間"]

    df = df.loc[selected]

    # ==================================================
    # 外宿資料
    # ==================================================

    leave = load_sheet_df(
        semester_ss,
        "外宿申請"
    )

    long_leave = load_sheet_df(
        semester_ss,
        "長期外宿"
    )

    late = load_sheet_df(
        semester_ss,
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

    for _, row in df.iterrows():

        sid = str(
            row["學號"]
        ).strip()

        d = pd.to_datetime(
            row["日期"]
        )

        t = row["刷卡時間"]

        status = "未申請"

        # ==================================================
        # 外宿申請
        # ==================================================

        if not leave.empty:

            leave["申請日期"] = pd.to_datetime(
                leave["申請日期"],
                errors="coerce"
            )

            leave["結束日期"] = pd.to_datetime(
                leave["結束日期"],
                errors="coerce"
            )

            match = leave[
                (
                    leave["學號"]
                    .astype(str)
                    == sid
                )
                &
                (
                    leave["申請日期"] <= d
                )
                &
                (
                    leave["結束日期"] >= d
                )
            ]

            if not match.empty:

                status = "外宿凌晨回宿"

        # ==================================================
        # 長期外宿
        # ==================================================

        if not long_leave.empty:

            weekday = weekday_map[
                d.weekday()
            ]

            match = long_leave[
                (
                    long_leave["學號"]
                    .astype(str)
                    == sid
                )
                &
                (
                    long_leave["星期"]
                    .astype(str)
                    .str.contains(weekday)
                )
            ]

            if not match.empty:

                status = "長期外宿凌晨回宿"

        # ==================================================
        # 晚歸
        # ==================================================

        if not late.empty:

            match = late[
                late["學號"]
                .astype(str)
                == sid
            ]

            if not match.empty:

                try:

                    limit = pd.to_datetime(
                        match.iloc[0]["返回時間"]
                    ).time()

                    if t.time() <= limit:

                        status = "晚歸正常"

                    else:

                        status = "晚歸超時"

                except:
                    pass

        status_list.append(status)

    df["狀態"] = status_list

    # ==================================================
    # 顯示欄位
    # ==================================================

    show_cols = [
        "房號",
        "學號",
        "姓名"
    ]

    df_C = df[
        df["姓名"]
        .str.upper()
        .str.startswith("C")
    ][show_cols]

    df_nonC = df[
        ~df["姓名"]
        .str.upper()
        .str.startswith("C")
    ][show_cols]

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
# Tabs 權限
# ==================================================

role = st.session_state.role

tab_names = []

if role in ["舍監", "行政"]:

    tab_names.append("連三天不假外宿")
    tab_names.append("每天點名不到名單")

if role == "行政":

    tab_names.append("上學期門禁")
    tab_names.append("下學期門禁")

if role == "樓長":

    tab_names.append("每天點名不到名單")

tabs = st.tabs(tab_names)

# ==================================================
# 共用資料
# ==================================================

data = load_rollcall_cache()

dates = sorted(
    data.keys(),
    reverse=True
)

# ==================================================
# TAB1
# ==================================================

if "連三天不假外宿" in tab_names:

    idx = tab_names.index(
        "連三天不假外宿"
    )

    with tabs[idx]:

        st.header("連三天不假外宿")

        search = st.text_input(
            "搜尋學號 / 姓名",
            key="search_3day"
        )

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
                    .str.strip()
                    == "缺"
                ].copy()

                temp["日期"] = d

                all_d.append(temp)

            st.subheader(
                f"{g[0]} ~ {g[-1]}"
            )

            if not all_d:

                st.info(
                    f"{g[0]} ~ {g[-1]} 此三天無人連三天不假外宿"
                )

                continue

            df_all = pd.concat(all_d)

            res = (
                df_all.groupby(
                    [
                        "房號",
                        "學號",
                        "姓名"
                    ]
                )["日期"]
                .nunique()
                .reset_index()
            )

            res = res[
                res["日期"] == 3
            ]

            if search:

                res = res[
                    (
                        res["學號"]
                        .astype(str)
                        .str.contains(search)
                    )
                    |
                    (
                        res["姓名"]
                        .astype(str)
                        .str.contains(search)
                    )
                ]

            if res.empty:

                st.info(
                    f"{g[0]} ~ {g[-1]} 此三天無人連三天不假外宿"
                )

            else:

                st.dataframe(
                    res[
                        [
                            "房號",
                            "學號",
                            "姓名"
                        ]
                    ],
                    use_container_width=True
                )

# ==================================================
# TAB2
# ==================================================

if "每天點名不到名單" in tab_names:

    idx = tab_names.index(
        "每天點名不到名單"
    )

    with tabs[idx]:

        st.header("每天點名不到名單")

        search = st.text_input(
            "搜尋學號 / 姓名",
            key="search_daily"
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
                .str.strip()
                == "缺"
            ]

            if miss.empty:
                continue

            show = miss[
                [
                    "房號",
                    "學號",
                    "姓名"
                ]
            ]

            if search:

                show = show[
                    (
                        show["學號"]
                        .astype(str)
                        .str.contains(search)
                    )
                    |
                    (
                        show["姓名"]
                        .astype(str)
                        .str.contains(search)
                    )
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
                "🔥 常缺席名單"
            )

            total = pd.concat(all_miss)

            freq = (
                total.groupby(
                    [
                        "房號",
                        "學號",
                        "姓名"
                    ]
                )
                .size()
                .reset_index(
                    name="缺席次數"
                )
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
# TAB3
# ==================================================

if "上學期門禁" in tab_names:

    idx = tab_names.index(
        "上學期門禁"
    )

    with tabs[idx]:

        st.header("上學期門禁")

        f = st.file_uploader(
            "上傳上學期門禁 Excel",
            type=["xlsx"],
            key="upper"
        )

        if f:

            result, c, n = analyze_gate(
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
# TAB4
# ==================================================

if "下學期門禁" in tab_names:

    idx = tab_names.index(
        "下學期門禁"
    )

    with tabs[idx]:

        st.header("下學期門禁")

        f = st.file_uploader(
            "上傳下學期門禁 Excel",
            type=["xlsx"],
            key="lower"
        )

        if f:

            result, c, n = analyze_gate(
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
# 登出
# ==================================================

if st.button("登出"):

    st.session_state.login = False
    st.session_state.role = ""
    st.session_state.user = ""

    st.rerun()

# ==================================================
# Footer
# ==================================================

st.divider()

st.caption(
    f"最後更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)