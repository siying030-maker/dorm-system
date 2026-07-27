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

# 這個密鑰必須在伺服器重新啟動後保持一致，才能讓使用者返回網頁時恢復登入。
# 若 Streamlit secrets 有設定 SESSION_SECRET，會優先使用；沒有設定時使用專案固定值產生。
def _get_session_secret():
    try:
        secret = st.secrets.get("SESSION_SECRET", "")
    except Exception:
        secret = ""

    if not secret:
        secret = os.environ.get("SESSION_SECRET", "")

    if not secret:
        secret = hashlib.sha256(
            ("dorm-system-session-v2|" + ADMIN_SHEET_URL).encode("utf-8")
        ).hexdigest()

    return str(secret).encode("utf-8")


def _b64encode(raw):
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def _session_payload():
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


def _create_token():
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


def _decode_token(token):
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

        last_active = float(payload.get("last_active_time", 0))

        if time.time() - last_active >= SESSION_TIMEOUT_SECONDS:
            return None

        return payload

    except Exception:
        return None


def _get_query_token():
    try:
        return str(st.query_params.get(SESSION_QUERY_KEY, "")).strip()
    except Exception:
        return ""


def _set_query_token(token):
    try:
        current = _get_query_token()
        if current != token:
            st.query_params[SESSION_QUERY_KEY] = token
    except Exception:
        pass


def _clear_query_token():
    try:
        if SESSION_QUERY_KEY in st.query_params:
            del st.query_params[SESSION_QUERY_KEY]
    except Exception:
        pass


def init_session():
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


def restore_login_session():
    """新分頁、重新整理或離開後返回時，從網址中的簽章權杖恢復登入。"""
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


def mark_user_activity():
    """只有完整頁面重跑（使用者操作或重新進入網頁）才更新活動時間。"""
    if not st.session_state.get("login", False):
        return

    st.session_state["last_active_time"] = time.time()
    _set_query_token(_create_token())


def seconds_until_logout():
    if not st.session_state.get("login", False):
        return 0

    last_active = float(st.session_state.get("last_active_time", 0) or 0)
    return max(0, int(SESSION_TIMEOUT_SECONDS - (time.time() - last_active)))


def is_session_expired():
    if not st.session_state.get("login", False):
        return False

    last_active = float(st.session_state.get("last_active_time", 0) or 0)
    return time.time() - last_active >= SESSION_TIMEOUT_SECONDS


def logout_session():
    """清除登入資料與網址權杖，穩定回到登入頁。"""
    _clear_query_token()
    st.session_state.clear()
    init_session()
