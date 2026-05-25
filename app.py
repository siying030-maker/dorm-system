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
# Session
# ==================================================

if "login" not in st.session_state:
    st.session_state.login = False

if "role" not in st.session_state:
    st.session_state.role = ""

if "user" not in st.session_state:
    st.session_state.user = ""

# ==================================================
# 新增
# ==================================================

if "dorm" not in st.session_state:
    st.session_state.dorm = ""

if "is_main" not in st.session_state:
    st.session_state.is_main = False

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

    

    role = st.selectbox(
        "登入權限",
        ["舍監", "行政", "樓長"]
    )

    # ==================================================
    # 舍監 / 行政
    # ==================================================

    if role in ["舍監", "行政"]:

        user_df = load_users(role)

        username = st.selectbox(
            "使用者",
            user_df.iloc[:, 0]
            .astype(str)
            .tolist()
        )

        password = st.text_input(
            "密碼",
            type="password"
        )

        if st.button("登入"):

            match = user_df[
                (
                    user_df.iloc[:, 0]
                    .astype(str)
                    .str.strip()
                    == username
                )
                &
                (
                    user_df.iloc[:, 1]
                    .astype(str)
                    .str.strip()
                    == password
                )
            ]

            if not match.empty:

                st.session_state.login = True
                st.session_state.role = role
                st.session_state.user = username

                # ==================================================
                # 非樓長初始化
                # ==================================================

                st.session_state.dorm = ""
                st.session_state.is_main = False

                st.rerun()

            else:

                st.error("密碼錯誤")

    # ==================================================
    # 樓長登入
    # ==================================================

    if role == "樓長":

        user_df = load_users("樓長")

        dorms = (
            user_df.iloc[:, 0]
            .astype(str)
            .unique()
            .tolist()
        )

        dorm = st.selectbox(
            "宿舍別",
            dorms
        )

        temp_df = user_df[
            user_df.iloc[:, 0]
            .astype(str)
            .str.strip()
            == dorm
        ]

        username = st.selectbox(
            "使用者",
            temp_df.iloc[:, 1]
            .astype(str)
            .tolist()
        )

        password = st.text_input(
            "密碼",
            type="password"
        )

        if st.button("登入"):

            match = temp_df[
                (
                    temp_df.iloc[:, 1]
                    .astype(str)
                    .str.strip()
                    == username
                )
                &
                (
                    temp_df.iloc[:, 2]
                    .astype(str)
                    .str.strip()
                    == password
                )
            ]

            if not match.empty:

                st.session_state.login = True
                st.session_state.role = role
                st.session_state.user = username

                # ==================================================
                # 樓長資訊
                # ==================================================

                row = match.iloc[0]

                st.session_state.dorm = str(
                    row.iloc[0]
                ).strip()

                st.session_state.is_main = (
                    str(row.iloc[3]).strip() == "是"
                )

                st.rerun()

            else:

                st.error("密碼錯誤")

    st.stop()

# ==================================================
# 登入成功
# ==================================================

st.success(f"{st.session_state.get('role','')} / {st.session_state.get('user','')}")

# ==================================================
# 登出
# ==================================================

if st.button("登出", key="logout_btn"):
    st.session_state.login = False
    st.session_state.role = ""
    st.session_state.user = ""
    st.session_state.dorm = ""
    st.session_state.is_main = False
    st.rerun()

# ==================================================
# Tab（唯一版本）
# ==================================================

tab_names = []

role = st.session_state.role
is_main = st.session_state.is_main

if role in ["舍監", "行政"]:
    tab_names += ["連三天不假外宿", "每日缺席名單"]

if role == "行政":
    tab_names += ["上學期門禁", "下學期門禁"]

if role == "樓長":
    tab_names += ["每日缺席名單"]

    if is_main:
        tab_names += ["整潔比賽"]

# 🚨 去重（保險）
tab_names = list(dict.fromkeys(tab_names))

# 🚨 沒 tab 直接停止
if len(tab_names) == 0:
    st.warning("目前沒有可用功能")
    st.stop()

# ⭐⭐⭐ 只建立一次 tabs（重點）
tabs = st.tabs(tab_names)

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
        "女一": "https://docs.google.com/spreadsheets/d/1U9bdg8CWASheYE7XxLt5p-otLDxKiotju4s72Car9rk/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1jNbe--UINl7NS6dpBU82AZJuT6wQ9VwVAlglyG7infQ/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1Vrst2-bqPE7flCIXeAI-lyN51Os9QwStx388DWx11w8/edit"
    },
    "下學期": {
        "男一": "https://docs.google.com/spreadsheets/d/1JSJx0cLdUxfIeYoe6dldeBe3Xeewm3uuIYrJkeYi_A8/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1KpqeWBWIR0g6RxZ_oFUFXbn34PbH7r18UI9NBsfWIPY/edit",
        "女一": "https://docs.google.com/spreadsheets/d/1Nf7U106SxRZUu1pb35Fu2xrN2BTV80lit43BcgE6GnA/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1NVt6M8SVc64zmRmxh268NlZqzT3JLpcGwuRBlkCe8oE/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1y2YB118Xg2Mq8w6NeabTXgZ-n1gN56kCalyJ5KlMk1I/edit"
    }
}

