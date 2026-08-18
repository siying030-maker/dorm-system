import pandas as pd
import streamlit as st

from core.config import ANNOUNCEMENT_URL
from core.google_api import (
    open_sheet,
    get_all_values,
    append_row,
    update_cell,
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
            return pd.DataFrame()

        headers = [
            str(x).strip()
            for x in values[0]
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

        # 只顯示啟用公告
        if "啟用" in df.columns:

            df["啟用"] = (
                df["啟用"]
                .astype(str)
                .str.strip()
            )

            df = df[
                df["啟用"].isin(
                    [
                        "是",
                        "TRUE",
                        "True",
                        "true",
                        "1",
                    ]
                )
            ]

        # 日期排序
        if "日期" in df.columns:

            df["_排序日期"] = pd.to_datetime(
                df["日期"],
                errors="coerce"
            )

            df = df.sort_values(
                "_排序日期",
                ascending=False
            )

            df = df.drop(
                columns=["_排序日期"]
            )

        return df.reset_index(
            drop=True
        )

    except Exception as error:

        st.warning(
            f"讀取公告失敗：{error}"
        )

        return pd.DataFrame()


# ==================================================
# 新增公告
# ==================================================

def add_announcement(
    date_value,
    title,
    content
):

    ss = open_sheet(
        ANNOUNCEMENT_URL
    )

    ws = ss.get_worksheet(0)

    append_row(
        ws,
        [
            str(date_value),
            title,
            content,
            "是",
        ]
    )

    load_announcements.clear()


# ==================================================
# 公告畫面
# ==================================================

def show_announcement():

    role = st.session_state.get(
        "role",
        ""
    )

    st.subheader(
        "📢 最新公告"
    )

    df = load_announcements()

    # ==================================================
    # 行政新增公告
    # ==================================================

    if role == "行政":

        with st.expander(
            "＋ 新增公告"
        ):

            announcement_date = st.date_input(
                "公告日期",
                key="announcement_date"
            )

            title = st.text_input(
                "公告標題",
                key="announcement_title"
            )

            content = st.text_area(
                "公告內容",
                key="announcement_content"
            )

            if st.button(
                "發布公告",
                key="save_announcement"
            ):

                if not title.strip():

                    st.warning(
                        "請輸入公告標題"
                    )

                elif not content.strip():

                    st.warning(
                        "請輸入公告內容"
                    )

                else:

                    try:

                        add_announcement(
                            announcement_date,
                            title.strip(),
                            content.strip()
                        )

                        st.success(
                            "公告已發布"
                        )

                        st.rerun()

                    except Exception as error:

                        st.error(
                            f"公告發布失敗：{error}"
                        )

    # ==================================================
    # 顯示公告
    # ==================================================

    if df.empty:

        st.info(
            "目前沒有公告"
        )

        return

    for _, row in df.iterrows():

        date_text = str(
            row.get(
                "日期",
                ""
            )
        ).strip()

        title = str(
            row.get(
                "標題",
                ""
            )
        ).strip()

        content = str(
            row.get(
                "內容",
                ""
            )
        ).strip()

        with st.container(
            border=True
        ):

            if date_text:

                st.caption(
                    date_text
                )

            if title:

                st.markdown(
                    f"### {title}"
                )

            if content:

                st.write(
                    content
                )