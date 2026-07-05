import time
import streamlit as st
import pandas as pd
from datetime import date

from core.google_api import open_sheet
from core.config import (
    UPPER_GATE_URL,
    LOWER_GATE_URL,
    WINTER_URL,
    SUMMER_URL,
    ROLLCALL_GIRL_URL,
    ROLLCALL_BOY_URL,
    NEED_MAKEUP_GIRL_URL,
    NEED_MAKEUP_BOY_URL,
)


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
        "女三": "https://docs.google.com/spreadsheets/d/17NJosTQ7PkrbcR6hCAcrRjELePnR5rXOnt_PRzBeO1Y/edit",
        "男一": "https://docs.google.com/spreadsheets/d/1xX2DBG8z5jGSthFdnLqsn5yhz-8JmLmTK_7VUVqHGmo/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1qqeVWUJBKls2LNRoEdOygHI8eYem6ysR8RFnRH3LRfI/edit",
    },
    "暑假": {
        "女一": "https://docs.google.com/spreadsheets/d/1kxfciu8TMwnQuwzA94H0c6cY3ClgRuRijzYwM4qEtt8/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1cXDLQM5F3lWwBlM_KRn1dhGfOviLfcJmAFiXBxp36u8/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1GcAoyLguL5huFcr_2X2Z2W9JGveWve9xNKKjnokZtek/edit",
        "男一": "https://docs.google.com/spreadsheets/d/1WpBP8lCWUdTm-SAIIplFOGdpBjv5vLsuCXb8tDCXx9Y/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1LklZ35ePTbI8fbec3VBDmuUwZJaaezWgbahSQocK4a8/edit",
    },
}

FLOOR_OPTIONS = {
    "女一": ["1F", "2F", "3F", "5F", "6F", "7F"],
    "女二": ["1F", "2F", "3F"],
    "女三": ["6F"],
    "男一": ["0F", "1F", "2F", "3F","4F","5F"],
    "男三": ["3F", "4F", "5F"],
}

DORM_PREFIX = {
    "女一": "81",
    "女二": "82",
    "女三": "83",
    "男一": "82",
    "男三": "83",
}


def normalize_dorm(value):
    return str(value).strip().replace("ㄧ", "一")


def normalize_value(value):
    value = str(value).strip().upper().replace(" ", "")

    if value.endswith(".0"):
        value = value[:-2]

    if value in ["NAN", "NONE", "NA"]:
        value = ""

    return value


def split_items(value):
    result = []

    for item in str(value).replace("，", ",").split(","):
        item = normalize_dorm(item)

        if item:
            result.append(item)

    return list(dict.fromkeys(result))


def split_floors(value):
    result = []

    for item in str(value).replace("，", ",").split(","):
        item = item.strip().upper()

        if item:
            result.append(item)

    return list(dict.fromkeys(result))


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


def get_attendance_url(term, dorm):

    dorm = normalize_dorm(dorm)

    if term in ["上學期", "上學期假日"]:
        return ATTENDANCE_SHEETS["上學期"].get(dorm, "")

    if term in ["下學期", "下學期假日"]:
        return ATTENDANCE_SHEETS["下學期"].get(dorm, "")

    if term == "寒假":
        return VACATION_SHEETS["寒假"].get(dorm, "")

    if term == "暑假":
        return VACATION_SHEETS["暑假"].get(dorm, "")

    return ""


def get_gate_sheet_url(term):

    if term in ["上學期", "上學期假日"]:
        return UPPER_GATE_URL

    if term in ["下學期", "下學期假日"]:
        return LOWER_GATE_URL

    if term == "寒假":
        return WINTER_URL

    if term == "暑假":
        return SUMMER_URL

    return LOWER_GATE_URL

def is_holiday_term(term):
    return term in ["上學期假日", "下學期假日"]

