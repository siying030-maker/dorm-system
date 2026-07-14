import random
import threading
import time
from typing import Any, Callable, Optional

import gspread
import streamlit as st

from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError


# ==================================================
# Google API 權限
# ==================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ==================================================
# 基本設定
# ==================================================

# Google Client 快取時間
CLIENT_CACHE_TTL = 3600

# Spreadsheet 連線快取時間
SHEET_CACHE_TTL = 3600

# 最大重試次數
MAX_RETRIES = 6

# 每次 API 請求最少間隔秒數
MIN_REQUEST_INTERVAL = 0.25


# ==================================================
# 執行緒安全限速
# ==================================================

_request_lock = threading.Lock()
_last_request_time = 0.0


def rate_limit(
    seconds: float = MIN_REQUEST_INTERVAL
) -> None:
    """
    確保 Google API 請求之間保留最小間隔，
    降低發生 429 配額限制的機率。
    """

    global _last_request_time

    with _request_lock:

        now = time.time()

        wait_time = (
            seconds
            -
            (now - _last_request_time)
        )

        if wait_time > 0:
            time.sleep(wait_time)

        _last_request_time = time.time()


# ==================================================
# Google API 錯誤判斷
# ==================================================

def get_api_status_code(
    error: Exception
) -> Optional[int]:
    """
    嘗試取得 Google API HTTP 狀態碼。
    """

    if isinstance(error, APIError):

        try:
            return int(
                error.response.status_code
            )

        except Exception:
            pass

    error_text = str(error)

    for status_code in [
        429,
        500,
        502,
        503,
        504,
    ]:

        if str(status_code) in error_text:
            return status_code

    return None


def is_retryable_error(
    error: Exception
) -> bool:
    """
    判斷錯誤是否可以自動重試。
    """

    status_code = get_api_status_code(
        error
    )

    if status_code in [
        429,
        500,
        502,
        503,
        504,
    ]:
        return True

    error_text = str(error).lower()

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
        "read timed out",
        "connection timed out",
    ]

    return any(
        keyword in error_text
        for keyword in retry_keywords
    )


# ==================================================
# Google API 自動重試
# ==================================================

