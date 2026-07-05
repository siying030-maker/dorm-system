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


st.set_page_config(
    page_title="宿舍管理系統",
    layout="wide"
)

st.title("宿舍管理系統")

init_session()

if not st.session_state.login:
    login_page()
    st.stop()

st.success(
    f"{st.session_state.role} / {st.session_state.user}"
)

if st.button("登出", key="logout_btn"):
    st.session_state.clear()
    st.rerun()


tab_names = build_tabs(
    st.session_state.role,
    st.session_state.is_main
)

tab_names = [
    t for t in tab_names
    if t != "連三天不假外宿"
]

if not tab_names:
    st.warning("目前沒有可用功能")
    st.stop()

tabs = st.tabs(tab_names)


if "點名系統" in tab_names:
    with tabs[tab_names.index("點名系統")]:
        show_attendance()


if "每日點名未到名單" in tab_names:
    with tabs[tab_names.index("每日點名未到名單")]:
        show_rollcall(
            mode="daily"
        )


if "補點名單" in tab_names:
    with tabs[tab_names.index("補點名單")]:
        show_makeup_rollcall()


if "獎懲查詢" in tab_names:
    with tabs[tab_names.index("獎懲查詢")]:
        show_reward_punishment()


if "上學期門禁" in tab_names:
    with tabs[tab_names.index("上學期門禁")]:

        upper_ss = open_sheet(UPPER_GATE_URL)

        show_gate(
            "上學期門禁",
            upper_ss,
            "upper_gate"
        )


if "下學期門禁" in tab_names:
    with tabs[tab_names.index("下學期門禁")]:

        lower_ss = open_sheet(LOWER_GATE_URL)

        show_gate(
            "下學期門禁",
            lower_ss,
            "lower_gate"
        )


if "整潔比賽" in tab_names:
    with tabs[tab_names.index("整潔比賽")]:
        show_clean()


if "整潔比賽(檢視)" in tab_names:
    with tabs[tab_names.index("整潔比賽(檢視)")]:
        show_clean_view()

if "上學期假日點名單" in tab_names:
    with tabs[tab_names.index("上學期假日點名單")]:
        show_holiday_rollcall("上學期")

if "下學期假日點名單" in tab_names:
    with tabs[tab_names.index("下學期假日點名單")]:
        show_holiday_rollcall("下學期")