import streamlit as st
import pandas as pd

from core.google_api import open_sheet
from core.config import ADMIN_SHEET_URL


def normalize_dorm(value):
    return str(value).strip().replace("ㄧ", "一")


@st.cache_data(ttl=300)
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

    user_col = "使用者"
    pwd_col = "密碼"

    if user_col not in user_df.columns or pwd_col not in user_df.columns:
        st.error("帳號表缺少「使用者」或「密碼」欄位")
        return

    if role == "樓長":

        dorm_col = "宿舍別"

        if dorm_col not in user_df.columns:
            st.error("樓長帳號表缺少「宿舍別」欄位")
            return

        dorm = st.selectbox(
            "宿舍別",
            user_df[dorm_col].astype(str).unique()
        )

        temp = user_df[
            user_df[dorm_col].astype(str).str.strip()
            ==
            str(dorm).strip()
        ]

        username = st.selectbox(
            "使用者",
            temp[user_col].astype(str).tolist()
        )

        password = st.text_input(
            "密碼",
            type="password"
        )

        if st.button("登入"):

            match = temp[
                (temp[user_col].astype(str).str.strip() == username)
                &
                (temp[pwd_col].astype(str).str.strip() == password)
            ]

            if match.empty:
                st.error("密碼錯誤")
                return

            row = match.iloc[0]

            st.session_state.login = True
            st.session_state.role = "樓長"
            st.session_state.user = username

            st.session_state.dorm = normalize_dorm(
                row.get("宿舍別", "")
            )

            st.session_state.is_main = (
                str(row.get("總樓", "")).strip() == "是"
            )

            st.session_state.manage_dorms = str(
                row.get("宿舍", "")
            ).strip()

            # 寒假權限：判斷「寒假宿舍別」是否有值
            st.session_state.winter_dorms = str(
                row.get("寒假宿舍別", "")
            ).strip()

            st.session_state.winter_floors = str(
                row.get("寒假樓層", "")
            ).strip()

            # 暑假權限：判斷「暑假宿舍別」是否有值
            st.session_state.summer_dorms = str(
                row.get("暑假宿舍別", "")
            ).strip()

            st.session_state.summer_floors = str(
                row.get("暑假樓層", "")
            ).strip()

            st.rerun()

    else:

        username = st.selectbox(
            "使用者",
            user_df[user_col].astype(str).tolist()
        )

        password = st.text_input(
            "密碼",
            type="password"
        )

        if st.button("登入"):

            match = user_df[
                (user_df[user_col].astype(str).str.strip() == username)
                &
                (user_df[pwd_col].astype(str).str.strip() == password)
            ]

            if match.empty:
                st.error("密碼錯誤")
                return

            st.session_state.login = True
            st.session_state.role = role
            st.session_state.user = username

            st.session_state.dorm = ""
            st.session_state.is_main = False
            st.session_state.manage_dorms = ""

            st.session_state.winter_dorms = ""
            st.session_state.winter_floors = ""

            st.session_state.summer_dorms = ""
            st.session_state.summer_floors = ""

            st.rerun()