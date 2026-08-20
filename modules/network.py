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
# 宿名整理
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


# ==================================================
# 床位 / 房號整理
# ==================================================

def normalize_value(value):

    return (
        str(value)
        .strip()
        .replace(" ", "")
        .replace("　", "")
    )


# ==================================================
# 拆分多宿舍
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
# 樓長權限
# ==================================================

def get_allowed_network_dorms():

    role = str(
        st.session_state.get(
            "role",
            ""
        )
    ).strip()

    # 只有樓長
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
# 判斷工作表是否屬於登入宿舍
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
    # 女一
    # ==================================================

    if building == "81":

        return (
            "81-" in title
            or
            "81宿" in title
        )

    # ==================================================
    # 82宿
    # 女二 / 男一
    # ==================================================

    if building == "82":

        if dorm == "女二":

            return (
                "82-" in title
                and
                "女" in title
            )

        if dorm == "男一":

            return (
                "82-" in title
                and
                "男" in title
            )

    # ==================================================
    # 83宿
    # 女三 / 男三
    # ==================================================

    if building == "83":

        if dorm == "女三":

            return (
                "83-" in title
                and
                "女" in title
            )

        if dorm == "男三":

            return (
                "83-" in title
                and
                "男" in title
            )

    return False


# ==================================================
# 房號格式
# ==================================================

def is_room_number(value):

    value = normalize_value(
        value
    )

    # 例如：
    # 81701
    # 82201
    # 83303

    return bool(
        re.fullmatch(
            r"\d{5}",
            value
        )
    )


# ==================================================
# 床位格式
# ==================================================

def is_bed_number(value):

    value = normalize_value(
        value
    )

    # 例如：
    # 81701-1
    # 82201-4

    return bool(
        re.fullmatch(
            r"\d{5}-\d+",
            value
        )
    )


# ==================================================
# 查詢整個房間
# ==================================================

@st.cache_data(
    ttl=10,
    show_spinner=False
)
def find_network_room(
    dorm,
    room_number
):

    dorm = normalize_dorm(
        dorm
    )

    room_number = normalize_value(
        room_number
    )

    building = DORM_TO_BUILDING.get(
        dorm
    )

    if not building:

        return []

    url = BUILDING_URLS.get(
        building
    )

    if not url:

        return []

    results = []

    try:

        spreadsheet = open_sheet(
            url
        )

        worksheets = get_worksheets(
            spreadsheet
        )

        # ==================================================
        # 只搜尋目前宿舍相關的 sheet
        # ==================================================

        matched_worksheets = [
            ws
            for ws in worksheets
            if worksheet_matches_dorm(
                ws.title,
                dorm
            )
        ]

        # 如果名稱比對不到
        # 才退回整份試算表搜尋
        if not matched_worksheets:

            matched_worksheets = (
                worksheets
            )

        # ==================================================
        # 搜尋所有符合這個房號的床位
        # ==================================================

        for worksheet in matched_worksheets:

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

                bed = normalize_value(
                    row[0]
                )

                # 不是床位資料
                if not is_bed_number(
                    bed
                ):

                    continue

                # ==================================================
                # 81701-1
                # 81701-2
                #
                # 取 "-" 前面的 81701
                # ==================================================

                bed_room = (
                    bed
                    .split("-")[0]
                )

                if (
                    bed_room
                    !=
                    room_number
                ):

                    continue

                results.append(
                    {
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
                        "工作表": (
                            worksheet.title
                        ),
                    }
                )

        # ==================================================
        # 床位排序
        # ==================================================

        results = sorted(
            results,
            key=lambda item: (
                item.get(
                    "床位",
                    ""
                )
            )
        )

        return results

    except Exception as error:

        raise RuntimeError(
            f"網路資料讀取失敗：{error}"
        )


# ==================================================
# 顯示單一帳號 / 密碼
# ==================================================

def show_value_card(
    title,
    value
):

    value = str(
        value
    ).strip()

    if not value:

        value = "無資料"

    st.markdown(
        f"""
        <div style="
            border:1px solid #d9d9d9;
            border-radius:10px;
            padding:16px 18px;
            margin-bottom:8px;
            background-color:rgba(240,242,246,0.65);
        ">
            <div style="
                font-size:15px;
                opacity:0.7;
                margin-bottom:5px;
            ">
                {title}
            </div>

            <div style="
                font-size:25px;
                font-weight:700;
                letter-spacing:1px;
                word-break:break-all;
            ">
                {value}
            </div>
        </div>
        """,
        unsafe_allow_html=True
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
    # 房號
    # ==================================================

    room_number = st.text_input(
        "輸入房號",
        placeholder="例如：81701",
        key="network_room_search"
    )

    search_clicked = st.button(
        "查詢整間房間網路資料",
        key="network_room_search_btn",
        type="primary",
        use_container_width=True
    )

    if not search_clicked:

        return

    room_number = normalize_value(
        room_number
    )

    # ==================================================
    # 驗證
    # ==================================================

    if not room_number:

        st.warning(
            "請輸入房號"
        )

        return

    if not is_room_number(
        room_number
    ):

        st.warning(
            "請輸入完整房號，例如：81701"
        )

        return

    # ==================================================
    # 棟別驗證
    # ==================================================

    building = DORM_TO_BUILDING.get(
        dorm,
        ""
    )

    if not room_number.startswith(
        building
    ):

        st.error(
            "此房號不屬於你目前管理的宿舍"
        )

        return

    # ==================================================
    # 查詢
    # ==================================================

    try:

        with st.spinner(
            "正在查詢整個房間..."
        ):

            results = (
                find_network_room(
                    dorm,
                    room_number
                )
            )

    except Exception as error:

        st.error(
            str(error)
        )

        return

    # ==================================================
    # 查無資料
    # ==================================================

    if not results:

        st.warning(
            f"查無房號 {room_number} 的網路資料"
        )

        return

    # ==================================================
    # 查詢結果
    # ==================================================

    st.success(
        f"查詢成功：{room_number} "
        f"共 {len(results)} 個床位"
    )

    st.divider()

    # ==================================================
    # 每個床位
    # ==================================================

    for result in results:

        st.subheader(
            f"🛏️ 床位 {result['床位']}"
        )

        # ==================================================
        # Hinet
        # ==================================================

        st.markdown(
            "### 🌐 Hinet 撥接網路（含 WIFI 上網）"
        )

        col1, col2 = st.columns(
            2
        )

        with col1:

            show_value_card(
                "帳號001",
                result[
                    "帳號001"
                ]
            )

        with col2:

            show_value_card(
                "密碼001",
                result[
                    "密碼001"
                ]
            )

        # ==================================================
        # WIFI
        # ==================================================

        st.markdown(
            '### 📶 僅限 WIFI 上網'
        )

        col3, col4 = st.columns(
            2
        )

        with col3:

            show_value_card(
                "帳號002",
                result[
                    "帳號002"
                ]
            )

        with col4:

            show_value_card(
                "密碼002",
                result[
                    "密碼002"
                ]
            )

        st.divider()