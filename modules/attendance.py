# modules/attendance.py

import re
import time
import streamlit as st
import pandas as pd
import gspread

from datetime import date
from functools import lru_cache
from google.oauth2.service_account import Credentials

from config import (
    UPPER_GATE_URL,
    LOWER_GATE_URL
)

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

def normalize_value(v):

    return (
        str(v)
        .strip()
        .replace(" ", "")
        .replace("-", "")
        .upper()
    )


def normalize_dorm(dorm):

    return (
        str(dorm)
        .strip()
        .replace("ㄧ", "一")
    )


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


def extract_sheet_id(url):

    return (
        url
        .split("/d/")[1]
        .split("/")[0]
    )


def get_floor_sheet_name(dorm, floor):

    code = DORM_PREFIX[dorm]

    return f"{code}-{floor}"


def get_dorm_gender(dorm):

    if dorm.startswith("女"):
        return "女生"

    return "男生"


def get_login_dorm_options():

    role = st.session_state.get("role", "")
    dorm = st.session_state.get("dorm", "")
    manage_dorms = st.session_state.get("manage_dorms", "")

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

            dorms = [normalize_dorm(dorm)]

        return list(dict.fromkeys(dorms))

    return [
        "女一",
        "女二",
        "女三",
        "男一",
        "男三"
    ]


def get_attendance_url(term, dorm):

    if term in ["上學期", "下學期"]:
        return ATTENDANCE_SHEETS[term].get(dorm, "")

    return VACATION_SHEETS[term].get(dorm, "")


def get_gate_sheet_url(term):

    if term == "上學期":
        return UPPER_GATE_URL

    return LOWER_GATE_URL


# ==================================================
# Google Sheet
# ==================================================

@lru_cache(maxsize=20)
def open_sheet(url):

    time.sleep(1)

    sheet_id = extract_sheet_id(url)

    return gc.open_by_key(sheet_id)


def read_worksheet_df(ss, sheet_name):

    try:

        ws = ss.worksheet(sheet_name)

        values = ws.get_all_values()

        if len(values) <= 1:
            return pd.DataFrame()

        header_index = 0

        for i, row in enumerate(values[:5]):

            row_text = "".join(
                [str(x) for x in row]
            )

            if (
                "學號" in row_text
                and
                (
                    "姓名" in row_text
                    or
                    "申請日期" in row_text
                )
            ):
                header_index = i
                break

        headers = build_unique_headers(
            values[header_index]
        )

        df = pd.DataFrame(
            values[header_index + 1:],
            columns=headers
        )

        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
        )

        return df

    except:
        return pd.DataFrame()


def find_col(df, keywords):

    for c in df.columns:

        c_text = str(c)

        if all(k in c_text for k in keywords):
            return c

    return None

# ==================================================
# 外宿 / 晚歸
# ==================================================

@st.cache_data(ttl=300)
def load_special_status(term, attendance_date):

    try:

        url = get_gate_sheet_url(term)

        ss = open_sheet(url)

        leave_df = read_worksheet_df(
            ss,
            "外宿申請"
        )

        late_df = read_worksheet_df(
            ss,
            "長期晚歸"
        )

        long_leave_df = read_worksheet_df(
            ss,
            "長期外宿"
        )

        target_date = pd.to_datetime(
            attendance_date
        ).date()

        outside_ids = set()
        late_ids = set()

        # ==================================================
        # 外宿申請
        # ==================================================

        if not leave_df.empty:

            sid_col = find_col(
                leave_df,
                ["學號"]
            )

            start_col = find_col(
                leave_df,
                ["申請日期"]
            )

            end_col = find_col(
                leave_df,
                ["結束日期"]
            )

            if sid_col and start_col and end_col:

                for _, row in leave_df.iterrows():

                    sid = normalize_value(
                        row.get(sid_col, "")
                    )

                    start_date = pd.to_datetime(
                        row.get(start_col, ""),
                        errors="coerce"
                    )

                    end_date = pd.to_datetime(
                        row.get(end_col, ""),
                        errors="coerce"
                    )

                    if (
                        sid
                        and
                        pd.notna(start_date)
                        and
                        pd.notna(end_date)
                    ):

                        if (
                            start_date.date()
                            <=
                            target_date
                            <=
                            end_date.date()
                        ):

                            outside_ids.add(sid)

        # ==================================================
        # 長期外宿
        # ==================================================

        if not long_leave_df.empty:

            sid_col = find_col(
                long_leave_df,
                ["學號"]
            )

            if sid_col:

                outside_ids.update(

                    long_leave_df[sid_col]
                    .astype(str)
                    .map(normalize_value)
                    .tolist()
                )

        # ==================================================
        # 長期晚歸
        # ==================================================

        if not late_df.empty:

            sid_col = find_col(
                late_df,
                ["學號"]
            )

            if sid_col:

                late_ids.update(

                    late_df[sid_col]
                    .astype(str)
                    .map(normalize_value)
                    .tolist()
                )

        return {

            "outside_ids": outside_ids,

            "late_ids": late_ids
        }

    except Exception as e:

        st.warning(
            f"讀取外宿晚歸失敗：{e}"
        )

        return {

            "outside_ids": set(),

            "late_ids": set()
        }

