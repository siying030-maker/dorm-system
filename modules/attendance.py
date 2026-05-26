# modules/attendance.py

import time
import streamlit as st
import pandas as pd
from datetime import date

from core.google_api import open_sheet
from core.config import (
    ROLLCALL_SHEET_URL,
    UPPER_GATE_URL,
    LOWER_GATE_URL,
)


# ==================================================
# 點名試算表
# ==================================================

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
        "男一": "https://docs.google.com/spreadsheets/d/1xX2DBG8z5jGSthFdnLqsn5yhz-8JmLmTK_7VUVqHGmo/edit",
    },
    "暑假": {
        "女一": "https://docs.google.com/spreadsheets/d/1kxfciu8TMwnQuwzA94H0c6cY3ClgRuRijzYwM4qEtt8/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1cXDLQM5F3lWwBlM_KRn1dhGfOviLfcJmAFiXBxp36u8/edit",
        "男一": "https://docs.google.com/spreadsheets/d/1WpBP8lCWUdTm-SAIIplFOGdpBjv5vLsuCXb8tDCXx9Y/edit",
    },
}


# ==================================================
# 樓層與宿舍代碼
# ==================================================

FLOOR_OPTIONS = {
    "女一": ["1F", "2F", "3F", "5F", "6F", "7F"],
    "女二": ["1F", "2F", "3F"],
    "女三": ["6F"],
    "男一": ["0F", "1F", "2F", "3F"],
    "男三": ["3F", "4F", "5F"],
}

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


def normalize_value(value):
    value = (
        str(value)
        .strip()
        .upper()
        .replace(" ", "")
    )

    if value.endswith(".0"):
        value = value[:-2]

    if value in ["NAN", "NONE", "NA"]:
        value = ""

    return value


def get_dorm_gender(dorm):
    dorm = normalize_dorm(dorm)

    if dorm.startswith("女"):
        return "女生"

    if dorm.startswith("男"):
        return "男生"

    return ""


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


def get_floor_sheet_name(dorm, floor):
    dorm = normalize_dorm(dorm)
    return f"{DORM_PREFIX[dorm]}-{floor}"


def get_attendance_url(term, dorm):
    dorm = normalize_dorm(dorm)

    if term in ["上學期", "下學期"]:
        return ATTENDANCE_SHEETS[term].get(dorm, "")

    if term in ["寒假", "暑假"]:
        return VACATION_SHEETS[term].get(dorm, "")

    return ""


def get_gate_sheet_url(term):
    if term in ["上學期", "寒假"]:
        return UPPER_GATE_URL

    return LOWER_GATE_URL


def build_unique_headers(headers):
    result = []
    used = {}

    for h in headers:
        h = str(h).strip()

        if h == "":
            h = f"欄位_{len(result)}"

        if h in used:
            used[h] += 1
            h = f"{h}_{used[h]}"
        else:
            used[h] = 0

        result.append(h)

    return result


def find_header_index(values):
    for i, row in enumerate(values[:8]):
        row_text = "".join([str(x) for x in row])

        if "學號" in row_text and (
            "姓名" in row_text
            or
            "申請日期" in row_text
            or
            "結束日期" in row_text
        ):
            return i

    return 0


def read_worksheet_df(ss, sheet_name):
    try:
        ws = ss.worksheet(sheet_name)

        values = ws.get_all_values(
            value_render_option="UNFORMATTED_VALUE"
        )

        if len(values) <= 1:
            return pd.DataFrame()

        header_index = find_header_index(values)

        headers = build_unique_headers(
            values[header_index]
        )

        data = values[header_index + 1:]

        df = pd.DataFrame(
            data,
            columns=headers
        )

        df.columns = df.columns.astype(str).str.strip()

        return df

    except:
        return pd.DataFrame()


def find_col(df, keywords, exclude_keywords=None):
    if exclude_keywords is None:
        exclude_keywords = []

    for k in keywords:
        for c in df.columns:
            c_str = str(c).strip()

            if c_str == k:
                if not any(ex in c_str for ex in exclude_keywords):
                    return c

    for k in keywords:
        for c in df.columns:
            c_str = str(c).strip()

            if k in c_str:
                if not any(ex in c_str for ex in exclude_keywords):
                    return c

    return None


