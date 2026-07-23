import pandas as pd
import streamlit as st

from core.google_api import open_sheet

from modules.attendance import (
    ATTENDANCE_SHEETS,
    FLOOR_OPTIONS,
    DORM_PREFIX,
    load_special_status,
    read_worksheet_df,
    find_col,
    normalize_value,
)


# ==================================================
# 宿舍名稱正規化
# ==================================================

def normalize_dorm(value):

    return (
        str(value)
        .strip()
        .replace("ㄧ", "一")
    )


# ==================================================
# 權限判斷
# ==================================================

def get_allowed_dorms(term):

    role = st.session_state.get(
        "role",
        ""
    )

    supervisor_type = st.session_state.get(
        "supervisor_type",
        ""
    )

    dorm = normalize_dorm(
        st.session_state.get(
            "dorm",
            ""
        )
    )

    manage_dorms = st.session_state.get(
        "manage_dorms",
        ""
    )

    if term not in ATTENDANCE_SHEETS:
        return []

    all_dorms = [
        normalize_dorm(item)
        for item in ATTENDANCE_SHEETS[term].keys()
    ]

    # 行政可以看全部
    if role == "行政":
        return all_dorms

    # 舍監依性別
    if role == "舍監":

        if supervisor_type == "男舍監":

            return [
                item
                for item in all_dorms
                if item.startswith("男")
            ]

        if supervisor_type == "女舍監":

            return [
                item
                for item in all_dorms
                if item.startswith("女")
            ]

    # 樓長優先使用可管理宿舍
    if role == "樓長":

        allowed = []

        if manage_dorms:

            for item in (
                str(manage_dorms)
                .replace("，", ",")
                .split(",")
            ):

                item = normalize_dorm(item)

                if (
                    item
                    and item in all_dorms
                ):
                    allowed.append(item)

        if allowed:

            return list(
                dict.fromkeys(
                    allowed
                )
            )

        # 沒有 manage_dorms 時依登入宿舍性別
        if dorm.startswith("男"):

            return [
                item
                for item in all_dorms
                if item.startswith("男")
            ]

        if dorm.startswith("女"):

            return [
                item
                for item in all_dorms
                if item.startswith("女")
            ]

    return []


# ==================================================
# 找 AQ 欄
# AQ 是第 43 欄，index 為 42
# ==================================================

def get_overseas_col(df):

    aq_col = find_col(
        df,
        [
            "本地/境外",
            "本地／境外",
            "本地境外",
            "原始資料備註",
        ]
    )

    if aq_col is not None:
        return aq_col

    if len(df.columns) >= 43:
        return df.columns[42]

    return None


# ==================================================
# 讀取假日點名學生
# AQ 欄只保留「境外」與「其他」
# ==================================================

