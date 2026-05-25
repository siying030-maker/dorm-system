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

CACHE_TTL = 300

# ==================================================
# Session 初始化
# ==================================================

if "login" not in st.session_state:
    st.session_state.login = False

if "role" not in st.session_state:
    st.session_state.role = ""

if "user" not in st.session_state:
    st.session_state.user = ""

if "is_main" not in st.session_state:
    st.session_state.is_main = False

if "dorm" not in st.session_state:
    st.session_state.dorm = ""

# ==================================================
# Google API
# ==================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["google"],
    scopes=SCOPES
)

client = gspread.authorize(creds)

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
# URL
# ==================================================

ROLLCALL_SHEET_URL = "https://docs.google.com/spreadsheets/d/18cr9QP_xp1kEB8V-hWa0iSmyWbxXOneNfppwt30KqbM/edit"

UPPER_GATE_URL = "https://docs.google.com/spreadsheets/d/1Pr1fQYH35KgXMkl6igxqc-3jnZ5ufi0QgWtgp3782Lo/edit"

LOWER_GATE_URL = "https://docs.google.com/spreadsheets/d/1ivjA_-voyNAUGbvbc5o5BULu_MgU2AqbNokvQJ5dfe4/edit"

ADMIN_SHEET_URL = "https://docs.google.com/spreadsheets/d/1eZgdlelXQWcO3ZRxeXRjXNTI1g1I6RUZPGtJoC9iRes/edit"

# ==================================================
# 開啟 sheet
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

rollcall_ss = open_sheet(ROLLCALL_SHEET_URL)
upper_ss = open_sheet(UPPER_GATE_URL)
lower_ss = open_sheet(LOWER_GATE_URL)
admin_ss = open_sheet(ADMIN_SHEET_URL)

# ==================================================
# 管理帳號
# ==================================================

@st.cache_data(ttl=300)
def load_users(sheet_name):

    try:

        ws = admin_ss.worksheet(sheet_name)

        df = pd.DataFrame(ws.get_all_records())

        df.columns = df.columns.str.strip()

        return df

    except:

        return pd.DataFrame()

# ==================================================
# 登入頁面
# ==================================================

if not st.session_state.login:

    st.subheader("登入權限")

    role = st.selectbox(
        "選擇身分",
        ["舍監", "行政", "樓長"]
    )

    # ==================================================
    # 舍監 / 行政
    # ==================================================

    if role in ["舍監", "行政"]:

        df = load_users(role)

        username = st.selectbox(
            "使用者",
            df["使用者"].astype(str).tolist()
        )

        password = st.text_input(
            "密碼",
            type="password"
        )

        if st.button("登入"):

            match = df[
                (df["使用者"].astype(str) == username)
                &
                (df["密碼"].astype(str) == password)
            ]

            if not match.empty:

                st.session_state.login = True
                st.session_state.role = role
                st.session_state.user = username

                st.rerun()

            else:

                st.error("密碼錯誤")

    # ==================================================
    # 樓長
    # ==================================================

    else:

        df = load_users("樓長")

        dorm = st.selectbox(
            "宿舍別",
            sorted(df["宿舍別"].dropna().unique())
        )

        dorm_df = df[df["宿舍別"] == dorm]

        username = st.selectbox(
            "使用者",
            dorm_df["使用者"].astype(str).tolist()
        )

        password = st.text_input(
            "密碼",
            type="password"
        )

        if st.button("登入"):

            match = dorm_df[
                (dorm_df["使用者"].astype(str) == username)
                &
                (dorm_df["密碼"].astype(str) == password)
            ]

            if not match.empty:

                st.session_state.login = True
                st.session_state.role = role
                st.session_state.user = username
                st.session_state.dorm = dorm

                total = str(
                    match.iloc[0]["總樓"]
                ).strip()

                st.session_state.is_main = (
                    total == "是"
                )

                st.rerun()

            else:

                st.error("密碼錯誤")

    st.stop()

# ==================================================
# 頂部資訊
# ==================================================

top1, top2 = st.columns([8, 2])

with top1:

    st.success(
        f"{st.session_state.role} / {st.session_state.user}"
    )

with top2:

    if st.button("登出"):

        st.session_state.login = False
        st.session_state.role = ""
        st.session_state.user = ""
        st.session_state.is_main = False
        st.session_state.dorm = ""

        st.rerun()

# ==================================================
# 點名資料（每天自動同步）
# ==================================================

