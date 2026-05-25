import streamlit as st
import pandas as pd

def login_page(load_users):

    role = st.selectbox("登入權限", ["舍監", "行政", "樓長"])

    if role in ["舍監", "行政"]:

        user_df = load_users(role)

        username = st.selectbox("使用者", user_df.iloc[:, 0].astype(str).tolist())
        password = st.text_input("密碼", type="password")

        if st.button("登入"):

            match = user_df[
                (user_df.iloc[:, 0].astype(str).str.strip() == username) &
                (user_df.iloc[:, 1].astype(str).str.strip() == password)
            ]

            if not match.empty:
                st.session_state.update({
                    "login": True,
                    "role": role,
                    "user": username,
                    "dorm": "",
                    "is_main": False
                })
                st.rerun()

            else:
                st.error("密碼錯誤")

    if role == "樓長":

        user_df = load_users("樓長")

        dorm = st.selectbox("宿舍別", user_df.iloc[:, 0].unique())
        temp = user_df[user_df.iloc[:, 0].astype(str) == dorm]

        username = st.selectbox("使用者", temp.iloc[:, 1].tolist())
        password = st.text_input("密碼", type="password")

        if st.button("登入"):

            match = temp[
                (temp.iloc[:, 1].astype(str) == username) &
                (temp.iloc[:, 2].astype(str) == password)
            ]

            if not match.empty:
                row = match.iloc[0]

                st.session_state.update({
                    "login": True,
                    "role": "樓長",
                    "user": username,
                    "dorm": str(row.iloc[0]).strip(),
                    "is_main": str(row.iloc[3]).strip() == "是"
                })
                st.rerun()

            else:
                st.error("密碼錯誤")