import time
import streamlit as st

from core.session import init_session
from core.google_api import open_sheet
from core.config import (
    ROLLCALL_GIRL_URL,
    ROLLCALL_BOY_URL,
    UPPER_GATE_URL,
    LOWER_GATE_URL,
)

from modules.auth import login_page
from modules.tab import build_tabs
from modules.rollcall import show_rollcall
from modules.gate import show_gate
from modules.clean import show_clean, show_clean_view
from modules.attendance import show_attendance
from modules.makeup_rollcall import show_makeup_rollcall
from modules.reward_punishment import show_reward_punishment
from modules.holiday_rollcall import show_holiday_rollcall


# ==============================
# 頁面設定
# ==============================

st.set_page_config(
    page_title="宿舍管理系統",
    layout="wide"
)

st.title("宿舍管理系統")


# ==============================
# 初始化登入狀態
# ==============================

init_session()


# ==============================
# 25 分鐘未操作自動登出
# ==============================

TIMEOUT_SECONDS = 25 * 60
now = time.time()

if "last_active_time" not in st.session_state:
    st.session_state["last_active_time"] = now

if st.session_state.get("login", False):

    last_active_time = st.session_state.get(
        "last_active_time",
        now
    )

    if now - last_active_time > TIMEOUT_SECONDS:
        st.session_state.clear()
        st.warning("已超過 25 分鐘未操作，系統已自動登出。")
        st.rerun()

    st.session_state["last_active_time"] = now


# ==============================
# 登入頁面
# ==============================

if not st.session_state.get("login", False):
    login_page()
    st.stop()


# ==============================
# 登入資訊
# ==============================

st.success(
    f"{st.session_state.get('role', '')} / "
    f"{st.session_state.get('user', '')}"
)


# ==============================
# 登出
# ==============================

if st.button(
    "登出",
    key="logout_btn"
):
    st.session_state.clear()
    st.rerun()


# ==============================
# 功能選單
# ==============================

tab_names = build_tabs(
    st.session_state.get("role", ""),
    st.session_state.get("is_main", False)
)

# 移除不要的頁面
tab_names = [
    t for t in tab_names
    if t != "連三天不假外宿"
]

if not tab_names:
    st.warning("目前沒有可用功能")
    st.stop()


# ==============================
# 自訂功能按鈕導覽
# ==============================

if "selected_page" not in st.session_state:
    st.session_state.selected_page = tab_names[0]

if st.session_state.selected_page not in tab_names:
    st.session_state.selected_page = tab_names[0]

cols = st.columns(len(tab_names))

for i, name in enumerate(tab_names):
    with cols[i]:
        if st.button(
            name,
            key=f"nav_btn_{name}",
            use_container_width=True
        ):
            st.session_state.selected_page = name
            st.rerun()

st.divider()

selected_page = st.session_state.selected_page


if selected_page == "點名系統":
    show_attendance()


elif selected_page == "補點名單":
    show_makeup_rollcall()


elif selected_page == "每日點名未到名單":

    role = st.session_state.get("role", "")
    supervisor_type = st.session_state.get("supervisor_type", "")
    dorm = st.session_state.get("dorm", "")
    gender = st.session_state.get("gender", "")

    if role == "行政":
        girl_ss = open_sheet(ROLLCALL_GIRL_URL)
        boy_ss = open_sheet(ROLLCALL_BOY_URL)
        show_rollcall([girl_ss, boy_ss], mode="daily_all")

    elif role == "舍監":

        if supervisor_type == "男舍監":
            boy_ss = open_sheet(ROLLCALL_BOY_URL)
            show_rollcall(boy_ss, mode="daily_boy")

        elif supervisor_type == "女舍監":
            girl_ss = open_sheet(ROLLCALL_GIRL_URL)
            show_rollcall(girl_ss, mode="daily_girl")

        else:
            st.warning("無法判斷舍監性別")

    elif role == "樓長":

        if str(dorm).startswith("男") or gender == "男":
            boy_ss = open_sheet(ROLLCALL_BOY_URL)
            show_rollcall(boy_ss, mode="daily_boy")

        elif str(dorm).startswith("女") or gender == "女":
            girl_ss = open_sheet(ROLLCALL_GIRL_URL)
            show_rollcall(girl_ss, mode="daily_girl")

        else:
            st.warning("無法判斷樓長宿舍性別")


elif selected_page == "獎懲查詢":
    show_reward_punishment()


elif selected_page == "上學期門禁":
    upper_ss = open_sheet(UPPER_GATE_URL)
    show_gate("上學期門禁", upper_ss, "upper_gate")


elif selected_page == "下學期門禁":
    lower_ss = open_sheet(LOWER_GATE_URL)
    show_gate("下學期門禁", lower_ss, "lower_gate")


elif selected_page == "整潔比賽":
    show_clean()


elif selected_page == "整潔比賽(檢視)":
    show_clean_view()


elif selected_page == "上學期假日點名單":
    show_holiday_rollcall("上學期")


elif selected_page == "下學期假日點名單":
    show_holiday_rollcall("下學期")

