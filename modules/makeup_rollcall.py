# modules/makeup_rollcall.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.google_api import (
    open_sheet,
    get_worksheet,
    get_all_values,
    update_cell,
)

from core.config import (
    NEED_MAKEUP_GIRL_URL,
    NEED_MAKEUP_BOY_URL,
    ROLLCALL_GIRL_URL,
    ROLLCALL_BOY_URL,
    ROLLCALL_SHEET_URL,
)


# =========================================================
# 基本工具
# =========================================================

def clean_sheet_value(value):
    """
    清理 Google Sheet 可能出現的：
    - 空白
    - BOM
    - 不換行空白
    - 零寬字元
    - Excel / Google Sheet 前導單引號
    """
    if value is None:
        return ""

    return (
        str(value)
        .replace("\u200b", "")
        .replace("\ufeff", "")
        .replace("\xa0", "")
        .replace("'", "")
        .strip()
    )


def normalize_text(value):
    return clean_sheet_value(value)


def normalize_gender(value):
    value = clean_sheet_value(value)

    if value in ["女生", "女", "F", "female", "Female", "FEMALE"]:
        return "女生"

    if value in ["男生", "男", "M", "male", "Male", "MALE"]:
        return "男生"

    return value


def gender_to_label(gender):
    gender = normalize_gender(gender)

    if gender == "女生":
        return "女生"

    if gender == "男生":
        return "男生"

    return gender


def canonical_dorm(value):
    """
    統一宿舍名稱格式
    """
    value = clean_sheet_value(value)

    if not value:
        return ""

    mapping = {
        "女一": "女一",
        "女一宿": "女一",
        "女生一宿": "女一",

        "女二": "女二",
        "女二宿": "女二",
        "女生二宿": "女二",

        "女三": "女三",
        "女三宿": "女三",
        "女生三宿": "女三",

        "女一一樓": "女一一樓",
        "女一1樓": "女一一樓",
        "女一1F": "女一一樓",

        "男一": "男一",
        "男一宿": "男一",

        "男三": "男三",
        "男三宿": "男三",
    }

    return mapping.get(value, value)


def find_col_index(headers, col_name):
    """
    找欄位 index
    找不到回傳 -1
    """
    headers = [clean_sheet_value(x) for x in headers]

    for i, header in enumerate(headers):
        if header == col_name:
            return i

    return -1


def normalize_date_value(value):
    """
    將 Google Sheet 日期統一成 YYYY-MM-DD
    支援：
    2026-09-22
    2026/09/22
    2026-09-22 00:00:00
    """
    value = clean_sheet_value(value)

    if not value:
        return ""

    value = value.replace("/", "-")

    # 如果後面有時間
    if " " in value:
        value = value.split(" ")[0]

    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return value


# =========================================================
# 權限 / 性別
# =========================================================

def get_login_gender():
    """
    取得目前登入者性別
    """
    gender = st.session_state.get("gender", "")

    if not gender:
        gender = st.session_state.get("性別", "")

    return normalize_gender(gender)


def get_allowed_genders():
    """
    行政：全部
    舍監：依性別
    樓長：依性別
    """

    role = clean_sheet_value(
        st.session_state.get("role")
        or st.session_state.get("身分")
        or st.session_state.get("權限")
        or ""
    )

    role_lower = role.lower()

    # 行政 / 管理者
    if role in ["行政", "管理員", "系統管理員", "宿舍管理員"] or \
       role_lower in ["admin", "administrator"]:

        return ["女生", "男生"]

    gender = get_login_gender()

    if gender in ["女生", "男生"]:
        return [gender]

    return ["女生", "男生"]


# =========================================================
# 補點日期
# =========================================================

def get_makeup_target_date():
    """
    補點日期規則：

    00:00 ~ 11:59
        → 顯示前一天

    12:00 ~ 23:59
        → 顯示今天
    """

    tz = ZoneInfo("Asia/Taipei")
    now = datetime.now(tz)

    if now.hour < 12:
        return (now - timedelta(days=1)).date()

    return now.date()


