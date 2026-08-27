import time
import streamlit as st
import pandas as pd
from datetime import date

from core.config import (
    UPPER_GATE_URL,
    LOWER_GATE_URL,
    WINTER_URL,
    SUMMER_URL,
    UNPAID_URL,
    ROLLCALL_GIRL_URL,
    ROLLCALL_BOY_URL,
    NEED_MAKEUP_GIRL_URL,
    NEED_MAKEUP_BOY_URL,
)

from core.google_api import (
    open_sheet,
    get_worksheet,
    get_all_values,
    get_worksheets,
    append_row,
    append_rows,
    add_worksheet,
    reorder_worksheets,
)


# =========================================================
# 點名 Google Sheet
# =========================================================

ATTENDANCE_SHEETS = {
    "上學期": {
        "女一": "https://docs.google.com/spreadsheets/d/1U9bdg8CWASheYE7XxLt5p-otLDxKiotju4s72Car9rk/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1jNbe--UINl7NS6dpBU82AZJuT6wQ9VwVAlglyG7infQ/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1Vrst2-bqPE7flCIXeAI-lyN51Os9QwStx388DWx11w8/edit",
        "男一": "https://docs.google.com/spreadsheets/d/1S2axgu2BWP8HnEs0RJdDcccdD1bvPdH26qrx3c4DeWo/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1RcRTslmv4s_C_7AH-WuqtLrty9l0A7YECvaGJETnpis/edit",
        "81宿_男": "https://docs.google.com/spreadsheets/d/1AXXoriPJTo7Uk-e72Oz_0NHxWQw66H414rV0RXRxe7U/edit",
    },

    "下學期": {
        "女一": "https://docs.google.com/spreadsheets/d/1Nf7U106SxRZUu1pb35Fu2xrN2BTV80lit43BcgE6GnA/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1NVt6M8SVc64zmRmxh268NlZqzT3JLpcGwuRBlkCe8oE/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1y2YB118Xg2Mq8w6NeabTXgZ-n1gN56kCalyJ5KlMk1I/edit",
        "男一": "https://docs.google.com/spreadsheets/d/1JSJx0cLdUxfIeYoe6dldeBe3Xeewm3uuIYrJkeYi_A8/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1KpqeWBWIR0g6RxZ_oFUFXbn34PbH7r18UI9NBsfWIPY/edit",
        "81宿_男": "https://docs.google.com/spreadsheets/d/10PubIXAC5-rjBUY0NGIzKN0AXSXfeKAuj_kqAo0pCZI/edit",
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


# =========================================================
# 樓層設定
# =========================================================

FLOOR_OPTIONS = {
    "女一": ["1F", "2F", "3F", "5F", "6F", "7F"],
    "女二": ["1F", "2F", "3F"],
    "女三": ["6F"],
    "男一": ["0F", "1F", "2F", "3F", "4F", "5F"],
    "男三": ["3F", "4F", "5F", "6F"],
}


# =========================================================
# 81宿_男 是獨立點名表，不需要樓層
# =========================================================

SPECIAL_NO_FLOOR_DORMS = [
    "81宿_男",
]


# =========================================================
# 宿舍前綴
# =========================================================

DORM_PREFIX = {
    "女一": "81",
    "女二": "82",
    "女三": "83",
    "男一": "82",
    "男三": "83",
}


# =========================================================
# 基本工具
# =========================================================

def normalize_dorm(value):

    return (
        str(value)
        .strip()
        .replace("ㄧ", "一")
    )


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


# =========================================================
# 判斷宿舍性別
# =========================================================

def get_dorm_gender(dorm):

    dorm = normalize_dorm(dorm)

    # 81宿_男 特別處理
    if dorm == "81宿_男":
        return "男生"

    if dorm.startswith("女"):
        return "女生"

    if dorm.startswith("男"):
        return "男生"

    return ""


# =========================================================
# 一般樓層 Sheet 名稱
# =========================================================

def get_floor_sheet_name(dorm, floor):

    dorm = normalize_dorm(dorm)

    if dorm not in DORM_PREFIX:
        return ""

    return f"{DORM_PREFIX[dorm]}-{floor}"


# =========================================================
# 取得點名 Google Sheet URL
# =========================================================

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


# =========================================================
# 外宿／門禁 Sheet
# =========================================================

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

    return term in [
        "上學期假日",
        "下學期假日"
    ]


# =========================================================
# 點名類型
# =========================================================

def get_available_terms():

    role = st.session_state.get(
        "role",
        ""
    )

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
    if st.session_state.get(
        "winter_dorms",
        ""
    ):

        return ["寒假"]

    if st.session_state.get(
        "summer_dorms",
        ""
    ):

        return ["暑假"]

    return [
        "上學期",
        "下學期",
        "上學期假日",
        "下學期假日"
    ]


# =========================================================
# 取得登入者可以管理的宿舍
# =========================================================

def get_login_dorm_options(term):

    role = st.session_state.get(
        "role",
        ""
    )

    if role in ["舍監", "行政"]:

        if term in ["寒假", "暑假"]:

            return list(
                VACATION_SHEETS[term].keys()
            )

        return [
            "女一",
            "女二",
            "女三",
            "男一",
            "男三",
            "81宿_男",
        ]

    # 寒假
    if term == "寒假":

        return [
            d
            for d in split_items(
                st.session_state.get(
                    "winter_dorms",
                    ""
                )
            )
            if d in VACATION_SHEETS["寒假"]
        ]

    # 暑假
    if term == "暑假":

        return [
            d
            for d in split_items(
                st.session_state.get(
                    "summer_dorms",
                    ""
                )
            )
            if d in VACATION_SHEETS["暑假"]
        ]

    # 樓長管理宿舍
    manage_dorms = st.session_state.get(
        "manage_dorms",
        ""
    )

    if manage_dorms:

        result = split_items(
            manage_dorms
        )

        # 保證 81宿_男 正確存在
        return result

    dorm = normalize_dorm(
        st.session_state.get(
            "dorm",
            ""
        )
    )

    return [dorm] if dorm else []


# =========================================================
# 取得樓層
# =========================================================

def get_floor_options(term, dorm):

    dorm = normalize_dorm(dorm)

    # =====================================================
    # 81宿_男 是獨立點名表
    # 完全不需要樓層
    # =====================================================

    if dorm in SPECIAL_NO_FLOOR_DORMS:

        return ["全部"]

    # =====================================================
    # 寒假、暑假女生
    # =====================================================

    if term in ["寒假", "暑假"] and dorm.startswith("女"):

        return ["全部"]

    # =====================================================
    # 寒假
    # =====================================================

    if term == "寒假":

        floors = split_floors(
            st.session_state.get(
                "winter_floors",
                ""
            )
        )

        if floors:
            return floors

    # =====================================================
    # 暑假
    # =====================================================

    if term == "暑假":

        floors = split_floors(
            st.session_state.get(
                "summer_floors",
                ""
            )
        )

        if floors:
            return floors

    # =====================================================
    # 假日
    # =====================================================

    if is_holiday_term(term):

        return ["全部"]

    # =====================================================
    # 一般宿舍
    # =====================================================

    return FLOOR_OPTIONS.get(
        dorm,
        []
    )


# =========================================================
# 取得要讀取的 Sheet
# =========================================================

def get_sheet_names_for_attendance(
    term,
    dorm,
    floor
):

    dorm = normalize_dorm(dorm)

    # =====================================================
    # 81宿_男
    #
    # 它的 Google Sheet 本身就是點名表
    # 不需要 81-1F、81-2F 之類 Sheet
    # =====================================================

    if dorm == "81宿_男":

        return ["81宿_男"]

    # =====================================================
    # 假日
    # =====================================================

    if is_holiday_term(term):

        return [
            get_floor_sheet_name(
                dorm,
                f
            )
            for f in FLOOR_OPTIONS.get(
                dorm,
                []
            )
        ]

    # =====================================================
    # 寒假、暑假女生
    # =====================================================

    if (
        term in ["寒假", "暑假"]
        and dorm.startswith("女")
    ):

        return [
            get_floor_sheet_name(
                dorm,
                f
            )
            for f in FLOOR_OPTIONS.get(
                dorm,
                []
            )
        ]

    # =====================================================
    # 一般樓層
    # =====================================================

    sheet_name = get_floor_sheet_name(
        dorm,
        floor
    )

    if sheet_name:
        return [sheet_name]

    return []


# =========================================================
# Google Sheet 欄位處理
# =========================================================

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

        row_text = "".join(
            [
                str(x)
                for x in row
            ]
        )

        if (
            "學號" in row_text
            and
            (
                "姓名" in row_text
                or "申請日期" in row_text
                or "結束日期" in row_text
            )
        ):

            return i

    return 0


def read_worksheet_df(
    ss,
    sheet_name
):

    try:

        ws = get_worksheet(
            ss,
            sheet_name
        )

        values = get_all_values(
            ws,
            value_render_option="UNFORMATTED_VALUE",
        )

        if len(values) <= 1:

            return pd.DataFrame()

        header_index = find_header_index(
            values
        )

        headers = build_unique_headers(
            values[header_index]
        )

        data = values[
            header_index + 1:
        ]

        if not data:

            return pd.DataFrame(
                columns=headers
            )

        df = pd.DataFrame(
            data,
            columns=headers,
        )

        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
        )

        return df

    except Exception as error:

        st.warning(
            f"{sheet_name} 讀取失敗：{error}"
        )

        return pd.DataFrame()


def find_col(
    df,
    keywords,
    exclude_keywords=None
):

    if exclude_keywords is None:
        exclude_keywords = []

    for k in keywords:

        for c in df.columns:

            c_str = str(c).strip()

            if (
                c_str == k
                and
                not any(
                    ex in c_str
                    for ex in exclude_keywords
                )
            ):

                return c

    for k in keywords:

        for c in df.columns:

            c_str = str(c).strip()

            if (
                k in c_str
                and
                not any(
                    ex in c_str
                    for ex in exclude_keywords
                )
            ):

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


# =========================================================
# 載入點名學生
# =========================================================

@st.cache_data(
    ttl=1800,
    show_spinner=False
)
def load_attendance_students(
    term,
    dorm,
    floor
):

    try:

        dorm = normalize_dorm(dorm)

        url = get_attendance_url(
            term,
            dorm
        )

        if url == "":

            return pd.DataFrame()

        ss = open_sheet(url)

        result_list = []

        sheet_names = (
            get_sheet_names_for_attendance(
                term,
                dorm,
                floor
            )
        )

        for sheet_name in sheet_names:

            df = read_worksheet_df(
                ss,
                sheet_name
            )

            if df.empty:

                st.warning(
                    f"{sheet_name} 暫時讀不到，正在略過"
                )

                continue

            temp = pd.DataFrame()

            # =================================================
            # 寒假、暑假
            # =================================================

            if term in ["寒假", "暑假"]:

                if len(df.columns) < 17:

                    st.warning(
                        f"{sheet_name} 欄位不足，至少需要 A~Q 欄"
                    )

                    continue

                temp["房號"] = (
                    df.iloc[:, 1]
                    .astype(str)
                    .map(normalize_value)
                )

                temp["床位"] = temp["房號"]

                temp["學號"] = (
                    df.iloc[:, 3]
                    .astype(str)
                    .map(normalize_value)
                )

                temp["班級"] = (
                    df.iloc[:, 4]
                    .astype(str)
                    .str.strip()
                )

                temp["姓名"] = (
                    df.iloc[:, 5]
                    .astype(str)
                    .str.strip()
                )

                temp["本地/境外"] = (
                    df.iloc[:, 8]
                    .astype(str)
                    .str.strip()
                )

                temp["手機"] = (
                    df.iloc[:, 9]
                    .astype(str)
                    .str.strip()
                )

                temp["家長姓名"] = (
                    df.iloc[:, 15]
                    .astype(str)
                    .str.strip()
                )

                temp["連絡電話1"] = (
                    df.iloc[:, 16]
                    .astype(str)
                    .str.strip()
                )

            # =================================================
            # 上學期、下學期、假日
            # =================================================

            else:

                if len(df.columns) < 43:

                    st.warning(
                        f"{sheet_name} 欄位不足，至少需要 A~AQ 欄"
                    )

                    continue

                temp["床位"] = (
                    df.iloc[:, 1]
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
                    df.iloc[:, 4]
                    .astype(str)
                    .map(normalize_value)
                )

                temp["班級"] = (
                    df.iloc[:, 5]
                    .astype(str)
                    .str.strip()
                )

                temp["姓名"] = (
                    df.iloc[:, 6]
                    .astype(str)
                    .str.strip()
                )

                temp["手機"] = (
                    df.iloc[:, 8]
                    .astype(str)
                    .str.strip()
                )

                temp["家長姓名"] = (
                    df.iloc[:, 14]
                    .astype(str)
                    .str.strip()
                )

                temp["連絡電話1"] = (
                    df.iloc[:, 16]
                    .astype(str)
                    .str.strip()
                )

                temp["本地/境外"] = (
                    df.iloc[:, 42]
                    .astype(str)
                    .str.strip()
                )

            # =================================================
            # 性別
            # =================================================

            temp["性別"] = (
                get_dorm_gender(dorm)
                .replace("生", "")
            )

            temp["讀取Sheet"] = sheet_name

            # =================================================
            # 假日點名只顯示境外生
            # =================================================

            if is_holiday_term(term):

                temp["本地/境外"] = (
                    temp["本地/境外"]
                    .astype(str)
                    .str.strip()
                )

                temp = temp[
                    temp["本地/境外"].isin(
                        [
                            "境外",
                            "其他",
                        ]
                    )
                ].copy()

            # =================================================
            # 過濾無效資料
            # =================================================

            temp = temp[
                (
                    temp["學號"]
                    .astype(str)
                    .str.strip()
                    != ""
                )
                &
                (
                    temp["姓名"]
                    .astype(str)
                    .str.strip()
                    != ""
                )
                &
                (
                    temp["床位"]
                    .astype(str)
                    .str.strip()
                    != ""
                )
            ].copy()

            temp = temp[
                ~temp["學號"]
                .astype(str)
                .str.upper()
                .isin(
                    [
                        "NAN",
                        "NONE",
                        "NA"
                    ]
                )
            ].copy()

            if not temp.empty:

                result_list.append(
                    temp
                )

        if result_list:

            result = pd.concat(
                result_list,
                ignore_index=True
            )

            return result[
                [
                    "學號",
                    "班級",
                    "姓名",
                    "床位",
                    "房號",
                    "本地/境外",
                    "手機",
                    "家長姓名",
                    "連絡電話1",
                    "性別",
                    "讀取Sheet"
                ]
            ]

        return pd.DataFrame()

    except Exception as e:

        st.error(
            f"讀取點名名單失敗：{e}"
        )

        return pd.DataFrame()


# =========================================================
# 未繳費名單
# =========================================================

@st.cache_data(
    ttl=300,
    show_spinner=False
)
def load_unpaid_ids():

    try:

        ss = open_sheet(
            UNPAID_URL
        )

        ws = ss.worksheet(
            "未繳費名單"
        )

        values = get_all_values(
            ws
        )

        if len(values) <= 1:
            return set()

        df = pd.DataFrame(
            values[1:],
            columns=values[0]
        )

        if len(df.columns) < 5:

            st.warning(
                "未繳費名單沒有 E 欄"
            )

            return set()

        sid_col = df.columns[4]

        ids = (
            df[sid_col]
            .astype(str)
            .map(normalize_value)
            .tolist()
        )

        return {
            x
            for x in ids
            if x != ""
        }

    except Exception as e:

        st.warning(
            f"讀取未繳費名單失敗：{e}"
        )

        return set()


# =========================================================
# 原始 Sheet
# =========================================================

def read_raw_sheet_df(
    ss,
    sheet_name
):

    try:

        ws = get_worksheet(
            ss,
            sheet_name
        )

        values = get_all_values(
            ws
        )

        if len(values) <= 2:

            return pd.DataFrame()

        headers = build_unique_headers(
            values[1]
        )

        data = values[2:]

        df = pd.DataFrame(
            data,
            columns=headers
        )

        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
        )

        return df

    except Exception as e:

        st.warning(
            f"{sheet_name} 讀取失敗：{e}"
        )

        return pd.DataFrame()


