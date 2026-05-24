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

CACHE_TTL = 86400  # 24小時

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
# 管理者登入
# ==================================================

st.sidebar.title("管理者登入")

role = st.sidebar.selectbox(
    "選擇身分",
    [
        "舍監",
        "行政",
        "樓長"
    ]
)

# ==================================================
# 讀取 Sheet
# ==================================================

try:

    role_ws = admin_ss.worksheet(role)

    role_data = role_ws.get_all_values()

    admin_df = pd.DataFrame(
        role_data[1:],
        columns=role_data[0]
    )

    admin_df.columns = (
        admin_df.columns.str.strip()
    )

except Exception as e:

    st.error(f"{role} Sheet 讀取失敗")

    st.code(str(e))

    st.stop()

# ==================================================
# 帳號密碼欄位
# ==================================================

user_col = admin_df.columns[0]
pass_col = admin_df.columns[1]

users = (
    admin_df[user_col]
    .dropna()
    .astype(str)
    .str.strip()
    .tolist()
)

selected_user = st.sidebar.selectbox(
    "選擇使用者",
    users
)

password = st.sidebar.text_input(
    "輸入密碼",
    type="password"
)

login_btn = st.sidebar.button("登入")

# ==================================================
# Session State
# ==================================================

if "logged_in" not in st.session_state:

    st.session_state.logged_in = False

if "role" not in st.session_state:

    st.session_state.role = ""

if "user" not in st.session_state:

    st.session_state.user = ""

# ==================================================
# 登入驗證
# ==================================================

if login_btn:

    match = admin_df[
        (
            admin_df[user_col]
            .astype(str)
            .str.strip()
            == selected_user
        )
        &
        (
            admin_df[pass_col]
            .astype(str)
            .str.strip()
            == password
        )
    ]

    if not match.empty:

        st.session_state.logged_in = True
        st.session_state.role = role
        st.session_state.user = selected_user

        st.rerun()

    else:

        st.sidebar.error(
            "帳號或密碼錯誤"
        )

# ==================================================
# 未登入
# ==================================================

if not st.session_state.logged_in:

    st.info("請先登入")

    st.stop()

# ==================================================
# 登入資訊
# ==================================================

st.sidebar.success(
    f"{st.session_state.role}"
    f" / "
    f"{st.session_state.user}"
)

if st.sidebar.button("登出"):

    st.session_state.logged_in = False
    st.session_state.role = ""
    st.session_state.user = ""

    st.rerun()

# ==================================================
# 讀點名資料
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
# 讀取指定 Sheet
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
    # 00~06
    # ==================================================

    df = df[
        (df["刷卡時間"].dt.hour >= 0)
        &
        (df["刷卡時間"].dt.hour < 6)
    ]

    # ==================================================
    # 移除 LHU / Y
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
        ["姓名", "日期", "刷卡時間"]
    )

    # ==================================================
    # 時差 > 60 分鐘保留
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
    # 讀取外宿資料
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

    status = []

    weekday_map = {
        0: "一",
        1: "二",
        2: "三",
        3: "四",
        4: "五",
        5: "六",
        6: "日"
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
                (
                    leave["學號"]
                    .astype(str)
                    .str.strip()
                    == sid
                )
                &
                (
                    pd.to_datetime(
                        leave["申請日期"]
                    )
                    <= d
                )
                &
                (
                    pd.to_datetime(
                        leave["結束日期"]
                    )
                    >= d
                )
            ]

            if not m.empty:

                s = "外宿"

        # ==================================================
        # 長期外宿
        # ==================================================

        if not long_leave.empty:

            w = weekday_map[
                d.weekday()
            ]

            m = long_leave[
                (
                    long_leave["學號"]
                    .astype(str)
                    .str.strip()
                    == sid
                )
                &
                (
                    long_leave["星期"]
                    .astype(str)
                    .str.contains(w)
                )
            ]

            if not m.empty:

                s = "長期外宿"

        # ==================================================
        # 長期晚歸
        # ==================================================

        if not late.empty:

            m = late[
                late["學號"]
                .astype(str)
                .str.strip()
                == sid
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

    df["狀態"] = status

    # ==================================================
    # 白卡
    # ==================================================

    df_c = df[
        df["姓名"]
        .str.upper()
        .str.startswith("C")
    ]

    df_normal = df[
        ~df["姓名"]
        .str.upper()
        .str.startswith("C")
    ]

    # ==================================================
    # 只顯示
    # ==================================================

    show_cols = [
        "房號",
        "學號",
        "姓名"
    ]

    return (
        df[show_cols],
        df_c[show_cols],
        df_normal[show_cols]
    )

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
# 權限 Tabs
# ==================================================

role = st.session_state.role

if role == "行政":

    tab1, tab2, tab3, tab4 = st.tabs([
        "連三天不假外宿",
        "每天點名不到名單",
        "上學期門禁",
        "下學期門禁"
    ])

elif role == "舍監":

    tab1, tab2 = st.tabs([
        "連三天不假外宿",
        "每天點名不到名單"
    ])

elif role == "樓長":

    tab2 = st.tabs([
        "每天點名不到名單"
    ])[0]

# ==================================================
# TAB1
# ==================================================

if role in ["行政", "舍監"]:

    with tab1:

        st.header("連三天不假外宿")

        data = load_rollcall_cache()

        search = st.text_input(
            "搜尋學號 / 姓名",
            key="tab1_search"
        )

        dates = sorted(
            data.keys(),
            reverse=True
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

            if not all_d:

                st.info(
                    f"{g[0]} ~ {g[-1]}"
                    " 無人連三天不假外宿"
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

            st.subheader(
                f"{g[0]} ~ {g[-1]}"
            )

            if res.empty:

                st.info(
                    f"{g[0]} ~ {g[-1]}"
                    " 無人連三天不假外宿"
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

with tab2:

    st.header("每天點名不到名單")

    data = load_rollcall_cache()

    search = st.text_input(
        "搜尋學號 / 姓名",
        key="tab2_search"
    )

    dates = sorted(
        data.keys(),
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

        if show.empty:
            continue

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

if role == "行政":

    with tab3:

        st.header("上學期門禁")

        f = st.file_uploader(
            "上傳上學期門禁",
            type=["xlsx"],
            key="upper"
        )

        if f:

            _, c, n = analyze_gate(
                f,
                upper_ss
            )

            st.subheader(
                "一般刷卡資料"
            )

            st.dataframe(
                n,
                use_container_width=True
            )

            st.subheader(
                "白卡刷卡資料"
            )

            st.dataframe(
                c,
                use_container_width=True
            )

            st.download_button(
                "下載一般刷卡資料",
                to_excel(n),
                "刷卡資料.xlsx"
            )

            st.download_button(
                "下載白卡刷卡資料",
                to_excel(c),
                "白卡刷卡資料.xlsx"
            )

# ==================================================
# TAB4
# ==================================================

if role == "行政":

    with tab4:

        st.header("下學期門禁")

        f = st.file_uploader(
            "上傳下學期門禁",
            type=["xlsx"],
            key="lower"
        )

        if f:

            _, c, n = analyze_gate(
                f,
                lower_ss
            )

            st.subheader(
                "一般刷卡資料"
            )

            st.dataframe(
                n,
                use_container_width=True
            )

            st.subheader(
                "白卡刷卡資料"
            )

            st.dataframe(
                c,
                use_container_width=True
            )

            st.download_button(
                "下載一般刷卡資料",
                to_excel(n),
                "刷卡資料.xlsx"
            )

            st.download_button(
                "下載白卡刷卡資料",
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