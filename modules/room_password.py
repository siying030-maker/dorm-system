import pandas as pd
import streamlit as st

from core.config import (
    UPPER_ROOM_PASSWORD,
    LOWER_ROOM_PASSWORD,
    WINTER_ROOM_PASSWORD,
    SUMMER_ROOM_PASSWORD,
)

from core.google_api import (
    open_sheet,
    get_worksheets,
    get_all_values,
    append_row,
    update_cell,
)


# ==================================================
# 密碼表試算表設定
# ==================================================

PASSWORD_SHEETS = {
    "上學期": UPPER_ROOM_PASSWORD,
    "下學期": LOWER_ROOM_PASSWORD,
    "寒假": WINTER_ROOM_PASSWORD,
    "暑假": SUMMER_ROOM_PASSWORD,
}


# ==================================================
# 宿舍房號前綴
# ==================================================

DORM_ROOM_PREFIX = {
    "女一": "81",
    "女二": "82",
    "女三": "83",
    "男一": "82",
    "男三": "83",
}


ALL_DORMS = [
    "女一",
    "女二",
    "女三",
    "男一",
    "男三",
]


# ==================================================
# 基本文字整理
# ==================================================

def normalize_dorm(value):
    """
    統一宿舍名稱，例如：
    女ㄧ → 女一
    女一空白 → 女一
    """

    return (
        str(value)
        .strip()
        .replace("ㄧ", "一")
        .replace("　", "")
        .replace(" ", "")
    )


def normalize_room(value):
    """
    統一房號格式。
    """

    value = (
        str(value)
        .strip()
        .replace(" ", "")
        .replace("　", "")
    )

    if value.endswith(".0"):
        value = value[:-2]

    if value.upper() in [
        "NAN",
        "NONE",
        "NA",
    ]:
        return ""

    return value


def split_dorms(value):
    """
    將：
    女一,女二
    女一，女二

    轉成：
    ["女一", "女二"]
    """

    result = []

    for item in (
        str(value)
        .replace("，", ",")
        .split(",")
    ):

        item = normalize_dorm(
            item
        )

        if (
            item
            and item in ALL_DORMS
        ):
            result.append(
                item
            )

    return list(
        dict.fromkeys(
            result
        )
    )


# ==================================================
# 找到指定宿舍 Worksheet
# ==================================================

def get_password_worksheet(
    spreadsheet,
    dorm
):
    """
    不直接使用 spreadsheet.worksheet("女一")，
    避免 Sheet 名稱存在空白或「ㄧ / 一」差異。

    會將所有 Sheet 名稱正規化後再比對。
    """

    dorm = normalize_dorm(
        dorm
    )

    worksheets = get_worksheets(
        spreadsheet
    )

    for worksheet in worksheets:

        worksheet_title = normalize_dorm(
            worksheet.title
        )

        if worksheet_title == dorm:
            return worksheet

    actual_titles = [
        worksheet.title
        for worksheet in worksheets
    ]

    raise ValueError(
        f"找不到宿舍工作表「{dorm}」。"
        f"目前試算表的工作表為："
        f"{'、'.join(actual_titles)}"
    )


# ==================================================
# 取得登入者可以使用的密碼表類型
# ==================================================

def get_allowed_password_terms():

    role = st.session_state.get(
        "role",
        ""
    )

    # ==============================================
    # 行政 / 生輔工讀
    # 四種全部可以查詢
    # ==============================================

    if role in [
        "行政",
        "生輔工讀",
        "舍監"
    ]:

        return [
            "上學期",
            "下學期",
            "寒假",
            "暑假",
        ]

    # ==============================================
    # 樓長
    # ==============================================

    if role == "樓長":

    # ==============================================
    # 取得寒假 / 暑假樓長設定
    # ==============================================

        winter_dorms = str(
            st.session_state.get(
                "winter_dorms",
                ""
            )
        ).strip()

        summer_dorms = str(
            st.session_state.get(
                "summer_dorms",
                ""
            )
        ).strip()

        # ==============================================
        # 寒暑假樓長
        # 有寒假 / 暑假設定時
        # 只顯示對應假期，不顯示上下學期
        # ==============================================

        holiday_terms = []

        if winter_dorms:
            holiday_terms.append("寒假")

        if summer_dorms:
            holiday_terms.append("暑假")

        if holiday_terms:
            return holiday_terms

        # ==============================================
        # 一般學期樓長
        # 沒有寒暑假設定才顯示上下學期
        # ==============================================

        return [
            "上學期",
            "下學期",
            ]

    return []


