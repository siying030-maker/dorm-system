import streamlit as st
import pandas as pd

from core.google_api import open_sheet
from core.config import (
    REWARD_UPPER_URL,
    REWARD_LOWER_URL,
)


TARGET_SHEET_NAME = "輸入_懲處_男女"


def make_unique_columns(columns):

    result = []
    used = {}

    for i, col in enumerate(columns):

        col = str(col).strip()

        if col == "":
            col = f"空白欄位_{i}"

        if col in used:
            used[col] += 1
            col = f"{col}_{used[col]}"
        else:
            used[col] = 0

        result.append(col)

    return result


@st.cache_data(ttl=1800)
def read_reward(url):

    try:
        ss = open_sheet(url)
        ws = ss.worksheet(TARGET_SHEET_NAME)

        values = ws.get_all_values()

        if len(values) <= 1:
            return pd.DataFrame()

        headers = make_unique_columns(values[0])

        df = pd.DataFrame(
            values[1:],
            columns=headers
        )

        df.columns = make_unique_columns(df.columns)

        df = df.loc[
            :,
            ~df.columns.duplicated()
        ]

        empty_cols = []

        for col in df.columns:
            if df[col].astype(str).str.strip().eq("").all():
                empty_cols.append(col)

        df = df.drop(
            columns=empty_cols,
            errors="ignore"
        )

        return df

    except Exception as e:
        st.warning(f"讀取獎懲資料失敗：{e}")
        return pd.DataFrame()


def show_reward_punishment():

    st.header("獎懲查詢")

    semester = st.selectbox(
        "學期",
        ["上學期", "下學期"],
        key="reward_semester"
    )

    url = (
        REWARD_UPPER_URL
        if semester == "上學期"
        else REWARD_LOWER_URL
    )

    df = read_reward(url)

    if df.empty:
        st.warning("查無獎懲資料")
        return

    keyword = st.text_input(
        "搜尋學號 / 姓名",
        key="reward_search"
    )

    if keyword:
        keyword = str(keyword).strip()

        condition = pd.Series(
            False,
            index=df.index
        )

        for col in ["學號", "姓名", "學生姓名", "姓名_1"]:
            if col in df.columns:
                condition = (
                    condition
                    |
                    df[col]
                    .astype(str)
                    .str.contains(keyword, na=False)
                )

        df = df[condition]

        # 只顯示指定欄位

    column_mapping = {
        "學號": ["學號"],
        "日期": ["日期"],
        "獎懲原因": ["獎懲詳細原因", "原因"],
        "獎懲": ["獎懲"],
        "數量": ["數量", "次數"]
    }

    show_df = pd.DataFrame()

    for new_col, possible_cols in column_mapping.items():

        for col in possible_cols:

            if col in df.columns:

                show_df[new_col] = df[col]
                break

    if show_df.empty:

        st.warning("找不到指定欄位")
        return

    st.dataframe(
        show_df,
        use_container_width=True
    )