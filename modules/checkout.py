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

    # 只有樓長可以勾選
    return role == "樓長"


# ==================================================
# 空 DataFrame
# ==================================================

def empty_checkout_df():

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
        return empty_checkout_df()

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
            return empty_checkout_df()

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

            # ==================================================
            # 空白列略過
            # ==================================================

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

        if not rows:
            return empty_checkout_df()

        df = pd.DataFrame(
            rows
        )

        # ==================================================
        # 試算表列轉數字
        #
        # Google Sheet 越下面 = 越晚新增
        # ==================================================

        df["試算表列"] = pd.to_numeric(
            df["試算表列"],
            errors="coerce"
        )

        # ==================================================
        # 同一學生多筆，只留最新一筆
        #
        # 使用：
        # 房號 + 姓名
        #
        # 先按照試算表列由大到小
        # 再 drop_duplicates
        # ==================================================

        df = df.sort_values(
            by="試算表列",
            ascending=False
        )

        df = df.drop_duplicates(
            subset=[
                "房號",
                "姓名",
            ],
            keep="first"
        ).copy()

        # ==================================================
        # 最新一筆已檢查 → 不顯示
        #
        # 一定要放在 drop_duplicates 之後
        # 才不會舊資料又跑出來
        # ==================================================

        df["檢查"] = (
            df["檢查"]
            .astype(str)
            .str.strip()
        )

        df = df[
            df["檢查"] != "已檢查"
        ].copy()

        if df.empty:
            return empty_checkout_df()

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
        # 今天仍顯示
        # 隔天自動消失
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
            return empty_checkout_df()

        # ==================================================
        # 時間排序
        # ==================================================

        df["_排序時間"] = pd.to_datetime(
            df["離宿時間"],
            format="%H:%M",
            errors="coerce"
        )

        # ==================================================
        # 畫面排序
        #
        # 日期早的先
        # 時間早的先
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
        # 移除排序欄
        # ==================================================

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

        return empty_checkout_df()


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

    # ==================================================
    # 清快取
    # ==================================================

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
    # 宿舍
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
    # 載入資料
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
            f"{dorm}目前沒有待檢查的離宿預約"
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
        f"{dorm}目前共有 {len(df)} 筆待檢查離宿預約"
    )

    st.caption(
        "同一學生只顯示最新一筆；"
        "勾選「已檢查」後會自動從名單消失；"
        "離宿日期隔天也會自動隱藏。"
    )

    st.divider()

    # ==================================================
    # 標題
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
    # 是否可以修改
    # ==================================================

    can_update = (
        can_update_checkout_check()
    )

    # ==================================================
    # 每筆資料
    # ==================================================

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

        # ==================================================
        # 房號
        # ==================================================

        with cols[0]:

            st.write(
                row.get(
                    "房號",
                    ""
                )
            )

        # ==================================================
        # 姓名
        # ==================================================

        with cols[1]:

            st.write(
                row.get(
                    "姓名",
                    ""
                )
            )

        # ==================================================
        # 日期
        # ==================================================

        with cols[2]:

            st.write(
                row.get(
                    "離宿日期",
                    ""
                )
            )

        # ==================================================
        # 時間
        # ==================================================

        with cols[3]:

            st.write(
                row.get(
                    "離宿時間",
                    ""
                )
            )

        # ==================================================
        # 檢查
        # ==================================================

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

            # ==================================================
            # 樓長
            # ==================================================

            if can_update:

                checked = st.checkbox(
                    "已檢查",
                    value=current_checked,
                    key=(
                        f"checkout_check_"
                        f"{dorm}_"
                        f"{int(row.get('試算表列'))}"
                    )
                )

                # ==================================================
                # 勾選後立即寫入
                # ==================================================

                if checked != current_checked:

                    try:

                        update_checkout_check(
                            dorm=dorm,
                            sheet_row=row.get(
                                "試算表列"
                            ),
                            checked=checked
                        )

                        # 因為已檢查資料會被 load_checkout_data 過濾
                        # rerun 後這一筆直接消失
                        st.rerun()

                    except Exception as error:

                        st.error(
                            f"更新失敗：{error}"
                        )

            # ==================================================
            # 行政 / 舍監
            # ==================================================

            else:

                st.write(
                    "未檢查"
                )

        st.divider()