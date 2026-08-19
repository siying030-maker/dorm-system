import pandas as pd
import streamlit as st

from core.config import CHECKOUT_RESERVATION_URL

from core.google_api import (
    open_sheet,
    get_worksheet,
    get_all_values,
)


# ==================================================
# 宿舍名稱
# ==================================================

ALL_DORMS = [
    "女一",
    "女二",
    "女三",
    "男一",
    "男三",
]


# ==================================================
# 文字整理
# ==================================================

def normalize_dorm(value):

    return (
        str(value)
        .strip()
        .replace("ㄧ", "一")
        .replace("宿", "")
        .replace("(涵青館)", "")
        .replace("（涵青館）", "")
        .replace(" ", "")
        .replace("　", "")
    )


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
# 權限：可以看到哪些宿舍
# ==================================================

def get_allowed_checkout_dorms():

    role = st.session_state.get(
        "role",
        ""
    )

    supervisor_type = st.session_state.get(
        "supervisor_type",
        ""
    )

    # ==============================================
    # 行政
    # ==============================================

    if role == "行政":

        return ALL_DORMS.copy()

    # ==============================================
    # 舍監
    # ==============================================

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

    # ==============================================
    # 樓長
    # ==============================================

    if role == "樓長":

        result = []

        # 一般學期宿舍
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

            result.extend(
                split_dorms(
                    value
                )
            )

        return list(
            dict.fromkeys(
                result
            )
        )

    return []


# ==================================================
# 讀取單一宿舍離宿資料
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

    if dorm not in ALL_DORMS:

        return pd.DataFrame()

    try:

        ss = open_sheet(
            CHECKOUT_RESERVATION_URL
        )

        ws = get_worksheet(
            ss,
            dorm
        )

        values = get_all_values(
            ws
        )

        if len(values) <= 1:

            return pd.DataFrame(
                columns=[
                    "房號",
                    "姓名",
                    "離宿日期",
                    "離宿時間",
                ]
            )

        headers = [
            str(value).strip()
            for value in values[0]
        ]

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
        # 只保留指定欄位
        # ==============================================

        wanted_columns = [
            "房號",
            "姓名",
            "離宿日期",
            "離宿時間",
        ]

        available_columns = [
            column
            for column in wanted_columns
            if column in df.columns
        ]

        if not available_columns:

            return pd.DataFrame()

        df = df[
            available_columns
        ].copy()

        # ==============================================
        # 清除空白資料
        # ==============================================

        if "房號" in df.columns:

            df["房號"] = (
                df["房號"]
                .astype(str)
                .str.strip()
            )

        if "姓名" in df.columns:

            df["姓名"] = (
                df["姓名"]
                .astype(str)
                .str.strip()
            )

        if "房號" in df.columns:

            df = df[
                df["房號"] != ""
            ].copy()

        if "姓名" in df.columns:

            df = df[
                df["姓名"] != ""
            ].copy()

        # ==============================================
        # 日期排序
        # ==============================================

        if "離宿日期" in df.columns:

            df["_date"] = pd.to_datetime(
                df["離宿日期"],
                errors="coerce"
            )

            df = df.sort_values(
                by=[
                    "_date",
                    "離宿時間",
                ]
                if "離宿時間" in df.columns
                else ["_date"],
                ascending=True
            )

            df = df.drop(
                columns=["_date"],
                errors="ignore"
            )

        return df.reset_index(
            drop=True
        )

    except Exception as error:

        st.warning(
            f"{dorm} 離宿資料讀取失敗：{error}"
        )

        return pd.DataFrame()


# ==================================================
# 顯示離宿
# ==================================================

def show_checkout():

    st.header(
        "離宿"
    )

    allowed_dorms = (
        get_allowed_checkout_dorms()
    )

    if not allowed_dorms:

        st.warning(
            "目前沒有離宿資料權限"
        )

        return

    dorm = st.selectbox(
        "宿舍",
        allowed_dorms,
        key="checkout_dorm"
    )

    # ==============================================
    # 重新整理
    # ==============================================

    if st.button(
        "重新整理離宿資料",
        key="refresh_checkout"
    ):

        load_checkout_data.clear()

        st.rerun()

    # ==============================================
    # 自動顯示資料
    # ==============================================

    df = load_checkout_data(
        dorm
    )

    if df.empty:

        st.info(
            f"{dorm}目前沒有離宿預約"
        )

        return

    # ==============================================
    # 搜尋
    # ==============================================

    search = st.text_input(
        "搜尋房號 / 姓名",
        key="checkout_search"
    )

    if search:

        search = str(
            search
        ).strip()

        condition = pd.Series(
            False,
            index=df.index
        )

        for column in [
            "房號",
            "姓名",
        ]:

            if column in df.columns:

                condition = (
                    condition
                    |
                    df[column]
                    .astype(str)
                    .str.contains(
                        search,
                        na=False
                    )
                )

        df = df[
            condition
        ].copy()

    if df.empty:

        st.info(
            "查無符合條件的離宿預約"
        )

        return

    st.success(
        f"{dorm}目前共有 {len(df)} 筆離宿預約"
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )