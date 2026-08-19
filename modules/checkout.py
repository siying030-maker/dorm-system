import pandas as pd
import streamlit as st

from core.config import (
    CHECKOUT_RESERVATION_URL,
)

from core.google_api import (
    open_sheet,
    get_worksheet,
    get_all_values,
    update_cell,
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

    value = (
        value
        .replace("(涵青館)", "")
        .replace("（涵青館）", "")
    )

    if value.endswith("宿"):
        value = value[:-1]

    return value


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
# 房號整理
# ==================================================

def normalize_room(value):

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


# ==================================================
# 一般文字整理
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
# 權限：可查看哪些宿舍
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

    return []


# ==================================================
# 是否可修改檢查狀態
# ==================================================

def can_update_checkout_check():

    role = str(
        st.session_state.get(
            "role",
            ""
        )
    ).strip()

    # 目前設定：只有樓長可以勾選檢查
    return role == "樓長"


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

    if dorm not in ALL_DORMS:

        return pd.DataFrame(
            columns=[
                "試算表列",
                "房號",
                "姓名",
                "離宿日期",
                "離宿時間",
                "檢查",
            ]
        )

    try:

        # ==================================================
        # 開啟試算表
        # ==================================================

        spreadsheet = open_sheet(
            CHECKOUT_RESERVATION_URL
        )

        worksheet = get_worksheet(
            spreadsheet,
            dorm
        )

        values = get_all_values(
            worksheet
        )

        if len(values) <= 1:

            return pd.DataFrame(
                columns=[
                    "試算表列",
                    "房號",
                    "姓名",
                    "離宿日期",
                    "離宿時間",
                    "檢查",
                ]
            )

        rows = []

        # ==================================================
        # 固定欄位
        #
        # A = 房號
        # B = 姓名
        # C = 離宿日期
        # D = 離宿時間
        # E = 檢查
        # ==================================================

        for sheet_row, raw_row in enumerate(
            values[1:],
            start=2
        ):

            row = list(
                raw_row
            )

            while len(row) < 5:
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

            check_status = normalize_text(
                row[4]
            )

            # ==============================================
            # 空白列略過
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

            if (
                room == ""
                and
                name == ""
            ):
                continue

            rows.append(
                {
                    "試算表列": sheet_row,
                    "房號": room,
                    "姓名": name,
                    "離宿日期": checkout_date,
                    "離宿時間": checkout_time,
                    "檢查": check_status,
                }
            )

        # ==================================================
        # 沒資料
        # ==================================================

        if not rows:

            return pd.DataFrame(
                columns=[
                    "試算表列",
                    "房號",
                    "姓名",
                    "離宿日期",
                    "離宿時間",
                    "檢查",
                ]
            )

        df = pd.DataFrame(
            rows
        )

        # ==================================================
        # 日期轉換
        # ==================================================

        df["_排序日期"] = pd.to_datetime(
            df["離宿日期"],
            errors="coerce"
        )

        # ==================================================
        # 只顯示今天～未來
        #
        # 例如：
        # 今天 8/19
        #
        # 8/18 ❌
        # 8/19 ✅
        # 8/20 ✅
        # ==================================================

        today = pd.Timestamp.now().normalize()

        df = df[
            df["_排序日期"].notna()
            &
            (
                df["_排序日期"]
                >=
                today
            )
        ].copy()

        if df.empty:

            return pd.DataFrame(
                columns=[
                    "試算表列",
                    "房號",
                    "姓名",
                    "離宿日期",
                    "離宿時間",
                    "檢查",
                ]
            )

        # ==================================================
        # 時間排序
        # ==================================================

        df["_排序時間"] = pd.to_datetime(
            df["離宿時間"],
            format="%H:%M",
            errors="coerce"
        )

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

        df = df.drop(
            columns=[
                "_排序日期",
                "_排序時間",
            ],
            errors="ignore"
        )

        return df.reset_index(
            drop=True
        )

    except Exception as error:

        st.warning(
            f"{dorm} 離宿資料讀取失敗：{error}"
        )

        return pd.DataFrame(
            columns=[
                "試算表列",
                "房號",
                "姓名",
                "離宿日期",
                "離宿時間",
                "檢查",
            ]
        )


# ==================================================
# 更新檢查狀態
# ==================================================

def update_checkout_check(
    dorm,
    sheet_row,
    checked
):

    dorm = normalize_dorm(
        dorm
    )

    if dorm not in ALL_DORMS:

        raise ValueError(
            "宿舍設定錯誤"
        )

    spreadsheet = open_sheet(
        CHECKOUT_RESERVATION_URL
    )

    worksheet = get_worksheet(
        spreadsheet,
        dorm
    )

    # ==================================================
    # E欄 = 第5欄
    # ==================================================

    value = (
        "已檢查"
        if checked
        else ""
    )

    update_cell(
        worksheet,
        int(sheet_row),
        5,
        value
    )

    # 清除離宿快取
    load_checkout_data.clear()


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
    # 讀取
    # ==================================================

    with st.spinner(
        "正在讀取離宿資料..."
    ):

        df = load_checkout_data(
            dorm
        )

    # ==================================================
    # 沒資料
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
                        keyword,
                        na=False,
                        regex=False
                    )
                )

        df = df[
            condition
        ].copy()

    # ==================================================
    # 搜尋後沒資料
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

    st.caption(
        "離宿日期當天仍會顯示；隔天開始自動隱藏。"
    )

    st.divider()

    # ==================================================
    # 標題列
    # ==================================================

    header_cols = st.columns(
        [
            1.3,
            1.4,
            1.5,
            1.1,
            1.1,
        ]
    )

    with header_cols[0]:
        st.markdown(
            "**房號**"
        )

    with header_cols[1]:
        st.markdown(
            "**姓名**"
        )

    with header_cols[2]:
        st.markdown(
            "**離宿日期**"
        )

    with header_cols[3]:
        st.markdown(
            "**離宿時間**"
        )

    with header_cols[4]:
        st.markdown(
            "**檢查**"
        )

    st.divider()

    # ==================================================
    # 每一筆離宿資料
    # ==================================================

    can_update = (
        can_update_checkout_check()
    )

    for _, row in df.iterrows():

        cols = st.columns(
            [
                1.3,
                1.4,
                1.5,
                1.1,
                1.1,
            ]
        )

        # ==============================================
        # 房號
        # ==============================================

        with cols[0]:

            st.write(
                row.get(
                    "房號",
                    ""
                )
            )

        # ==============================================
        # 姓名
        # ==============================================

        with cols[1]:

            st.write(
                row.get(
                    "姓名",
                    ""
                )
            )

        # ==============================================
        # 日期
        # ==============================================

        with cols[2]:

            st.write(
                row.get(
                    "離宿日期",
                    ""
                )
            )

        # ==============================================
        # 時間
        # ==============================================

        with cols[3]:

            st.write(
                row.get(
                    "離宿時間",
                    ""
                )
            )

        # ==============================================
        # 檢查
        # ==============================================

        with cols[4]:

            current_checked = (
                str(
                    row.get(
                        "檢查",
                        ""
                    )
                ).strip()
                ==
                "已檢查"
            )

            # ==========================================
            # 樓長：可修改
            # ==========================================

            if can_update:

                checked = st.checkbox(
                    "已檢查",
                    value=current_checked,
                    key=(
                        f"checkout_check_"
                        f"{dorm}_"
                        f"{row.get('試算表列')}"
                    )
                )

                # ======================================
                # 有改變才寫入
                # ======================================

                if checked != current_checked:

                    try:

                        update_checkout_check(
                            dorm=dorm,
                            sheet_row=row.get(
                                "試算表列"
                            ),
                            checked=checked
                        )

                        st.success(
                            "已更新"
                        )

                        st.rerun()

                    except Exception as error:

                        st.error(
                            f"更新失敗：{error}"
                        )

            # ==========================================
            # 行政 / 舍監：只檢視
            # ==========================================

            else:

                if current_checked:

                    st.success(
                        "已檢查"
                    )

                else:

                    st.write(
                        "未檢查"
                    )

        st.divider()