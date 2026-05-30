import streamlit as st
import pandas as pd

from core.google_api import open_sheet
from core.config import ADMIN_SHEET_URL


def clean_text(value):
    return str(value).strip()


def normalize_dorm(value):
    return str(value).strip().replace("ㄧ", "一")


@st.cache_data(ttl=1800)
def load_users(role):
    try:
        ss = open_sheet(ADMIN_SHEET_URL)
        ws = ss.worksheet(role)
        values = ws.get_all_values()

        if len(values) <= 1:
            return pd.DataFrame()

        df = pd.DataFrame(values[1:], columns=values[0])
        df.columns = df.columns.astype(str).str.strip()
        return df

    except Exception as e:
        st.error(f"讀取 {role} 帳號失敗：{e}")
        return pd.DataFrame()


def login_page():

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

    # =========================
    # 樓長登入：保留宿舍別選擇
    # =========================
    if role == "樓長":

        if "宿舍別" not in user_df.columns:
            st.error("樓長帳號表缺少「宿舍別」欄位")
            return

        dorm_selected = st.selectbox(
            "宿舍別",
            user_df["宿舍別"].astype(str).str.strip().unique()
        )

        temp = user_df[
            user_df["宿舍別"].astype(str).str.strip()
            ==
            str(dorm_selected).strip()
        ]

        username = st.selectbox(
            "使用者",
            temp["使用者"].astype(str).tolist()
        )

        password = st.text_input(
            "密碼",
            type="password"
        )

        if st.button("登入"):

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

    # =========================
    # 舍監 / 行政登入
    # =========================
    else:

        username = st.selectbox(
            "使用者",
            user_df["使用者"].astype(str).tolist()
        )

        password = st.text_input(
            "密碼",
            type="password"
        )

        if st.button("登入"):

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

            st.session_state.supervisor_type = clean_text(
                row.get("男女舍監", "")
            )

            st.session_state.dorm = ""
            st.session_state.is_main = False
            st.session_state.manage_dorms = ""

            st.session_state.winter_dorms = ""
            st.session_state.winter_floors = ""
            st.session_state.summer_dorms = ""
            st.session_state.summer_floors = ""

            st.rerun()