# =========================================================
# 取得來源 URL
# =========================================================

def get_rollcall_url_by_gender(gender):
    gender = normalize_gender(gender)

    if gender == "女生":
        return ROLLCALL_GIRL_URL

    if gender == "男生":
        return ROLLCALL_BOY_URL

    raise ValueError(f"無法判斷性別：{gender}")


def get_need_makeup_url_by_gender(gender):
    gender = normalize_gender(gender)

    if gender == "女生":
        return NEED_MAKEUP_GIRL_URL

    if gender == "男生":
        return NEED_MAKEUP_BOY_URL

    raise ValueError(f"無法判斷性別：{gender}")


# =========================================================
# 讀取「統一點名總表」
# =========================================================

@st.cache_data(ttl=15, show_spinner=False)
def load_need_makeup_source(gender):
    """
    ROLLCALL_SHEET_URL 是「單一工作表」

    欄位：
    日期
    宿舍
    床位
    房號
    學號
    班級
    姓名
    狀態
    備註
    性別

    注意：
    日期不是 worksheet 名稱，
    而是資料中的「日期」欄位。
    """

    gender = normalize_gender(gender)

    try:
        ss = open_sheet(ROLLCALL_SHEET_URL)

        # ★ 統一點名總表只有一張工作表
        ws = ss.sheet1

        values = get_all_values(ws)

        if not values:
            return pd.DataFrame()

        if len(values) < 2:
            return pd.DataFrame()

        headers = [clean_sheet_value(x) for x in values[0]]

        df = pd.DataFrame(
            values[1:],
            columns=headers
        )

        # 確認必要欄位
        required_cols = ["日期", "學號", "姓名", "狀態"]

        for col in required_cols:
            if col not in df.columns:
                st.error(
                    f"統一點名總表缺少欄位：{col}"
                )
                return pd.DataFrame()

        # -------------------------------------------------
        # 清理文字欄位
        # -------------------------------------------------

        for col in df.columns:
            df[col] = df[col].apply(clean_sheet_value)

        # -------------------------------------------------
        # 日期標準化
        # -------------------------------------------------

        target_date = get_makeup_target_date()
        target_date_str = target_date.strftime("%Y-%m-%d")

        df["日期"] = df["日期"].apply(normalize_date_value)

        # 只抓目標日期
        df = df[
            df["日期"] == target_date_str
        ].copy()

        if df.empty:
            return pd.DataFrame()

        # -------------------------------------------------
        # 狀態
        # -------------------------------------------------

        df["狀態"] = df["狀態"].apply(clean_sheet_value)

        # 只顯示缺 / 未入住
        df = df[
            df["狀態"].isin(
                ["缺", "未入住"]
            )
        ].copy()

        if df.empty:
            return pd.DataFrame()

        # -------------------------------------------------
        # 性別
        # -------------------------------------------------

        if "性別" in df.columns:

            df["性別"] = df["性別"].apply(
                normalize_gender
            )

            df = df[
                df["性別"] == gender
            ].copy()

        else:
            # 理論上目前的表一定有性別
            df["性別"] = gender

        if df.empty:
            return pd.DataFrame()

        # -------------------------------------------------
        # 來源資訊
        # -------------------------------------------------

        df["來源Sheet"] = ws.title

        return df.reset_index(drop=True)

    except Exception as e:

        st.error(
            f"讀取統一點名總表失敗：{e}"
        )

        return pd.DataFrame()


# =========================================================
# 宿舍欄位處理
# =========================================================

def _prepare_dorm_column(df):
    """
    如果「宿舍」欄位不存在或空白，
    依照：

    女生：
        81 → 女一
        82 → 女二
        83 → 女三

    男生：
        81 → 女一一樓
        82 → 男一
        83 → 男三
    """

    df = df.copy()

    if "宿舍" not in df.columns:
        df["宿舍"] = ""

    df["宿舍"] = df["宿舍"].apply(
        canonical_dorm
    )

    if "房號" not in df.columns:
        return df

    if "性別" not in df.columns:
        df["性別"] = ""

    def infer_dorm(row):

        current_dorm = canonical_dorm(
            row.get("宿舍", "")
        )

        if current_dorm:
            return current_dorm

        gender = normalize_gender(
            row.get("性別", "")
        )

        room = clean_sheet_value(
            row.get("房號", "")
        )

        # 房號前兩碼
        room_prefix = room[:2]

        # -----------------------------
        # 女生
        # -----------------------------

        if gender == "女生":

            if room_prefix == "81":
                return "女一"

            if room_prefix == "82":
                return "女二"

            if room_prefix == "83":
                return "女三"

        # -----------------------------
        # 男生
        # -----------------------------

        if gender == "男生":

            if room_prefix == "81":
                return "女一一樓"

            if room_prefix == "82":
                return "男一"

            if room_prefix == "83":
                return "男三"

        return ""

    df["宿舍"] = df.apply(
        infer_dorm,
        axis=1
    )

    return df


# =========================================================
# 取得樓長可以看的宿舍
# =========================================================

def get_allowed_dorms():
    """
    從 session_state 取得樓長負責宿舍
    """

    possible_keys = [
        "allowed_dorms",
        "允許宿舍",
        "負責宿舍",
        "dorms",
        "宿舍",
    ]

    raw = None

    for key in possible_keys:

        if key in st.session_state:

            value = st.session_state.get(key)

            if value not in [
                None,
                "",
                [],
            ]:
                raw = value
                break

    if raw is None:
        return []

    if isinstance(raw, list):
        values = raw
    else:
        values = str(raw).split(",")

    result = []

    for value in values:

        dorm = canonical_dorm(value)

        if dorm and dorm not in result:
            result.append(dorm)

    return result


# =========================================================
# 樓長宿舍判斷
# =========================================================

def infer_dorm_for_leader(row):
    """
    依照性別 + 房號判斷宿舍
    """

    gender = normalize_gender(
        row.get("性別", "")
    )

    room = clean_sheet_value(
        row.get("房號", "")
    )

    room_prefix = room[:2]

    if gender == "女生":

        if room_prefix == "81":
            return "女一"

        if room_prefix == "82":
            return "女二"

        if room_prefix == "83":
            return "女三"

    elif gender == "男生":

        if room_prefix == "81":
            return "女一一樓"

        if room_prefix == "82":
            return "男一"

        if room_prefix == "83":
            return "男三"

    return ""


def filter_by_leader_scope(df):
    """
    行政：
        全部

    舍監：
        依性別

    樓長：
        依負責宿舍
    """

    df = df.copy()

    if df.empty:
        return df

    role = clean_sheet_value(
        st.session_state.get("role")
        or st.session_state.get("身分")
        or st.session_state.get("權限")
        or ""
    )

    role_lower = role.lower()

    # =====================================================
    # 行政
    # =====================================================

    if role in [
        "行政",
        "管理員",
        "系統管理員",
        "宿舍管理員",
    ] or role_lower in [
        "admin",
        "administrator",
    ]:

        return df

    # =====================================================
    # 舍監
    # =====================================================

    if role in [
        "舍監",
        "舍長",
    ]:

        gender = get_login_gender()

        if gender in ["女生", "男生"]:

            if "性別" in df.columns:

                df = df[
                    df["性別"].apply(
                        normalize_gender
                    ) == gender
                ].copy()

        return df

    # =====================================================
    # 樓長
    # =====================================================

    if role in [
        "樓長",
        "樓層長",
    ]:

        allowed_dorms = get_allowed_dorms()

        if not allowed_dorms:
            return df.iloc[0:0].copy()

        df = _prepare_dorm_column(df)

        # 先使用原本宿舍欄位
        df["_判斷宿舍"] = df["宿舍"].apply(
            canonical_dorm
        )

        # 宿舍空白再依性別 + 房號判斷
        df.loc[
            df["_判斷宿舍"] == "",
            "_判斷宿舍"
        ] = df[
            df["_判斷宿舍"] == ""
        ].apply(
            infer_dorm_for_leader,
            axis=1
        )

        df = df[
            df["_判斷宿舍"].isin(
                allowed_dorms
            )
        ].copy()

        df.drop(
            columns=["_判斷宿舍"],
            inplace=True,
            errors="ignore"
        )

        return df

    return df


