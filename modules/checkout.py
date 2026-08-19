import pandas as pd
import streamlit as st

from core.config import (
    CHECKOUT_RESERVATION_URL,
)

from core.google_api import (
    open_sheet,
    get_worksheet,
    get_all_values,
)


# ==================================================
# 宿舍設定
# ==================================================

ALL_DORMS = [
    "女一",
    "女二",
    "女三",
    "男一",
    "男三",
]


# ==================================================
# 宿舍名稱整理
# ==================================================

def normalize_dorm(value):

    value = (
        str(value)
        .strip()
        .replace("ㄧ", "一")
        .replace("　", "")
        .replace(" ", "")
    )

    # ==============================================
    # 涵青館名稱
    # ==============================================

    value = (
        value
        .replace("(涵青館)", "")
        .replace("（涵青館）", "")
    )

    # ==============================================
    # 女一宿 → 女一
    # 男三宿 → 男三
    # ==============================================

    if value.endswith("宿"):
        value = value[:-1]

    return value


# ==================================================
# 拆分多個宿舍
# ==================================================

def split_dorms(value):

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
            and
            item in ALL_DORMS
        ):

            result.append(
                item
            )

    # 去除重複
    return list(
        dict.fromkeys(
            result
        )
    )


# ==================================================
# 取得登入者可以看的宿舍
# ==================================================

