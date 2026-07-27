import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from core.google_api import (
    open_sheet,
    get_worksheet,
    get_worksheets,
    get_all_values,
    get_values,
    append_row,
    append_rows,
    add_worksheet,
)


# ==================================================
# 宿舍住宿名單試算表
# ==================================================

CLEAN_SHEET = {
    "上學期": {
        "男一": (
            "https://docs.google.com/spreadsheets/d/"
            "1S2axgu2BWP8HnEs0RJdDcccdD1bvPdH26qrx3c4DeWo/edit"
        ),
        "男三": (
            "https://docs.google.com/spreadsheets/d/"
            "1RcRTslmv4s_C_7AH-WuqtLrty9l0A7YECvaGJETnpis/edit"
        ),
        "女一": (
            "https://docs.google.com/spreadsheets/d/"
            "1U9bdg8CWASheYE7XxLt5p-otLDxKiotju4s72Car9rk/edit"
        ),
        "女二": (
            "https://docs.google.com/spreadsheets/d/"
            "1jNbe--UINl7NS6dpBU82AZJuT6wQ9VwVAlglyG7infQ/edit"
        ),
        "女三": (
            "https://docs.google.com/spreadsheets/d/"
            "1Vrst2-bqPE7flCIXeAI-lyN51Os9QwStx388DWx11w8/edit"
        ),
    },
    "下學期": {
        "男一": (
            "https://docs.google.com/spreadsheets/d/"
            "1JSJx0cLdUxfIeYoe6dldeBe3Xeewm3uuIYrJkeYi_A8/edit"
        ),
        "男三": (
            "https://docs.google.com/spreadsheets/d/"
            "1KpqeWBWIR0g6RxZ_oFUFXbn34PbH7r18UI9NBsfWIPY/edit"
        ),
        "女一": (
            "https://docs.google.com/spreadsheets/d/"
            "1Nf7U106SxRZUu1pb35Fu2xrN2BTV80lit43BcgE6GnA/edit"
        ),
        "女二": (
            "https://docs.google.com/spreadsheets/d/"
            "1NVt6M8SVc64zmRmxh268NlZqzT3JLpcGwuRBlkCe8oE/edit"
        ),
        "女三": (
            "https://docs.google.com/spreadsheets/d/"
            "1y2YB118Xg2Mq8w6NeabTXgZ-n1gN56kCalyJ5KlMk1I/edit"
        ),
    },
}


# ==================================================
# 整潔比賽結果試算表
# ==================================================

CLEAN_RESULT_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1ojWln4x5MGTqZZfGe3ySbd8-g6FwTsMff2tonx5tCRc/edit"
)


# ==================================================
# 宿舍樓層
# ==================================================

FLOOR_OPTIONS = {
    "女一": [
        "1F",
        "2F",
        "3F",
        "5F",
        "6F",
        "7F",
    ],
    "女二": [
        "1F",
        "2F",
        "3F",
    ],
    "女三": [
        "6F",
    ],
    "男一": [
        "0F",
        "1F",
        "2F",
        "3F",
        "4F",
        "5F",
    ],
    "男三": [
        "3F",
        "4F",
        "5F",
    ],
}


# ==================================================
# 宿舍 Sheet 前綴
# ==================================================

DORM_PREFIX = {
    "女一": "81",
    "女二": "82",
    "女三": "83",
    "男一": "82",
    "男三": "83",
}


# ==================================================
# 基本正規化
# ==================================================

def normalize_dorm(dorm):
    return (
        str(dorm)
        .strip()
        .replace("ㄧ", "一")
    )


def normalize_room(value):
    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    if value.upper() in [
        "NAN",
        "NONE",
        "NA",
    ]:
        value = ""

    return value


def normalize_value(value):
    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    if value.upper() in [
        "NAN",
        "NONE",
        "NA",
    ]:
        value = ""

    return value


# ==================================================
# 樓層 Sheet 名稱
# ==================================================