@st.cache_data(ttl=300)
def load_rollcall_data():

    data = {}

    worksheets = rollcall_ss.worksheets()

    for ws in worksheets:

        try:

            # 只抓日期格式 Sheet
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

            # ==================================================
            # 必須有狀態欄位
            # ==================================================

            if "狀態" not in df.columns:
                continue

            df["狀態"] = (
                df["狀態"]
                .astype(str)
                .str.strip()
            )

            # ==================================================
            # 只保留 缺 / 未入住
            # ==================================================

            df = df[
                df["狀態"]
                .isin([
                    "缺",
                    "未入住"
                ])
            ].copy()

            # ==================================================
            # 清除空姓名
            # ==================================================

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
# 載入資料
# ==================================================

data = load_rollcall_data()

# ==================================================
# 月份
# ==================================================

all_months = sorted(list(set([

    d[:7]

    for d in data.keys()

])), reverse=True)

current_month = datetime.now().strftime("%Y-%m")

default_index = 0

if current_month in all_months:

    default_index = all_months.index(current_month)

month = st.selectbox(
    "月份",
    all_months,
    index=default_index
)

# ==================================================
# 搜尋
# ==================================================

search = st.text_input(
    "搜尋學號 / 姓名"
)

# ==================================================
# 日期（新到舊）
# ==================================================

dates = sorted([

    d for d in data.keys()

    if d.startswith(month)

], reverse=True)

# ==================================================
# Tabs 權限
# ==================================================

tab_names = []

# ==================================================
# 舍監 / 行政
# ==================================================

if st.session_state.role in ["舍監", "行政"]:

    tab_names.extend([
        "連三天不假外宿",
        "每日缺席名單"
    ])

# ==================================================
# 行政
# ==================================================

if st.session_state.role == "行政":

    tab_names.extend([
        "上學期門禁",
        "下學期門禁"
    ])

# ==================================================
# 樓長
# ==================================================

if st.session_state.role == "樓長":

    tab_names.append(
        "每日缺席名單"
    )

tabs = st.tabs(tab_names)

# ==================================================
# TAB1 連三天不假外宿
# ==================================================

