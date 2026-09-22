import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.google_api import (
    open_sheet,
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
    """清理 Google Sheet 儲存格內容"""

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value).strip()


def normalize_text(value):
    """文字正規化"""

    value = clean_sheet_value(value)

    if not value:
        return ""

    return (
        value
        .replace("\u3000", " ")
        .replace("\n", "")
        .replace("\r", "")
        .strip()
    )


def normalize_gender(value):
    """統一性別文字"""

    value = normalize_text(value)

    if not value:
        return ""

    if "女" in value:
        return "女生"

    if "男" in value:
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
    """統一宿舍名稱"""

    value = normalize_text(value)

    if not value:
        return ""

    value = (
        value
        .replace("宿舍", "")
        .replace("宿", "")
        .replace("女生", "")
        .replace("男生", "")
        .strip()
    )

    dorm_map = {
        "女一": "女一",
        "女二": "女二",
        "女三": "女三",
        "男一": "男一",
        "男三": "男三",
        "女一一樓": "女一一樓",
        "女一1樓": "女一一樓",
        "女一樓": "女一一樓",
    }

    return dorm_map.get(
        value,
        value
    )


def find_col_index(headers, target_name):
    """
    找欄位。

    注意：
    回傳的是 Python 0-based index。

    Google Sheets update_cell()
    則需要 1-based index，
    所以寫入時必須 +1。
    """

    headers = [
        clean_sheet_value(x)
        for x in headers
    ]

    target_name = clean_sheet_value(
        target_name
    )

    for i, header in enumerate(headers):

        if header == target_name:
            return i

    return -1


def normalize_date_value(value):
    """日期統一成 YYYY-MM-DD"""

    value = clean_sheet_value(value)

    if not value:
        return ""

    try:

        dt = pd.to_datetime(
            value,
            errors="coerce"
        )

        if pd.notna(dt):

            return dt.strftime(
                "%Y-%m-%d"
            )

    except Exception:
        pass

    value = value.replace(
        "/",
        "-"
    )

    if len(value) >= 10:

        candidate = value[:10]

        try:

            dt = pd.to_datetime(
                candidate,
                errors="coerce"
            )

            if pd.notna(dt):

                return dt.strftime(
                    "%Y-%m-%d"
                )

        except Exception:
            pass

    return value


# =========================================================
# 登入資訊
# =========================================================

def get_login_role():

    role_keys = [
        "role",
        "身分",
        "權限",
        "user_role",
        "supervisor_type",
    ]

    for key in role_keys:

        value = normalize_text(
            st.session_state.get(
                key,
                ""
            )
        )

        if value:
            return value

    return ""


def get_login_gender():

    gender_keys = [
        "gender",
        "性別",
        "user_gender",
    ]

    for key in gender_keys:

        value = normalize_gender(
            st.session_state.get(
                key,
                ""
            )
        )

        if value in [
            "女生",
            "男生"
        ]:

            return value

    return ""


def get_allowed_genders():

    role = get_login_role()

    role_lower = role.lower()

    # 行政可以看男女
    if (
        "行政" in role
        or "管理員" in role
        or "系統管理員" in role
        or role_lower in [
            "admin",
            "administrator",
        ]
    ):

        return [
            "女生",
            "男生"
        ]

    gender = get_login_gender()

    if gender in [
        "女生",
        "男生"
    ]:

        return [gender]

    return [
        "女生",
        "男生"
    ]


# =========================================================
# 補點日期
# =========================================================

def get_makeup_target_date():
    """
    00:00～11:59 → 前一天
    12:00～23:59 → 當天
    """

    tz = ZoneInfo(
        "Asia/Taipei"
    )

    now = datetime.now(tz)

    if now.hour < 12:

        target_date = (
            now.date()
            - timedelta(days=1)
        )

    else:

        target_date = now.date()

    return target_date.strftime(
        "%Y-%m-%d"
    )


# =========================================================
# URL 對應
# =========================================================

def get_rollcall_url_by_gender(gender):

    gender = normalize_gender(
        gender
    )

    if gender == "女生":
        return ROLLCALL_GIRL_URL

    if gender == "男生":
        return ROLLCALL_BOY_URL

    return ""


