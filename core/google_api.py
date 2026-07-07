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


def rate_limit(seconds=0.5):
    global _last_call

    now = time.time()
    wait = seconds - (now - _last_call)

    if wait > 0:
        time.sleep(wait)

    _last_call = time.time()


def extract_sheet_id(url):
    return url.split("/d/")[1].split("/")[0]


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
    sheet_id = extract_sheet_id(url)

    for i in range(5):
        try:
            rate_limit(0.5)
            return client.open_by_key(sheet_id)

        except Exception as e:
            if "429" in str(e):
                time.sleep((i + 1) * 5)
            else:
                raise e

    raise Exception("Google API 過載，請稍後再試")