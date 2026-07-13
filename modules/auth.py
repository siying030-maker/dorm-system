import streamlit as st
import pandas as pd

from core.google_api import (
    open_sheet,
    get_worksheet,
    get_all_values,
)

from core.config import ADMIN_SHEET_URL


def clean_text(value):
    return str(value).strip()


def normalize_dorm(value):
    return str(value).strip().replace("ㄧ", "一")


def normalize_gender(value):
    value = str(value).strip()

    if "男" in value:
        return "男"

    if "女" in value:
        return "女"

    return ""


def normalize_supervisor_type(value):
    value = str(value).strip()

    if "男" in value:
        return "男舍監"

    if "女" in value:
        return "女舍監"

    return ""

def normalize_gender(value):
    value = str(value).strip()

    if "男" in value:
        return "男"

    if "女" in value:
        return "女"

    return ""

import time

@st.cache_data(ttl=120, show_spinner=False)
def load_users(role):

    try:
        ss = open_sheet(ADMIN_SHEET_URL)

        ws = get_worksheet(
            ss,
            role
        )

        values = get_all_values(ws)

        if len(values) <= 1:
            return pd.DataFrame()

        headers = [
            str(value).strip()
            for value in values[0]
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

        return df

    except Exception as e:
        st.error(f"讀取 {role} 帳號失敗：{e}")
        return pd.DataFrame()


def get_row_gender(row):
    for col in ["性別", "男女舍監", "宿舍別", "寒假宿舍別", "暑假宿舍別"]:
        value = row.get(col, "")
        gender = normalize_gender(value)

        if gender:
            return gender

    return ""


def login_page():

    if st.button(
    "重新讀取帳號資料",
    key="refresh_login_accounts",
):
        load_users.clear()
        st.rerun()

    role = st.selectbox(
        "登入權限",
        ["舍監", "行政", "樓長"]
    )
    user_df = load_users(role)

    if user_df.empty:
        st.warning(f"{role} 沒有帳號資料")
        return

    user_df.columns = user_df.columns.astype(str).str.strip()

    if "使用者" not in user_df.columns or "密碼" not in user_df.columns:
        st.error("帳號表缺少「使用者」或「密碼」欄位")
        return

    if role == "樓長":

        if "宿舍別" not in user_df.columns:
            st.error("樓長帳號表缺少「宿舍別」欄位")
            return

        dorm_selected = st.selectbox(
            "宿舍別",
            user_df["宿舍別"].astype(str).str.strip().unique(),
            key="login_leader_dorm"
        )

        temp = user_df[
            user_df["宿舍別"].astype(str).str.strip()
            ==
            str(dorm_selected).strip()
        ]

        username = st.selectbox(
            "使用者",
            temp["使用者"].astype(str).tolist(),
            key="login_leader_user"
        )

        password = st.text_input(
            "密碼",
            type="password",
            key="login_leader_password"
        )

        
        if st.button("登入", key="login_leader_btn"):

            match = temp[
                (temp["使用者"].astype(str).str.strip() == username)
                &
                (temp["密碼"].astype(str).str.strip() == password)
            ]

            if match.empty:
                st.error("密碼錯誤")
                return

            row = match.iloc[0]

            st.session_state.login = True
            st.session_state.role = "樓長"
            st.session_state.user = username

            st.session_state.supervisor_type = ""

            st.session_state.dorm = normalize_dorm(
                row.get("宿舍別", "")
            )

            st.session_state.gender = normalize_gender(
            row.get("性別", "")
            )

            st.session_state.gender = get_row_gender(row)

            st.session_state.is_main = (
                clean_text(row.get("總樓", "")) == "是"
            )

            st.session_state.manage_dorms = clean_text(
                row.get("宿舍", "")
            )

            st.session_state.winter_dorms = clean_text(
                row.get("寒假宿舍別", "")
            )

            st.session_state.winter_floors = clean_text(
                row.get("寒假樓層", "")
            )

            st.session_state.summer_dorms = clean_text(
                row.get("暑假宿舍別", "")
            )

            st.session_state.summer_floors = clean_text(
                row.get("暑假樓層", "")
            )

            st.rerun()

    else:

        username = st.selectbox(
            "使用者",
            user_df["使用者"].astype(str).tolist(),
            key="login_user"
        )

        password = st.text_input(
            "密碼",
            type="password",
            key="login_password"
        )

        if st.button("登入", key="login_btn"):

            match = user_df[
                (user_df["使用者"].astype(str).str.strip() == username)
                &
                (user_df["密碼"].astype(str).str.strip() == password)
            ]

            if match.empty:
                st.error("密碼錯誤")
                return

            row = match.iloc[0]

            st.session_state.login = True
            st.session_state.role = role
            st.session_state.user = username

            if role == "舍監":
                st.session_state.supervisor_type = normalize_supervisor_type(
                    row.get("男女舍監", "")
                )
            else:
                st.session_state.supervisor_type = ""

            st.session_state.gender = get_row_gender(row)

            st.session_state.dorm = ""
            st.session_state.gender = ""
            st.session_state.is_main = False
            st.session_state.manage_dorms = ""

            st.session_state.winter_dorms = ""
            st.session_state.winter_floors = ""
            st.session_state.summer_dorms = ""
            st.session_state.summer_floors = ""

            st.rerun()