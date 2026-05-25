import streamlit as st
import pandas as pd
from core.gsheet import open_sheet
from core.config import ADMIN_SHEET_URL

def load_users(sheet_name):
    ss = open_sheet(ADMIN_SHEET_URL)
    ws = ss.worksheet(sheet_name)
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip()
    return df


def login_page():
    role = st.selectbox("登入權限", ["舍監", "行政", "樓長"])

    if role in ["舍監", "行政"]:
        df = load_users(role)

        username = st.selectbox("使用者", df.iloc[:, 0].astype(str))
        password = st.text_input("密碼", type="password")

        if st.button("登入"):
            match = df[
                (df.iloc[:,0].astype(str).str.strip() == username) &
                (df.iloc[:,1].astype(str).str.strip() == password)
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

    elif role == "樓長":
        df = load_users("樓長")

        dorms = df.iloc[:,0].unique().tolist()
        dorm = st.selectbox("宿舍別", dorms)

        temp = df[df.iloc[:,0].astype(str) == dorm]

        username = st.selectbox("使用者", temp.iloc[:,1].astype(str))
        password = st.text_input("密碼", type="password")

        if st.button("登入"):
            match = temp[
                (temp.iloc[:,1].astype(str).str.strip() == username) &
                (temp.iloc[:,2].astype(str).str.strip() == password)
            ]

            if not match.empty:
                row = match.iloc[0]

                st.session_state.update({
                    "login": True,
                    "role": role,
                    "user": username,
                    "dorm": str(row.iloc[0]).strip(),
                    "is_main": str(row.iloc[3]).strip() == "是"
                })
                st.rerun()
            else:
                st.error("密碼錯誤")