# ==================================================
# 依密碼表類型取得可使用宿舍
# ==================================================

def get_allowed_dorms(
    password_term
):

    role = st.session_state.get(
        "role",
        ""
    )

    # ==============================================
    # 行政 / 生輔工讀
    # 可查詢所有宿舍
    # ==============================================

    if role in [
        "行政",
        "生輔工讀",
        "舍監"
    ]:

        return ALL_DORMS.copy()

    # ==============================================
    # 只有樓長繼續往下
    # ==============================================

    if role != "樓長":
        return []

    # ==============================================
    # 寒假
    # 只使用 winter_dorms
    # ==============================================

    if password_term == "寒假":

        winter_dorms = (
            st.session_state.get(
                "winter_dorms",
                ""
            )
        )

        return split_dorms(
            winter_dorms
        )

    # ==============================================
    # 暑假
    # 只使用 summer_dorms
    # ==============================================

    if password_term == "暑假":

        summer_dorms = (
            st.session_state.get(
                "summer_dorms",
                ""
            )
        )

        return split_dorms(
            summer_dorms
        )

    # ==============================================
    # 上學期 / 下學期
    # 使用 manage_dorms
    # ==============================================

    manage_dorms = (
        st.session_state.get(
            "manage_dorms",
            ""
        )
    )

    if manage_dorms:

        allowed = split_dorms(
            manage_dorms
        )

        if allowed:
            return allowed

    # ==============================================
    # manage_dorms 沒資料時
    # fallback 到 dorm
    # ==============================================

    dorm = normalize_dorm(
        st.session_state.get(
            "dorm",
            ""
        )
    )

    if (
        dorm
        and dorm in ALL_DORMS
    ):

        return [
            dorm
        ]

    return []


# ==================================================
# 是否可以寫入密碼
# ==================================================

def can_write_password():
    """
    只有樓長可以新增 / 修改密碼。

    行政、生輔工讀只能查詢。
    """

    return (
        st.session_state.get(
            "role",
            ""
        )
        ==
        "樓長"
    )


# ==================================================
# 取得密碼表網址
# ==================================================

def get_password_sheet_url(
    password_term
):

    return PASSWORD_SHEETS.get(
        password_term,
        ""
    )


# ==================================================
# 讀取房間密碼
# ==================================================

@st.cache_data(
    ttl=10,
    show_spinner=False
)
def load_room_passwords(
    password_term,
    dorm
):

    dorm = normalize_dorm(
        dorm
    )

    if dorm not in ALL_DORMS:

        return pd.DataFrame(
            columns=[
                "房號",
                "密碼",
            ]
        )

    url = get_password_sheet_url(
        password_term
    )

    if not url:

        return pd.DataFrame(
            columns=[
                "房號",
                "密碼",
            ]
        )

    try:

        spreadsheet = open_sheet(
            url
        )

        worksheet = get_password_worksheet(
            spreadsheet,
            dorm
        )

        values = get_all_values(
            worksheet
        )

        # ==============================================
        # 完全沒有資料
        # ==============================================

        if not values:

            return pd.DataFrame(
                columns=[
                    "房號",
                    "密碼",
                ]
            )

        # ==============================================
        # 標題
        # ==============================================

        headers = [
            str(value).strip()
            for value in values[0]
        ]

        if len(headers) < 2:

            return pd.DataFrame(
                columns=[
                    "房號",
                    "密碼",
                ]
            )

        # ==============================================
        # DataFrame
        # ==============================================

        df = pd.DataFrame(
            values[1:],
            columns=headers
        )

        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
        )

        # ==============================================
        # 必須存在房號 / 密碼
        # ==============================================

        if (
            "房號" not in df.columns
            or
            "密碼" not in df.columns
        ):

            st.warning(
                f"{password_term} / {dorm} "
                "工作表必須有「房號」與「密碼」欄位"
            )

            return pd.DataFrame(
                columns=[
                    "房號",
                    "密碼",
                ]
            )

        df = df[
            [
                "房號",
                "密碼",
            ]
        ].copy()

        # ==============================================
        # 整理房號
        # ==============================================

        df["房號"] = (
            df["房號"]
            .astype(str)
            .map(normalize_room)
        )

        # 密碼不能轉數字
        # 避免 0012 被轉成 12
        df["密碼"] = (
            df["密碼"]
            .astype(str)
            .str.strip()
        )

        # 移除空房號
        df = df[
            df["房號"] != ""
        ].copy()

        return df.reset_index(
            drop=True
        )

    except Exception as error:

        st.error(
            f"讀取 {password_term} / "
            f"{dorm} 房間密碼失敗：{error}"
        )

        return pd.DataFrame(
            columns=[
                "房號",
                "密碼",
            ]
        )