def get_need_makeup_url_by_gender(gender):

    gender = normalize_gender(
        gender
    )

    if gender == "女生":
        return NEED_MAKEUP_GIRL_URL

    if gender == "男生":
        return NEED_MAKEUP_BOY_URL

    return ""


# =========================================================
# 讀取待補點資料
# =========================================================

@st.cache_data(ttl=15)
def load_need_makeup_source():
    """
    從統一點名總表讀取待補點資料。

    統一點名總表欄位：

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
    """

    try:

        ss = open_sheet(
            ROLLCALL_SHEET_URL
        )

        # 統一點名總表只有一個工作表
        ws = ss.sheet1

        values = get_all_values(
            ws
        )

        if not values:
            return pd.DataFrame()

        if len(values) < 2:
            return pd.DataFrame()

        headers = [
            clean_sheet_value(x)
            for x in values[0]
        ]

        rows = values[1:]

        normalized_rows = []

        for row in rows:

            row = list(row)

            if len(row) < len(headers):

                row.extend(
                    [""] * (
                        len(headers)
                        - len(row)
                    )
                )

            if len(row) > len(headers):

                row = row[
                    :len(headers)
                ]

            normalized_rows.append(
                row
            )

        df = pd.DataFrame(
            normalized_rows,
            columns=headers
        )

        if df.empty:
            return df

        # =====================================================
        # 日期
        # =====================================================

        if "日期" not in df.columns:
            return pd.DataFrame()

        df["日期"] = (
            df["日期"]
            .apply(
                normalize_date_value
            )
        )

        target_date = (
            get_makeup_target_date()
        )

        df = df[
            df["日期"]
            == target_date
        ].copy()

        if df.empty:
            return df

        # =====================================================
        # 狀態
        # =====================================================

        if "狀態" not in df.columns:
            return pd.DataFrame()

        df["狀態"] = (
            df["狀態"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        # 已補點不再顯示
        df = df[
            df["狀態"].isin(
                [
                    "缺",
                    "未入住"
                ]
            )
        ].copy()

        if df.empty:
            return df

        # =====================================================
        # 性別
        # =====================================================

        allowed_genders = (
            get_allowed_genders()
        )

        if "性別" in df.columns:

            df["性別"] = (
                df["性別"]
                .apply(
                    normalize_gender
                )
            )

            df = df[
                df["性別"].isin(
                    allowed_genders
                )
            ].copy()

        return df

    except Exception as e:

        st.error(
            f"讀取需補點資料失敗：{e}"
        )

        return pd.DataFrame()


# =========================================================
# 宿舍處理
# =========================================================

def _prepare_dorm_column(df):

    df = df.copy()

    if "宿舍" not in df.columns:
        df["宿舍"] = ""

    df["宿舍"] = (
        df["宿舍"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    return df


def get_allowed_dorms():

    role = get_login_role()

    # 舍監、舍長不限制管理宿舍
    if "舍監" in role:
        return []

    if "舍長" in role:
        return []

    keys = [
        "manage_dorm",
        "管理宿舍",
        "dorm",
        "宿舍",
    ]

    result = []

    for key in keys:

        value = st.session_state.get(
            key,
            ""
        )

        if isinstance(
            value,
            list
        ):

            for item in value:

                item = canonical_dorm(
                    item
                )

                if item:
                    result.append(
                        item
                    )

        else:

            value = normalize_text(
                value
            )

            if value:

                for item in (
                    value
                    .replace(
                        "/",
                        ","
                    )
                    .replace(
                        "、",
                        ","
                    )
                    .split(",")
                ):

                    item = canonical_dorm(
                        item
                    )

                    if item:
                        result.append(
                            item
                        )

    return list(
        dict.fromkeys(result)
    )


def infer_dorm_for_leader(row):

    gender = normalize_gender(
        row.get(
            "性別",
            ""
        )
    )

    room = normalize_text(
        row.get(
            "房號",
            ""
        )
    )

    if not room:

        room = normalize_text(
            row.get(
                "床位",
                ""
            )
        )

    room = (
        room
        .replace(
            " ",
            ""
        )
        .replace(
            ".0",
            ""
        )
    )

    if len(room) < 2:
        return ""

    prefix = room[:2]

    if gender == "女生":

        mapping = {
            "81": "女一",
            "82": "女二",
            "83": "女三",
        }

        return mapping.get(
            prefix,
            ""
        )

    if gender == "男生":

        mapping = {
            "81": "女一一樓",
            "82": "男一",
            "83": "男三",
        }

        return mapping.get(
            prefix,
            ""
        )

    return ""


def filter_by_leader_scope(df):

    df = df.copy()

    if df.empty:
        return df

    role = get_login_role()

    role_lower = role.lower()

    # 舍監
    if "舍監" in role:
        return df

    # 舍長
    if "舍長" in role:
        return df

    # 行政
    if (
        "行政" in role
        or "管理員" in role
        or "系統管理員" in role
        or role_lower in [
            "admin",
            "administrator",
        ]
    ):

        return df

    # 樓長
    if (
        "樓長" in role
        or "樓層長" in role
    ):

        allowed_dorms = (
            get_allowed_dorms()
        )

        if not allowed_dorms:

            return df.iloc[
                0:0
            ].copy()

        df = _prepare_dorm_column(
            df
        )

        df["_判斷宿舍"] = (
            df["宿舍"]
            .apply(
                canonical_dorm
            )
        )

        empty_mask = (
            df["_判斷宿舍"]
            == ""
        )

        if empty_mask.any():

            df.loc[
                empty_mask,
                "_判斷宿舍"
            ] = df.loc[
                empty_mask
            ].apply(
                infer_dorm_for_leader,
                axis=1
            )

        df = df[
            df["_判斷宿舍"]
            .isin(
                allowed_dorms
            )
        ].copy()

        df.drop(
            columns=[
                "_判斷宿舍"
            ],
            inplace=True,
            errors="ignore"
        )

        return df

    return df


# =========================================================
# 寫入後驗證
# =========================================================

def write_status_and_verify(
    ws,
    matched_row,
    status_col,
    source_name=""
):
    """
    將狀態改成「已補點」並重新讀取驗證。

    status_col：
        Python 0-based

    Google Sheet：
        1-based

    所以真正寫入：
        status_col + 1
    """

    if status_col < 0:

        raise Exception(
            f"{source_name} 找不到「狀態」欄"
        )

    google_status_col = (
        status_col + 1
    )

    # =====================================================
    # 寫入
    # =====================================================

    update_cell(
        ws,
        matched_row,
        google_status_col,
        "已補點"
    )

    # =====================================================
    # 重新讀取確認
    # =====================================================

    check_values = get_all_values(
        ws
    )

    if not check_values:

        raise Exception(
            f"{source_name} 寫入後無法重新讀取資料"
        )

    # Google Sheet row number 是 1-based
    # list index 是 0-based
    check_row_index = (
        matched_row - 1
    )

    if (
        check_row_index < 0
        or check_row_index
        >= len(check_values)
    ):

        raise Exception(
            f"{source_name} 寫入後找不到第 "
            f"{matched_row} 列"
        )

    check_row = check_values[
        check_row_index
    ]

    if (
        status_col < 0
        or status_col
        >= len(check_row)
    ):

        raise Exception(
            f"{source_name} 寫入後找不到狀態欄"
        )

    check_status = (
        clean_sheet_value(
            check_row[status_col]
        )
    )

    if check_status != "已補點":

        raise Exception(
            f"{source_name} 寫入驗證失敗，"
            f"目前狀態為「{check_status}」"
        )

    return True


# =========================================================
# ① 更新統一點名總表
# =========================================================

def update_rollcall_status_to_makeup(
    target_row
):
    """
    統一點名總表：

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

    只修改：
        狀態 → 已補點
    """

    try:

        ss = open_sheet(
            ROLLCALL_SHEET_URL
        )

        ws = ss.sheet1

        values = get_all_values(
            ws
        )

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

        if date_col == -1:

            raise Exception(
                "統一點名總表找不到「日期」欄"
            )

        if sid_col == -1:

            raise Exception(
                "統一點名總表找不到「學號」欄"
            )

        if status_col == -1:

            raise Exception(
                "統一點名總表找不到「狀態」欄"
            )

        target_date = (
            normalize_date_value(
                target_row.get(
                    "日期",
                    ""
                )
            )
        )

        target_sid = normalize_text(
            target_row.get(
                "學號",
                ""
            )
        )

        target_name = normalize_text(
            target_row.get(
                "姓名",
                ""
            )
        )

        target_room = normalize_text(
            target_row.get(
                "房號",
                ""
            )
        )

        matched_row = None

        for row_number, row in enumerate(
            values[1:],
            start=2
        ):

            row = list(row)

            if len(row) < len(headers):

                row.extend(
                    [""] * (
                        len(headers)
                        - len(row)
                    )
                )

            row_date = (
                normalize_date_value(
                    row[date_col]
                )
            )

            row_sid = normalize_text(
                row[sid_col]
            )

            row_name = ""

            if name_col != -1:

                row_name = normalize_text(
                    row[name_col]
                )

            row_room = ""

            if room_col != -1:

                row_room = normalize_text(
                    row[room_col]
                )

            # 日期 + 學號 + 姓名
            if (
                row_date == target_date
                and row_sid == target_sid
                and target_name
                and row_name == target_name
            ):

                matched_row = row_number
                break

            # 日期 + 學號
            if (
                row_date == target_date
                and row_sid == target_sid
            ):

                matched_row = row_number
                break

            # 日期 + 姓名 + 房號
            if (
                row_date == target_date
                and target_name
                and row_name == target_name
                and target_room
                and row_room == target_room
            ):

                matched_row = row_number
                break

        if matched_row is None:

            raise Exception(
                "統一點名總表找不到對應學生："
                f"{target_date} / "
                f"{target_sid} / "
                f"{target_name}"
            )

        # ★★★ 0-based → 1-based ★★★
        write_status_and_verify(
            ws,
            matched_row,
            status_col,
            "統一點名總表"
        )

        return True

    except Exception as e:

        raise Exception(
            f"統一點名總表更新失敗：{e}"
        )


# =========================================================
# ② 更新男女需補點表
# =========================================================

def update_need_makeup_status_to_done(
    gender,
    target_row
):
    """
    女生：
        NEED_MAKEUP_GIRL_URL

    男生：
        NEED_MAKEUP_BOY_URL

    只修改：
        狀態 → 已補點
    """

    try:

        source_url = (
            get_need_makeup_url_by_gender(
                gender
            )
        )

        if not source_url:

            raise Exception(
                f"找不到 {gender} 的需補點表"
            )

        ss = open_sheet(
            source_url
        )

        ws = ss.sheet1

        values = get_all_values(
            ws
        )

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
                f"{gender} 需補點表找不到「學號」欄"
            )

        if status_col == -1:

            raise Exception(
                f"{gender} 需補點表找不到「狀態」欄"
            )

        target_sid = normalize_text(
            target_row.get(
                "學號",
                ""
            )
        )

        target_name = normalize_text(
            target_row.get(
                "姓名",
                ""
            )
        )

        target_room = normalize_text(
            target_row.get(
                "房號",
                ""
            )
        )

        matched_row = None

        for row_number, row in enumerate(
            values[1:],
            start=2
        ):

            row = list(row)

            if len(row) < len(headers):

                row.extend(
                    [""] * (
                        len(headers)
                        - len(row)
                    )
                )

            row_sid = normalize_text(
                row[sid_col]
            )

            row_name = ""

            if name_col != -1:

                row_name = normalize_text(
                    row[name_col]
                )

            row_room = ""

            if room_col != -1:

                row_room = normalize_text(
                    row[room_col]
                )

            # 學號 + 姓名
            if (
                row_sid == target_sid
                and target_name
                and row_name == target_name
            ):

                matched_row = row_number
                break

            # 學號
            if row_sid == target_sid:

                matched_row = row_number
                break

            # 姓名 + 房號
            if (
                target_name
                and row_name == target_name
                and target_room
                and row_room == target_room
            ):

                matched_row = row_number
                break

        if matched_row is None:

            raise Exception(
                f"{gender} 需補點表找不到學生："
                f"{target_sid} / "
                f"{target_name}"
            )

        # ★★★ 0-based → 1-based ★★★
        write_status_and_verify(
            ws,
            matched_row,
            status_col,
            f"{gender}需補點表"
        )

        return True

    except Exception as e:

        raise Exception(
            f"{gender}需補點表更新失敗：{e}"
        )


# =========================================================
# ③ 更新男女一般點名表
# =========================================================

def update_gender_rollcall_status(
    gender,
    target_row
):
    """
    女生：
        ROLLCALL_GIRL_URL

    男生：
        ROLLCALL_BOY_URL

    只修改：
        狀態 → 已補點
    """

    try:

        source_url = (
            get_rollcall_url_by_gender(
                gender
            )
        )

        if not source_url:

            raise Exception(
                f"找不到 {gender} 的一般點名表"
            )

        ss = open_sheet(
            source_url
        )

        ws = ss.sheet1

        values = get_all_values(
            ws
        )

        if not values:

            raise Exception(
                f"{gender} 一般點名表沒有資料"
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
                f"{gender} 一般點名表找不到「學號」欄"
            )

        if status_col == -1:

            raise Exception(
                f"{gender} 一般點名表找不到「狀態」欄"
            )

        target_sid = normalize_text(
            target_row.get(
                "學號",
                ""
            )
        )

        target_name = normalize_text(
            target_row.get(
                "姓名",
                ""
            )
        )

        target_room = normalize_text(
            target_row.get(
                "房號",
                ""
            )
        )

        matched_row = None

        for row_number, row in enumerate(
            values[1:],
            start=2
        ):

            row = list(row)

            if len(row) < len(headers):

                row.extend(
                    [""] * (
                        len(headers)
                        - len(row)
                    )
                )

            row_sid = normalize_text(
                row[sid_col]
            )

            row_name = ""

            if name_col != -1:

                row_name = normalize_text(
                    row[name_col]
                )

            row_room = ""

            if room_col != -1:

                row_room = normalize_text(
                    row[room_col]
                )

            # 學號 + 姓名
            if (
                row_sid == target_sid
                and target_name
                and row_name == target_name
            ):

                matched_row = row_number
                break

            # 學號
            if row_sid == target_sid:

                matched_row = row_number
                break

            # 姓名 + 房號
            if (
                target_name
                and row_name == target_name
                and target_room
                and row_room == target_room
            ):

                matched_row = row_number
                break

        if matched_row is None:

            raise Exception(
                f"{gender} 一般點名表找不到學生："
                f"{target_sid} / "
                f"{target_name}"
            )

        # ★★★ 0-based → 1-based ★★★
        write_status_and_verify(
            ws,
            matched_row,
            status_col,
            f"{gender}一般點名表"
        )

        return True

    except Exception as e:

        raise Exception(
            f"{gender}一般點名表更新失敗：{e}"
        )


# =========================================================
# 主畫面
# =========================================================

def show_makeup_rollcall():

    st.title("補點名單")

    # =====================================================
    # 登入資訊
    # =====================================================

    role = get_login_role()

    # =====================================================
    # 補點日期
    # =====================================================

    target_date = (
        get_makeup_target_date()
    )

    st.caption(
        f"補點日期：{target_date}"
    )

    # =====================================================
    # 讀取資料
    # =====================================================

    df = load_need_makeup_source()

    if df.empty:

        st.info(
            "目前沒有需要補點的人員"
        )

        return

    # =====================================================
    # 舍監 / 舍長不做管理宿舍篩選
    # =====================================================

    if (
        "舍監" not in role
        and "舍長" not in role
    ):

        df = filter_by_leader_scope(
            df
        )

    if df.empty:

        st.info(
            "目前沒有符合您管理範圍的補點人員。"
        )

        return

    # =====================================================
    # 顯示人數
    # =====================================================

    st.success(
        f"目前共有 {len(df)} 位需要補點"
    )

    # =====================================================
    # 排序
    # =====================================================

    sort_columns = []

    if "房號" in df.columns:
        sort_columns.append(
            "房號"
        )

    if "姓名" in df.columns:
        sort_columns.append(
            "姓名"
        )

    if sort_columns:

        df = df.sort_values(
            by=sort_columns,
            kind="stable"
        )

    # =====================================================
    # 顯示清單
    # =====================================================

    display_columns = [
        "日期",
        "宿舍",
        "床位",
        "房號",
        "學號",
        "班級",
        "姓名",
        "狀態",
        "性別",
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

    st.divider()

    # =====================================================
    # 選擇學生
    # =====================================================

    st.subheader(
        "確認補點"
    )

    option_map = {}

    for index, row in df.iterrows():

        sid = normalize_text(
            row.get(
                "學號",
                ""
            )
        )

        name = normalize_text(
            row.get(
                "姓名",
                ""
            )
        )

        room = normalize_text(
            row.get(
                "房號",
                ""
            )
        )

        gender_value = normalize_gender(
            row.get(
                "性別",
                ""
            )
        )

        label = (
            f"{room}｜"
            f"{name}｜"
            f"{sid}｜"
            f"{gender_value}"
        )

        option_map[label] = index

    if not option_map:

        st.info(
            "目前沒有可以選擇的補點人員。"
        )

        return

    selected_label = st.selectbox(
        "請選擇已完成補點的學生",
        options=list(
            option_map.keys()
        ),
        key="makeup_student_select"
    )

    selected_index = option_map[
        selected_label
    ]

    selected_row = df.loc[
        selected_index
    ]

    # =====================================================
    # 學生資料
    # =====================================================

    st.write(
        "### 學生資料"
    )

    info_col1, info_col2 = (
        st.columns(2)
    )

    with info_col1:

        st.write(
            f"**姓名：** "
            f"{selected_row.get('姓名', '')}"
        )

        st.write(
            f"**學號：** "
            f"{selected_row.get('學號', '')}"
        )

        st.write(
            f"**房號：** "
            f"{selected_row.get('房號', '')}"
        )

    with info_col2:

        st.write(
            f"**性別：** "
            f"{selected_row.get('性別', '')}"
        )

        st.write(
            f"**狀態：** "
            f"{selected_row.get('狀態', '')}"
        )

        st.write(
            f"**日期：** "
            f"{selected_row.get('日期', '')}"
        )

    st.divider()

    # =====================================================
    # 確認補點完成
    # =====================================================

    if st.button(
        "確認補點完成",
        type="primary",
        use_container_width=True,
        key="submit_makeup"
    ):

        try:

            target_row = (
                selected_row.to_dict()
            )

            # =================================================
            # 判斷學生性別
            # =================================================

            student_gender = (
                normalize_gender(
                    target_row.get(
                        "性別",
                        ""
                    )
                )
            )

            if student_gender not in [
                "女生",
                "男生"
            ]:

                raise Exception(
                    "無法判斷學生性別："
                    f"{student_gender}"
                )

            student_name = (
                normalize_text(
                    target_row.get(
                        "姓名",
                        ""
                    )
                )
            )

            student_sid = (
                normalize_text(
                    target_row.get(
                        "學號",
                        ""
                    )
                )
            )

            # =================================================
            # ① 統一點名總表
            # =================================================

            update_rollcall_status_to_makeup(
                target_row
            )

            # =================================================
            # ② 男女需補點表
            # =================================================

            update_need_makeup_status_to_done(
                student_gender,
                target_row
            )

            # =================================================
            # ③ 男女一般點名表
            # =================================================

            update_gender_rollcall_status(
                student_gender,
                target_row
            )

            # =================================================
            # 清除補點資料快取
            # =================================================

            load_need_makeup_source.clear()

            # =================================================
            # 成功
            # =================================================

            st.success(
                f"「{student_name}」補點完成！"
            )

            st.info(
                f"學號：{student_sid}\n\n"
                "統一點名總表、"
                f"{student_gender}需補點表、"
                f"{student_gender}一般點名表，"
                "「狀態」皆已更新為「已補點」。"
            )

            st.rerun()

        except Exception as e:

            st.error(
                f"補點更新失敗：{e}"
            )