import streamlit as st
import pandas as pd
from datetime import date

from core.google_api import open_sheet
from core.config import ROLLCALL_SHEET_URL


ATTENDANCE_SHEETS = {
    "上學期": {
        "女一": "https://docs.google.com/spreadsheets/d/1U9bdg8CWASheYE7XxLt5p-otLDxKiotju4s72Car9rk/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1jNbe--UINl7NS6dpBU82AZJuT6wQ9VwVAlglyG7infQ/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1Vrst2-bqPE7flCIXeAI-lyN51Os9QwStx388DWx11w8/edit",
        "男一": "https://docs.google.com/spreadsheets/d/1S2axgu2BWP8HnEs0RJdDcccdD1bvPdH26qrx3c4DeWo/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1RcRTslmv4s_C_7AH-WuqtLrty9l0A7YECvaGJETnpis/edit",
    },
    "下學期": {
        "女一": "https://docs.google.com/spreadsheets/d/1Nf7U106SxRZUu1pb35Fu2xrN2BTV80lit43BcgE6GnA/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1NVt6M8SVc64zmRmxh268NlZqzT3JLpcGwuRBlkCe8oE/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1y2YB118Xg2Mq8w6NeabTXgZ-n1gN56kCalyJ5KlMk1I/edit",
        "男一": "https://docs.google.com/spreadsheets/d/1JSJx0cLdUxfIeYoe6dldeBe3Xeewm3uuIYrJkeYi_A8/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1KpqeWBWIR0g6RxZ_oFUFXbn34PbH7r18UI9NBsfWIPY/edit",
    },
}

VACATION_SHEETS = {
    "寒假": {
        "女一": "https://docs.google.com/spreadsheets/d/1svJOTt-BQmws2Xsy2e3mrHrsqZAi_GD1rYX4t2LxE6Y/edit",
        "女二": "https://docs.google.com/spreadsheets/d/17TqcEpi_6O-qsO5ZFl17GvO91yU2LgmN36sjO_Zbbi8/edit",
        "女三": "https://docs.google.com/spreadsheets/d/17TqcEpi_6O-qsO5ZFl17GvO91yU2LgmN36sjO_Zbbi8/edit",
        "男一": "https://docs.google.com/spreadsheets/d/1xX2DBG8z5jGSthFdnLqsn5yhz-8JmLmTK_7VUVqHGmo/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1xX2DBG8z5jGSthFdnLqsn5yhz-8JmLmTK_7VUVqHGmo/edit",
    },
    "暑假": {
        "女一": "https://docs.google.com/spreadsheets/d/1kxfciu8TMwnQuwzA94H0c6cY3ClgRuRijzYwM4qEtt8/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1cXDLQM5F3lWwBlM_KRn1dhGfOviLfcJmAFiXBxp36u8/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1cXDLQM5F3lWwBlM_KRn1dhGfOviLfcJmAFiXBxp36u8/edit",
        "男一": "https://docs.google.com/spreadsheets/d/1WpBP8lCWUdTm-SAIIplFOGdpBjv5vLsuCXb8tDCXx9Y/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1WpBP8lCWUdTm-SAIIplFOGdpBjv5vLsuCXb8tDCXx9Y/edit",
    },
}

FLOOR_OPTIONS = {
    "女一": ["1F", "2F", "3F", "5F", "6F", "7F"],
    "女二": ["1F", "2F", "3F"],
    "女三": ["6F"],
    "男一": ["0F", "1F", "2F", "3F", "4F", "5F"],
    "男三": ["3F", "4F", "5F"],
}

DORM_PREFIX = {
    "女一": "81",
    "女二": "82",
    "女三": "83",
    "男一": "82",
    "男三": "83",
}


def normalize_dorm(dorm):
    return str(dorm).strip().replace("ㄧ", "一")


def normalize_room(value):
    value = str(value).strip()
    if value.endswith(".0"):
        value = value[:-2]
    return value


def get_dorm_gender(dorm):
    dorm = normalize_dorm(dorm)

    if dorm.startswith("女"):
        return "女生"

    if dorm.startswith("男"):
        return "男生"

    return ""


def get_floor_sheet_name(dorm, floor):
    dorm = normalize_dorm(dorm)
    return f"{DORM_PREFIX[dorm]}-{floor}"


def get_login_dorm_options():
    role = st.session_state.get("role", "")
    dorm = st.session_state.get("dorm", "")
    manage_dorms = st.session_state.get("manage_dorms", "")

    if role == "樓長":

        if manage_dorms:
            dorms = [
                normalize_dorm(d)
                for d in manage_dorms.replace("，", ",").split(",")
                if d.strip()
            ]
        else:
            dorms = [normalize_dorm(dorm)]

        return list(dict.fromkeys(dorms))

    return ["女一", "女二", "女三", "男一", "男三"]


def fix_headers(headers):
    fixed = []
    used = {}

    for i, h in enumerate(headers):
        h = str(h).strip()

        if h == "":
            h = f"欄位_{i}"

        if h in used:
            used[h] += 1
            h = f"{h}_{used[h]}"
        else:
            used[h] = 0

        fixed.append(h)

    return fixed


def find_col(df, keywords):
    columns = list(df.columns)

    for k in keywords:
        for c in columns:
            if str(c).strip() == k:
                return c

    for k in keywords:
        for c in columns:
            if k in str(c):
                return c

    return None