def get_allowed_checkout_dorms():

    role = str(
        st.session_state.get(
            "role",
            ""
        )
    ).strip()

    supervisor_type = str(
        st.session_state.get(
            "supervisor_type",
            ""
        )
    ).strip()

    # ==================================================
    # 行政
    # ==================================================

    if role == "行政":

        return ALL_DORMS.copy()

    # ==================================================
    # 舍監
    # ==================================================

    if role == "舍監":

        if supervisor_type == "女舍監":

            return [
                "女一",
                "女二",
                "女三",
            ]

        if supervisor_type == "男舍監":

            return [
                "男一",
                "男三",
            ]

        return []

    # ==================================================
    # 樓長
    # ==================================================

    if role == "樓長":

        allowed = []

        # ==============================================
        # 一般學期宿舍
        # ==============================================

        for value in [
            st.session_state.get(
                "manage_dorms",
                ""
            ),
            st.session_state.get(
                "dorm",
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
    # 其他角色
    # ==================================================

    return []


# ==================================================
# 清理房號
# ==================================================

def normalize_room(value):

    value = str(
        value
    ).strip()

    value = (
        value
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


# ==================================================
# 清理文字
# ==================================================

def normalize_text(value):

    value = str(
        value
    ).strip()

    if value.upper() in [
        "NAN",
        "NONE",
        "NA",
    ]:
        return ""

    return value


# ==================================================
# 讀取離宿資料
# ==================================================

@st.cache_data(
    ttl=10,
    show_spinner=False
)
def load_checkout_data(
    dorm
):

    dorm = normalize_dorm(
        dorm
    )

    # ==================================================
    # 驗證宿舍
    # ==================================================

    if dorm not in ALL_DORMS:

        return pd.DataFrame(
            columns=[
                "房號",
                "姓名",
                "離宿日期",
                "離宿時間",
            ]
        )

    try:

        # ==================================================
        # 開啟離宿預約試算表
        # ==================================================

        spreadsheet = open_sheet(
            CHECKOUT_RESERVATION_URL
        )

        # ==================================================
        # 每個宿舍有自己的 Sheet
        #
        # 女一
        # 女二
        # 女三
        # 男一
        # 男三
        # ==================================================

        worksheet = get_worksheet(
            spreadsheet,
            dorm
        )

        values = get_all_values(
            worksheet
        )

        # ==================================================
        # 沒資料
        # ==================================================

        if len(values) <= 1:

            return pd.DataFrame(
                columns=[
                    "房號",
                    "姓名",
                    "離宿日期",
                    "離宿時間",
                ]
            )

        # ==================================================
        # 重要：
        #
        # 不使用 Google Sheet 第一列作為 DataFrame 欄名
        #
        # 因為之前你的試算表有：
        #
        # 房號
        # 姓名
        # 離宿時間
        # 離宿時間
        #
        # 會造成 Duplicate column names
        #
        # 所以固定：
        #
        # A = 房號
        # B = 姓名
        # C = 離宿日期
        # D = 離宿時間
        # ==================================================

        rows = []

        for raw_row in values[1:]:

            row = list(
                raw_row
            )

            # ==============================================
            # 至少補到 4 欄
            # ==============================================

            while len(row) < 4:
                row.append("")

            room = normalize_room(
                row[0]
            )

            name = normalize_text(
                row[1]
            )

            checkout_date = normalize_text(
                row[2]
            )

            checkout_time = normalize_text(
                row[3]
            )

            # ==============================================
            # 完全空白列略過
            # ==============================================

            if (
                room == ""
                and
                name == ""
                and
                checkout_date == ""
                and
                checkout_time == ""
            ):
                continue

            # ==============================================
            # 至少需要房號或姓名
            # ==============================================

            if (
                room == ""
                and
                name == ""
            ):
                continue

            rows.append(
                {
                    "房號": room,
                    "姓名": name,
                    "離宿日期": checkout_date,
                    "離宿時間": checkout_time,
                }
            )

        # ==================================================
        # 沒有有效資料
        # ==================================================

        if not rows:

            return pd.DataFrame(
                columns=[
                    "房號",
                    "姓名",
                    "離宿日期",
                    "離宿時間",
                ]
            )

        # ==================================================
        # 建立 DataFrame
        # ==================================================

        df = pd.DataFrame(
            rows,
            columns=[
                "房號",
                "姓名",
                "離宿日期",
                "離宿時間",
            ]
        )

        # ==================================================
        # 日期轉換，只拿來排序
        # ==================================================

        df["_排序日期"] = pd.to_datetime(
            df["離宿日期"],
            errors="coerce"
        )

        today = pd.Timestamp.now().normalize()

        df = df[
            df["_排序日期"].notna()
            &
            (df["_排序日期"] >= today)
        ].copy()

        # ==================================================
        # 時間也建立排序欄
        # ==================================================

        df["_排序時間"] = pd.to_datetime(
            df["離宿時間"],
            format="%H:%M",
            errors="coerce"
        )

        # ==================================================
        # 日期 → 時間排序
        # ==================================================

        df = df.sort_values(
            by=[
                "_排序日期",
                "_排序時間",
                "房號",
            ],
            ascending=[
                True,
                True,
                True,
            ],
            na_position="last"
        )

        # ==================================================
        # 移除排序用欄位
        # ==================================================

        df = df.drop(
            columns=[
                "_排序日期",
                "_排序時間",
            ],
            errors="ignore"
        )

        # ==================================================
        # 最後再次強制欄位順序
        # 防止 PyArrow Duplicate Column Error
        # ==================================================

        df = df[
            [
                "房號",
                "姓名",
                "離宿日期",
                "離宿時間",
            ]
        ].copy()

        df.columns = [
            "房號",
            "姓名",
            "離宿日期",
            "離宿時間",
        ]

        return df.reset_index(
            drop=True
        )

    except Exception as error:

        st.warning(
            f"{dorm} 離宿資料讀取失敗：{error}"
        )

        return pd.DataFrame(
            columns=[
                "房號",
                "姓名",
                "離宿日期",
                "離宿時間",
            ]
        )


# ==================================================
# 主畫面
# ==================================================

def show_checkout():

    st.header(
        "離宿"
    )

    # ==================================================
    # 權限
    # ==================================================

    allowed_dorms = (
        get_allowed_checkout_dorms()
    )

    if not allowed_dorms:

        st.warning(
            "目前沒有離宿資料權限"
        )

        return

    # ==================================================
    # 宿舍選擇
    # ==================================================

    dorm = st.selectbox(
        "宿舍",
        allowed_dorms,
        key="checkout_dorm"
    )

    # ==================================================
    # 重新整理
    # ==================================================

    if st.button(
        "重新整理離宿資料",
        key="refresh_checkout"
    ):

        load_checkout_data.clear()

        st.rerun()

    # ==================================================
    # 讀取資料
    # ==================================================

    with st.spinner(
        "正在讀取離宿資料..."
    ):

        df = load_checkout_data(
            dorm
        )

    # ==================================================
    # 沒有預約
    # ==================================================

    if df.empty:

        st.info(
            f"{dorm}目前沒有離宿預約"
        )

        return

    # ==================================================
    # 搜尋
    # ==================================================

    search = st.text_input(
        "搜尋房號 / 姓名",
        key="checkout_search"
    )

    if search:

        keyword = str(
            search
        ).strip()

        condition = pd.Series(
            False,
            index=df.index
        )

        # ==============================================
        # 房號
        # ==============================================

        if "房號" in df.columns:

            condition = (
                condition
                |
                df["房號"]
                .astype(str)
                .str.contains(
                    keyword,
                    na=False,
                    regex=False
                )
            )

        # ==============================================
        # 姓名
        # ==============================================

        if "姓名" in df.columns:

            condition = (
                condition
                |
                df["姓名"]
                .astype(str)
                .str.contains(
                    keyword,
                    na=False,
                    regex=False
                )
            )

        df = df[
            condition
        ].copy()

    # ==================================================
    # 搜尋後沒結果
    # ==================================================

    if df.empty:

        st.info(
            "查無符合條件的離宿預約"
        )

        return

    # ==================================================
    # 數量
    # ==================================================

    st.success(
        f"{dorm}目前共有 {len(df)} 筆離宿預約"
    )

    # ==================================================
    # 顯示資料
    # ==================================================

    display_df = df[
        [
            "房號",
            "姓名",
            "離宿日期",
            "離宿時間",
        ]
    ].copy()

    # 再次保險：欄名一定唯一
    display_df.columns = [
        "房號",
        "姓名",
        "離宿日期",
        "離宿時間",
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )