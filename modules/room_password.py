import pandas as pd
import streamlit as st

from core.config import UPPER_ROOM_PASSWORD
from core.google_api import (
    open_sheet,
    get_worksheet,
    get_all_values,
    append_row,
    update_cell,
)


DORM_ROOM_PREFIX = {
    "女一": "81",
    "女二": "82",
    "女三": "83",
    "男一": "82",
    "男三": "83",
}

ALL_DORMS = ["女一", "女二", "女三", "男一", "男三"]


def normalize_dorm(value):
    return str(value).strip().replace("ㄧ", "一")


def normalize_room(value):
    value = str(value).strip().replace(" ", "")

    if value.endswith(".0"):
        value = value[:-2]

    if value.upper() in ["NAN", "NONE", "NA"]:
        return ""

    return value


def split_dorms(value):
    result = []

    for item in str(value).replace("，", ",").split(","):
        item = normalize_dorm(item)
        if item and item in ALL_DORMS:
            result.append(item)

    return list(dict.fromkeys(result))


def get_allowed_dorms():
    role = st.session_state.get("role", "")

    # 行政與生輔工讀可以查詢全部宿舍
    if role in ["行政", "生輔工讀"]:
        return ALL_DORMS.copy()

    if role == "樓長":
        allowed = []

        for value in [
            st.session_state.get("dorm", ""),
            st.session_state.get("manage_dorms", ""),
            st.session_state.get("winter_dorms", ""),
            st.session_state.get("summer_dorms", ""),
        ]:
            allowed.extend(split_dorms(value))

        return list(dict.fromkeys(allowed))

    return []


def can_write_password():
    # 依需求：只有樓長能新增／修改密碼
    return st.session_state.get("role", "") == "樓長"


@st.cache_data(ttl=10, show_spinner=False)
def load_room_passwords(dorm):
    dorm = normalize_dorm(dorm)

    if dorm not in ALL_DORMS:
        return pd.DataFrame(columns=["房號", "密碼"])

    try:
        ss = open_sheet(UPPER_ROOM_PASSWORD)
        ws = get_worksheet(ss, dorm)
        values = get_all_values(ws)

        if not values:
            return pd.DataFrame(columns=["房號", "密碼"])

        headers = [str(x).strip() for x in values[0]]

        if len(headers) < 2:
            return pd.DataFrame(columns=["房號", "密碼"])

        df = pd.DataFrame(values[1:], columns=headers)
        df.columns = df.columns.astype(str).str.strip()

        if "房號" not in df.columns or "密碼" not in df.columns:
            return pd.DataFrame(columns=["房號", "密碼"])

        df = df[["房號", "密碼"]].copy()
        df["房號"] = df["房號"].astype(str).map(normalize_room)
        df["密碼"] = df["密碼"].astype(str).str.strip()

        df = df[df["房號"] != ""].copy()
        return df.reset_index(drop=True)

    except Exception as error:
        st.error(f"讀取 {dorm} 房間密碼失敗：{error}")
        return pd.DataFrame(columns=["房號", "密碼"])


def save_room_password(dorm, room, password):
    dorm = normalize_dorm(dorm)
    room = normalize_room(room)
    password = str(password).strip()

    if dorm not in ALL_DORMS:
        raise ValueError("宿舍設定錯誤")

    if room == "":
        raise ValueError("請輸入房號")

    if password == "":
        raise ValueError("請輸入密碼")

    expected_prefix = DORM_ROOM_PREFIX.get(dorm, "")

    if expected_prefix and not room.startswith(expected_prefix):
        raise ValueError(
            f"{dorm} 房號應以 {expected_prefix} 開頭，例如 {expected_prefix}101"
        )

    ss = open_sheet(UPPER_ROOM_PASSWORD)
    ws = get_worksheet(ss, dorm)
    values = get_all_values(ws)

    # 工作表為空時先補標題
    if not values:
        append_row(ws, ["房號", "密碼"])
        values = [["房號", "密碼"]]

    headers = [str(x).strip() for x in values[0]]

    if "房號" not in headers or "密碼" not in headers:
        raise ValueError(f"{dorm} 工作表必須有「房號」與「密碼」欄位")

    room_col = headers.index("房號") + 1
    password_col = headers.index("密碼") + 1

    # 同一房號已存在：直接更新密碼，不重複新增房號
    for row_index, row in enumerate(values[1:], start=2):
        existing_room = ""
        if len(row) >= room_col:
            existing_room = normalize_room(row[room_col - 1])

        if existing_room == room:
            update_cell(ws, row_index, password_col, password)
            load_room_passwords.clear()
            return "updated"

    # 新房號：新增一列，保持欄位順序
    new_row = [""] * max(len(headers), 2)
    new_row[room_col - 1] = room
    new_row[password_col - 1] = password
    append_row(ws, new_row)
    load_room_passwords.clear()
    return "created"


def show_room_password():
    st.header("密碼表")

    role = st.session_state.get("role", "")
    allowed_dorms = get_allowed_dorms()

    if not allowed_dorms:
        st.warning("目前沒有密碼表權限")
        return

    if st.button(
        "重新整理密碼表",
        key="refresh_room_password",
    ):
        load_room_passwords.clear()
        st.rerun()

    dorm = st.selectbox(
        "宿舍",
        allowed_dorms,
        key="room_password_dorm",
    )

    st.caption(
        f"房號規則：{dorm} 房號以 {DORM_ROOM_PREFIX.get(dorm, '')} 開頭"
    )

    # ==================================================
    # 查詢
    # ==================================================
    st.subheader("查詢房間密碼")

    search_room = st.text_input(
        "輸入房號查詢",
        key="room_password_search",
        placeholder="例如：81101",
    )

    df = load_room_passwords(dorm)

    if search_room:
        target = normalize_room(search_room)
        result = df[df["房號"] == target].copy()

        if result.empty:
            st.warning("查無此房號")
        else:
            st.dataframe(
                result[["房號", "密碼"]],
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("請輸入房號進行查詢")

    # 行政與生輔工讀到此為止，只能查詢
    if not can_write_password():
        if role == "行政":
            st.caption("行政權限：僅可查詢房間密碼")
        elif role == "生輔工讀":
            st.caption("生輔工讀權限：僅可查詢房間密碼")
        return

    # ==================================================
    # 樓長新增／修改
    # ==================================================
    st.divider()
    st.subheader("新增 / 修改房間密碼")

    with st.form("room_password_save_form", clear_on_submit=False):
        room = st.text_input(
            "房號",
            key="room_password_write_room",
            placeholder="例如：81101",
        )

        password = st.text_input(
            "密碼",
            key="room_password_write_password",
        )

        submitted = st.form_submit_button(
            "儲存密碼",
            use_container_width=True,
        )

    if submitted:
        try:
            action = save_room_password(
                dorm,
                room,
                password,
            )

            if action == "updated":
                st.success("房號已存在，密碼已更新。")
            else:
                st.success("房號與密碼已新增。")

            st.rerun()

        except Exception as error:
            st.error(f"儲存失敗：{error}")