# =========================================================
# 更新「統一點名總表」
# =========================================================

def update_rollcall_status_to_makeup(target_row):
    """
    更新：

    ROLLCALL_SHEET_URL

    欄位：
    日期
    學號
    姓名
    房號
    狀態

    找人優先順序：

    1. 日期 + 學號 + 姓名
    2. 日期 + 學號
    3. 日期 + 姓名 + 房號
    """

    ss = open_sheet(ROLLCALL_SHEET_URL)

    ws = ss.sheet1

    values = get_all_values(ws)

    if not values:
        raise Exception(
            "統一點名總表沒有資料"
        )

    headers = [
        clean_sheet_value(x)
        for x in values[0]
    ]

    date_col = find_col_index(
        headers,
        "日期"
    )

    sid_col = find_col_index(
        headers,
        "學號"
    )

    name_col = find_col_index(
        headers,
        "姓名"
    )

    room_col = find_col_index(
        headers,
        "房號"
    )

    status_col = find_col_index(
        headers,
        "狀態"
    )

    if sid_col == -1:
        raise Exception(
            "統一點名總表找不到「學號」欄位"
        )

    if status_col == -1:
        raise Exception(
            "統一點名總表找不到「狀態」欄位"
        )

    target_date = normalize_date_value(
        target_row.get("日期", "")
    )

    target_sid = clean_sheet_value(
        target_row.get("學號", "")
    )

    target_name = clean_sheet_value(
        target_row.get("姓名", "")
    )

    target_room = clean_sheet_value(
        target_row.get("房號", "")
    )

    matched_row = None

    # =====================================================
    # 第一優先：日期 + 學號 + 姓名
    # =====================================================

    for row_index, row in enumerate(
        values[1:],
        start=2
    ):

        row = list(row)

        row_date = (
            normalize_date_value(
                row[date_col]
            )
            if date_col != -1
            and date_col < len(row)
            else ""
        )

        row_sid = (
            clean_sheet_value(
                row[sid_col]
            )
            if sid_col < len(row)
            else ""
        )

        row_name = (
            clean_sheet_value(
                row[name_col]
            )
            if name_col != -1
            and name_col < len(row)
            else ""
        )

        if (
            row_date == target_date
            and row_sid == target_sid
            and row_name == target_name
        ):

            matched_row = row_index
            break

    # =====================================================
    # 第二優先：日期 + 學號
    # =====================================================

    if matched_row is None:

        for row_index, row in enumerate(
            values[1:],
            start=2
        ):

            row = list(row)

            row_date = (
                normalize_date_value(
                    row[date_col]
                )
                if date_col != -1
                and date_col < len(row)
                else ""
            )

            row_sid = (
                clean_sheet_value(
                    row[sid_col]
                )
                if sid_col < len(row)
                else ""
            )

            if (
                row_date == target_date
                and row_sid == target_sid
            ):

                matched_row = row_index
                break

    # =====================================================
    # 第三優先：日期 + 姓名 + 房號
    # =====================================================

    if matched_row is None:

        for row_index, row in enumerate(
            values[1:],
            start=2
        ):

            row = list(row)

            row_date = (
                normalize_date_value(
                    row[date_col]
                )
                if date_col != -1
                and date_col < len(row)
                else ""
            )

            row_name = (
                clean_sheet_value(
                    row[name_col]
                )
                if name_col != -1
                and name_col < len(row)
                else ""
            )

            row_room = (
                clean_sheet_value(
                    row[room_col]
                )
                if room_col != -1
                and room_col < len(row)
                else ""
            )

            if (
                row_date == target_date
                and row_name == target_name
                and row_room == target_room
            ):

                matched_row = row_index
                break

    if matched_row is None:

        raise Exception(
            "統一點名總表找不到此學生："
            f"日期={target_date}、"
            f"學號={target_sid}、"
            f"姓名={target_name}、"
            f"房號={target_room}"
        )

    # Google Sheet 欄位 index → A1 column index
    update_cell(
        ws,
        matched_row,
        status_col,
        "已補點"
    )


