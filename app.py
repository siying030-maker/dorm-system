import streamlit as st

from core.session import init_session
from auth.login import login_page
from modules.gate import analyze_gate
from modules.clean import query_clean

init_session()

st.title("宿舍管理系統")

if not st.session_state.login:
    login_page()
    st.stop()

st.success(f"{st.session_state.role} / {st.session_state.user}")

if st.button("登出"):
    st.session_state.clear()
    st.rerun()