# =========================================================
# 日期
# =========================================================

def parse_sheet_date(value):

    if value is None:
        return pd.NaT

    value_str = str(value).strip()

    if value_str == "":
        return pd.NaT

    try:

        num = float(value_str)

        if 20000 <= num <= 60000:

            return (
                pd.Timestamp("1899-12-30")
                +
                pd.to_timedelta(
                    num,
                    unit="D"
                )
            )

    except:
        pass

    return pd.to_datetime(
        value_str,
        errors="coerce"
    )


# =========================================================
# 特殊狀態
# =========================================================

@st.cache_data(
    ttl=300,
    show_spinner=False
)
def load_special_status(
    term,
    attendance_date
):

    empty_result = {
        "leave_ids": set(),
        "long_leave_ids": set(),
        "late_ids": set(),
    }

    try:

        url = get_gate_sheet_url(
            term
        )

        if not url:

            st.warning(
                f"{term} 沒有設定外宿晚歸試算表"
            )

            return empty_result

        ss = open_sheet(
            url
        )

        target_date = (
            pd.to_datetime(
                attendance_date
            ).date()
        )

        leave_ids = set()
        long_leave_ids = set()
        late_ids = set()

        # =================================================
        # 外宿申請
        # =================================================

        try:

            leave_ws = get_worksheet(
                ss,
                "外宿申請"
            )

            leave_values = get_all_values(
                leave_ws,
                value_render_option="UNFORMATTED_VALUE"
            )

            for row in leave_values:

                if len(row) < 15:
                    continue

                sid = normalize_value(
                    row[2]
                )

                start_date = parse_sheet_date(
                    row[13]
                )

                end_date = parse_sheet_date(
                    row[14]
                )

                if sid == "":
                    continue

                if "學號" in sid:
                    continue

                if (
                    pd.isna(start_date)
                    or
                    pd.isna(end_date)
                ):
                    continue

                if (
                    start_date.date()
                    <= target_date
                    <= end_date.date()
                ):

                    leave_ids.add(
                        sid
                    )

        except Exception as error:

            st.warning(
                f"外宿申請讀取失敗：{error}"
            )

        # =================================================
        # 長期外宿
        # =================================================

        try:

            long_leave_ws = get_worksheet(
                ss,
                "長期外宿"
            )

            long_leave_values = get_all_values(
                long_leave_ws
            )

            for row in long_leave_values:

                if len(row) < 3:
                    continue

                sid = normalize_value(
                    row[2]
                )

                if (
                    sid
                    and
                    "學號" not in sid
                ):

                    long_leave_ids.add(
                        sid
                    )

        except Exception as error:

            st.warning(
                f"長期外宿讀取失敗：{error}"
            )

        # =================================================
        # 長期晚歸
        # =================================================

        try:

            late_ws = get_worksheet(
                ss,
                "長期晚歸"
            )

            late_values = get_all_values(
                late_ws
            )

            for row in late_values:

                if len(row) < 3:
                    continue

                sid = normalize_value(
                    row[2]
                )

                if (
                    sid
                    and
                    "學號" not in sid
                ):

                    late_ids.add(
                        sid
                    )

        except Exception as error:

            st.warning(
                f"長期晚歸讀取失敗：{error}"
            )

        return {
            "leave_ids": leave_ids,
            "long_leave_ids": long_leave_ids,
            "late_ids": late_ids,
        }

    except Exception as error:

        st.warning(
            f"讀取外宿／晚歸資料失敗：{error}"
        )

        return empty_result