# =========================================================
# 更新「需補點」女生 / 男生表
# =========================================================

def update_need_makeup_status_to_done(
    gender,
    target_row
):
    """
    更新：

    NEED_MAKEUP_GIRL_URL
    或
    NEED_MAKEUP_BOY_URL

    欄位：

    學號
    班級
    姓名
    床位
    房號
    本地/境外
    手機
    家長姓名
    連絡電話1
    狀態
    備註

    找人：

    1. 學號 + 姓名
    2. 學號
    3. 姓名 + 房號
    """

    source_url = get_need_makeup_url_by_gender(
        gender
    )

    ss = open_sheet(source_url)

    ws = ss.sheet1

    values = get_all_values(ws)

    if not values:
        raise Exception(
            f"{gender} 需補點表沒有資料"
        )

    headers = [
        clean_sheet_value(x)
        for x in values[0]
    ]

    sid_col = find_col_index(
        headers,
        "學號"
    )

    name_col = find_col_index(
        headers,
        "姓名"
    )

    room_col = find_col_index(
        headers,
        "房號"
    )

    status_col = find_col_index(
        headers,
        "狀態"
    )

    if sid_col == -1:
        raise Exception(
            f"{gender} 需補點表找不到「學號」欄位"
        )

    if status_col == -1:
        raise Exception(
            f"{gender} 需補點表找不到「狀態」欄位"
        )

    target_sid = clean_sheet_value(
        target_row.get("學號", "")
    )

    target_name = clean_sheet_value(
        target_row.get("姓名", "")
    )

    target_room = clean_sheet_value(
        target_row.get("房號", "")
    )

    matched_row = None

    # =====================================================
    # 第一優先：學號 + 姓名
    # =====================================================

    for row_index, row in enumerate(
        values[1:],
        start=2
    ):

        row = list(row)

        row_sid = (
            clean_sheet_value(
                row[sid_col]
            )
            if sid_col < len(row)
            else ""
        )

        row_name = (
            clean_sheet_value(
                row[name_col]
            )
            if name_col != -1
            and name_col < len(row)
            else ""
        )

        if (
            row_sid == target_sid
            and row_name == target_name
        ):

            matched_row = row_index
            break

    # =====================================================
    # 第二優先：學號
    # =====================================================

    if matched_row is None:

        for row_index, row in enumerate(
            values[1:],
            start=2
        ):

            row = list(row)

            row_sid = (
                clean_sheet_value(
                    row[sid_col]
                )
                if sid_col < len(row)
                else ""
            )

            if row_sid == target_sid:

                matched_row = row_index
                break

    # =====================================================
    # 第三優先：姓名 + 房號
    # =====================================================

    if matched_row is None:

        for row_index, row in enumerate(
            values[1:],
            start=2
        ):

            row = list(row)

            row_name = (
                clean_sheet_value(
                    row[name_col]
                )
                if name_col != -1
                and name_col < len(row)
                else ""
            )

            row_room = (
                clean_sheet_value(
                    row[room_col]
                )
                if room_col != -1
                and room_col < len(row)
                else ""
            )

            if (
                row_name == target_name
                and row_room == target_room
            ):

                matched_row = row_index
                break

    if matched_row is None:

        raise Exception(
            f"{gender} 需補點表找不到此學生："
            f"{target_sid}"
        )

    update_cell(
        ws,
        matched_row,
        status_col,
        "已補點"
    )


# =========================================================
# 更新女生 / 男生「一般點名表」
# =========================================================