# ==================================================
# 載入點名名單
# ==================================================

@st.cache_data(ttl=300)
def load_attendance_students(term, dorm, floor):
    try:
        dorm = normalize_dorm(dorm)

        url = get_attendance_url(term, dorm)

        if url == "":
            return pd.DataFrame()

        ss = open_sheet(url)

        sheet_name = get_floor_sheet_name(
            dorm,
            floor
        )

        time.sleep(0.3)

        df = read_worksheet_df(
            ss,
            sheet_name
        )

        if df.empty:
            return pd.DataFrame()

        bed_col = find_col(df, ["床位"])
        room_col = find_col(df, ["房號", "寢室"])
        sid_col = find_col(df, ["學號"], exclude_keywords=["替代"])
        name_col = find_col(df, ["姓名", "名字"])

        if name_col is None:
            return pd.DataFrame()

        result = pd.DataFrame()

        if bed_col:
            result["床位"] = (
                df[bed_col]
                .astype(str)
                .map(normalize_value)
            )

            result["房號"] = (
                result["床位"]
                .astype(str)
                .str.split("-")
                .str[0]
            )

        elif room_col:
            result["房號"] = (
                df[room_col]
                .astype(str)
                .map(normalize_value)
            )
            result["床位"] = result["房號"]

        else:
            return pd.DataFrame()

        if sid_col:
            result["學號"] = (
                df[sid_col]
                .astype(str)
                .map(normalize_value)
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

        result = result[
            result["房號"] != ""
        ]

        return result[
            [
                "房號",
                "床位",
                "學號",
                "姓名"
            ]
        ]

    except Exception as e:
        st.error(f"讀取點名名單失敗：{e}")
        return pd.DataFrame()


# ==================================================
# 載入外宿 / 晚歸資料
# 完全用學號判斷
# ==================================================

@st.cache_data(ttl=300)
def load_special_status(term, attendance_date):
    try:
        url = get_gate_sheet_url(term)
        ss = open_sheet(url)

        leave_df = read_worksheet_df(ss, "外宿申請")
        late_df = read_worksheet_df(ss, "長期晚歸")
        long_leave_df = read_worksheet_df(ss, "長期外宿")

        target_date = pd.to_datetime(attendance_date).date()

        outside_ids = set()
        late_ids = set()

        # 外宿申請
        if not leave_df.empty:
            sid_col = find_col(leave_df, ["學號"])
            start_col = find_col(leave_df, ["申請日期"])
            end_col = find_col(leave_df, ["結束日期"])

            if sid_col and start_col and end_col:
                for _, row in leave_df.iterrows():
                    sid = normalize_value(row.get(sid_col, ""))

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
                        if start_date.date() <= target_date <= end_date.date():
                            outside_ids.add(sid)

        # 長期外宿
        if not long_leave_df.empty:
            sid_col = find_col(long_leave_df, ["學號"])

            if sid_col:
                outside_ids.update(
                    long_leave_df[sid_col]
                    .astype(str)
                    .map(normalize_value)
                    .tolist()
                )

        # 長期晚歸
        if not late_df.empty:
            sid_col = find_col(late_df, ["學號"])

            if sid_col:
                late_ids.update(
                    late_df[sid_col]
                    .astype(str)
                    .map(normalize_value)
                    .tolist()
                )

        return {
            "outside_ids": {
                normalize_value(x)
                for x in outside_ids
                if normalize_value(x) != ""
            },
            "late_ids": {
                normalize_value(x)
                for x in late_ids
                if normalize_value(x) != ""
            },
        }

    except Exception as e:
        st.warning(f"讀取外宿 / 晚歸資料失敗：{e}")

        return {
            "outside_ids": set(),
            "late_ids": set(),
        }


# ==================================================
# 儲存點名結果
# ==================================================

def save_rollcall_result(attendance_date, dorm, floor, final_df):
    ss = open_sheet(ROLLCALL_SHEET_URL)
    sheet_name = str(attendance_date)

    try:
        ws = ss.worksheet(sheet_name)

    except:
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

    for _, r in final_df.iterrows():
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


def color_text(text, color):
    return f"<span style='color:{color}; font-weight:700'>{text}</span>"


# ==================================================
# 點名主畫面
# ==================================================

def show_attendance():
    st.header("點名系統")

    term = st.selectbox(
        "點名類型",
        ["上學期", "下學期", "寒假", "暑假"],
        key="attendance_term"
    )

    dorm_options = get_login_dorm_options()

    if term in ["寒假", "暑假"]:
        dorm_options = [
            d for d in dorm_options
            if d in VACATION_SHEETS[term]
        ]

    if not dorm_options:
        st.warning("此點名類型沒有可用宿舍")
        return

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
        key="attendance_gender"
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

    sheet_name = get_floor_sheet_name(
        dorm,
        floor
    )

    st.info(f"目前讀取 Sheet：{sheet_name}")

    if st.button("載入點名名單", key="load_attendance"):
        students = load_attendance_students(
            term,
            dorm,
            floor
        )

        special_status = load_special_status(
            term,
            attendance_date
        )

        st.session_state["attendance_students"] = students
        st.session_state["attendance_special_status"] = special_status

        if students.empty:
            st.warning("查無學生資料")
        else:
            st.success(f"成功載入 {len(students)} 筆資料")
            st.caption(
                f"外宿 {len(special_status['outside_ids'])} 筆，"
                f"晚歸 {len(special_status['late_ids'])} 筆"
            )

    students = st.session_state.get(
        "attendance_students",
        pd.DataFrame()
    )

    special_status = st.session_state.get(
        "attendance_special_status",
        {
            "outside_ids": set(),
            "late_ids": set(),
        }
    )

    if students.empty:
        return

    outside_ids = special_status.get("outside_ids", set())
    late_ids = special_status.get("late_ids", set())

    st.divider()
    st.subheader("點名名單")

    st.caption("紅色：外宿　黃色：晚歸")

    final_rows = []

    for i, row in students.iterrows():
        sid = normalize_value(row["學號"])

        is_outside = sid in outside_ids
        is_late = sid in late_ids

        if is_outside:
            color = "red"
            mark = "外宿"
        elif is_late:
            color = "#b58900"
            mark = "晚歸"
        else:
            color = "black"
            mark = ""

        cols = st.columns([1, 1, 1, 1, 1, 1])

        bed_show = row["床位"] if row["床位"] else row["房號"]

        cols[0].markdown(
            color_text(bed_show, color),
            unsafe_allow_html=True
        )

        cols[1].markdown(
            color_text(row["學號"], color),
            unsafe_allow_html=True
        )

        cols[2].markdown(
            color_text(row["姓名"], color),
            unsafe_allow_html=True
        )

        if mark:
            cols[3].markdown(
                color_text(mark, color),
                unsafe_allow_html=True
            )
        else:
            cols[3].write("")

        default_status = "在"

        if is_outside:
            default_status = "缺"

        status = cols[4].selectbox(
            "狀態",
            ["在", "缺", "未入住"],
            index=["在", "缺", "未入住"].index(default_status),
            key=f"attendance_status_{term}_{dorm}_{floor}_{i}"
        )

        note = cols[5].text_input(
            "備註",
            key=f"attendance_note_{term}_{dorm}_{floor}_{i}"
        )

        final_rows.append({
            "日期": str(attendance_date),
            "宿舍": dorm,
            "樓層": floor,
            "房號": row["房號"],
            "床位": row["床位"],
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

    if st.button("儲存點名結果", key="save_attendance"):
        try:
            save_rollcall_result(
                attendance_date,
                dorm,
                floor,
                final_df
            )

            st.success("點名結果已儲存")

        except Exception as e:
            st.error(f"儲存失敗：{e}")