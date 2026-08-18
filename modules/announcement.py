import pandas as pd
import streamlit as st

from core.config import ANNOUNCEMENT_URL
from core.google_api import (
    open_sheet,
    get_all_values,
)


# ==================================================
# 讀取公告
# ==================================================

@st.cache_data(
    ttl=10,
    show_spinner=False
)
def load_announcements():

    try:

        ss = open_sheet(
            ANNOUNCEMENT_URL
        )

        ws = ss.get_worksheet(0)

        values = get_all_values(
            ws
        )

        if len(values) <= 1:
            return []

        headers = [
            str(value).strip()
            for value in values[0]
        ]

        if "內容" not in headers:
            st.warning(
                "公告試算表必須有「內容」欄位"
            )
            return []

        content_index = headers.index(
            "內容"
        )

        announcements = []

        for row in values[1:]:

            if len(row) <= content_index:
                continue

            content = str(
                row[content_index]
            ).strip()

            if content:
                announcements.append(
                    content
                )

        return announcements

    except Exception as error:

        st.warning(
            f"讀取公告失敗：{error}"
        )

        return []


# ==================================================
# 顯示公告
# ==================================================

def show_announcement():

    role = st.session_state.get(
        "role",
        ""
    )

    # 目前只讓樓長、行政看到
    if role not in [
        "樓長",
        "行政",
    ]:
        return

    announcements = (
        load_announcements()
    )

    if not announcements:
        return

    st.subheader(
        "📢 公告"
    )

    for content in announcements:

        st.info(
            content
        )