if "連三天不假外宿" in tab_names:

    idx = tab_names.index(
        "連三天不假外宿"
    )

    with tabs[idx]:

        st.header("連三天不假外宿")

        found = False

        for i in range(len(dates) - 2):

            group = dates[i:i+3]

            dfs = []

            for d in group:

                df = data[d].copy()

                df["日期"] = d

                dfs.append(df)

            total = pd.concat(dfs)

            # ==================================================
            # 連三天
            # ==================================================

            res = (
                total.groupby(
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

            # ==================================================
            # 搜尋
            # ==================================================

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

            # ==================================================
            # 顯示
            # ==================================================

            if not res.empty:

                found = True

                show = res[
                    [
                        "房號",
                        "學號",
                        "姓名"
                    ]
                ]

                st.subheader(
                    f"{group[0]} ~ {group[-1]}"
                )

                # ==================================================
                # 未入住紅字
                # ==================================================

                unlive_ids = []

                for d in group:

                    temp = data[d]

                    temp = temp[
                        temp["狀態"] == "未入住"
                    ]

                    unlive_ids.extend(
                        temp["學號"]
                        .astype(str)
                        .tolist()
                    )

                style_df = show.style.apply(

                    lambda row: [

                        "color:red;font-weight:bold"
                        if str(row["學號"]) in unlive_ids
                        else ""

                        for _ in row

                    ],

                    axis=1
                )

                st.dataframe(
                    style_df,
                    use_container_width=True
                )

        # ==================================================
        # 無資料
        # ==================================================

        if not found:

            st.info(
                "無連續三天不假外宿"
            )

# ==================================================
# TAB2 每日缺席名單
# ==================================================

if "每日缺席名單" in tab_names:

    idx = tab_names.index(
        "每日缺席名單"
    )

    with tabs[idx]:

        st.header("每日缺席名單")

        found = False

        for d in dates:

            df = data[d].copy()

            # ==================================================
            # 搜尋
            # ==================================================

            if search:

                df = df[

                    (
                        df["學號"]
                        .astype(str)
                        .str.contains(search)
                    )

                    |

                    (
                        df["姓名"]
                        .astype(str)
                        .str.contains(search)
                    )

                ]

            if df.empty:
                continue

            found = True

            # ==================================================
            # 顯示欄位
            # ==================================================

            show = df[
                [
                    "房號",
                    "學號",
                    "姓名"
                ]
            ]

            st.subheader(d)

            # ==================================================
            # 未入住紅字
            # ==================================================

            unlive_ids = df[
                df["狀態"] == "未入住"
            ]["學號"].astype(str).tolist()

            style_df = show.style.apply(

                lambda row: [

                    "color:red;font-weight:bold"
                    if str(row["學號"]) in unlive_ids
                    else ""

                    for _ in row

                ],

                axis=1
            )

            st.dataframe(
                style_df,
                use_container_width=True
            )

        # ==================================================
        # 無資料
        # ==================================================

        if not found:

            st.info("本月無資料")

# ==================================================
# 門禁 helper
# ==================================================

def load_sheet_df(ss, name):

    try:

        ws = ss.worksheet(name)

        return pd.DataFrame(
            ws.get_all_records()
        )

    except:

        return pd.DataFrame()

# ==================================================
# 門禁分析（完整保留）
# ==================================================

def analyze_gate(file, semester_url):

    if file is None:
        return None, None, None

    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()

    df["刷卡時間"] = pd.to_datetime(df["刷卡時間"], errors="coerce")
    df["日期"] = df["刷卡時間"].dt.date

    df = df[(df["刷卡時間"].dt.hour >= 0) & (df["刷卡時間"].dt.hour < 6)]

    df["姓名"] = df["姓名"].astype(str)
    df = df[~df["姓名"].str.upper().str.startswith(("LHU", "Y"))]

    df = df.sort_values(by=["姓名", "日期", "刷卡時間"])

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

    df = df.loc[selected].copy()

    leave = load_sheet_df(semester_url, "外宿申請")
    long_leave = load_sheet_df(semester_url, "長期外宿")
    late = load_sheet_df(semester_url, "長期晚歸")

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

        if not leave.empty:

            leave["申請日期"] = pd.to_datetime(
                leave["申請日期"],
                errors="coerce"
            )

            leave["結束日期"] = pd.to_datetime(
                leave["結束日期"],
                errors="coerce"
            )

            m = leave[
                (leave["學號"].astype(str) == sid)
                &
                (leave["申請日期"] <= d)
                &
                (leave["結束日期"] >= d)
            ]

            if not m.empty:
                s = "外宿"

        if not long_leave.empty:

            weekday = weekday_map[d.weekday()]

            m = long_leave[
                (long_leave["學號"].astype(str) == sid)
                &
                (
                    long_leave["星期"]
                    .astype(str)
                    .str.contains(weekday)
                )
            ]

            if not m.empty:
                s = "長期外宿"

        if not late.empty:

            m = late[
                late["學號"]
                .astype(str)
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

    df["狀態判斷"] = status

    show = ["房號", "學號", "姓名"]

    df_C = df[
        df["姓名"]
        .str.upper()
        .str.startswith("C")
    ][show]

    df_N = df[
        ~df["姓名"]
        .str.upper()
        .str.startswith("C")
    ][show]

    return df, df_C, df_N

# ==================================================
# Excel
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
# 上學期門禁
# ==================================================

if "上學期門禁" in tab_names:

    idx = tab_names.index("上學期門禁")

    with tabs[idx]:

        st.header("上學期門禁")

        f = st.file_uploader(
            "Excel",
            type=["xlsx"],
            key="upper_gate"
        )

        if f:

            result, c, n = analyze_gate(
                f,
                upper_ss
            )

            st.subheader("一般")

            st.dataframe(
                n,
                use_container_width=True
            )

            st.subheader("白卡")

            st.dataframe(
                c,
                use_container_width=True
            )

# ==================================================
# 下學期門禁
# ==================================================

if "下學期門禁" in tab_names:

    idx = tab_names.index("下學期門禁")

    with tabs[idx]:

        st.header("下學期門禁")

        f = st.file_uploader(
            "Excel",
            type=["xlsx"],
            key="lower_gate"
        )

        if f:

            result, c, n = analyze_gate(
                f,
                lower_ss
            )

            st.subheader("一般")

            st.dataframe(
                n,
                use_container_width=True
            )

            st.subheader("白卡")

            st.dataframe(
                c,
                use_container_width=True
            )
 # ==================================================
# 整潔比賽 Sheet URL
# ==================================================

CLEAN_SHEET = {

    "上學期": {

        "男一": "https://docs.google.com/spreadsheets/d/1S2axgu2BWP8HnEs0RJdDcccdD1bvPdH26qrx3c4DeWo/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1RcRTslmv4s_C_7AH-WuqtLrty9l0A7YECvaGJETnpis/edit",
        "女ㄧ": "https://docs.google.com/spreadsheets/d/1U9bdg8CWASheYE7XxLt5p-otLDxKiotju4s72Car9rk/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1jNbe--UINl7NS6dpBU82AZJuT6wQ9VwVAlglyG7infQ/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1Vrst2-bqPE7flCIXeAI-lyN51Os9QwStx388DWx11w8/edit"
    },

    "下學期": {

        "男一": "https://docs.google.com/spreadsheets/d/1JSJx0cLdUxfIeYoe6dldeBe3Xeewm3uuIYrJkeYi_A8/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1KpqeWBWIR0g6RxZ_oFUFXbn34PbH7r18UI9NBsfWIPY/edit",
        "女ㄧ": "https://docs.google.com/spreadsheets/d/1Nf7U106SxRZUu1pb35Fu2xrN2BTV80lit43BcgE6GnA/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1NVt6M8SVc64zmRmxh268NlZqzT3JLpcGwuRBlkCe8oE/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1y2YB118Xg2Mq8w6NeabTXgZ-n1gN56kCalyJ5KlMk1I/edit"
    }
}

# ==================================================
# Session
# ==================================================

if "clean_records" not in st.session_state:
    st.session_state.clean_records = []

# ==================================================
# 讀住宿名單
# ==================================================

@st.cache_data(ttl=300)
def load_clean_sheet(url):

    try:

        ss = open_sheet(url)

        ws = ss.sheet1

        df = pd.DataFrame(
            ws.get_all_records()
        )

        df.columns = df.columns.str.strip()

        return df

    except:

        return pd.DataFrame()

# ==================================================
# 整潔比賽（總樓）
# ==================================================

if "整潔比賽" in tab_names:

    idx = tab_names.index("整潔比賽")

    with tabs[idx]:

        st.header("整潔比賽")

        dorm = st.session_state.dorm

        semester = st.selectbox(
            "學期",
            ["上學期", "下學期"],
            key="clean_semester"
        )

        contest = st.selectbox(
            "第幾次",
            ["第一次", "第二次", "第三次"],
            key="clean_contest"
        )

        rank = st.selectbox(
            "名次",
            ["第一名", "第二名", "第三名"],
            key="clean_rank"
        )

        room = st.text_input(
            "房號",
            key="clean_room"
        )

        if room:

            try:

                url = CLEAN_SHEET[semester][dorm]

                df = load_clean_sheet(url)

                room_col = None

                for c in df.columns:

                    if "房" in c:
                        room_col = c
                        break

                if room_col:

                    res = df[
                        df[room_col]
                        .astype(str)
                        .str.strip()
                        == room.strip()
                    ]

                    if not res.empty:

                        show_cols = []

                        for c in df.columns:

                            if (
                                "房" in c or
                                "學號" in c or
                                "姓名" in c
                            ):
                                show_cols.append(c)

                        st.dataframe(
                            res[show_cols],
                            use_container_width=True
                        )

                        if st.button("送出"):

                            temp = res[show_cols].copy()

                            temp["宿舍"] = dorm
                            temp["學期"] = semester
                            temp["次數"] = contest
                            temp["名次"] = rank

                            st.session_state.clean_records.append(temp)

                            st.success("新增成功")

                    else:

                        st.warning("查無房號")

            except Exception as e:

                st.error(str(e))

# ==================================================
# 整潔比賽(檢視)
# ==================================================

if "整潔比賽(檢視)" in tab_names:

    idx = tab_names.index("整潔比賽(檢視)")

    with tabs[idx]:

        st.header("整潔比賽(檢視)")

        if len(st.session_state.clean_records) == 0:

            st.info("尚無資料")

        else:

            total = pd.concat(
                st.session_state.clean_records,
                ignore_index=True
            )

            filter_sem = st.selectbox(
                "學期",
                ["全部", "上學期", "下學期"],
                key="view_sem"
            )

            filter_contest = st.selectbox(
                "第幾次",
                ["全部", "第一次", "第二次", "第三次"],
                key="view_contest"
            )

            filter_rank = st.selectbox(
                "名次",
                ["全部", "第一名", "第二名", "第三名"],
                key="view_rank"
            )

            if filter_sem != "全部":

                total = total[
                    total["學期"]
                    == filter_sem
                ]

            if filter_contest != "全部":

                total = total[
                    total["次數"]
                    == filter_contest
                ]

            if filter_rank != "全部":

                total = total[
                    total["名次"]
                    == filter_rank
                ]

            st.dataframe(
                total,
                use_container_width=True
            )