# =========================================================
# 寫入 Sheet
# =========================================================

def append_rows_to_sheet(
    spreadsheet_url,
    sheet_name,
    headers,
    rows,
):

    if not rows:
        return 0

    spreadsheet = open_sheet(
        spreadsheet_url
    )

    worksheet_created = False

    try:

        worksheet = get_worksheet(
            spreadsheet,
            sheet_name
        )

    except Exception:

        worksheet = add_worksheet(
            spreadsheet,
            title=sheet_name,
            rows=max(
                3000,
                len(rows) + 100
            ),
            cols=max(
                20,
                len(headers) + 5
            ),
        )

        worksheet_created = True

    if worksheet_created:

        append_row(
            worksheet,
            headers
        )

        try:

            worksheets = get_worksheets(
                spreadsheet
            )

            new_order = [
                worksheet
            ] + [
                item
                for item in worksheets
                if item.id != worksheet.id
            ]

            reorder_worksheets(
                spreadsheet,
                new_order
            )

        except Exception as error:

            st.warning(
                "Sheet 已建立，但移到最前面失敗："
                f"{error}"
            )

    else:

        try:

            current_values = get_all_values(
                worksheet
            )

            if len(current_values) == 0:

                append_row(
                    worksheet,
                    headers
                )

        except Exception:
            pass

    append_rows(
        worksheet,
        rows
    )

    return len(rows)


