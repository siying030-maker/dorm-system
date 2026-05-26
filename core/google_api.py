import time
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

CACHE_TTL = 3600

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

_last_call = 0

def rate_limit():
    global _last_call
    now = time.time()

    if now - _last_call < 0.3:
        time.sleep(0.3)

    _last_call = time.time()


@st.cache_resource(ttl=CACHE_TTL)
def get_client():
    creds = Credentials.from_service_account_info(
        st.secrets["google"],
        scopes=SCOPES
    )
    return gspread.authorize(creds)


@st.cache_resource(ttl=CACHE_TTL)
def open_sheet(url):
    client = get_client()

    for i in range(5):
        try:
            rate_limit()
            return client.open_by_url(url)

        except Exception as e:
            if "429" in str(e):
                time.sleep((i + 1) * 5)
            else:
                raise e

    raise Exception("Google API 過載")