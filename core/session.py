import base64
import hashlib
import hmac
import json
import os
import time

import streamlit as st

from core.config import ADMIN_SHEET_URL


SESSION_TIMEOUT_SECONDS = 30 * 60
SESSION_QUERY_KEY = "login_session"


# 固定簽章密鑰：Streamlit Cloud 重啟後仍可驗證網址中的登入權杖。
# 正式環境建議在 Streamlit secrets 設定：
# SESSION_SECRET = "一段夠長且固定的隨機字串"
def _get_session_secret() -> bytes:
    try:
        secret = st.secrets.get("SESSION_SECRET", "")
    except Exception:
        secret = ""

    if not secret:
        secret = os.environ.get("SESSION_SECRET", "")

    if not secret:
        secret = hashlib.sha256(
            ("dorm-system-session-v3|" + ADMIN_SHEET_URL).encode("utf-8")
        ).hexdigest()

    return str(secret).encode("utf-8")


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def _session_payload() -> dict:
    return {
        "login": bool(st.session_state.get("login", False)),
        "role": st.session_state.get("role", ""),
        "user": st.session_state.get("user", ""),
        "dorm": st.session_state.get("dorm", ""),
        "gender": st.session_state.get("gender", ""),
        "supervisor_type": st.session_state.get("supervisor_type", ""),
        "is_main": bool(st.session_state.get("is_main", False)),
        "manage_dorms": st.session_state.get("manage_dorms", ""),
        "winter_dorms": st.session_state.get("winter_dorms", ""),
        "winter_floors": st.session_state.get("winter_floors", ""),
        "summer_dorms": st.session_state.get("summer_dorms", ""),
        "summer_floors": st.session_state.get("summer_floors", ""),
        "last_active_time": float(
            st.session_state.get("last_active_time", time.time())
        ),
    }


def _create_token() -> str:
    payload_bytes = json.dumps(
        _session_payload(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    payload_part = _b64encode(payload_bytes)
    signature = hmac.new(
        _get_session_secret(),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    return f"{payload_part}.{_b64encode(signature)}"


def _decode_token(token: str):
    try:
        payload_part, signature_part = str(token).split(".", 1)
        expected_signature = hmac.new(
            _get_session_secret(),
            payload_part.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        actual_signature = _b64decode(signature_part)

        if not hmac.compare_digest(expected_signature, actual_signature):
            return None

        payload = json.loads(_b64decode(payload_part).decode("utf-8"))
        if not payload.get("login", False):
            return None

        last_active = float(payload.get("last_active_time", 0) or 0)
        if last_active <= 0:
            return None

        if time.time() - last_active >= SESSION_TIMEOUT_SECONDS:
            return None

        return payload
    except Exception:
        return None


def _get_query_token() -> str:
    try:
        value = st.query_params.get(SESSION_QUERY_KEY, "")
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        return str(value).strip()
    except Exception:
        return ""


def _set_query_token(token: str) -> None:
    try:
        if _get_query_token() != token:
            st.query_params[SESSION_QUERY_KEY] = token
    except Exception:
        pass


def _clear_query_token() -> None:
    try:
        if SESSION_QUERY_KEY in st.query_params:
            del st.query_params[SESSION_QUERY_KEY]
    except Exception:
        pass


def init_session() -> None:
    defaults = {
        "login": False,
        "role": "",
        "user": "",
        "dorm": "",
        "gender": "",
        "supervisor_type": "",
        "is_main": False,
        "manage_dorms": "",
        "winter_dorms": "",
        "winter_floors": "",
        "summer_dorms": "",
        "summer_floors": "",
        "last_active_time": 0.0,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def restore_login_session() -> bool:
    """F5、重新開啟分頁或離開後返回時，從簽章權杖恢復登入。"""
    if st.session_state.get("login", False):
        return True

    token = _get_query_token()
    if not token:
        return False

    payload = _decode_token(token)
    if payload is None:
        _clear_query_token()
        return False

    for key, value in payload.items():
        st.session_state[key] = value

    return True


def mark_user_activity() -> None:
    """
    完整頁面因使用者操作、F5 或返回網頁而重跑時，更新活動時間。
    fragment 的背景逾時檢查不會呼叫本函式，因此不會無限延長登入。
    """
    if not st.session_state.get("login", False):
        return

    st.session_state["last_active_time"] = time.time()
    _set_query_token(_create_token())


def seconds_until_logout() -> int:
    if not st.session_state.get("login", False):
        return 0

    last_active = float(st.session_state.get("last_active_time", 0) or 0)
    return max(0, int(SESSION_TIMEOUT_SECONDS - (time.time() - last_active)))


def is_session_expired() -> bool:
    if not st.session_state.get("login", False):
        return False

    last_active = float(st.session_state.get("last_active_time", 0) or 0)
    if last_active <= 0:
        return True

    return time.time() - last_active >= SESSION_TIMEOUT_SECONDS


def logout_session() -> None:
    """主動登出或逾時時，清除登入資料並回到登入頁。"""
    _clear_query_token()
    st.session_state.clear()
    init_session()