# ==================================================
# 樓層設定
# ==================================================

FLOOR_OPTIONS = {
    "女一": ["1F", "2F", "3F", "5F", "6F", "7F"],
    "女二": ["1F", "2F", "3F"],
    "女三": ["6F"],
    "男一": ["MB", "1F", "2F", "3F", "4F", "5F"],
    "男三": ["3F", "4F", "5F"]
}

# ==================================================
# 讀 sheet
# ==================================================

@st.cache_data(ttl=300)
def load_clean_sheet(url):
    try:
        ss = open_sheet(url)
        ws = ss.sheet1
        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

# ==================================================
# TAB：整潔比賽（穩定版）
# ==================================================

if "整潔比賽" in tab_names:

    idx = tab_names.index("整潔比賽")

    with tabs[idx]:

        st.header("整潔比賽")
        dorm = st.session_state.dorm

        st.subheader(f"宿舍：{dorm}")

        school_year = st.text_input("學年", placeholder="例如：114")
        semester = st.selectbox("學期", ["上學期", "下學期"])
        contest = st.selectbox("第幾次", ["第一次", "第二次", "第三次"])
        rank = st.selectbox("名次", ["第一名", "第二名", "第三名"])

        floors = FLOOR_OPTIONS.get(dorm, [])

        st.divider()
        st.subheader("各樓層房號")

        room_inputs = {}

        for floor in floors:
            room_inputs[floor] = st.text_input(
                f"{floor} 房號",
                key=f"clean_{dorm}_{semester}_{contest}_{rank}_{floor}"
            )

        # ==================================================
        # 查詢資料
        # ==================================================

        result_list = []

        for floor, room in room_inputs.items():

            room = str(room).strip()

            if not room:
                continue

            try:
                url = CLEAN_SHEET[semester][dorm]
                df = load_clean_sheet(url)

                if df.empty:
                    continue

                room_col = next((c for c in df.columns if "房" in c), None)
                if not room_col:
                    continue

                res = df[
                    df[room_col].astype(str).str.strip() == room
                ]

                if res.empty:
                    continue

                show_cols = [
                    c for c in df.columns
                    if ("房" in c or "學號" in c or "姓名" in c)
                ]

                temp = res[show_cols].copy()
                temp["樓層"] = floor

                result_list.append(temp)

            except Exception as e:
                st.error(f"{floor} 查詢錯誤：{e}")

        # ==================================================
        # 顯示結果
        # ==================================================

        if len(result_list) > 0:

            total = pd.concat(result_list, ignore_index=True)

            st.divider()
            st.subheader("名單確認")
            st.dataframe(total, use_container_width=True)

            # ==================================================
            # 儲存（防重複）
            # ==================================================

            if st.button("儲存", key=f"save_clean_{dorm}_{semester}_{contest}_{rank}"):

                try:

                    try:
                        ws = clean_result_ss.worksheet("整潔比賽")
                    except:
                        ws = clean_result_ss.add_worksheet(
                            title="整潔比賽",
                            rows=5000,
                            cols=20
                        )
                        ws.append_row([
                            "學年", "學期", "次數", "名次",
                            "宿舍", "樓層", "房號", "學號", "姓名"
                        ])

                    # ==================================================
                    # 🔥 防止重複寫入（關鍵修正）
                    # ==================================================

                    existing = pd.DataFrame(ws.get_all_records())

                    for _, r in total.iterrows():

                        room_value = ""
                        sid_value = ""
                        name_value = ""

                        for c in total.columns:
                            if "房" in c:
                                room_value = r[c]
                            if "學號" in c:
                                sid_value = r[c]
                            if "姓名" in c:
                                name_value = r[c]

                        # 防重複 key
                        key = f"{school_year}-{semester}-{contest}-{rank}-{dorm}-{room_value}-{sid_value}"

                        if not existing.empty:
                            if key in existing.astype(str).agg("-".join, axis=1).values:
                                continue

                        ws.append_row([
                            school_year,
                            semester,
                            contest,
                            rank,
                            dorm,
                            r["樓層"],
                            room_value,
                            sid_value,
                            name_value
                        ])

                    st.success("儲存成功（已防止重複資料）")

                except Exception as e:
                    st.error(str(e))