@st.cache_data(
    ttl=1800,
    show_spinner=False
)
def load_holiday_students(
    term,
    allowed_dorms
):

    result = []

    if term not in ATTENDANCE_SHEETS:

        st.warning(
            f"找不到假日點名學期設定：{term}"
        )

        return pd.DataFrame()

    dorms = ATTENDANCE_SHEETS[term]

    normalized_allowed_dorms = [
        normalize_dorm(item)
        for item in allowed_dorms
    ]

    for original_dorm, url in dorms.items():

        dorm = normalize_dorm(
            original_dorm
        )

        if dorm not in normalized_allowed_dorms:
            continue

        try:

            ss = open_sheet(url)

            floors = FLOOR_OPTIONS.get(
                dorm,
                []
            )

            for floor in floors:

                prefix = DORM_PREFIX.get(
                    dorm,
                    ""
                )

                if prefix == "":
                    continue

                sheet_name = (
                    f"{prefix}-{floor}"
                )

                df = read_worksheet_df(
                    ss,
                    sheet_name
                )

                if df.empty:
                    continue

                # 學號
                sid_col = find_col(
                    df,
                    ["學號"],
                    exclude_keywords=[
                        "替代"
                    ]
                )

                # 姓名
                name_col = find_col(
                    df,
                    [
                        "姓名",
                        "名字",
                    ]
                )

                # 床位固定為 B 欄
                if len(df.columns) < 2:
                    continue

                bed_col = df.columns[1]

                # AQ 本地／境外
                overseas_col = get_overseas_col(
                    df
                )

                if sid_col is None:
                    continue

                if name_col is None:
                    continue

                if overseas_col is None:

                    st.warning(
                        f"{dorm} {sheet_name} 找不到 AQ 本地/境外欄位"
                    )

                    continue

                df = df.copy()

                df["_本地境外判斷"] = (
                    df[overseas_col]
                    .astype(str)
                    .str.strip()
                )

                # ==================================
                # 只保留「境外」與「其他」
                # ==================================

                temp_df = df[
                    df["_本地境外判斷"].isin(
                        [
                            "境外",
                            "其他",
                        ]
                    )
                ].copy()

                if temp_df.empty:
                    continue

                temp = pd.DataFrame(
                    index=temp_df.index
                )

                temp["宿舍"] = dorm
                temp["樓層"] = floor

                temp["床位"] = (
                    temp_df[bed_col]
                    .astype(str)
                    .map(normalize_value)
                )

                temp["房號"] = (
                    temp["床位"]
                    .astype(str)
                    .str.split("-")
                    .str[0]
                )

                temp["學號"] = (
                    temp_df[sid_col]
                    .astype(str)
                    .map(normalize_value)
                )

                temp["姓名"] = (
                    temp_df[name_col]
                    .astype(str)
                    .str.strip()
                )

                temp["本地境外"] = (
                    temp_df["_本地境外判斷"]
                    .astype(str)
                    .str.strip()
                )

                # 移除空白資料
                temp = temp[
                    temp["學號"]
                    .astype(str)
                    .str.strip()
                    .ne("")
                ].copy()

                temp = temp[
                    temp["姓名"]
                    .astype(str)
                    .str.strip()
                    .ne("")
                ].copy()

                temp = temp[
                    temp["房號"]
                    .astype(str)
                    .str.strip()
                    .ne("")
                ].copy()

                # 移除 nan、None
                temp = temp[
                    ~temp["學號"]
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

        except Exception as error:

            st.warning(
                f"{term} {dorm} 讀取失敗：{error}"
            )

    if not result:
        return pd.DataFrame()

    final_df = pd.concat(
        result,
        ignore_index=True
    )

    # 避免同一位學生重複
    final_df = final_df.drop_duplicates(
        subset=[
            "宿舍",
            "床位",
            "學號",
        ],
        keep="first"
    )

    # 排序
    final_df = final_df.sort_values(
        by=[
            "宿舍",
            "床位",
        ],
        ascending=True
    )

    return final_df.reset_index(
        drop=True
    )


# ==================================================
# 外宿／長期外宿／長期晚歸
# ==================================================

def add_special_status(
    df,
    term,
    attendance_date
):

    special = load_special_status(
        term,
        attendance_date
    )

    leave_ids = special.get(
        "leave_ids",
        set()
    )

    long_leave_ids = special.get(
        "long_leave_ids",
        set()
    )

    late_ids = special.get(
        "late_ids",
        set()
    )

    result = df.copy()

    status_values = []

    for sid in result[
        "學號"
    ].astype(str):

        sid = normalize_value(
            sid
        )

        statuses = []

        if sid in leave_ids:
            statuses.append(
                "外宿申請"
            )

        if sid in long_leave_ids:
            statuses.append(
                "長期外宿"
            )

        if sid in late_ids:
            statuses.append(
                "長期晚歸"
            )

        if statuses:

            status_values.append(
                "、".join(statuses)
            )

        else:

            status_values.append(
                "正常"
            )

    result["特殊狀態"] = (
        status_values
    )

    return result


# ==================================================
# 特殊狀態顏色
# ==================================================

def highlight_special_status(row):

    status = str(
        row.get(
            "特殊狀態",
            ""
        )
    ).strip()

    # 同時有多個狀態時，
    # 依外宿、長期外宿、長期晚歸優先顯示顏色

    if "外宿申請" in status:

        return [
            "color:red;font-weight:bold"
            for _ in row
        ]

    if "長期外宿" in status:

        return [
            "color:blue;font-weight:bold"
            for _ in row
        ]

    if "長期晚歸" in status:

        return [
            "color:#b58900;font-weight:bold"
            for _ in row
        ]

    return [
        ""
        for _ in row
    ]


# ==================================================
# 主畫面
# ==================================================

def show_holiday_rollcall(term):

    st.header(
        f"{term}假日點名單"
    )

    allowed_dorms = get_allowed_dorms(
        term
    )

    if not allowed_dorms:

        st.warning(
            "沒有假日點名單權限"
        )

        return

    st.info(
        "目前讀取宿舍："
        +
        "、".join(
            allowed_dorms
        )
    )

    # ==============================================
    # 點名日期
    # ==============================================

    attendance_date = st.date_input(
        "點名日期",
        value=pd.Timestamp.now().date(),
        key=f"holiday_date_{term}"
    )

    # ==============================================
    # 重新整理
    # ==============================================

    if st.button(
        "重新讀取假日點名單",
        key=f"refresh_holiday_rollcall_{term}"
    ):

        load_holiday_students.clear()

        try:
            load_special_status.clear()
        except Exception:
            pass

        st.rerun()

    # ==============================================
    # 讀取學生
    # ==============================================

    df = load_holiday_students(
        term,
        allowed_dorms
    )

    if df.empty:

        st.warning(
            "AQ 欄沒有「境外」或「其他」的學生資料"
        )

        return

    df = add_special_status(
        df,
        term,
        attendance_date
    )

    # ==============================================
    # 搜尋
    # ==============================================

    search = st.text_input(
        "搜尋學號 / 姓名 / 房號 / 床位",
        key=f"holiday_search_{term}"
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
            "學號",
            "姓名",
            "房號",
            "床位",
        ]:

            if column in df.columns:

                condition = (
                    condition
                    |
                    df[column]
                    .astype(str)
                    .str.contains(
                        search,
                        case=False,
                        na=False,
                        regex=False
                    )
                )

        df = df[
            condition
        ].copy()

    if df.empty:

        st.info(
            "查無符合條件的學生"
        )

        return

    # ==============================================
    # 統計
    # ==============================================

    overseas_count = (
        df["本地境外"]
        .astype(str)
        .eq("境外")
        .sum()
    )

    other_count = (
        df["本地境外"]
        .astype(str)
        .eq("其他")
        .sum()
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "總人數",
        len(df)
    )

    col2.metric(
        "境外",
        int(overseas_count)
    )

    col3.metric(
        "其他",
        int(other_count)
    )

    # ==============================================
    # 顯示資料
    # ==============================================

    show_cols = [
        column
        for column in [
            "宿舍",
            "樓層",
            "房號",
            "床位",
            "學號",
            "姓名",
            "本地境外",
            "特殊狀態",
        ]
        if column in df.columns
    ]

    show_df = df[
        show_cols
    ].copy()

    st.caption(
        "AQ 欄顯示範圍：境外、其他｜"
        "紅色：外宿申請　"
        "藍色：長期外宿　"
        "黃色：長期晚歸"
    )

    style_df = (
        show_df.style
        .apply(
            highlight_special_status,
            axis=1
        )
    )

    st.dataframe(
        style_df,
        use_container_width=True,
        hide_index=True
    )