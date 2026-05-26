import streamlit as st

from core.session import init_session
from core.google_api import open_sheet
from core.config import (
    ROLLCALL_SHEET_URL,
    UPPER_GATE_URL,
    LOWER_GATE_URL,
)
from modules.auth import login_page
from modules.tab import build_tabs
from modules.rollcall import show_rollcall
from modules.gate import show_gate
from modules.clean import show_clean, show_clean_view




# ==================================================
# 基本設定
# ==================================================

st.set_page_config(
    page_title="宿舍管理系統",
    layout="wide"
)

st.title("宿舍管理系統")

init_session()


# ==================================================
# 登入
# ==================================================

if not st.session_state.login:
    login_page()
    st.stop()


# ==================================================
# 登入成功 / 登出
# ==================================================

st.success(
    f"{st.session_state.role} / {st.session_state.user}"
)

if st.button("登出", key="logout_btn"):
    st.session_state.clear()
    st.rerun()


# ==================================================
# 開啟 Google Sheets
# ==================================================

rollcall_ss = open_sheet(ROLLCALL_SHEET_URL)
upper_ss = open_sheet(UPPER_GATE_URL)
lower_ss = open_sheet(LOWER_GATE_URL)


# ==================================================
# Tabs
# ==================================================

tab_names = build_tabs(
    st.session_state.role,
    st.session_state.is_main
)

if not tab_names:
    st.warning("目前沒有可用功能")
    st.stop()

tabs = st.tabs(tab_names)


# ==================================================
# 分頁內容
# ==================================================

if "連三天不假外宿" in tab_names:
    with tabs[tab_names.index("連三天不假外宿")]:
        show_rollcall(
            rollcall_ss,
            mode="three_days"
        )

if "每日缺席名單" in tab_names:
    with tabs[tab_names.index("每日缺席名單")]:
        show_rollcall(
            rollcall_ss,
            mode="daily"
        )

if "上學期門禁" in tab_names:
    with tabs[tab_names.index("上學期門禁")]:
        show_gate(
            "上學期門禁",
            upper_ss,
            "upper_gate"
        )

if "下學期門禁" in tab_names:
    with tabs[tab_names.index("下學期門禁")]:
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