def get_available_terms():

    role = st.session_state.get("role", "")

    if role in ["舍監", "行政"]:
        return [
            "上學期",
            "下學期",
            "上學期假日",
            "下學期假日",
            "寒假",
            "暑假"
        ]

    # 樓長
    if st.session_state.get("winter_dorms", ""):
        return ["寒假"]

    if st.session_state.get("summer_dorms", ""):
        return ["暑假"]

    return [
        "上學期",
        "下學期",
        "上學期假日",
        "下學期假日"
    ]

def get_login_dorm_options(term):
    role = st.session_state.get("role", "")

    if role in ["舍監", "行政"]:
        if term in ["寒假", "暑假"]:
            return list(VACATION_SHEETS[term].keys())

        return ["女一", "女二", "女三", "男一", "男三"]

    if term == "寒假":
        return [
            d for d in split_items(st.session_state.get("winter_dorms", ""))
            if d in VACATION_SHEETS["寒假"]
        ]

    if term == "暑假":
        return [
            d for d in split_items(st.session_state.get("summer_dorms", ""))
            if d in VACATION_SHEETS["暑假"]
        ]

    manage_dorms = st.session_state.get("manage_dorms", "")

    if manage_dorms:
        return split_items(manage_dorms)

    dorm = normalize_dorm(st.session_state.get("dorm", ""))
    return [dorm] if dorm else []


def get_floor_options(term, dorm):
    dorm = normalize_dorm(dorm)

   
    if term in ["寒假", "暑假"] and dorm.startswith("女"):
        return ["全部"]

    if term == "寒假":
        floors = split_floors(st.session_state.get("winter_floors", ""))
        if floors:
            return floors

    if term == "暑假":
        floors = split_floors(st.session_state.get("summer_floors", ""))
        if floors:
            return floors
    
    if is_holiday_term(term):
        return ["全部"]

    return FLOOR_OPTIONS.get(dorm, [])


def get_sheet_names_for_attendance(term, dorm, floor):
    dorm = normalize_dorm(dorm)

    if is_holiday_term(term):
        return [
            get_floor_sheet_name(dorm, f)
            for f in FLOOR_OPTIONS.get(dorm, [])
        ]

    if term in ["寒假", "暑假"] and dorm.startswith("女"):
        return [
            get_floor_sheet_name(dorm, f)
            for f in FLOOR_OPTIONS.get(dorm, [])
        ]

    return [get_floor_sheet_name(dorm, floor)]


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
            or "申請日期" in row_text
            or "結束日期" in row_text
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
        headers = build_unique_headers(values[header_index])
        data = values[header_index + 1:]

        df = pd.DataFrame(data, columns=headers)
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

            if c_str == k and not any(ex in c_str for ex in exclude_keywords):
                return c

    for k in keywords:
        for c in df.columns:
            c_str = str(c).strip()

            if k in c_str and not any(ex in c_str for ex in exclude_keywords):
                return c

    return None
def get_overseas_col(df):

    col = find_col(
        df,
        [
            "本地/境外",
            "本地境外",
            "原始資料備註"
        ]
    )

    if col:
        return col

    if len(df.columns) >= 43:
        return df.columns[42]

    return None


