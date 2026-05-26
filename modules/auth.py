import streamlit as st
import pandas as pd

from core.google_api import open_sheet
from core.config import ADMIN_SHEET_URL


@st.cache_data(ttl=300)
def load_users(sheet_name):

    try:
        ss = open_sheet(ADMIN_SHEET_URL)
        ws = ss.worksheet(sheet_name)

        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()

        return df

    except Exception as e:
        st.error(f"讀取 {sheet_name} 帳號失敗")
        st.code(str(e))
        return pd.DataFrame()


def login_page():

    role = st.selectbox(
        "登入權限",
        ["舍監", "行政", "樓長"]
    )

    # ==================================================
    # 舍監 / 行政
    # ==================================================

    if role in ["舍監", "行政"]:

        user_df = load_users(role)

        if user_df.empty:
            st.warning(f"{role} 沒有帳號資料")
            st.stop()

        username = st.selectbox(
            "使用者",
            user_df.iloc[:, 0].astype(str).tolist()
        )

        password = st.text_input(
            "密碼",
            type="password"
        )

        if st.button("登入", key=f"login_{role}"):

            match = user_df[
                (
                    user_df.iloc[:, 0]
                    .astype(str)
                    .str.strip()
                    == username
                )
                &
                (
                    user_df.iloc[:, 1]
                    .astype(str)
                    .str.strip()
                    == password
                )
            ]

            if not match.empty:

                st.session_state.login = True
                st.session_state.role = role
                st.session_state.user = username
                st.session_state.dorm = ""
                st.session_state.is_main = False
                st.session_state.manage_dorms = ""

                st.rerun()

            else:
                st.error("密碼錯誤")

    # ==================================================
    # 樓長
    # ==================================================

    if role == "樓長":

        user_df = load_users("樓長")

        if user_df.empty:
            st.warning("樓長沒有帳號資料")
            st.stop()

        dorms = (
            user_df.iloc[:, 0]
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
        )

        dorm = st.selectbox(
            "宿舍別",
            dorms
        )

        temp = user_df[
            user_df.iloc[:, 0]
            .astype(str)
            .str.strip()
            == dorm
        ]

        username = st.selectbox(
            "使用者",
            temp.iloc[:, 1].astype(str).tolist()
        )

        password = st.text_input(
            "密碼",
            type="password"
        )

        if st.button("登入", key="login_樓長"):

            match = temp[
                (
                    temp.iloc[:, 1]
                    .astype(str)
                    .str.strip()
                    == username
                )
                &
                (
                    temp.iloc[:, 2]
                    .astype(str)
                    .str.strip()
                    == password
                )
            ]

            if not match.empty:

                row = match.iloc[0]

                st.session_state.login = True
                st.session_state.role = "樓長"
                st.session_state.user = username

                st.session_state.dorm = str(row.iloc[0]).strip()
                st.session_state.is_main = str(row.iloc[3]).strip() == "是"

                if len(row) >= 5:
                    st.session_state.manage_dorms = str(row.iloc[4]).strip()
                else:
                    st.session_state.manage_dorms = str(row.iloc[0]).strip()

                st.rerun()

            else:
                st.error("密碼錯誤")