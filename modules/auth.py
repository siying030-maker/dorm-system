import streamlit as st


def normalize_dorm(value):
    return str(value).strip().replace("ㄧ", "一")


def login_page(load_users):

    role = st.selectbox("登入權限", ["舍監", "行政", "樓長"])

    if role in ["舍監", "行政"]:

        user_df = load_users(role)

        if user_df.empty:
            st.warning(f"{role} 沒有帳號資料")
            return

        username = st.selectbox("使用者", user_df.iloc[:, 0].astype(str).tolist())
        password = st.text_input("密碼", type="password")

        if st.button("登入"):

            match = user_df[
                (user_df.iloc[:, 0].astype(str).str.strip() == username)
                &
                (user_df.iloc[:, 1].astype(str).str.strip() == password)
            ]

            if not match.empty:
                st.session_state.update({
                    "login": True,
                    "role": role,
                    "user": username,
                    "dorm": "",
                    "is_main": False,
                    "manage_dorms": "",
                    "winter_main": False,
                    "winter_dorms": "",
                    "summer_main": False,
                    "summer_dorms": "",
                })
                st.rerun()
            else:
                st.error("密碼錯誤")

    if role == "樓長":

        user_df = load_users("樓長")

        if user_df.empty:
            st.warning("樓長 沒有帳號資料")
            return

        user_df.columns = user_df.columns.astype(str).str.strip()

        dorm = st.selectbox("宿舍別", user_df.iloc[:, 0].astype(str).unique())

        temp = user_df[
            user_df.iloc[:, 0].astype(str).str.strip() == str(dorm).strip()
        ]

        username = st.selectbox("使用者", temp.iloc[:, 1].astype(str).tolist())
        password = st.text_input("密碼", type="password")

        if st.button("登入"):

            match = temp[
                (temp.iloc[:, 1].astype(str).str.strip() == username)
                &
                (temp.iloc[:, 2].astype(str).str.strip() == password)
            ]

            if not match.empty:
                row = match.iloc[0]

                # 一般學期總樓
                is_main = False
                manage_dorms = ""

                if "總樓" in user_df.columns:
                    is_main = str(row.get("總樓", "")).strip() == "是"

                if "宿舍" in user_df.columns:
                    manage_dorms = str(row.get("宿舍", "")).strip()

                # 寒假樓長
                winter_main = False
                winter_dorms = ""

                if "寒假樓長" in user_df.columns:
                    winter_main = str(row.get("寒假樓長", "")).strip() == "是"

                if "寒假宿舍別" in user_df.columns:
                    winter_dorms = str(row.get("寒假宿舍別", "")).strip()

                # 暑假樓長
                summer_main = False
                summer_dorms = ""

                if "暑假樓長" in user_df.columns:
                    summer_main = str(row.get("暑假樓長", "")).strip() == "是"

                if "暑假宿舍別" in user_df.columns:
                    summer_dorms = str(row.get("暑假宿舍別", "")).strip()

                st.session_state.update({
                    "login": True,
                    "role": "樓長",
                    "user": username,
                    "dorm": normalize_dorm(row.iloc[0]),
                    "is_main": is_main,
                    "manage_dorms": manage_dorms,
                    "winter_main": winter_main,
                    "winter_dorms": winter_dorms,
                    "summer_main": summer_main,
                    "summer_dorms": summer_dorms,
                })

                st.rerun()

            else:
                st.error("密碼錯誤")