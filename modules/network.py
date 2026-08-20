import re

import streamlit as st

from core.config import (
    NETWORK_81_URL,
    NETWORK_82_URL,
    NETWORK_83_URL,
)

from core.google_api import (
    open_sheet,
    get_worksheets,
    get_values,
)


# ==================================================
# 宿舍設定
# ==================================================

DORM_TO_BUILDING = {
    "女一": "81",
    "女二": "82",
    "女三": "83",
    "男一": "82",
    "男三": "83",
}


BUILDING_URLS = {
    "81": NETWORK_81_URL,
    "82": NETWORK_82_URL,
    "83": NETWORK_83_URL,
}


# ==================================================
# 名稱整理
# ==================================================

def normalize_dorm(value):

    value = (
        str(value)
        .strip()
        .replace("ㄧ", "一")
        .replace(" ", "")
        .replace("　", "")
        .replace("(涵青館)", "")
        .replace("（涵青館）", "")
    )

    if value.endswith("宿"):
        value = value[:-1]

    return value


def normalize_bed(value):

    return (
        str(value)
        .strip()
        .replace(" ", "")
        .replace("　", "")
    )


# ==================================================
# 拆宿舍設定
# ==================================================

def split_dorms(value):

    result = []

    for item in (
        str(value)
        .replace("，", ",")
        .split(",")
    ):

        dorm = normalize_dorm(
            item
        )

        if dorm in DORM_TO_BUILDING:
            result.append(
                dorm
            )

    return list(
        dict.fromkeys(
            result
        )
    )


# ==================================================
# 取得樓長可查詢宿舍
# ==================================================

def get_allowed_network_dorms():

    role = str(
        st.session_state.get(
            "role",
            ""
        )
    ).strip()

    # ==================================================
    # 只有樓長
    # ==================================================

    if role != "樓長":
        return []

    allowed = []

    for value in [
        st.session_state.get(
            "dorm",
            ""
        ),
        st.session_state.get(
            "manage_dorms",
            ""
        ),
        st.session_state.get(
            "winter_dorms",
            ""
        ),
        st.session_state.get(
            "summer_dorms",
            ""
        ),
    ]:

        allowed.extend(
            split_dorms(
                value
            )
        )

    return list(
        dict.fromkeys(
            allowed
        )
    )


# ==================================================
# 判斷工作表是否屬於宿舍
# ==================================================

def worksheet_matches_dorm(
    worksheet_title,
    dorm
):

    title = (
        str(worksheet_title)
        .strip()
        .replace(" ", "")
    )

    dorm = normalize_dorm(
        dorm
    )

    building = DORM_TO_BUILDING.get(
        dorm,
        ""
    )

    if not building:
        return False

    # ==================================================
    # 81宿
    # ==================================================

    if building == "81":

        # 81只有使用81資料來源
        return "81-" in title or "81宿" in title

    # ==================================================
    # 82宿
    #
    # 女二 = 女
    # 男一 = 男
    # ==================================================

    if building == "82":

        if dorm == "女二":
            return (
                "82-" in title
                and "女" in title
            )

        if dorm == "男一":
            return (
                "82-" in title
                and "男" in title
            )

    # ==================================================
    # 83宿
    #
    # 女三 = 女
    # 男三 = 男
    # ==================================================

    if building == "83":

        if dorm == "女三":
            return (
                "83-" in title
                and "女" in title
            )

        if dorm == "男三":
            return (
                "83-" in title
                and "男" in title
            )

    return False


# ==================================================
# 床位格式
# ==================================================

def is_bed_value(value):

    value = normalize_bed(
        value
    )

    # 例如：
    # 82201-1
    # 83303-4

    return bool(
        re.fullmatch(
            r"\d{5}-\d+",
            value
        )
    )


# ==================================================
# 查詢網路
# ==================================================