@st.cache_data(ttl=300)
def load_attendance_students(term, dorm, floor):
    try:
        dorm = normalize_dorm(dorm)
        url = get_attendance_url(term, dorm)

        if url == "":
            return pd.DataFrame()

        ss = open_sheet(url)
        result_list = []

        sheet_names = get_sheet_names_for_attendance(term, dorm, floor)

        for sheet_name in sheet_names:
            time.sleep(0.2)

            df = read_worksheet_df(ss, sheet_name)

            if df.empty:
                continue

            if len(df.columns) < 6:
                continue

            # 固定欄位：
            # B欄 = 床位，例如 82113-1
            # D欄 = 學號
            # F欄 = 姓名
            bed_col = df.columns[1]
            sid_col = df.columns[3]
            name_col = df.columns[5]

            temp = pd.DataFrame()

            temp["床位"] = (
                df[bed_col]
                .astype(str)
                .map(normalize_value)
            )

            temp["房號"] = (
                temp["床位"]
                .astype(str)
                .str.split("-")
                .str[0]
            )

            temp["學號"] = (
                df[sid_col]
                .astype(str)
                .map(normalize_value)
            )

            temp["姓名"] = (
                df[name_col]
                .astype(str)
                .str.strip()
            )
            if is_holiday_term(term):

                overseas_col = get_overseas_col(df)

                if overseas_col is None:
                    continue

                temp["本地境外"] = (
                    df[overseas_col]
                    .astype(str)
                    .str.strip()
                )

                temp = temp[
                    temp["本地境外"]
                    .astype(str)
                    .str.contains("境外", na=False)
                ].copy()

            temp["性別"] = get_dorm_gender(dorm).replace("生", "")
            temp["讀取Sheet"] = sheet_name

            temp = temp[
                (temp["床位"].astype(str).str.strip() != "")
                &
                (temp["房號"].astype(str).str.strip() != "")
                &
                (temp["學號"].astype(str).str.strip() != "")
                &
                (temp["姓名"].astype(str).str.strip() != "")
            ].copy()

            temp = temp[
                ~temp["學號"].astype(str).str.upper().isin(
                    ["NAN", "NONE", "NA"]
                )
            ].copy()

            temp = temp[
                ~temp["姓名"].astype(str).str.upper().isin(
                    ["NAN", "NONE", "NA"]
                )
            ].copy()

            if not temp.empty:
                result_list.append(temp)

        if result_list:
            result = pd.concat(
                result_list,
                ignore_index=True
            )

            return result[
    [
        c for c in [
            "房號",
            "床位",
            "學號",
            "姓名",
            "性別",
            "本地境外",
            "讀取Sheet"
        ]
        if c in result.columns
    ]
]

        return pd.DataFrame()

    except Exception as e:
        st.error(f"讀取點名名單失敗：{e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_special_status(term, attendance_date):
    try:
        url = get_gate_sheet_url(term)
        ss = open_sheet(url)

        leave_df = read_worksheet_df(ss, "外宿申請")
        late_df = read_worksheet_df(ss, "長期晚歸")
        long_leave_df = read_worksheet_df(ss, "長期外宿")

        target_date = pd.to_datetime(attendance_date).date()

        leave_ids = set()
        late_ids = set()
        long_leave_ids = set()

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

                    if sid and pd.notna(start_date) and pd.notna(end_date):
                        if start_date.date() <= target_date <= end_date.date():
                            leave_ids.add(sid)

        if not long_leave_df.empty:
            sid_col = find_col(long_leave_df, ["學號"])

            if sid_col:
                long_leave_ids.update(
                    long_leave_df[sid_col]
                    .astype(str)
                    .map(normalize_value)
                    .tolist()
                )

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
            "leave_ids": {
                normalize_value(x)
                for x in leave_ids
                if normalize_value(x) != ""
            },
            "long_leave_ids": {
                normalize_value(x)
                for x in long_leave_ids
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
            "leave_ids": set(),
            "long_leave_ids": set(),
            "late_ids": set(),
        }


def append_rows_to_sheet(url, sheet_name, headers, rows):

    ss = open_sheet(url)

    try:
        ws = ss.worksheet(sheet_name)

    except:

        ws = ss.add_worksheet(
            title=sheet_name,
            rows=3000,
            cols=len(headers) + 5
        )

        ws.append_row(headers)

        # 新增的 Sheet 移到最前面
        worksheets = ss.worksheets()

        new_order = [ws] + [
            w for w in worksheets
            if w.id != ws.id
        ]

        ss.reorder_worksheets(new_order)

    if rows:
        ws.append_rows(rows)

def save_rollcall_result(attendance_date, dorm, floor, final_df):
    gender = get_dorm_gender(dorm)

    if gender == "女生":
        need_makeup_url = NEED_MAKEUP_GIRL_URL
        rollcall_url = ROLLCALL_GIRL_URL

    elif gender == "男生":
        need_makeup_url = NEED_MAKEUP_BOY_URL
        rollcall_url = ROLLCALL_BOY_URL

    else:
        raise Exception("無法判斷宿舍性別")

    sheet_name = str(attendance_date)

    headers = [
        "日期",
        "性別",
        "宿舍",
        "樓層",
        "房號",
        "床位",
        "學號",
        "姓名",
        "狀態",
        "備註"
    ]

    all_rows = []
    absent_rows = []

    for _, r in final_df.iterrows():
        status = str(r.get("狀態", "")).strip()

        row_data = [
            str(attendance_date),
            r.get("性別", gender.replace("生", "")),
            dorm,
            floor,
            r.get("房號", ""),
            r.get("床位", ""),
            r.get("學號", ""),
            r.get("姓名", ""),
            status,
            r.get("備註", "")
        ]

        all_rows.append(row_data)

        if status == "缺":
            absent_rows.append(row_data)

    append_rows_to_sheet(
        need_makeup_url,
        sheet_name,
        headers,
        all_rows
    )

    append_rows_to_sheet(
        rollcall_url,
        sheet_name,
        headers,
        absent_rows
    )


def color_text(text, color):
    return f"<span style='color:{color}; font-weight:700'>{text}</span>"


def show_attendance():

    st.header("點名系統")

    term_options = get_available_terms()

    term = st.selectbox(
        "點名類型",
        term_options,
        key="attendance_term"
    )

    dorm_options = get_login_dorm_options(term)

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

    floors = get_floor_options(term, dorm)

    if not floors:
        st.warning("此宿舍沒有樓層設定")
        return

    if is_holiday_term(term):
        floor = "全部"
        st.info("假日點名：不分樓層，只顯示境外生")
    else:
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

    sheet_names = get_sheet_names_for_attendance(
        term,
        dorm,
        floor
    )

    st.info("目前讀取 Sheet：" + "、".join(sheet_names))

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

    students = st.session_state.get(
        "attendance_students",
        pd.DataFrame()
    )

    special_status = st.session_state.get(
        "attendance_special_status",
        {
            "leave_ids": set(),
            "long_leave_ids": set(),
            "late_ids": set(),
        }
    )

    if students.empty:
        return

    # 再保險過濾一次，避免畫面顯示只有床位、沒有學號姓名的空白列
    students = students[
        (students["學號"].astype(str).str.strip() != "")
        &
        (students["姓名"].astype(str).str.strip() != "")
    ].copy()

    if students.empty:
        st.warning("查無有效學生資料")
        return

    leave_ids = special_status.get("leave_ids", set())
    long_leave_ids = special_status.get("long_leave_ids", set())
    late_ids = special_status.get("late_ids", set())

    st.divider()
    st.subheader("點名名單")
    st.caption("紅色：外宿申請　藍色：長期外宿　黃色：長期晚歸")

    final_rows = []

    for i, row in students.iterrows():

        sid = normalize_value(row["學號"])

        if sid in leave_ids:
            color = "red"
            mark = "外宿申請"
            default_status = "缺"

        elif sid in long_leave_ids:
            color = "blue"
            mark = "長期外宿"
            default_status = "缺"

        elif sid in late_ids:
            color = "#b58900"
            mark = "長期晚歸"
            default_status = "在"

        else:
            color = "black"
            mark = ""
            default_status = "在"

    st.markdown(
        f"""
        <div style="font-size:18px;font-weight:700;margin-bottom:6px;">
            {color_text(row["床位"], color)}
            &nbsp;&nbsp;
            {color_text(row["學號"], color)}
            &nbsp;&nbsp;
            {color_text(row["姓名"], color)}
    </div>
    """,
    unsafe_allow_html=True
)

    status = st.selectbox(
        "狀態",
        ["在", "缺", "未入住"],
        index=["在", "缺", "未入住"].index(default_status),
        key=f"attendance_status_{term}_{dorm}_{floor}_{i}"
)

    note = st.text_input(
        "備註",
        key=f"attendance_note_{term}_{dorm}_{floor}_{i}"
)

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

            