# ==================================================
# 載入點名名單
# ==================================================

@st.cache_data(ttl=300)
def load_attendance_students(
    term,
    dorm,
    floor
):

    url = get_attendance_url(
        term,
        dorm
    )

    if url == "":
        return pd.DataFrame()

    sh = open_sheet(url)

    # ==================================================
    # 寒暑假
    # ==================================================

    if term in ["寒假", "暑假"]:

        sheet_name = get_floor_sheet_name(
            dorm,
            floor
        )

        ws = sh.worksheet(sheet_name)

    # ==================================================
    # 上下學期
    # ==================================================

    else:

        sheet_name = get_floor_sheet_name(
            dorm,
            floor
        )

        ws = sh.worksheet(sheet_name)

    values = ws.get_all_values()

    if len(values) <= 1:
        return pd.DataFrame()

    headers = build_unique_headers(
        values[0]
    )

    df = pd.DataFrame(
        values[1:],
        columns=headers
    )

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
    )

    # ==================================================
    # 找欄位
    # ==================================================

    room_col = None
    sid_col = None
    name_col = None

    for c in df.columns:

        c_str = str(c).strip()

        if room_col is None:

            if "床位" in c_str:
                room_col = c

            elif "房號" in c_str:
                room_col = c

        if sid_col is None:

            if (
                "學號" in c_str
                and
                "替代" not in c_str
            ):
                sid_col = c

        if name_col is None:

            if "姓名" in c_str:
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

    if "-" in str(result["床位"].iloc[0]):

        result["房號"] = (
            result["床位"]
            .str.split("-")
            .str[0]
        )

    else:

        result["房號"] = result["床位"]

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

    result = result[
        result["姓名"] != ""
    ]

    return result[
        ["房號", "床位", "學號", "姓名"]
    ]

# ==================================================
# 顏色
# ==================================================

def get_student_style(student_id, special_status):

    sid = normalize_value(student_id)

    if sid in special_status["outside_ids"]:

        return """
        background-color:#ffdddd;
        color:red;
        padding:6px;
        border-radius:6px;
        font-weight:bold;
        """

    if sid in special_status["late_ids"]:

        return """
        background-color:#fff3cd;
        color:#856404;
        padding:6px;
        border-radius:6px;
        font-weight:bold;
        """

    return ""

# ==================================================
# 主畫面
# ==================================================

def show_attendance():

    st.header("點名系統")

    term = st.selectbox(
        "點名類型",
        ["上學期", "下學期", "寒假", "暑假"]
    )

    dorm_options = get_login_dorm_options()

    if term in ["寒假", "暑假"]:

        dorm_options = [

            d

            for d in dorm_options

            if d in VACATION_SHEETS[term]
        ]

    dorm = st.selectbox(
        "宿舍",
        dorm_options
    )

    gender = get_dorm_gender(dorm)

    st.text_input(
        "性別",
        value=gender,
        disabled=True
    )

    floor = st.selectbox(
        "樓層",
        FLOOR_OPTIONS[dorm]
    )

    attendance_date = st.date_input(
        "點名日期",
        value=date.today()
    )

    if st.button("載入點名名單"):

        students = load_attendance_students(
            term,
            dorm,
            floor
        )

        st.session_state[
            "attendance_students"
        ] = students

    students = st.session_state.get(
        "attendance_students",
        pd.DataFrame()
    )

    if students.empty:

        st.warning("查無學生資料")
        return

    # ==================================================
    # 外宿 / 晚歸
    # ==================================================

    special_status = load_special_status(
        term,
        attendance_date
    )

    st.divider()

    final_rows = []

    for i, row in students.iterrows():

        sid = normalize_value(
            row["學號"]
        )

        style = get_student_style(
            sid,
            special_status
        )

        cols = st.columns(
            [1, 1, 1, 1, 1]
        )

        cols[0].markdown(
            f'<div style="{style}">{row["床位"]}</div>',
            unsafe_allow_html=True
        )

        cols[1].markdown(
            f'<div style="{style}">{row["學號"]}</div>',
            unsafe_allow_html=True
        )

        cols[2].markdown(
            f'<div style="{style}">{row["姓名"]}</div>',
            unsafe_allow_html=True
        )

        default_status = "在"

        if sid in special_status["outside_ids"]:
            default_status = "缺"

        status = cols[3].selectbox(
            "狀態",
            ["在", "缺", "未入住"],
            index=["在", "缺", "未入住"].index(default_status),
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

            "床位": row["床位"],

            "學號": row["學號"],

            "姓名": row["姓名"],

            "狀態": status,

            "備註": note
        })

    st.divider()

    final_df = pd.DataFrame(
        final_rows
    )

    st.dataframe(
        final_df,
        use_container_width=True
    )