@st.cache_data(
    ttl=10,
    show_spinner=False
)
def find_network_account(
    dorm,
    target_bed
):

    dorm = normalize_dorm(
        dorm
    )

    target_bed = normalize_bed(
        target_bed
    )

    building = DORM_TO_BUILDING.get(
        dorm
    )

    if not building:
        return None

    url = BUILDING_URLS.get(
        building
    )

    if not url:
        return None

    try:

        spreadsheet = open_sheet(
            url
        )

        worksheets = get_worksheets(
            spreadsheet
        )

        # ==================================================
        # 只搜尋這個宿舍相符的工作表
        # ==================================================

        matched_worksheets = [
            ws
            for ws in worksheets
            if worksheet_matches_dorm(
                ws.title,
                dorm
            )
        ]

        # 如果工作表命名跟預期不同，
        # 至少限制在該棟試算表內搜尋
        if not matched_worksheets:
            matched_worksheets = worksheets

        for worksheet in matched_worksheets:

            # ==================================================
            # 只需要 A:E
            #
            # A 床位
            # B 帳號001
            # C 密碼001
            # D 帳號002
            # E 密碼002
            # ==================================================

            values = get_values(
                worksheet,
                "A:E"
            )

            for raw_row in values:

                row = list(
                    raw_row
                )

                while len(row) < 5:
                    row.append("")

                bed = normalize_bed(
                    row[0]
                )

                if not is_bed_value(
                    bed
                ):
                    continue

                if bed != target_bed:
                    continue

                return {
                    "床位": bed,
                    "帳號001": str(
                        row[1]
                    ).strip(),
                    "密碼001": str(
                        row[2]
                    ).strip(),
                    "帳號002": str(
                        row[3]
                    ).strip(),
                    "密碼002": str(
                        row[4]
                    ).strip(),
                    "工作表": worksheet.title,
                }

        return None

    except Exception as error:

        raise RuntimeError(
            f"網路資料讀取失敗：{error}"
        )


# ==================================================
# 主畫面
# ==================================================

def show_network():

    st.header(
        "網路查詢"
    )

    # ==================================================
    # 權限
    # ==================================================

    role = str(
        st.session_state.get(
            "role",
            ""
        )
    ).strip()

    if role != "樓長":

        st.warning(
            "僅樓長可使用網路查詢"
        )

        return

    allowed_dorms = (
        get_allowed_network_dorms()
    )

    if not allowed_dorms:

        st.warning(
            "目前沒有可查詢的宿舍"
        )

        return

    # ==================================================
    # 宿舍
    # ==================================================

    if len(allowed_dorms) == 1:

        dorm = allowed_dorms[0]

        st.info(
            f"目前宿舍：{dorm}宿"
        )

    else:

        dorm = st.selectbox(
            "宿舍",
            allowed_dorms,
            key="network_dorm"
        )

    # ==================================================
    # 查詢床位
    # ==================================================

    bed = st.text_input(
        "輸入床位",
        placeholder="例如：82201-1",
        key="network_bed_search"
    )

    search_clicked = st.button(
        "查詢網路帳號",
        key="network_search_btn",
        type="primary",
        use_container_width=True
    )

    if not search_clicked:
        return

    bed = normalize_bed(
        bed
    )

    if not bed:

        st.warning(
            "請輸入床位"
        )

        return

    if not is_bed_value(
        bed
    ):

        st.warning(
            "床位格式錯誤，例如：82201-1"
        )

        return

    # ==================================================
    # 房號權限再次確認
    # ==================================================

    building = DORM_TO_BUILDING.get(
        dorm,
        ""
    )

    if not bed.startswith(
        building
    ):

        st.error(
            "此床位不屬於你目前管理的宿舍"
        )

        return

    # ==================================================
    # 查詢
    # ==================================================

    try:

        with st.spinner(
            "正在查詢網路資料..."
        ):

            result = find_network_account(
                dorm,
                bed
            )

    except Exception as error:

        st.error(
            str(error)
        )

        return

    if not result:

        st.warning(
            "查無此床位的網路資料"
        )

        return

    # ==================================================
    # 查詢結果
    # ==================================================

    st.success(
        f"查詢成功：{result['床位']}"
    )

    st.subheader(
        "Hinet 撥接網路（含 WIFI 上網）"
    )

    col1, col2 = st.columns(
        2
    )

    with col1:

        st.text_input(
            "帳號001",
            value=result[
                "帳號001"
            ],
            disabled=True,
            key="network_account_001"
        )

    with col2:

        st.text_input(
            "密碼001",
            value=result[
                "密碼001"
            ],
            disabled=True,
            key="network_password_001"
        )

    st.subheader(
        '僅限 "WIFI" 上網'
    )

    col3, col4 = st.columns(
        2
    )

    with col3:

        st.text_input(
            "帳號002",
            value=result[
                "帳號002"
            ],
            disabled=True,
            key="network_account_002"
        )

    with col4:

        st.text_input(
            "密碼002",
            value=result[
                "密碼002"
            ],
            disabled=True,
            key="network_password_002"
        )