def find_student_id_col(df):
    columns = list(df.columns)

    for c in columns:
        if str(c).strip() == "學號":
            return c

    for c in columns:
        c_str = str(c)
        if "學號" in c_str and "正式" in c_str:
            return c

    for c in columns:
        c_str = str(c)
        if "學號" in c_str and "替代" not in c_str:
            return c

    return None


@st.cache_data(ttl=1800)
def load_floor_data(url, sheet_name):
    try:
        ss = open_sheet(url)
        ws = ss.worksheet(sheet_name)

        values = ws.get_all_values()

        if len(values) <= 1:
            return pd.DataFrame()

        headers = fix_headers(values[0])

        df = pd.DataFrame(
            values[1:],
            columns=headers
        )

        df.columns = df.columns.astype(str).str.strip()

        return df

    except Exception:
        return pd.DataFrame()


def get_attendance_url(term, dorm):
    dorm = normalize_dorm(dorm)

    if term in ["上學期", "下學期"]:
        return ATTENDANCE_SHEETS[term][dorm]

    if term in ["寒假", "暑假"]:
        return VACATION_SHEETS[term][dorm]

    return ""


def load_attendance_students(term, dorm, floor):
    dorm = normalize_dorm(dorm)

    url = get_attendance_url(term, dorm)

    if url == "":
        return pd.DataFrame()

    sheet_name = get_floor_sheet_name(dorm, floor)

    df = load_floor_data(url, sheet_name)

    if df.empty:
        return pd.DataFrame()

    bed_col = find_col(df, ["床位"])
    sid_col = find_student_id_col(df)
    name_col = find_col(df, ["姓名", "名字"])

    if bed_col is None or name_col is None:
        return pd.DataFrame()

    result = pd.DataFrame()

    result["床位"] = df[bed_col].apply(normalize_room)
    result["房號"] = result["床位"].astype(str).str.split("-").str[0]

    if sid_col:
        result["學號"] = df[sid_col].astype(str)
    else:
        result["學號"] = ""

    result["姓名"] = df[name_col].astype(str)

    result = result[
        result["姓名"].astype(str).str.strip() != ""
    ]

    return result[["房號", "床位", "學號", "姓名"]]


def save_rollcall(attendance_date, dorm, floor, data):
    ss = open_sheet(ROLLCALL_SHEET_URL)

    sheet_name = str(attendance_date)

    try:
        ws = ss.worksheet(sheet_name)
    except Exception:
        ws = ss.add_worksheet(
            title=sheet_name,
            rows=3000,
            cols=20
        )

        ws.append_row([
            "日期",
            "宿舍",
            "樓層",
            "房號",
            "床位",
            "學號",
            "姓名",
            "狀態",
            "備註"
        ])

    rows = []

    for _, r in data.iterrows():
        rows.append([
            str(attendance_date),
            dorm,
            floor,
            r.get("房號", ""),
            r.get("床位", ""),
            r.get("學號", ""),
            r.get("姓名", ""),
            r.get("狀態", ""),
            r.get("備註", "")
        ])

    if rows:
        ws.append_rows(rows)


def show_attendance():

    st.header("點名系統")

    term = st.selectbox(
        "點名類型",
        ["上學期", "下學期", "寒假", "暑假"],
        key="attendance_term"
    )

    dorm_options = get_login_dorm_options()

    dorm = st.selectbox(
        "宿舍",
        dorm_options,
        key="attendance_dorm"
    )

    gender = get_dorm_gender(dorm)

    st.text_input(
        "性別",
        value=gender,
        disabled=True,
        key="attendance_gender_show"
    )

    floors = FLOOR_OPTIONS.get(dorm, [])

    floor = st.selectbox(
        "樓層",
        floors,
        key="attendance_floor"
    )

    attendance_date = st.date_input(
        "點名日期",
        value=date.today(),
        key="attendance_date"
    )

    sheet_name = get_floor_sheet_name(dorm, floor)

    st.info(f"將讀取 Sheet：{sheet_name}")

    if st.button("載入點名名單", key="load_attendance"):

        students = load_attendance_students(
            term,
            dorm,
            floor
        )

        st.session_state.attendance_students = students

        if students.empty:
            st.warning("查無學生資料，請確認試算表網址與 Sheet 名稱")
        else:
            st.success("載入成功")

    students = st.session_state.get(
        "attendance_students",
        pd.DataFrame()
    )

    if students.empty:
        return

    st.divider()
    st.subheader("點名名單")

    records = []

    for i, r in students.iterrows():

        cols = st.columns([1, 1, 1, 1, 1, 2])

        cols[0].write(r["房號"])
        cols[1].write(r["床位"])
        cols[2].write(r["學號"])
        cols[3].write(r["姓名"])

        status = cols[4].selectbox(
            "狀態",
            ["在", "缺", "請假", "未入住"],
            key=f"attendance_status_{i}"
        )

        note = cols[5].text_input(
            "備註",
            key=f"attendance_note_{i}"
        )

        records.append({
            "房號": r["房號"],
            "床位": r["床位"],
            "學號": r["學號"],
            "姓名": r["姓名"],
            "狀態": status,
            "備註": note
        })

    final_df = pd.DataFrame(records)

    st.divider()

    if st.button("儲存點名結果", key="save_attendance"):

        save_rollcall(
            attendance_date,
            dorm,
            floor,
            final_df
        )

        st.success("點名結果已儲存")