import random
import threading
import time
from typing import Any, Callable, Optional

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError


# ==================================================
# 基本設定
# ==================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CLIENT_CACHE_TTL = 3600
SHEET_CACHE_TTL = 3600

MAX_RETRIES = 6
MIN_REQUEST_INTERVAL = 0.45

_request_lock = threading.Lock()
_last_request_time = 0.0


# ==================================================
# API 限速
# ==================================================

def rate_limit(seconds: float = MIN_REQUEST_INTERVAL) -> None:
    """
    確保 Google API 請求之間保留最小間隔，
    避免短時間大量請求造成 429。
    """
    global _last_request_time

    with _request_lock:
        now = time.time()
        wait_time = seconds - (now - _last_request_time)

        if wait_time > 0:
            time.sleep(wait_time)

        _last_request_time = time.time()


# ==================================================
# 錯誤判斷
# ==================================================

def get_api_status_code(error: Exception) -> Optional[int]:
    if isinstance(error, APIError):
        try:
            return int(error.response.status_code)
        except Exception:
            pass

    text = str(error)

    for code in [429, 500, 502, 503, 504]:
        if str(code) in text:
            return code

    return None


def is_retryable_error(error: Exception) -> bool:
    status_code = get_api_status_code(error)

    if status_code in [429, 500, 502, 503, 504]:
        return True

    text = str(error).lower()

    retry_keywords = [
        "quota exceeded",
        "rate limit",
        "service is currently unavailable",
        "temporarily unavailable",
        "backend error",
        "internal error",
        "timeout",
        "connection reset",
        "connection aborted",
        "remote end closed connection",
    ]

    return any(keyword in text for keyword in retry_keywords)


# ==================================================
# 自動重試
# ==================================================

def retry_call(
    func: Callable[[], Any],
    retries: int = MAX_RETRIES,
    base_wait: float = 1.0,
) -> Any:
    """
    遇到 429、500、502、503、504 時自動重試。

    等待時間大致為：
    1、2、4、8、16、32 秒，再加少量隨機時間。
    """
    last_error = None

    for attempt in range(retries):
        try:
            rate_limit()
            return func()

        except Exception as error:
            last_error = error

            if not is_retryable_error(error):
                raise

            if attempt >= retries - 1:
                break

            wait_time = (
                base_wait * (2 ** attempt)
                + random.uniform(0.2, 0.9)
            )

            time.sleep(wait_time)

    raise RuntimeError(
        f"Google API 多次重試後仍無法連線：{last_error}"
    )


# ==================================================
# 取得 Google Client
# ==================================================

@st.cache_resource(ttl=CLIENT_CACHE_TTL)
def get_client():
    credentials = Credentials.from_service_account_info(
        st.secrets["google"],
        scopes=SCOPES,
    )

    return gspread.authorize(credentials)


# ==================================================
# 網址處理
# ==================================================

def extract_sheet_id(url_or_id: str) -> str:
    value = str(url_or_id).strip()

    if "/d/" in value:
        return value.split("/d/")[1].split("/")[0]

    return value


# ==================================================
# 開啟試算表
# ==================================================

@st.cache_resource(ttl=SHEET_CACHE_TTL)
def open_sheet(url_or_id: str):
    client = get_client()
    sheet_id = extract_sheet_id(url_or_id)

    return retry_call(
        lambda: client.open_by_key(sheet_id),
        retries=MAX_RETRIES,
        base_wait=1.5,
    )


# ==================================================
# Worksheet 操作
# ==================================================

def get_worksheet(spreadsheet, sheet_name: str):
    return retry_call(
        lambda: spreadsheet.worksheet(sheet_name),
        retries=MAX_RETRIES,
        base_wait=1.0,
    )


def get_first_worksheet(spreadsheet):
    worksheet = retry_call(
        lambda: spreadsheet.get_worksheet(0),
        retries=MAX_RETRIES,
        base_wait=1.0,
    )

    if worksheet is None:
        raise RuntimeError("試算表沒有任何工作表")

    return worksheet


def get_worksheets(spreadsheet):
    return retry_call(
        lambda: spreadsheet.worksheets(),
        retries=MAX_RETRIES,
        base_wait=1.0,
    )


# ==================================================
# 讀取資料
# ==================================================

def get_all_values(
    worksheet,
    value_render_option: Optional[str] = None,
):
    if value_render_option:
        return retry_call(
            lambda: worksheet.get_all_values(
                value_render_option=value_render_option
            ),
            retries=MAX_RETRIES,
            base_wait=1.0,
        )

    return retry_call(
        lambda: worksheet.get_all_values(),
        retries=MAX_RETRIES,
        base_wait=1.0,
    )


def get_values(
    worksheet,
    range_name: str,
    value_render_option: Optional[str] = None,
):
    if value_render_option:
        return retry_call(
            lambda: worksheet.get(
                range_name,
                value_render_option=value_render_option,
            ),
            retries=MAX_RETRIES,
            base_wait=1.0,
        )

    return retry_call(
        lambda: worksheet.get(range_name),
        retries=MAX_RETRIES,
        base_wait=1.0,
    )


# ==================================================
# 寫入資料
# ==================================================

def append_row(worksheet, row: list):
    return retry_call(
        lambda: worksheet.append_row(
            row,
            value_input_option="USER_ENTERED",
        ),
        retries=MAX_RETRIES,
        base_wait=1.5,
    )


def append_rows(worksheet, rows: list):
    if not rows:
        return None

    return retry_call(
        lambda: worksheet.append_rows(
            rows,
            value_input_option="USER_ENTERED",
        ),
        retries=MAX_RETRIES,
        base_wait=1.5,
    )


def update_cell(
    worksheet,
    row: int,
    col: int,
    value: Any,
):
    return retry_call(
        lambda: worksheet.update_cell(row, col, value),
        retries=MAX_RETRIES,
        base_wait=1.5,
    )


def add_worksheet(
    spreadsheet,
    title: str,
    rows: int = 3000,
    cols: int = 20,
):
    return retry_call(
        lambda: spreadsheet.add_worksheet(
            title=title,
            rows=rows,
            cols=cols,
        ),
        retries=MAX_RETRIES,
        base_wait=1.5,
    )


def reorder_worksheets(spreadsheet, worksheets):
    return retry_call(
        lambda: spreadsheet.reorder_worksheets(worksheets),
        retries=MAX_RETRIES,
        base_wait=1.5,
    )