def get_floor_sheet_name(
    dorm,
    floor,
):
    dorm = normalize_dorm(dorm)

    prefix = DORM_PREFIX.get(
        dorm,
        ""
    )

    if prefix == "":
        return ""

    return f"{prefix}-{floor}"


# ==================================================
# 取得登入者管理宿舍
# ==================================================

def get_manage_dorm_options():

    manage_dorms = st.session_state.get(
        "manage_dorms",
        ""
    )

    if manage_dorms:

        dorm_options = [
            normalize_dorm(item)
            for item in (
                str(manage_dorms)
                .replace("，", ",")
                .split(",")
            )
            if str(item).strip()
        ]

    else:

        dorm_value = normalize_dorm(
            st.session_state.get(
                "dorm",
                ""
            )
        )

        dorm_options = (
            [dorm_value]
            if dorm_value
            else []
        )

    dorm_options = [
        dorm
        for dorm in dorm_options
        if dorm in DORM_PREFIX
    ]

    return list(
        dict.fromkeys(
            dorm_options
        )
    )


# ==================================================
# 欄位尋找
# ==================================================

def find_col(
    df,
    keywords,
):

    columns = list(df.columns)

    # 完全符合
    for keyword in keywords:

        for column in columns:

            if str(column).strip() == keyword:
                return column

    # 部分符合
    for keyword in keywords:

        for column in columns:

            if keyword in str(column):
                return column

    return None


def find_student_id_col(df):

    columns = list(df.columns)

    # 最高優先：真正的學號
    for column in columns:

        if str(column).strip() == "學號":
            return column

    # 第二優先：正式學號
    for column in columns:

        column_text = str(column)

        if (
            "正式" in column_text
            and "學號" in column_text
        ):
            return column

    # 第三優先：含學號但不含替代
    for column in columns:

        column_text = str(column)

        if (
            "學號" in column_text
            and "替代" not in column_text
        ):
            return column

    return None


# ==================================================
# 建立唯一欄位名稱
# ==================================================

def build_unique_headers(headers):

    result = []
    used = {}

    for index, header in enumerate(headers):

        header = str(header).strip()

        if header == "":
            header = f"欄位_{index}"

        if header in used:

            used[header] += 1

            header = (
                f"{header}_"
                f"{used[header]}"
            )

        else:
            used[header] = 0

        result.append(header)

    return result


# ==================================================
# 讀取樓層住宿名單
# ==================================================

@st.cache_data(
    ttl=1800,
    show_spinner=False,
)
def load_clean_floor_sheet(
    url,
    sheet_name,
):

    try:

        ss = open_sheet(url)

        ws = get_worksheet(
            ss,
            sheet_name
        )

        # 整潔比賽只需要住宿基本資料
        # 先抓 A:AQ，避免抓到大量無用尾端資料
        values = get_values(
            ws,
            "A:AQ",
            value_render_option="UNFORMATTED_VALUE",
        )

        if len(values) <= 1:
            return pd.DataFrame()

        headers = build_unique_headers(
            values[0]
        )

        data = values[1:]

        if not data:
            return pd.DataFrame(
                columns=headers
            )

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

    except Exception as error:

        st.warning(
            f"{sheet_name} 讀取失敗：{error}"
        )

        return pd.DataFrame()


# ==================================================
# 查詢整潔比賽房間名單
# ==================================================