# ==================================================
# 新增 / 修改密碼
# ==================================================

def save_room_password(
    password_term,
    dorm,
    room,
    password
):

    # ==============================================
    # 權限保險
    # ==============================================

    if not can_write_password():

        raise PermissionError(
            "目前帳號沒有修改密碼的權限"
        )

    dorm = normalize_dorm(
        dorm
    )

    room = normalize_room(
        room
    )

    password = str(
        password
    ).strip()

    # ==============================================
    # 驗證宿舍
    # ==============================================

    if dorm not in ALL_DORMS:

        raise ValueError(
            "宿舍設定錯誤"
        )

    # ==============================================
    # 驗證房號
    # ==============================================

    if room == "":

        raise ValueError(
            "請輸入房號"
        )

    # ==============================================
    # 驗證密碼
    # ==============================================

    if password == "":

        raise ValueError(
            "請輸入密碼"
        )

    # ==============================================
    # 驗證房號前綴
    # ==============================================

    expected_prefix = (
        DORM_ROOM_PREFIX.get(
            dorm,
            ""
        )
    )

    if (
        expected_prefix
        and
        not room.startswith(
            expected_prefix
        )
    ):

        raise ValueError(
            f"{dorm} 房號應以 "
            f"{expected_prefix} 開頭。"
            f"例如：{expected_prefix}101"
        )

    # ==============================================
    # 取得試算表
    # ==============================================

    url = get_password_sheet_url(
        password_term
    )

    if not url:

        raise ValueError(
            f"找不到「{password_term}」密碼表設定"
        )

    spreadsheet = open_sheet(
        url
    )

    worksheet = get_password_worksheet(
        spreadsheet,
        dorm
    )

    values = get_all_values(
        worksheet
    )

    # ==============================================
    # Sheet 完全空白
    # ==============================================

    if not values:

        append_row(
            worksheet,
            [
                "房號",
                "密碼",
            ]
        )

        values = [
            [
                "房號",
                "密碼",
            ]
        ]

    # ==============================================
    # 標題
    # ==============================================

    headers = [
        str(value).strip()
        for value in values[0]
    ]

    if (
        "房號" not in headers
        or
        "密碼" not in headers
    ):

        raise ValueError(
            f"{password_term} / {dorm} "
            "工作表必須有「房號」與「密碼」欄位"
        )

    room_col = (
        headers.index(
            "房號"
        )
        +
        1
    )

    password_col = (
        headers.index(
            "密碼"
        )
        +
        1
    )

    # ==============================================
    # 房號已存在 → 修改密碼
    # ==============================================

    for row_index, row in enumerate(
        values[1:],
        start=2
    ):

        existing_room = ""

        if len(row) >= room_col:

            existing_room = normalize_room(
                row[
                    room_col - 1
                ]
            )

        if existing_room == room:

            update_cell(
                worksheet,
                row_index,
                password_col,
                password
            )

            # 清除密碼表快取
            load_room_passwords.clear()

            return "updated"

    # ==============================================
    # 房號不存在 → 新增
    # ==============================================

    new_row = [
        ""
    ] * max(
        len(headers),
        2
    )

    new_row[
        room_col - 1
    ] = room

    new_row[
        password_col - 1
    ] = password

    append_row(
        worksheet,
        new_row
    )

    load_room_passwords.clear()

    return "created"


