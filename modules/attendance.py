# modules/attendance.py

import time
import streamlit as st
import pandas as pd
import gspread

from google.oauth2.service_account import Credentials
from datetime import date


# ==================================================
# Google API
# ==================================================

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["google"],
    scopes=scope
)

gc = gspread.authorize(creds)


# ==================================================
# 點名試算表
# ==================================================

ATTENDANCE_SHEETS = {

    "上學期": {

        "女一":
        "https://docs.google.com/spreadsheets/d/1U9bdg8CWASheYE7XxLt5p-otLDxKiotju4s72Car9rk/edit",

        "女二":
        "https://docs.google.com/spreadsheets/d/1jNbe--UINl7NS6dpBU82AZJuT6wQ9VwVAlglyG7infQ/edit",

        "女三":
        "https://docs.google.com/spreadsheets/d/1Vrst2-bqPE7flCIXeAI-lyN51Os9QwStx388DWx11w8/edit",

        "男一":
        "https://docs.google.com/spreadsheets/d/1S2axgu2BWP8HnEs0RJdDcccdD1bvPdH26qrx3c4DeWo/edit",

        "男三":
        "https://docs.google.com/spreadsheets/d/1RcRTslmv4s_C_7AH-WuqtLrty9l0A7YECvaGJETnpis/edit",
    },

    "下學期": {

        "女一":
        "https://docs.google.com/spreadsheets/d/1Nf7U106SxRZUu1pb35Fu2xrN2BTV80lit43BcgE6GnA/edit",

        "女二":
        "https://docs.google.com/spreadsheets/d/1NVt6M8SVc64zmRmxh268NlZqzT3JLpcGwuRBlkCe8oE/edit",

        "女三":
        "https://docs.google.com/spreadsheets/d/1y2YB118Xg2Mq8w6NeabTXgZ-n1gN56kCalyJ5KlMk1I/edit",

        "男一":
        "https://docs.google.com/spreadsheets/d/1JSJx0cLdUxfIeYoe6dldeBe3Xeewm3uuIYrJkeYi_A8/edit",

        "男三":
        "https://docs.google.com/spreadsheets/d/1KpqeWBWIR0g6RxZ_oFUFXbn34PbH7r18UI9NBsfWIPY/edit",
    }
}


# ==================================================
# 寒暑假
# ==================================================

VACATION_SHEETS = {

    "寒假": {

        "女一":
        "https://docs.google.com/spreadsheets/d/1svJOTt-BQmws2Xsy2e3mrHrsqZAi_GD1rYX4t2LxE6Y/edit",

        "女二":
        "https://docs.google.com/spreadsheets/d/17TqcEpi_6O-qsO5ZFl17GvO91yU2LgmN36sjO_Zbbi8/edit",

        "男一":
        "https://docs.google.com/spreadsheets/d/1xX2DBG8z5jGSthFdnLqsn5yhz-8JmLmTK_7VUVqHGmo/edit",
    },

    "暑假": {

        "女一":
        "https://docs.google.com/spreadsheets/d/1kxfciu8TMwnQuwzA94H0c6cY3ClgRuRijzYwM4qEtt8/edit",

        "女二":
        "https://docs.google.com/spreadsheets/d/1cXDLQM5F3lWwBlM_KRn1dhGfOviLfcJmAFiXBxp36u8/edit",

        "男一":
        "https://docs.google.com/spreadsheets/d/1WpBP8lCWUdTm-SAIIplFOGdpBjv5vLsuCXb8tDCXx9Y/edit",
    }
}


# ==================================================
# 樓層
# ==================================================

FLOOR_OPTIONS = {

    "女一": ["1F", "2F", "3F", "5F", "6F", "7F"],

    "女二": ["1F", "2F", "3F"],

    "女三": ["6F"],

    "男一": ["0F", "1F", "2F", "3F"],

    "男三": ["3F", "4F", "5F"]
}


# ==================================================
# 宿舍代碼
# ==================================================

