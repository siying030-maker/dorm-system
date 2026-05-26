import streamlit as st


def init_session():
    defaults = {
        "login": False,
        "role": "",
        "user": "",
        "dorm": "",
        "is_main": False
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value