# =========================================================
# 儲存點名結果
# =========================================================

def save_rollcall_result(
    attendance_date,
    dorm,
    floor,
    final_df
):

    gender = get_dorm_gender(
        dorm
    )

    if gender == "女生":

        need_makeup_url = (
            NEED_MAKEUP_GIRL_URL
        )

        rollcall_url = (
            ROLLCALL_GIRL_URL
        )

    elif gender == "男生":

        need_makeup_url = (
            NEED_MAKEUP_BOY_URL
        )

        rollcall_url = (
            ROLLCALL_BOY_URL
        )

    else:

        raise Exception(
            "無法判斷宿舍性別"
        )

    sheet_name = str(
        attendance_date
    )

    rollcall_headers = [
        "學號",
        "班級",
        "姓名",
        "床位",
        "房號",
        "本地/境外",
        "手機",
        "家長姓名",
        "連絡電話1",
        "狀態",
        "備註",
    ]

    makeup_headers = [
        "宿舍",
        "床位",
        "房號",
        "學號",
        "班級",
        "姓名",
        "狀態",
        "備註",
    ]

    absent_rollcall_rows = []
    absent_makeup_rows = []

    for _, student_row in final_df.iterrows():

        status = str(
            student_row.get(
                "狀態",
                ""
            )
        ).strip()

        if status != "缺":
            continue

        rollcall_row = [
            student_row.get("學號", ""),
            student_row.get("班級", ""),
            student_row.get("姓名", ""),
            student_row.get("床位", ""),
            student_row.get("房號", ""),
            student_row.get("本地/境外", ""),
            student_row.get("手機", ""),
            student_row.get("家長姓名", ""),
            student_row.get("連絡電話1", ""),
            status,
            student_row.get("備註", ""),
        ]

        makeup_row = [
            dorm,
            student_row.get("床位", ""),
            student_row.get("房號", ""),
            student_row.get("學號", ""),
            student_row.get("班級", ""),
            student_row.get("姓名", ""),
            status,
            student_row.get("備註", ""),
        ]

        absent_rollcall_rows.append(
            rollcall_row
        )

        absent_makeup_rows.append(
            makeup_row
        )

    if not absent_rollcall_rows:
        return 0

    append_rows_to_sheet(
        spreadsheet_url=rollcall_url,
        sheet_name=sheet_name,
        headers=rollcall_headers,
        rows=absent_rollcall_rows,
    )

    append_rows_to_sheet(
        spreadsheet_url=need_makeup_url,
        sheet_name=sheet_name,
        headers=makeup_headers,
        rows=absent_makeup_rows,
    )

    return len(
        absent_rollcall_rows
    )


