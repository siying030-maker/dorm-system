import time
import random
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials


CACHE_TTL = 3600

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_last_call = 0


def rate_limit(seconds=0.6):
    global _last_call

    now = time.time()
    wait = seconds - (now - _last_call)

    if wait > 0:
        time.sleep(wait)

    _last_call = time.time()


def extract_sheet_id(url):
    return url.split("/d/")[1].split("/")[0]


def is_retryable_error(error):
    text = str(error)

    retry_keywords = [
        "429",
        "Quota exceeded",
        "Rate Limit",
        "Internal error",
        "Backend Error",
        "503",
        "500",
        "timeout",
        "temporarily unavailable",
    ]

    return any(k.lower() in text.lower() for k in retry_keywords)


def retry_call(func, retries=5, base_wait=1.5):

    last_error = None

    for attempt in range(retries):

        try:
            rate_limit()
            return func()

        except Exception as e:
            last_error = e

            if not is_retryable_error(e):
                raise e

            wait = base_wait * (2 ** attempt) + random.uniform(0, 0.8)
            time.sleep(wait)

    raise Exception(f"Google API 連線失敗，請稍後再試：{last_error}")


@st.cache_resource(ttl=CACHE_TTL)
def get_client():

    creds = Credentials.from_service_account_info(
        st.secrets["google"],
        scopes=SCOPES,
    )

    return gspread.authorize(creds)


@st.cache_resource(ttl=CACHE_TTL)
def open_sheet(url):

    client = get_client()
    sheet_id = extract_sheet_id(url)

    return retry_call(
        lambda: client.open_by_key(sheet_id),
        retries=5,
        base_wait=2,
    )


def get_worksheet(spreadsheet, sheet_name):

    return retry_call(
        lambda: spreadsheet.worksheet(sheet_name),
        retries=5,
        base_wait=1.5,
    )


def get_first_worksheet(spreadsheet):

    return retry_call(
        lambda: spreadsheet.get_worksheet(0),
        retries=5,
        base_wait=1.5,
    )


def get_worksheets(spreadsheet):

    return retry_call(
        lambda: spreadsheet.worksheets(),
        retries=5,
        base_wait=1.5,
    )


def get_values(worksheet, range_name=None):

    if range_name:
        return retry_call(
            lambda: worksheet.get(range_name),
            retries=5,
            base_wait=1.5,
        )

    return retry_call(
        lambda: worksheet.get_all_values(),
        retries=5,
        base_wait=1.5,
    )


def get_all_values(worksheet, value_render_option=None):

    if value_render_option:
        return retry_call(
            lambda: worksheet.get_all_values(
                value_render_option=value_render_option
            ),
            retries=5,
            base_wait=1.5,
        )

    return retry_call(
        lambda: worksheet.get_all_values(),
        retries=5,
        base_wait=1.5,
    )


def append_row(worksheet, row):

    return retry_call(
        lambda: worksheet.append_row(row),
        retries=5,
        base_wait=1.5,
    )


def append_rows(worksheet, rows):

    if not rows:
        return None

    return retry_call(
        lambda: worksheet.append_rows(rows),
        retries=5,
        base_wait=1.5,
    )


def update_cell(worksheet, row, col, value):

    return retry_call(
        lambda: worksheet.update_cell(row, col, value),
        retries=5,
        base_wait=1.5,
    )


def add_worksheet(spreadsheet, title, rows=3000, cols=20):

    return retry_call(
        lambda: spreadsheet.add_worksheet(
            title=title,
            rows=rows,
            cols=cols,
        ),
        retries=5,
        base_wait=1.5,
    )


def reorder_worksheets(spreadsheet, worksheets):

    return retry_call(
        lambda: spreadsheet.reorder_worksheets(worksheets),
        retries=5,
        base_wait=1.5,
    )