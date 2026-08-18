import streamlit as st

from core.session import (
    init_session,
    restore_login_session,
    mark_user_activity,
    is_session_expired,
    logout_session,
)
from core.google_api import (
    open_sheet,
    sync_all_sheet_data,
    ensure_sheet_data_fresh,
)
from core.config import (
    ROLLCALL_GIRL_URL,
    ROLLCALL_BOY_URL,
    UPPER_GATE_URL,
    LOWER_GATE_URL,
)

from modules.auth import login_page
from modules.tab import build_tabs
from modules.rollcall import show_rollcall
from modules.gate import show_gate
from modules.clean import show_clean, show_clean_view
from modules.attendance import show_attendance
from modules.makeup_rollcall import show_makeup_rollcall
from modules.reward_punishment import show_reward_punishment
from modules.holiday_rollcall import show_holiday_rollcall
from modules.room_password import show_room_password


# ==============================
# 頁面設定
# ==============================

st.set_page_config(
    page_title="宿舍管理系統",
    layout="wide"
)

st.title("宿舍管理系統")


# ==============================
# 初始化與恢復登入狀態
# ==============================

init_session()
restore_login_session()


# ==============================
# 登入頁面
# ==============================

if not st.session_state.get("login", False):
    login_page()
    st.stop()


# ==============================
# 30 分鐘未操作自動登出
# ==============================

# 完整頁面執行代表使用者有操作、重新整理或返回網頁。
# 只有這裡會更新活動時間；下方 fragment 的背景檢查不會延長登入。
mark_user_activity()

# 每次使用者操作時，最多沿用 10 秒資料快取；之後自動讀取最新試算表。
# 不會在每個元件重跑時都打 Google API，可避免 Streamlit Cloud 配額不穩。
ensure_sheet_data_fresh(max_age_seconds=10)


@st.fragment(run_every=15)
def session_timeout_watcher():
    """每 15 秒檢查登入是否已超過 30 分鐘未操作。"""
    if is_session_expired():
        logout_session()
        st.warning("已超過 30 分鐘未操作，系統已自動登出。")
        st.rerun(scope="app")


session_timeout_watcher()


# ==============================
# 登入資訊
# ==============================

st.success(
    f"{st.session_state.get('role', '')} / "
    f"{st.session_state.get('user', '')}"
)


# ==============================
# 登出
# ==============================

if st.button(
    "登出",
    key="logout_btn"
):
    logout_session()
    st.rerun()


# ==============================
# 全系統試算表同步
# ==============================

if st.button(
    "同步最新試算表",
    key="sync_all_sheets_btn",
    use_container_width=True,
):
    sync_all_sheet_data()

    # 清除目前頁面暫存的已載入資料，避免畫面保留舊名單。
    transient_keys = [
        key for key in list(st.session_state.keys())
        if key.startswith((
            "attendance_",
            "makeup_",
            "rollcall_",
            "gate_",
            "reward_",
            "clean_",
            "holiday_",
            "room_password_",
        ))
        and key not in {"sheet_sync_revision"}
    ]

    for key in transient_keys:
        st.session_state.pop(key, None)

    st.success("所有功能已同步最新試算表資料。")
    st.rerun()


# ==============================
# 功能選單
# ==============================

tab_names = build_tabs(
    st.session_state.get("role", ""),
    st.session_state.get("is_main", False)
)

# 移除不要的頁面
tab_names = [
    t for t in tab_names
    if t != "連三天不假外宿"
]

if not tab_names:
    st.warning("目前沒有可用功能")
    st.stop()


# ==============================
# 自訂功能按鈕導覽
# ==============================

if "selected_page" not in st.session_state:
    st.session_state.selected_page = tab_names[0]

if st.session_state.selected_page not in tab_names:
    st.session_state.selected_page = tab_names[0]

cols = st.columns(len(tab_names))

for i, name in enumerate(tab_names):
    with cols[i]:
        if st.button(
            name,
            key=f"nav_btn_{name}",
            use_container_width=True
        ):
            st.session_state.selected_page = name
            st.rerun()

st.divider()

selected_page = st.session_state.selected_page


if selected_page == "點名系統":
    show_attendance()


elif selected_page == "補點名單":
    show_makeup_rollcall()


elif selected_page == "每日點名未到名單":

    role = st.session_state.get("role", "")
    supervisor_type = st.session_state.get("supervisor_type", "")
    dorm = st.session_state.get("dorm", "")
    gender = st.session_state.get("gender", "")

    if role == "行政":
        show_rollcall(mode="daily_all")

    elif role == "舍監":

        if supervisor_type == "男舍監":
            show_rollcall(mode="daily_boy")

        elif supervisor_type == "女舍監":
            show_rollcall(mode="daily_girl")

        else:
            st.warning("無法判斷舍監性別")

    elif role == "樓長":

        if str(dorm).startswith("男") or gender == "男":
            show_rollcall(mode="daily_boy")

        elif str(dorm).startswith("女") or gender == "女":
            show_rollcall(mode="daily_girl")

        else:
            st.warning("無法判斷樓長宿舍性別")


elif selected_page == "獎懲查詢":
    show_reward_punishment()


elif selected_page == "上學期門禁":
    upper_ss = open_sheet(UPPER_GATE_URL)
    show_gate("上學期門禁", upper_ss, "upper_gate")


elif selected_page == "下學期門禁":
    lower_ss = open_sheet(LOWER_GATE_URL)
    show_gate("下學期門禁", lower_ss, "lower_gate")


elif selected_page == "整潔比賽":
    show_clean()


elif selected_page == "整潔比賽(檢視)":
    show_clean_view()


elif selected_page == "上學期假日點名單":
    show_holiday_rollcall("上學期")


elif selected_page == "下學期假日點名單":
    show_holiday_rollcall("下學期")



elif selected_page == "密碼表":
    show_room_password()