# =========================================================
# 顯示文字顏色
# =========================================================

def color_text(
    text,
    color
):

    return (
        f"<span style='color:{color}; "
        f"font-weight:700'>{text}</span>"
    )


# =========================================================
# 點名主畫面
# =========================================================

def show_attendance():

    st.header("點名系統")

    # =====================================================
    # 點名類型
    # =====================================================

    term_options = get_available_terms()

    if not term_options:

        st.warning(
            "目前沒有可使用的點名類型"
        )

        return

    term = st.selectbox(
        "點名類型",
        term_options,
        key="attendance_term"
    )

    # =====================================================
    # 宿舍
    # =====================================================

    dorm_options = get_login_dorm_options(
        term
    )

    if not dorm_options:

        st.warning(
            "此點名類型沒有可用宿舍"
        )

        return

    dorm = st.selectbox(
        "宿舍",
        dorm_options,
        key="attendance_dorm"
    )

    # =====================================================
    # 性別
    # =====================================================

    gender = get_dorm_gender(
        dorm
    )

    st.text_input(
        "性別",
        value=gender,
        disabled=True,
        key="attendance_gender"
    )

    # =====================================================
    # 樓層
    # =====================================================

    floors = get_floor_options(
        term,
        dorm
    )

    if not floors:

        st.warning(
            f"{dorm} 沒有樓層設定"
        )

        return

    # =====================================================
    # 81宿_男 特別處理
    # =====================================================

    if dorm == "81宿_男":

        floor = "全部"

        st.info(
            "81宿_男：使用獨立點名表，不分樓層"
        )

    elif is_holiday_term(term):

        floor = "全部"

        st.info(
            "假日點名：不分樓層，只顯示境外生"
        )

    else:

        floor = st.selectbox(
            "樓層",
            floors,
            key="attendance_floor"
        )

    # =====================================================
    # 日期
    # =====================================================

    attendance_date = st.date_input(
        "點名日期",
        value=date.today(),
        key="attendance_date"
    )

    # =====================================================
    # 顯示目前讀取 Sheet
    # =====================================================

    sheet_names = (
        get_sheet_names_for_attendance(
            term,
            dorm,
            floor
        )
    )

    if sheet_names:

        st.info(
            "目前讀取 Sheet："
            +
            "、".join(sheet_names)
        )

    # =====================================================
    # 重新讀取
    # =====================================================

    if st.button(
        "重新讀取點名名單",
        key="refresh_attendance_students"
    ):

        load_attendance_students.clear()
        load_special_status.clear()
        load_unpaid_ids.clear()

        st.session_state.pop(
            "attendance_students",
            None
        )

        st.session_state.pop(
            "attendance_special_status",
            None
        )

        st.session_state.pop(
            "attendance_unpaid_ids",
            None
        )

        st.session_state.pop(
            "attendance_loaded_context",
            None
        )

        st.rerun()

    # =====================================================
    # 載入點名名單
    # =====================================================

    if st.button(
        "載入點名名單",
        key="load_attendance"
    ):

        loaded_students = pd.DataFrame()

        loaded_special_status = {
            "leave_ids": set(),
            "long_leave_ids": set(),
            "late_ids": set(),
        }

        loaded_unpaid_ids = set()

        try:

            with st.spinner(
                "正在載入點名名單..."
            ):

                loaded_students = (
                    load_attendance_students(
                        term,
                        dorm,
                        floor
                    )
                )

                loaded_special_status = (
                    load_special_status(
                        term,
                        attendance_date
                    )
                )

                loaded_unpaid_ids = (
                    load_unpaid_ids()
                )

            st.session_state[
                "attendance_students"
            ] = loaded_students

            st.session_state[
                "attendance_special_status"
            ] = loaded_special_status

            st.session_state[
                "attendance_unpaid_ids"
            ] = loaded_unpaid_ids

            st.session_state[
                "attendance_loaded_context"
            ] = {
                "term": term,
                "dorm": dorm,
                "floor": floor,
                "attendance_date": str(
                    attendance_date
                ),
            }

            if loaded_students.empty:

                st.warning(
                    "查無學生資料，請確認宿舍、樓層與 Sheet 名稱。"
                )

            else:

                st.success(
                    f"成功載入 {len(loaded_students)} 筆資料"
                )

        except Exception as error:

            st.session_state[
                "attendance_students"
            ] = pd.DataFrame()

            st.session_state[
                "attendance_special_status"
            ] = {
                "leave_ids": set(),
                "long_leave_ids": set(),
                "late_ids": set(),
            }

            st.session_state[
                "attendance_unpaid_ids"
            ] = set()

            st.session_state.pop(
                "attendance_loaded_context",
                None
            )

            st.error(
                f"載入點名名單失敗：{error}"
            )

    # =====================================================
    # 取得 Session
    # =====================================================

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

    unpaid_ids = st.session_state.get(
        "attendance_unpaid_ids",
        set()
    )

    loaded_context = st.session_state.get(
        "attendance_loaded_context",
        {}
    )

    # =====================================================
    # 型態確認
    # =====================================================

    if not isinstance(
        students,
        pd.DataFrame
    ):

        students = pd.DataFrame()

    if not isinstance(
        special_status,
        dict
    ):

        special_status = {
            "leave_ids": set(),
            "long_leave_ids": set(),
            "late_ids": set(),
        }

    if not isinstance(
        unpaid_ids,
        set
    ):

        unpaid_ids = set(
            unpaid_ids
        )

    # =====================================================
    # 尚未載入
    # =====================================================

    if students.empty:

        st.info(
            "請先按「載入點名名單」"
        )

        return

    # =====================================================
    # Context
    # =====================================================

    current_context = {
        "term": term,
        "dorm": dorm,
        "floor": floor,
        "attendance_date": str(
            attendance_date
        ),
    }

    if (
        loaded_context
        and
        loaded_context != current_context
    ):

        st.warning(
            "點名類型、宿舍、樓層或日期已變更，請重新載入點名名單。"
        )

        return

    # =====================================================
    # 必要欄位
    # =====================================================

    required_columns = [
        "床位",
        "學號",
        "姓名",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in students.columns
    ]

    if missing_columns:

        st.error(
            "點名資料缺少欄位："
            +
            "、".join(missing_columns)
        )

        st.write(
            "目前實際讀取欄位：",
            list(students.columns)
        )

        return

    # =====================================================
    # 清理
    # =====================================================

    students = students.copy()

    students["床位"] = (
        students["床位"]
        .astype(str)
        .map(normalize_value)
    )

    students["學號"] = (
        students["學號"]
        .astype(str)
        .map(normalize_value)
    )

    students["姓名"] = (
        students["姓名"]
        .astype(str)
        .str.strip()
    )

    students = students[
        (students["床位"] != "")
        &
        (students["學號"] != "")
        &
        (students["姓名"] != "")
    ].copy()

    students = students[
        ~students["學號"]
        .astype(str)
        .str.upper()
        .isin(
            [
                "NAN",
                "NONE",
                "NA",
            ]
        )
    ].copy()

    students = students[
        ~students["姓名"]
        .astype(str)
        .str.upper()
        .isin(
            [
                "NAN",
                "NONE",
                "NA",
            ]
        )
    ].copy()

    students = students.reset_index(
        drop=True
    )

    if students.empty:

        st.warning(
            "資料已成功讀取，但過濾後沒有有效學生資料。"
        )

        return

    # =====================================================
    # 特殊狀態
    # =====================================================

    leave_ids = special_status.get(
        "leave_ids",
        set()
    )

    long_leave_ids = special_status.get(
        "long_leave_ids",
        set()
    )

    late_ids = special_status.get(
        "late_ids",
        set()
    )

    # =====================================================
    # 點名畫面
    # =====================================================

    st.divider()

    st.subheader(
        "點名名單"
    )

    st.caption(
        "紫色：外宿申請　"
        "藍色：長期外宿　"
        "黃色：長期晚歸　"
        "紅色：未繳費"
    )

    st.success(
        f"目前顯示 {len(students)} 位學生"
    )

    final_rows = []

    # =====================================================
    # 每位學生
    # =====================================================

    for i, row in students.iterrows():

        sid = normalize_value(
            row.get(
                "學號",
                ""
            )
        )

        is_unpaid = (
            sid in unpaid_ids
        )

        is_leave = (
            sid in leave_ids
        )

        is_long_leave = (
            sid in long_leave_ids
        )

        is_late = (
            sid in late_ids
        )

        default_status = "在"

        # =================================================
        # 學生基本資料
        # =================================================

        st.subheader(
            f"{row.get('床位', '')}　"
            f"{row.get('學號', '')}　"
            f"{row.get('姓名', '')}"
        )

        # =================================================
        # 外宿
        # =================================================

        if is_leave:

            st.markdown(
                "<span style='color:#9C27B0;"
                "font-size:18px;font-weight:700;'>"
                "外宿"
                "</span>",
                unsafe_allow_html=True
            )

        # =================================================
        # 長期外宿
        # =================================================

        if is_long_leave:

            st.markdown(
                "<span style='color:#1976D2;"
                "font-size:18px;font-weight:700;'>"
                "長期外宿"
                "</span>",
                unsafe_allow_html=True
            )

        # =================================================
        # 長期晚歸
        # =================================================

        if is_late:

            st.markdown(
                "<span style='color:#C49000;"
                "font-size:18px;font-weight:700;'>"
                "長期晚歸"
                "</span>",
                unsafe_allow_html=True
            )

        # =================================================
        # 未繳費
        # =================================================

        if is_unpaid:

            st.markdown(
                "<span style='color:#D32F2F;"
                "font-size:18px;font-weight:700;'>"
                "未繳費"
                "</span>",
                unsafe_allow_html=True
            )

        # =================================================
        # 狀態
        # =================================================

        status_options = [
            "在",
            "缺",
            "未入住",
        ]

        status = st.selectbox(
            "狀態",
            status_options,
            index=status_options.index(
                default_status
            ),
            key=(
                f"attendance_status_"
                f"{term}_{dorm}_{floor}_{sid}_{i}"
            )
        )

        # =================================================
        # 備註
        # =================================================

        note = st.text_input(
            "備註",
            key=(
                f"attendance_note_"
                f"{term}_{dorm}_{floor}_{sid}_{i}"
            )
        )

        final_rows.append(
            {
                "學號": row.get(
                    "學號",
                    ""
                ),

                "班級": row.get(
                    "班級",
                    ""
                ),

                "姓名": row.get(
                    "姓名",
                    ""
                ),

                "床位": row.get(
                    "床位",
                    ""
                ),

                "房號": row.get(
                    "房號",
                    ""
                ),

                "本地/境外": row.get(
                    "本地/境外",
                    ""
                ),

                "手機": row.get(
                    "手機",
                    ""
                ),

                "家長姓名": row.get(
                    "家長姓名",
                    ""
                ),

                "連絡電話1": row.get(
                    "連絡電話1",
                    ""
                ),

                "狀態": status,

                "備註": note,
            }
        )

        st.divider()

    # =====================================================
    # DataFrame
    # =====================================================

    final_df = pd.DataFrame(
        final_rows
    )

    if final_df.empty:

        st.warning(
            "目前沒有可儲存的點名資料"
        )

        return

    # =====================================================
    # 預覽
    # =====================================================

    st.subheader(
        "點名結果預覽"
    )

    preview_columns = [
        column
        for column in [
            "床位",
            "學號",
            "班級",
            "姓名",
            "狀態",
            "備註",
        ]
        if column in final_df.columns
    ]

    st.dataframe(
        final_df[
            preview_columns
        ],
        use_container_width=True,
        hide_index=True
    )

    # =====================================================
    # 儲存
    # =====================================================

    if st.button(
        "儲存點名結果",
        key="save_attendance"
    ):

        try:

            with st.spinner(
                "正在儲存點名結果..."
            ):

                absent_count = (
                    save_rollcall_result(
                        attendance_date,
                        dorm,
                        floor,
                        final_df
                    )
                )

            if absent_count == 0:

                st.info(
                    "本次沒有狀態為「缺」的學生，不寫入試算表。"
                )

            else:

                st.success(
                    f"已成功儲存 {absent_count} 位缺席學生。"
                )

        except Exception as error:

            st.error(
                f"儲存失敗：{error}"
            )