def update_gender_rollcall_status(
    gender,
    target_row
):
    """
    更新：

    女生 → ROLLCALL_GIRL_URL
    男生 → ROLLCALL_BOY_URL

    這兩張也是單一工作表。

    找人：

    1. 學號 + 姓名
    2. 學號
    3. 姓名 + 房號
    """

    source_url = get_rollcall_url_by_gender(
        gender
    )

    ss = open_sheet(source_url)

    ws = ss.sheet1

    values = get_all_values(ws)

    if not values:
        raise Exception(
            f"{gender} 點名表沒有資料"
        )

    headers = [
        clean_sheet_value(x)
        for x in values[0]
    ]

    sid_col = find_col_index(
        headers,
        "學號"
    )

    name_col = find_col_index(
        headers,
        "姓名"
    )

    room_col = find_col_index(
        headers,
        "房號"
    )

    status_col = find_col_index(
        headers,
        "狀態"
    )

    if sid_col == -1:
        raise Exception(
            f"{gender} 點名表找不到「學號」欄位"
        )

    if status_col == -1:
        raise Exception(
            f"{gender} 點名表找不到「狀態」欄位"
        )

    target_sid = clean_sheet_value(
        target_row.get("學號", "")
    )

    target_name = clean_sheet_value(
        target_row.get("姓名", "")
    )

    target_room = clean_sheet_value(
        target_row.get("房號", "")
    )

    matched_row = None

    # =====================================================
    # 第一優先：學號 + 姓名
    # =====================================================

    for row_index, row in enumerate(
        values[1:],
        start=2
    ):

        row = list(row)

        row_sid = (
            clean_sheet_value(
                row[sid_col]
            )
            if sid_col < len(row)
            else ""
        )

        row_name = (
            clean_sheet_value(
                row[name_col]
            )
            if name_col != -1
            and name_col < len(row)
            else ""
        )

        if (
            row_sid == target_sid
            and row_name == target_name
        ):

            matched_row = row_index
            break

    # =====================================================
    # 第二優先：學號
    # =====================================================

    if matched_row is None:

        for row_index, row in enumerate(
            values[1:],
            start=2
        ):

            row = list(row)

            row_sid = (
                clean_sheet_value(
                    row[sid_col]
                )
                if sid_col < len(row)
                else ""
            )

            if row_sid == target_sid:

                matched_row = row_index
                break

    # =====================================================
    # 第三優先：姓名 + 房號
    # =====================================================

    if matched_row is None:

        for row_index, row in enumerate(
            values[1:],
            start=2
        ):

            row = list(row)

            row_name = (
                clean_sheet_value(
                    row[name_col]
                )
                if name_col != -1
                and name_col < len(row)
                else ""
            )

            row_room = (
                clean_sheet_value(
                    row[room_col]
                )
                if room_col != -1
                and room_col < len(row)
                else ""
            )

            if (
                row_name == target_name
                and row_room == target_room
            ):

                matched_row = row_index
                break

    if matched_row is None:

        raise Exception(
            f"{gender} 點名表找不到此學生："
            f"{target_sid}"
        )

    update_cell(
        ws,
        matched_row,
        status_col,
        "已補點"
    )


# =========================================================
# 顯示補點系統
# =========================================================