# ==================================================
# 主畫面
# ==================================================

def show_room_password():

    st.header(
        "密碼表"
    )

    role = st.session_state.get(
        "role",
        ""
    )

    # ==============================================
    # 可使用的密碼表類型
    # ==============================================

    allowed_terms = (
        get_allowed_password_terms()
    )

    if not allowed_terms:

        st.warning(
            "目前沒有密碼表權限"
        )

        return

    password_term = st.selectbox(
        "密碼表類型",
        allowed_terms,
        key="room_password_term",
    )

    # ==============================================
    # 可使用宿舍
    # ==============================================

    allowed_dorms = get_allowed_dorms(
        password_term
    )

    if not allowed_dorms:

        st.warning(
            f"沒有「{password_term}」密碼表的宿舍權限"
        )

        return

    dorm = st.selectbox(
        "宿舍",
        allowed_dorms,
        key="room_password_dorm",
    )

    prefix = (
        DORM_ROOM_PREFIX.get(
            dorm,
            ""
        )
    )

    st.caption(
        f"房號規則：{dorm} 房號以 "
        f"{prefix} 開頭"
    )

    # ==============================================
    # 重新整理
    # ==============================================

    if st.button(
        "重新整理密碼表",
        key="refresh_room_password",
    ):

        load_room_passwords.clear()

        st.rerun()

    # ==============================================
    # 查詢
    # ==============================================

    st.subheader(
        "查詢房間密碼"
    )

    search_room = st.text_input(
        "輸入房號查詢",
        key="room_password_search",
        placeholder=(
            f"例如：{prefix}101"
        ),
    )

    # ==============================================
    # 載入資料
    # ==============================================

    df = load_room_passwords(
        password_term,
        dorm
    )

    # ==============================================
    # 搜尋
    # ==============================================

    if search_room:

        target_room = normalize_room(
            search_room
        )

        result = df[
            df["房號"] == target_room
        ].copy()

        if result.empty:

            st.warning(
                "查無此房號"
            )

        else:

            st.success(
                "查詢成功"
            )

            st.dataframe(
                result[
                    [
                        "房號",
                        "密碼",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

    else:

        st.info(
            "請輸入房號進行查詢"
        )

    # ==============================================
    # 行政、生輔工讀只能查詢
    # ==============================================

    if not can_write_password():

        st.divider()

        if role == "行政":

            st.caption(
                "行政權限："
                "可查詢上學期、下學期、寒假、暑假密碼表，"
                "不可修改密碼。"
            )

        elif role == "生輔工讀":

            st.caption(
                "生輔工讀權限："
                "可查詢上學期、下學期、寒假、暑假密碼表，"
                "不可修改密碼。"
            )

        elif role == "舍監":
        
                    st.caption(
                        "舍監權限："
                        "可查詢上學期、下學期、寒假、暑假密碼表，"
                        "不可修改密碼。"
                    )

        return

    # ==============================================
    # 樓長新增 / 修改
    # ==============================================

    st.divider()

    st.subheader(
        "新增 / 修改房間密碼"
    )

    with st.form(
        "room_password_save_form",
        clear_on_submit=False
    ):

        room = st.text_input(
            "房號",
            key="room_password_write_room",
            placeholder=(
                f"例如：{prefix}101"
            ),
        )

        password = st.text_input(
            "密碼",
            key="room_password_write_password",
        )

        submitted = (
            st.form_submit_button(
                "儲存密碼",
                use_container_width=True,
            )
        )

    # ==============================================
    # 儲存
    # ==============================================

    if submitted:

        try:

            action = save_room_password(
                password_term,
                dorm,
                room,
                password,
            )

            if action == "updated":

                st.success(
                    f"{password_term} / "
                    f"{dorm} / "
                    f"{normalize_room(room)} "
                    "密碼已更新。"
                )

            elif action == "created":

                st.success(
                    f"{password_term} / "
                    f"{dorm} / "
                    f"{normalize_room(room)} "
                    "密碼已新增。"
                )

            # 清快取
            load_room_passwords.clear()

            st.rerun()

        except Exception as error:

            st.error(
                f"儲存失敗：{error}"
            )