DORM_PREFIX = {

    "女一": "81",

    "女二": "82",

    "女三": "83",

    "男一": "82",

    "男三": "83",
}


# ==================================================
# 工具
# ==================================================

def normalize_dorm(dorm):

    return str(dorm).strip().replace("ㄧ", "一")


def get_login_dorm_options():

    role = st.session_state.get("role", "")
    dorm = st.session_state.get("dorm", "")
    manage_dorms = st.session_state.get(
        "manage_dorms",
        ""
    )

    if role == "樓長":

        if manage_dorms:

            dorms = [

                normalize_dorm(d)

                for d in manage_dorms
                .replace("，", ",")
                .split(",")

                if d.strip()
            ]

        else:

            dorms = [
                normalize_dorm(dorm)
            ]

        return list(dict.fromkeys(dorms))

    return [
        "女一",
        "女二",
        "女三",
        "男一",
        "男三"
    ]


def get_dorm_gender(dorm):

    dorm = normalize_dorm(dorm)

    if dorm.startswith("女"):
        return "女生"

    if dorm.startswith("男"):
        return "男生"

    return ""


def extract_sheet_id(url):

    return (
        url
        .split("/d/")[1]
        .split("/")[0]
    )


def get_floor_sheet_name(dorm, floor):

    dorm = normalize_dorm(dorm)

    code = DORM_PREFIX[dorm]

    return f"{code}-{floor}"


def get_attendance_url(term, dorm):

    dorm = normalize_dorm(dorm)

    if term in ["上學期", "下學期"]:

        return ATTENDANCE_SHEETS[term].get(
            dorm,
            ""
        )

    if term in ["寒假", "暑假"]:

        return VACATION_SHEETS[term].get(
            dorm,
            ""
        )

    return ""


# ==================================================
# 修正重複欄位名稱
# ==================================================

def build_unique_headers(headers):

    result = []
    used = {}

    for h in headers:

        h = str(h).strip()

        if h in used:

            used[h] += 1
            h = f"{h}_{used[h]}"

        else:

            used[h] = 0

        result.append(h)

    return result


# ==================================================
# 讀取 Google Sheet（快取）
# ==================================================

@st.cache_data(ttl=300)

def load_attendance_students(
    term,
    dorm,
    floor
):

    try:

        url = get_attendance_url(
            term,
            dorm
        )

        if url == "":
            return pd.DataFrame()

        sheet_id = extract_sheet_id(url)

        # ==================================================
        # API 保護
        # ==================================================

        time.sleep(1)

        sh = gc.open_by_key(sheet_id)

        # ==================================================
        # 統一樓層 Sheet
        # ==================================================

        sheet_name = get_floor_sheet_name(
            dorm,
            floor
        )

        ws = sh.worksheet(sheet_name)

        values = ws.get_all_values(
            value_render_option="UNFORMATTED_VALUE"
        )

        if len(values) <= 1:
            return pd.DataFrame()

        # ==================================================
        # 修正重複欄位
        # ==================================================

        headers = build_unique_headers(
            values[0]
        )

        df = pd.DataFrame(
            values[1:],
            columns=headers
        )

        df.columns = (
            pd.Index(df.columns)
            .astype(str)
            .str.strip()
        )

        # ==================================================
        # 寒暑假格式
        # ==================================================

        if term in ["寒假", "暑假"]:

            room_col = None
            sid_col = None
            name_col = None

            for c in df.columns:

                c_str = str(c).strip()

                if (
                    room_col is None
                    and
                    "房號" in c_str
                ):
                    room_col = c

                if (
                    sid_col is None
                    and
                    "學號" in c_str
                ):
                    sid_col = c

                if (
                    name_col is None
                    and
                    "姓名" in c_str
                ):
                    name_col = c

            if room_col is None:
                return pd.DataFrame()

            if name_col is None:
                return pd.DataFrame()

            result = pd.DataFrame()

            result["房號"] = (
                df[room_col]
                .astype(str)
                .str.strip()
            )

            result["床位"] = ""

            if sid_col:

                result["學號"] = (
                    df[sid_col]
                    .astype(str)
                    .str.strip()
                )

            else:

                result["學號"] = ""

            result["姓名"] = (
                df[name_col]
                .astype(str)
                .str.strip()
            )

        # ==================================================
        # 上下學期格式
        # ==================================================

        else:

            room_col = None
            sid_col = None
            name_col = None

            for c in df.columns:

                c_str = str(c).strip()

                if (
                    room_col is None
                    and
                    "床位" in c_str
                ):
                    room_col = c

                if (
                    sid_col is None
                    and
                    "學號" in c_str
                    and
                    "替代" not in c_str
                ):
                    sid_col = c

                if (
                    name_col is None
                    and
                    "姓名" in c_str
                ):
                    name_col = c

            if room_col is None:
                return pd.DataFrame()

            if name_col is None:
                return pd.DataFrame()

            result = pd.DataFrame()

            result["床位"] = (
                df[room_col]
                .astype(str)
                .str.strip()
            )

            result["房號"] = (
                result["床位"]
                .astype(str)
                .str.split("-")
                .str[0]
            )

            if sid_col:

                result["學號"] = (
                    df[sid_col]
                    .astype(str)
                    .str.strip()
                )

            else:

                result["學號"] = ""

            result["姓名"] = (
                df[name_col]
                .astype(str)
                .str.strip()
            )

        # ==================================================
        # 清除空白
        # ==================================================

        result = result[
            result["姓名"] != ""
        ]

        return result[
            ["房號", "床位", "學號", "姓名"]
        ]

    except Exception as e:

        st.error(f"讀取失敗：{e}")

        return pd.DataFrame()