def retry_call(
    func: Callable[[], Any],
    retries: int = MAX_RETRIES,
    base_wait: float = 1.0,
) -> Any:
    """
    遇到 429、500、502、503、504 時自動重試。

    等待時間：
    約 1、2、4、8、16、32 秒，
    並加入少量隨機時間避免同時重試。
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
                +
                random.uniform(0.2, 0.9)
            )

            time.sleep(wait_time)

    raise RuntimeError(
        "Google API 多次重試後仍無法連線："
        f"{last_error}"
    )


# ==================================================
# 取得 Google Client
# ==================================================

@st.cache_resource(
    ttl=CLIENT_CACHE_TTL
)
def get_client():
    """
    建立並快取 Google API Client。
    整個 Streamlit App 共用同一個連線。
    """

    credentials = (
        Credentials
        .from_service_account_info(
            st.secrets["google"],
            scopes=SCOPES,
        )
    )

    return gspread.authorize(
        credentials
    )


# ==================================================
# 試算表網址處理
# ==================================================

def extract_sheet_id(
    url_or_id: str
) -> str:
    """
    從 Google Sheet 網址中取出 Spreadsheet ID。
    如果傳入的已經是 ID，直接回傳。
    """

    value = str(
        url_or_id
    ).strip()

    if "/d/" in value:

        return (
            value
            .split("/d/")[1]
            .split("/")[0]
        )

    return value


# ==================================================
# 開啟 Google 試算表
# ==================================================

@st.cache_resource(
    ttl=SHEET_CACHE_TTL
)
def open_sheet(
    url_or_id: str
):
    """
    開啟 Google 試算表並快取 Spreadsheet 物件。
    """

    client = get_client()

    sheet_id = extract_sheet_id(
        url_or_id
    )

    return retry_call(
        lambda: client.open_by_key(
            sheet_id
        ),
        retries=MAX_RETRIES,
        base_wait=1.5,
    )


# ==================================================
# Worksheet 操作
# ==================================================

def get_worksheet(
    spreadsheet,
    sheet_name: str
):
    """
    取得指定名稱的 Worksheet。
    """

    return retry_call(
        lambda: spreadsheet.worksheet(
            sheet_name
        ),
        retries=MAX_RETRIES,
        base_wait=1.0,
    )


def get_first_worksheet(
    spreadsheet
):
    """
    取得第一個 Worksheet。
    """

    worksheet = retry_call(
        lambda: spreadsheet.get_worksheet(
            0
        ),
        retries=MAX_RETRIES,
        base_wait=1.0,
    )

    if worksheet is None:
        raise RuntimeError(
            "試算表沒有任何工作表"
        )

    return worksheet


def get_worksheets(
    spreadsheet
):
    """
    取得所有 Worksheets。
    """

    return retry_call(
        lambda: spreadsheet.worksheets(),
        retries=MAX_RETRIES,
        base_wait=1.0,
    )


# ==================================================
# 讀取 Google Sheet
# ==================================================

def get_all_values(
    worksheet,
    value_render_option: Optional[str] = None,
):
    """
    讀取 Worksheet 所有資料。
    """

    if value_render_option:

        return retry_call(
            lambda: worksheet.get_all_values(
                value_render_option=(
                    value_render_option
                )
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
    """
    讀取指定範圍，例如 A:Q、A1:F100。
    """

    if value_render_option:

        return retry_call(
            lambda: worksheet.get(
                range_name,
                value_render_option=(
                    value_render_option
                ),
            ),
            retries=MAX_RETRIES,
            base_wait=1.0,
        )

    return retry_call(
        lambda: worksheet.get(
            range_name
        ),
        retries=MAX_RETRIES,
        base_wait=1.0,
    )


# ==================================================
# 寫入 Google Sheet
# ==================================================

def append_row(
    worksheet,
    row: list
):
    """
    新增單筆資料。
    """

    return retry_call(
        lambda: worksheet.append_row(
            row,
            value_input_option=(
                "USER_ENTERED"
            ),
        ),
        retries=MAX_RETRIES,
        base_wait=1.5,
    )


def append_rows(
    worksheet,
    rows: list
):
    """
    一次新增多筆資料。
    """

    if not rows:
        return None

    return retry_call(
        lambda: worksheet.append_rows(
            rows,
            value_input_option=(
                "USER_ENTERED"
            ),
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
    """
    更新單一儲存格。
    """

    return retry_call(
        lambda: worksheet.update_cell(
            row,
            col,
            value
        ),
        retries=MAX_RETRIES,
        base_wait=1.5,
    )


def update_range(
    worksheet,
    range_name: str,
    values: list,
):
    """
    更新指定儲存格範圍。
    """

    return retry_call(
        lambda: worksheet.update(
            range_name=range_name,
            values=values,
            value_input_option=(
                "USER_ENTERED"
            ),
        ),
        retries=MAX_RETRIES,
        base_wait=1.5,
    )


# ==================================================
# 建立與排列 Worksheet
# ==================================================

def add_worksheet(
    spreadsheet,
    title: str,
    rows: int = 3000,
    cols: int = 20,
):
    """
    建立新的 Worksheet。
    """

    return retry_call(
        lambda: spreadsheet.add_worksheet(
            title=title,
            rows=rows,
            cols=cols,
        ),
        retries=MAX_RETRIES,
        base_wait=1.5,
    )


def reorder_worksheets(
    spreadsheet,
    worksheets
):
    """
    重新排列 Worksheets。
    """

    return retry_call(
        lambda: spreadsheet.reorder_worksheets(
            worksheets
        ),
        retries=MAX_RETRIES,
        base_wait=1.5,
    )