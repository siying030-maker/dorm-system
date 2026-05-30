import streamlit as st
import pandas as pd

from core.google_api import open_sheet
from core.config import (
    REWARD_UPPER_URL,
    REWARD_LOWER_URL,
)


def read_reward(url):
    ss = open_sheet(url)
    dfs = []

    for ws in ss.worksheets():
        try:
            values = ws.get_all_values()

            if len(values) <= 1:
                continue

            df = pd.DataFrame(values[1:], columns=values[0])
            df.columns = df.columns.astype(str).str.strip()
            df["來源Sheet"] = ws.title

            dfs.append(df)

        except:
            continue

    if dfs:
        return pd.concat(dfs, ignore_index=True)

    return pd.DataFrame()


def show_reward_punishment():
    st.header("獎懲查詢")

    semester = st.selectbox(
        "學期",
        ["上學期", "下學期"],
        key="reward_semester"
    )

    url = REWARD_UPPER_URL if semester == "上學期" else REWARD_LOWER_URL

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

        condition = False

        for col in ["學號", "姓名"]:
            if col in df.columns:
                condition = condition | df[col].astype(str).str.contains(keyword, na=False)

        df = df[condition]

    st.dataframe(
        df,
        use_container_width=True
    )