def show_makeup_rollcall():

    st.subheader("補點名單")

    allowed_genders = get_allowed_genders()

    # =====================================================
    # 讀取資料
    # =====================================================

    all_data = []

    for gender in allowed_genders:

        try:

            df_gender = load_need_makeup_source(
                gender
            )

            if df_gender is not None and not df_gender.empty:

                all_data.append(
                    df_gender
                )

        except Exception as e:

            st.error(
                f"讀取 {gender} 補點資料失敗：{e}"
            )

    # =====================================================
    # 沒有資料
    # =====================================================

    if not all_data:

        target_date = get_makeup_target_date()

        st.info(
            f"{target_date.strftime('%Y-%m-%d')} "
            "目前沒有需要補點的人員。"
        )

        return

    # =====================================================
    # 合併
    # =====================================================

    df = pd.concat(
        all_data,
        ignore_index=True
    )

    # =====================================================
    # 樓長 / 舍監權限
    # =====================================================

    df = filter_by_leader_scope(df)

    if df.empty:

        st.info(
            "目前沒有符合您管理範圍的補點人員。"
        )

        return

    # =====================================================
    # 搜尋
    # =====================================================

    search_text = st.text_input(
        "搜尋",
        placeholder="輸入學號、姓名、房號或床位",
        key="makeup_search"
    )

    if search_text:

        search_text = clean_sheet_value(
            search_text
        ).lower()

        search_columns = [
            "學號",
            "姓名",
            "房號",
            "床位",
            "班級",
            "宿舍",
        ]

        mask = pd.Series(
            False,
            index=df.index
        )

        for col in search_columns:

            if col in df.columns:

                mask = (
                    mask
                    |
                    df[col]
                    .astype(str)
                    .str.lower()
                    .str.contains(
                        search_text,
                        na=False,
                        regex=False
                    )
                )

        df = df[mask].copy()

    # =====================================================
    # 搜尋後沒有資料
    # =====================================================

    if df.empty:

        st.info(
            "找不到符合的補點人員。"
        )

        return

    # =====================================================
    # 顯示資料
    # =====================================================

    display_columns = [
        "床位",
        "學號",
        "班級",
        "姓名",
        "房號",
        "宿舍",
        "性別",
        "狀態",
        "備註",
    ]

    display_columns = [
        col
        for col in display_columns
        if col in df.columns
    ]

    st.dataframe(
        df[display_columns],
        use_container_width=True,
        hide_index=True
    )

    # =====================================================
    # 選擇學生
    # =====================================================

    def make_option(row):

        room = clean_sheet_value(
            row.get("房號", "")
        )

        bed = clean_sheet_value(
            row.get("床位", "")
        )

        sid = clean_sheet_value(
            row.get("學號", "")
        )

        name = clean_sheet_value(
            row.get("姓名", "")
        )

        return (
            f"{room} / "
            f"{bed} / "
            f"{sid} / "
            f"{name}"
        )

    options = list(df.index)

    selected_index = st.selectbox(
        "選擇要補點的人員",
        options,
        format_func=lambda x: make_option(
            df.loc[x]
        ),
        key="makeup_student_select"
    )

    # =====================================================
    # 顯示選擇資料
    # =====================================================

    selected_row = df.loc[
        selected_index
    ]

    st.markdown("### 選擇的人員")

    info_cols = st.columns(4)

    with info_cols[0]:
        st.write(
            f"**姓名**：{selected_row.get('姓名', '')}"
        )

    with info_cols[1]:
        st.write(
            f"**學號**：{selected_row.get('學號', '')}"
        )

    with info_cols[2]:
        st.write(
            f"**房號**：{selected_row.get('房號', '')}"
        )

    with info_cols[3]:
        st.write(
            f"**性別**：{selected_row.get('性別', '')}"
        )

    # =====================================================
    # 補點完成
    # =====================================================

    if st.button(
        "確認補點完成",
        type="primary",
        use_container_width=True,
        key="submit_makeup"
    ):

        try:

            target_row = (
                selected_row
                .to_dict()
            )

            gender = normalize_gender(
                target_row.get(
                    "性別",
                    ""
                )
            )

            if gender not in [
                "女生",
                "男生",
            ]:

                raise Exception(
                    f"無法判斷學生性別：{gender}"
                )

            # =================================================
            # 1. 更新統一點名總表
            # =================================================

            update_rollcall_status_to_makeup(
                target_row
            )

            # =================================================
            # 2. 更新女生 / 男生「需補點表」
            # =================================================

            update_need_makeup_status_to_done(
                gender,
                target_row
            )

            # =================================================
            # 3. 更新女生 / 男生「一般點名表」
            # =================================================

            update_gender_rollcall_status(
                gender,
                target_row
            )

            # =================================================
            # 清除快取
            # =================================================

            load_need_makeup_source.clear()

            st.success(
                "補點完成！\n\n"
                "已同步更新：\n"
                "• 統一點名總表\n"
                "• 女生／男生需補點表\n"
                "• 女生／男生一般點名表"
            )

            # =================================================
            # 重新整理
            # =================================================

            st.rerun()

        except Exception as e:

            st.error(
                f"更新失敗：{e}"
            )