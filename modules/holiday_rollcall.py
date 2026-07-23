import pandas as pd
import streamlit as st

from core.google_api import open_sheet
from modules.attendance import (
    ATTENDANCE_SHEETS,
    FLOOR_OPTIONS,
    DORM_PREFIX,
    get_gate_sheet_url,
    load_special_status,
    read_worksheet_df,
    find_col,
    normalize_value,
)


# ==================================================
# 權限判斷
# ==================================================

def get_allowed_dorms(term):

    role = st.session_state.get("role", "")
    supervisor_type = st.session_state.get("supervisor_type", "")
    dorm = st.session_state.get("dorm", "")

    all_dorms = list(ATTENDANCE_SHEETS[term].keys())

    if role == "行政":
        return all_dorms

    if role == "舍監":

        if supervisor_type == "男舍監":
            return [
                d for d in all_dorms
                if d.startswith("男")
            ]

        if supervisor_type == "女舍監":
            return [
                d for d in all_dorms
                if d.startswith("女")
            ]

    if role == "樓長":

        if str(dorm).startswith("男"):
            return [
                d for d in all_dorms
                if d.startswith("男")
            ]

        if str(dorm).startswith("女"):
            return [
                d for d in all_dorms
                if d.startswith("女")
            ]

    return []


# ==================================================
# 找 AQ 欄
# AQ = 第 43 欄，index = 42
# 若欄名有 本地/境外，也優先使用欄名
# ==================================================

def get_overseas_col(df):

    aq_col = find_col(
        df,
        [
            "本地/境外",
            "本地境外",
            "原始資料備註"
        ]
    )

    if aq_col:
        return aq_col

    if len(df.columns) >= 43:
        return df.columns[42]

    return None


# ==================================================
# 讀取假日境外生
# ==================================================

@st.cache_data(ttl=1800)
def load_holiday_students(term, allowed_dorms):

    result = []

    dorms = ATTENDANCE_SHEETS[term]

    for dorm, url in dorms.items():

        if dorm not in allowed_dorms:
            continue

        try:
            ss = open_sheet(url)

            for floor in FLOOR_OPTIONS.get(dorm, []):

                sheet_name = f"{DORM_PREFIX[dorm]}-{floor}"

                df = read_worksheet_df(
                    ss,
                    sheet_name
                )

                if df.empty:
                    continue

                sid_col = find_col(
                    df,
                    ["學號"],
                    exclude_keywords=["替代"]
                )

                name_col = find_col(
                    df,
                    ["姓名", "名字"]
                )

                # 固定抓 B 欄作為床位，例如 82113-1
                if len(df.columns) < 2:
                    continue

                bed_col = df.columns[1]

                overseas_col = get_overseas_col(df)

                if sid_col is None:
                    continue

                if name_col is None:
                    continue

                if overseas_col is None:
                    continue

                temp_df = df[
                    df[overseas_col]
                    .astype(str)
                    .str.strip()
                    .str.contains("境外","其他", na=False)
                ].copy()

                if temp_df.empty:
                    continue

                temp = pd.DataFrame()

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
                    temp_df[overseas_col]
                    .astype(str)
                    .str.strip()
                )

                temp = temp[temp["學號"] != ""]
                temp = temp[temp["姓名"] != ""]
                temp = temp[temp["房號"] != ""]

                if not temp.empty:
                    result.append(temp)

        except Exception as e:
            st.warning(f"{term} {dorm} 讀取失敗：{e}")

    if result:
        return pd.concat(
            result,
            ignore_index=True
        )

    return pd.DataFrame()


# ==================================================
# 外宿 / 長期外宿 / 長期晚歸
# ==================================================

def add_special_status(df, term):

    special = load_special_status(
        term,
        pd.Timestamp.now()
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

    status_list = []

    for sid in df["學號"].astype(str):

        sid = normalize_value(sid)

        if sid in leave_ids:
            status_list.append("外宿申請")

        elif sid in long_leave_ids:
            status_list.append("長期外宿")

        elif sid in late_ids:
            status_list.append("長期晚歸")

        else:
            status_list.append("正常")

    df["特殊狀態"] = status_list

    return df


# ==================================================
# 顏色
# ==================================================

def highlight_special_status(row):

    status = str(
        row.get("特殊狀態", "")
    ).strip()

    if status == "外宿申請":
        return [
            "color:red;font-weight:bold"
            for _ in row
        ]

    if status == "長期外宿":
        return [
            "color:blue;font-weight:bold"
            for _ in row
        ]

    if status == "長期晚歸":
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

    st.header(f"{term}假日點名單")

    allowed_dorms = get_allowed_dorms(term)

    if not allowed_dorms:
        st.warning("沒有假日點名單權限")
        return

    st.info(
        "目前讀取宿舍："
        +
        "、".join(allowed_dorms)
    )

    df = load_holiday_students(
        term,
        allowed_dorms
    )

    if df.empty:
        st.warning("沒有境外生資料")
        return

    df = add_special_status(
        df,
        term
    )

    search = st.text_input(
        "搜尋學號 / 姓名 / 房號",
        key=f"holiday_search_{term}"
    )

    if search:
        search = str(search).strip()

        condition = pd.Series(
            False,
            index=df.index
        )

        for col in ["學號", "姓名", "房號", "床位"]:

            if col in df.columns:

                condition = (
                    condition
                    |
                    df[col]
                    .astype(str)
                    .str.contains(
                        search,
                        na=False
                    )
                )

        df = df[condition]

    if df.empty:
        st.info("查無符合條件的境外生")
        return

    show_cols = [
        "宿舍",
        "樓層",
        "房號",
        "床位",
        "學號",
        "姓名",
        "本地境外",
        "特殊狀態"
    ]

    show_cols = [
        c for c in show_cols
        if c in df.columns
    ]

    show_df = df[show_cols].copy()

    st.caption(
        "紅色：外宿申請　藍色：長期外宿　黃色：長期晚歸"
    )

    style_df = show_df.style.apply(
        highlight_special_status,
        axis=1
    )

    st.dataframe(
        style_df,
        use_container_width=True,
        hide_index=True
    )