import streamlit as st
import pandas as pd

from core.google_api import open_sheet
from core.config import (
    REWARD_UPPER_URL,
    REWARD_LOWER_URL,
)


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

    ss = open_sheet(url)

    dfs = []

    for ws in ss.worksheets():

        try:
            values = ws.get_all_values()

            if len(values) <= 1:
                continue

            headers = make_unique_columns(values[0])

            df = pd.DataFrame(
                values[1:],
                columns=headers
            )

            df.columns = make_unique_columns(df.columns)

            df["來源Sheet"] = ws.title

            df = df.loc[
                :,
                ~df.columns.duplicated()
            ]

            dfs.append(df)

        except:
            continue

    if dfs:

        clean_dfs = []

        for df in dfs:
            df = df.copy()
            df.columns = make_unique_columns(df.columns)
            df = df.loc[:, ~df.columns.duplicated()]
            clean_dfs.append(df)

        return pd.concat(
            clean_dfs,
            ignore_index=True,
            sort=False
        )

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

    empty_cols = []

    for col in df.columns:
        if df[col].astype(str).str.strip().eq("").all():
            empty_cols.append(col)

    df = df.drop(
        columns=empty_cols,
        errors="ignore"
    )

    st.dataframe(
        df,
        use_container_width=True
    )