def query_clean(
    semester,
    dorm,
    rooms,
):

    dorm = normalize_dorm(dorm)

    if semester not in CLEAN_SHEET:

        st.warning(
            "找不到學期設定"
        )

        return pd.DataFrame()

    if dorm not in CLEAN_SHEET[semester]:

        st.warning(
            f"找不到 {dorm} 的住宿名單試算表"
        )

        return pd.DataFrame()

    url = CLEAN_SHEET[
        semester
    ][dorm]

    result = []

    for floor, room in rooms.items():

        room = normalize_room(room)

        if room == "":
            continue

        sheet_name = get_floor_sheet_name(
            dorm,
            floor
        )

        if sheet_name == "":

            st.warning(
                f"{dorm} 無法判斷 Sheet 前綴"
            )

            continue

        df = load_clean_floor_sheet(
            url,
            sheet_name
        )

        if df.empty:

            st.warning(
                f"{floor} 的 {sheet_name} "
                "沒有資料或讀取失敗"
            )

            continue

        bed_col = find_col(
            df,
            [
                "床位",
            ]
        )

        sid_col = find_student_id_col(
            df
        )

        name_col = find_col(
            df,
            [
                "姓名",
                "名字",
            ]
        )

        if bed_col is None:

            # 若找不到床位欄，保險固定抓 B 欄
            if len(df.columns) >= 2:
                bed_col = df.columns[1]

            else:

                st.warning(
                    f"{sheet_name} 找不到床位欄位"
                )

                continue

        if sid_col is None:

            # 上下學期固定 E 欄為學號
            if len(df.columns) >= 5:
                sid_col = df.columns[4]

        if name_col is None:

            # 上下學期固定 G 欄為姓名
            if len(df.columns) >= 7:
                name_col = df.columns[6]

        df = df.copy()

        df["_床位比對"] = (
            df[bed_col]
            .astype(str)
            .map(normalize_room)
        )

        # 可同時接受：
        # 82113
        # 82113-1
        if "-" in room:

            condition = (
                df["_床位比對"]
                ==
                room
            )

        else:

            condition = (
                df["_床位比對"]
                .astype(str)
                .str.startswith(
                    f"{room}-",
                    na=False
                )
            )

        res = df[
            condition
        ].copy()

        if res.empty:

            st.warning(
                f"{sheet_name} 查無房號：{room}"
            )

            continue

        temp = pd.DataFrame()

        temp["房號"] = (
            res["_床位比對"]
            .astype(str)
            .str.split("-")
            .str[0]
        )

        if sid_col is not None:

            temp["學號"] = (
                res[sid_col]
                .astype(str)
                .map(normalize_value)
            )

        else:
            temp["學號"] = ""

        if name_col is not None:

            temp["姓名"] = (
                res[name_col]
                .astype(str)
                .str.strip()
            )

        else:
            temp["姓名"] = ""

        temp = temp[
            temp["姓名"]
            .astype(str)
            .str.strip()
            .ne("")
        ].copy()

        temp = temp[
            ~temp["姓名"]
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

        if not temp.empty:
            result.append(temp)

    if result:

        total = pd.concat(
            result,
            ignore_index=True
        )

        total = total.drop_duplicates(
            subset=[
                "房號",
                "學號",
                "姓名",
            ],
            keep="first"
        )

        return total.reset_index(
            drop=True
        )

    return pd.DataFrame()


# ==================================================
# 建立或取得結果 Sheet
# ==================================================

def get_or_create_result_worksheet(
    school_year,
):

    ss = open_sheet(
        CLEAN_RESULT_URL
    )

    sheet_name = str(
        school_year
    ).strip()

    try:

        ws = get_worksheet(
            ss,
            sheet_name
        )

    except Exception:

        ws = add_worksheet(
            ss,
            title=sheet_name,
            rows=5000,
            cols=20,
        )

        append_row(
            ws,
            [
                "學年",
                "學期",
                "次數",
                "名次",
                "宿舍",
                "房號",
                "學號",
                "姓名",
            ]
        )

    return ws


# ==================================================
# 儲存整潔比賽結果
# ==================================================

def save_clean_result(
    total,
    school_year,
    semester,
    contest,
    rank,
    dorm,
):

    dorm = normalize_dorm(dorm)

    ws = get_or_create_result_worksheet(
        school_year
    )

    rows = []

    for _, row in total.iterrows():

        name = str(
            row.get(
                "姓名",
                ""
            )
        ).strip()

        if name == "":
            continue

        rows.append(
            [
                school_year,
                semester,
                contest,
                rank,
                dorm,
                row.get(
                    "房號",
                    ""
                ),
                row.get(
                    "學號",
                    ""
                ),
                name,
            ]
        )

    if not rows:
        return 0

    # 一次批次寫入，避免逐筆 append_row
    append_rows(
        ws,
        rows
    )

    return len(rows)


# ==================================================
# 讀取目前整潔比賽設定
# ==================================================

def parse_clean_date(value):
    """支援 Google 日期序號、datetime、2026/7/28、2026-07-28 等格式。"""
    if value is None:
        return pd.NaT

    if isinstance(value, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(value)

    text = str(value).strip()
    if text == "":
        return pd.NaT

    # Google Sheets / Excel 日期序號
    try:
        number = float(text)
        if 20000 <= number <= 60000:
            return pd.Timestamp("1899-12-30") + pd.to_timedelta(number, unit="D")
    except (TypeError, ValueError):
        pass

    # 民國年格式，例如 115/07/28 或 115-07-28
    roc_match = pd.Series([text]).str.extract(
        r"^\s*(\d{2,3})[年/\-.](\d{1,2})[月/\-.](\d{1,2})日?\s*$"
    ).iloc[0]
    if roc_match.notna().all():
        year, month, day = map(int, roc_match.tolist())
        if year < 1911:
            year += 1911
        try:
            return pd.Timestamp(year=year, month=month, day=day)
        except ValueError:
            return pd.NaT

    return pd.to_datetime(text, errors="coerce")


def taiwan_today():
    """使用台灣時區，避免 Streamlit Cloud 的 UTC 日期造成跨日誤判。"""
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


@st.cache_data(
    ttl=10,
    show_spinner=False,
)
def get_current_clean_setting():
    """
    讀取目前可輸入的整潔比賽設定。

    支援新版欄位：
    A 學期、B 第幾次、C 整潔比賽日期、D 可輸入期間開始、E 可輸入期間結束

    也保留舊版「可輸入期間」欄位，例如：2026/7/28 ~ 2026/8/6。
    """
    try:
        ss = open_sheet(CLEAN_RESULT_URL)
        ws = get_worksheet(ss, "整潔比賽時間判斷")

        # 需讀到 E 欄，不能只讀 A:D。
        values = get_values(
            ws,
            "A:E",
            value_render_option="UNFORMATTED_VALUE",
        )

        if len(values) <= 1:
            return None

        headers = build_unique_headers(values[0])
        width = len(headers)
        rows = [list(row) + [""] * (width - len(row)) for row in values[1:]]
        rows = [row[:width] for row in rows]
        df = pd.DataFrame(rows, columns=headers)
        df.columns = df.columns.astype(str).str.strip()

        today = taiwan_today()

        for _, row in df.iterrows():
            start_raw = row.get("可輸入期間開始", "")
            end_raw = row.get("可輸入期間結束", "")

            start_date = parse_clean_date(start_raw)
            end_date = parse_clean_date(end_raw)

            # 向下相容舊版「可輸入期間」單欄位。
            if pd.isna(start_date) or pd.isna(end_date):
                period = str(row.get("可輸入期間", "")).strip()
                normalized_period = (
                    period.replace("～", "~")
                    .replace("－", "~")
                    .replace("—", "~")
                )
                if "~" in normalized_period:
                    start_text, end_text = normalized_period.split("~", 1)
                    start_date = parse_clean_date(start_text)
                    end_date = parse_clean_date(end_text)

            if pd.isna(start_date) or pd.isna(end_date):
                continue

            start_day = start_date.date()
            end_day = end_date.date()

            # 若試算表不小心把開始、結束填反，自動交換。
            if start_day > end_day:
                start_day, end_day = end_day, start_day

            if start_day <= today <= end_day:
                contest_date = parse_clean_date(row.get("整潔比賽日期", ""))
                contest_date_text = (
                    contest_date.strftime("%Y/%m/%d")
                    if not pd.isna(contest_date)
                    else str(row.get("整潔比賽日期", "")).strip()
                )

                return {
                    "學期": str(row.get("學期", "")).strip(),
                    "第幾次": str(row.get("第幾次", "")).strip(),
                    "整潔比賽日期": contest_date_text,
                    "可輸入期間": (
                        f"{start_day.strftime('%Y/%m/%d')} ~ "
                        f"{end_day.strftime('%Y/%m/%d')}"
                    ),
                    "可輸入期間開始": start_day.isoformat(),
                    "可輸入期間結束": end_day.isoformat(),
                }

        return None

    except Exception as error:
        st.warning(f"讀取整潔比賽判斷失敗：{error}")
        return None


# ==================================================
# 整潔比賽輸入頁面
# ==================================================

def show_clean():

    st.header(
        "整潔比賽"
    )

    # ==============================================
    # 重新讀取設定
    # ==============================================

    if st.button(
        "重新讀取整潔比賽設定",
        key="refresh_clean_setting"
    ):

        get_current_clean_setting.clear()
        load_clean_floor_sheet.clear()

        st.rerun()

    # ==============================================
    # 目前整潔比賽
    # ==============================================

    setting = get_current_clean_setting()

    if setting is None:

        st.warning(
            "目前不在整潔比賽可輸入期間"
        )

        return

    clean_term = setting.get(
        "學期",
        ""
    )

    contest = setting.get(
        "第幾次",
        ""
    )

    if "-" not in clean_term:

        st.warning(
            "整潔比賽學期格式錯誤，"
            "應為例如：115-1"
        )

        return

    term_parts = clean_term.split(
        "-",
        1
    )

    school_year = term_parts[0]

    semester_number = term_parts[1]

    semester = (
        "上學期"
        if semester_number == "1"
        else "下學期"
    )

    st.info(
        f"""
目前學年：{school_year}

目前學期：{semester}

目前整潔比賽：{contest}

比賽日期：{setting.get("整潔比賽日期", "")}

可輸入期間：{setting.get("可輸入期間", "")}
"""
    )

    # ==============================================
    # 宿舍
    # ==============================================

    dorm_options = get_manage_dorm_options()

    if not dorm_options:

        st.warning(
            "沒有可管理的宿舍"
        )

        return

    dorm = st.selectbox(
        "宿舍",
        dorm_options,
        key="clean_dorm_select"
    )

    st.subheader(
        f"宿舍：{dorm}"
    )

    # ==============================================
    # 名次
    # ==============================================

    rank = st.selectbox(
        "名次",
        [
            "第一名",
            "第二名",
            "第三名",
        ],
        key="clean_rank"
    )

    # ==============================================
    # 樓層房號
    # ==============================================

    floors = FLOOR_OPTIONS.get(
        dorm,
        []
    )

    if not floors:

        st.warning(
            "此宿舍沒有樓層設定"
        )

        return

    st.divider()

    st.subheader(
        "各樓層房號"
    )

    rooms = {}

    for floor in floors:

        sheet_name = get_floor_sheet_name(
            dorm,
            floor
        )

        rooms[floor] = st.text_input(
            f"{floor} 房號（讀取 {sheet_name}）",
            key=(
                f"clean_room_"
                f"{dorm}_"
                f"{floor}_"
                f"{semester}_"
                f"{contest}_"
                f"{rank}"
            )
        )

    # ==============================================
    # 查詢
    # ==============================================

    query_key = (
        f"clean_result_"
        f"{dorm}_"
        f"{semester}_"
        f"{contest}_"
        f"{rank}"
    )

    if st.button(
        "查詢名單",
        key=(
            f"query_clean_"
            f"{dorm}_"
            f"{semester}_"
            f"{contest}_"
            f"{rank}"
        )
    ):

        with st.spinner(
            "正在查詢住宿名單..."
        ):

            total = query_clean(
                semester,
                dorm,
                rooms
            )

        st.session_state[
            query_key
        ] = total

        if total.empty:

            st.warning(
                "查無資料，請確認房號是否存在於該樓層 Sheet"
            )

        else:

            st.success(
                f"查詢成功，共 {len(total)} 位學生"
            )

    total = st.session_state.get(
        query_key,
        pd.DataFrame()
    )

    if not isinstance(
        total,
        pd.DataFrame
    ):
        total = pd.DataFrame()

    if total.empty:

        st.info(
            "請輸入房號後按「查詢名單」"
        )

        return

    # ==============================================
    # 顯示名單
    # ==============================================

    st.divider()

    st.subheader(
        "名單確認"
    )

    st.dataframe(
        total[
            [
                "房號",
                "學號",
                "姓名",
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    # ==============================================
    # 儲存
    # ==============================================

    if st.button(
        "儲存到試算表",
        key=(
            f"save_clean_"
            f"{dorm}_"
            f"{semester}_"
            f"{contest}_"
            f"{rank}"
        )
    ):

        try:

            with st.spinner(
                "正在儲存整潔比賽結果..."
            ):

                saved_count = save_clean_result(
                    total,
                    school_year,
                    semester,
                    contest,
                    rank,
                    dorm
                )

            if saved_count == 0:

                st.warning(
                    "沒有可儲存的學生資料"
                )

            else:

                st.success(
                    f"已成功儲存 {saved_count} 筆資料"
                )

        except Exception as error:

            st.error(
                f"儲存失敗：{error}"
            )


# ==================================================
# 整潔比賽檢視頁面
# ==================================================

def show_clean_view():

    st.header(
        "整潔比賽（檢視）"
    )

    if st.button(
        "重新整理整潔比賽資料",
        key="refresh_clean_view"
    ):

        st.rerun()

    try:

        ss = open_sheet(
            CLEAN_RESULT_URL
        )

        worksheets = get_worksheets(
            ss
        )

        sheet_names = [
            ws.title
            for ws in worksheets
            if ws.title != "整潔比賽時間判斷"
        ]

        if not sheet_names:

            st.info(
                "尚無資料"
            )

            return

        sheet_names = sorted(
            sheet_names,
            reverse=True
        )

        school_year = st.selectbox(
            "學年",
            sheet_names,
            key="view_clean_school_year"
        )

        ws = get_worksheet(
            ss,
            school_year
        )

        values = get_all_values(
            ws
        )

        if len(values) <= 1:

            st.info(
                "尚無資料"
            )

            return

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

        semester = st.selectbox(
            "學期",
            [
                "全部",
                "上學期",
                "下學期",
            ],
            key="view_clean_semester"
        )

        contest = st.selectbox(
            "第幾次",
            [
                "全部",
                "第一次",
                "第二次",
                "第三次",
            ],
            key="view_clean_contest"
        )

        rank = st.selectbox(
            "名次",
            [
                "全部",
                "第一名",
                "第二名",
                "第三名",
            ],
            key="view_clean_rank"
        )

        if (
            semester != "全部"
            and "學期" in df.columns
        ):

            df = df[
                df["學期"]
                .astype(str)
                .str.strip()
                ==
                semester
            ].copy()

        if (
            contest != "全部"
            and "次數" in df.columns
        ):

            df = df[
                df["次數"]
                .astype(str)
                .str.strip()
                ==
                contest
            ].copy()

        if (
            rank != "全部"
            and "名次" in df.columns
        ):

            df = df[
                df["名次"]
                .astype(str)
                .str.strip()
                ==
                rank
            ].copy()

        show_cols = [
            "宿舍",
            "名次",
            "房號",
            "學號",
            "姓名",
        ]

        for column in show_cols:

            if column not in df.columns:
                df[column] = ""

        df = df[
            df["姓名"]
            .astype(str)
            .str.strip()
            .ne("")
        ].copy()

        if df.empty:

            st.info(
                "查無符合條件的資料"
            )

            return

        st.dataframe(
            df[show_cols],
            use_container_width=True,
            hide_index=True
        )

    except Exception as error:

        st.error(
            f"讀取整潔比賽資料失敗：{error}"
        )