# ==================================================
# 主頁面
# ==================================================

def show_attendance():

    st.header("點名系統")

    term = st.selectbox(
        "點名類型",
        ["上學期", "下學期", "寒假", "暑假"],
        key="attendance_term"
    )

    dorm_options = get_login_dorm_options()

    # ==================================================
    # 寒暑假限制宿舍
    # ==================================================

    if term in ["寒假", "暑假"]:

        dorm_options = [

            d

            for d in dorm_options

            if d in VACATION_SHEETS[term]
        ]

    dorm = st.selectbox(
        "宿舍",
        dorm_options,
        key="attendance_dorm"
    )

    gender = get_dorm_gender(dorm)

    st.text_input(
        "性別",
        value=gender,
        disabled=True
    )

    floors = FLOOR_OPTIONS.get(
        dorm,
        []
    )

    floor = st.selectbox(
        "樓層",
        floors,
        key="attendance_floor"
    )

    attendance_date = st.date_input(
        "點名日期",
        value=date.today()
    )

    # ==================================================
    # 載入名單
    # ==================================================

    if st.button("載入點名名單"):

        students = load_attendance_students(
            term,
            dorm,
            floor
        )

        st.session_state[
            "attendance_students"
        ] = students

        if students.empty:

            st.warning("查無學生資料")

        else:

            st.success(
                f"成功載入 {len(students)} 筆資料"
            )

    students = st.session_state.get(
        "attendance_students",
        pd.DataFrame()
    )

    if students.empty:
        return

    st.divider()

    st.subheader("點名名單")

    final_rows = []

    for i, row in students.iterrows():

        cols = st.columns(
            [1, 1, 1, 1, 1]
        )

        cols[0].write(row["房號"])
        cols[1].write(row["學號"])
        cols[2].write(row["姓名"])

        status = cols[3].selectbox(
            "狀態",
            ["在", "缺", "請假", "未入住"],
            key=f"status_{i}"
        )

        note = cols[4].text_input(
            "備註",
            key=f"note_{i}"
        )

        final_rows.append({

            "日期": str(attendance_date),

            "宿舍": dorm,

            "樓層": floor,

            "房號": row["房號"],

            "學號": row["學號"],

            "姓名": row["姓名"],

            "狀態": status,

            "備註": note
        })

    final_df = pd.DataFrame(final_rows)

    st.divider()

    st.dataframe(
        final_df,
        use_container_width=True
    )