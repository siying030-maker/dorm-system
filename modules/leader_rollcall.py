import streamlit as st
import pandas as pd

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.google_api import (
    open_sheet,
    get_worksheet,
    get_all_values,
)

from core.config import ADMIN_SHEET_URL


# =========================================================
# 基本設定
# =========================================================

TZ = ZoneInfo("Asia/Taipei")

ROLLCALL_RECORD_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1S4yvnH9Eh7wYEUgmViQe8v_IgFyV7w1-fx494TGtffM"
    "/edit?usp=sharing"
)

RECORD_HEADERS = [
    "宿舍",
    "姓名",
    "送出時間",
]


# =========================================================
# 共用函式
# =========================================================

def normalize_text(value):
    return str(value).strip()


def normalize_dorm(value):
    value = normalize_text(value)

    value = (
        value
        .replace("ㄧ", "一")
        .replace("，", ",")
        .replace("、", ",")
        .replace("宿", "")
    )

    return value.strip()


def get_today():
    return datetime.now(TZ).date()


def get_target_date():
    """
    00:00～23:59 顯示當天檢查結果。

    例如：
    2026/09/22 00:00
    → 檢查 2026/09/21 的點名

    06:00 前也仍然顯示前一天。
    """

    now = datetime.now(TZ)

    if now.hour == 0:
        return now.date() - timedelta(days=1)

    return now.date()


# =========================================================
# 讀取 ADMIN 樓長資料
# =========================================================

@st.cache_data(ttl=30, show_spinner=False)
def load_leader_list():

    ss = open_sheet(ADMIN_SHEET_URL)

    # ADMIN 第一個工作表
    try:
        ws = ss.worksheets()[0]
    except Exception:
        raise Exception("找不到 ADMIN 樓長工作表")

    values = get_all_values(ws)

    if not values or len(values) <= 1:
        return pd.DataFrame()

    df = pd.DataFrame(
        values[1:],
        columns=values[0],
    )

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
    )

    # -----------------------------------------------------
    # 只抓「樓長」
    # -----------------------------------------------------

    if "角色" in df.columns:

        df = df[
            df["角色"]
            .astype(str)
            .str.strip()
            .eq("樓長")
        ].copy()

    elif "總樓" in df.columns:

        # 如果 ADMIN 表沒有「角色」，
        # 依你目前帳號格式，非「是」的帳號仍可能是樓長。
        #
        # 實際角色如果是由程式另外判斷，
        # 這裡保留所有有宿舍資料的帳號。
        pass

    # -----------------------------------------------------
    # 姓名
    # -----------------------------------------------------

    if "姓名" not in df.columns:

        if "使用者" in df.columns:
            df["姓名"] = df["使用者"]

        else:
            df["姓名"] = ""

    # -----------------------------------------------------
    # 宿舍
    # -----------------------------------------------------

    if "宿舍" not in df.columns:
        df["宿舍"] = ""

    df["姓名"] = (
        df["姓名"]
        .astype(str)
        .str.strip()
    )

    df["宿舍"] = (
        df["宿舍"]
        .astype(str)
        .str.strip()
    )

    # -----------------------------------------------------
    # 移除沒有宿舍的帳號
    # -----------------------------------------------------

    df = df[
        df["宿舍"].astype(str).str.strip().ne("")
    ].copy()

    # -----------------------------------------------------
    # 如果一個樓長管理多個宿舍
    # 例如：
    # 女一，女二，女三
    # 拆成多筆
    # -----------------------------------------------------

    rows = []

    for _, row in df.iterrows():

        name = normalize_text(row.get("姓名", ""))
        dorm_text = normalize_text(row.get("宿舍", ""))

        if not name or not dorm_text:
            continue

        dorm_text = (
            dorm_text
            .replace("，", ",")
            .replace("、", ",")
            .replace("/", ",")
            .replace("／", ",")
        )

        dorms = [
            normalize_dorm(x)
            for x in dorm_text.split(",")
            if normalize_dorm(x)
        ]

        for dorm in dorms:

            rows.append({
                "姓名": name,
                "宿舍": dorm,
            })

    if not rows:
        return pd.DataFrame(
            columns=["姓名", "宿舍"]
        )

    result = pd.DataFrame(rows)

    # 同一個樓長 + 同一宿舍只留一筆
    result = result.drop_duplicates(
        subset=["姓名", "宿舍"]
    )

    return result.reset_index(drop=True)


# =========================================================
# 讀取點名紀錄
# =========================================================

def load_rollcall_records():

    ss = open_sheet(ROLLCALL_RECORD_URL)

    try:
        ws = get_worksheet(ss, "點名紀錄")
    except Exception:

        # 如果沒有「點名紀錄」工作表，
        # 使用第一個工作表
        try:
            ws = ss.worksheets()[0]
        except Exception:
            raise Exception(
                "找不到點名紀錄工作表"
            )

    values = get_all_values(ws)

    if not values:
        return pd.DataFrame(
            columns=RECORD_HEADERS
        )

    if len(values) == 1:
        return pd.DataFrame(
            columns=values[0]
        )

    df = pd.DataFrame(
        values[1:],
        columns=values[0],
    )

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
    )

    for col in RECORD_HEADERS:

        if col not in df.columns:
            df[col] = ""

    df["宿舍"] = (
        df["宿舍"]
        .astype(str)
        .str.strip()
    )

    df["姓名"] = (
        df["姓名"]
        .astype(str)
        .str.strip()
    )

    df["送出時間"] = (
        df["送出時間"]
        .astype(str)
        .str.strip()
    )

    return df[
        RECORD_HEADERS
    ].copy()


# =========================================================
# 建立 / 確認點名紀錄 Sheet
# =========================================================

def get_record_worksheet():

    ss = open_sheet(ROLLCALL_RECORD_URL)

    try:
        return get_worksheet(
            ss,
            "點名紀錄"
        )

    except Exception:

        # 如果你的 google_api 支援 add_worksheet
        try:
            ws = ss.add_worksheet(
                title="點名紀錄",
                rows=1000,
                cols=3,
            )

            ws.append_row(
                RECORD_HEADERS
            )

            return ws

        except Exception:
            # 最後退回第一個工作表
            ws = ss.worksheets()[0]

            values = get_all_values(ws)

            if not values:
                ws.append_row(
                    RECORD_HEADERS
                )

            return ws


# =========================================================
# 判斷某樓長是否已送出
# =========================================================

def has_submitted(
    records,
    dorm,
    name,
    target_date,
):

    if records.empty:
        return False

    dorm = normalize_dorm(dorm)
    name = normalize_text(name)

    date_text = target_date.strftime(
        "%Y-%m-%d"
    )

    for _, row in records.iterrows():

        record_dorm = normalize_dorm(
            row.get("宿舍", "")
        )

        record_name = normalize_text(
            row.get("姓名", "")
        )

        submit_time = normalize_text(
            row.get("送出時間", "")
        )

        if (
            record_dorm == dorm
            and record_name == name
            and submit_time.startswith(
                date_text
            )
        ):
            return True

    return False


# =========================================================
# 寫入送出紀錄
# =========================================================

def record_submission(
    dorm,
    name,
):

    target_date = get_target_date()

    records = load_rollcall_records()

    # 防止重複送出
    if has_submitted(
        records,
        dorm,
        name,
        target_date,
    ):
        return False

    ws = get_record_worksheet()

    now = datetime.now(TZ)

    ws.append_row([
        dorm,
        name,
        now.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    ])

    return True


# =========================================================
# 樓長點名檢查頁面
# =========================================================

def show_leader_rollcall():

    st.header("樓長點名送出狀況")

    st.caption(
        "每天 00:00 統計前一天的樓長點名送出狀況。"
    )

    # -----------------------------------------------------
    # 登入帳號
    # -----------------------------------------------------

    login_name = normalize_text(
        st.session_state.get(
            "user",
            ""
        )
    )

    role = normalize_text(
        st.session_state.get(
            "role",
            ""
        )
    )

    # -----------------------------------------------------
    # 只有樓長可以使用
    # -----------------------------------------------------

    if role != "樓長":

        st.warning(
            "此頁面僅提供樓長使用。"
        )

        return

    # -----------------------------------------------------
    # 找目前樓長
    # -----------------------------------------------------

    leaders = load_leader_list()

    if leaders.empty:

        st.error(
            "ADMIN 樓長資料目前沒有資料。"
        )

        return

    # 優先用登入帳號找
    current_leader = leaders[
        leaders["姓名"].astype(str).eq(
            login_name
        )
    ].copy()

    # 如果找不到，嘗試使用 session 的 dorm
    if current_leader.empty:

        login_dorm = normalize_dorm(
            st.session_state.get(
                "dorm",
                ""
            )
        )

        if login_dorm:

            current_leader = leaders[
                leaders["宿舍"]
                .astype(str)
                .str.contains(
                    login_dorm,
                    na=False
                )
            ].copy()

    if current_leader.empty:

        st.warning(
            "目前登入帳號不在 ADMIN 樓長名單中。"
        )

        return

    # -----------------------------------------------------
    # 目標日期
    # -----------------------------------------------------

    target_date = get_target_date()

    st.info(
        f"統計日期：{target_date.strftime('%Y-%m-%d')}"
    )

    # -----------------------------------------------------
    # 目前樓長可管理的宿舍
    # -----------------------------------------------------

    current_dorms = (
        current_leader["宿舍"]
        .dropna()
        .astype(str)
        .tolist()
    )

    # -----------------------------------------------------
    # 顯示「我已送出點名」
    # -----------------------------------------------------

    st.subheader("今日點名")

    records = load_rollcall_records()

    submitted_current = []

    for dorm in current_dorms:

        submitted = has_submitted(
            records,
            dorm,
            login_name,
            target_date,
        )

        submitted_current.append(
            (dorm, submitted)
        )

    for dorm, submitted in submitted_current:

        if submitted:

            st.success(
                f"✅ {dorm}：已送出"
            )

        else:

            st.warning(
                f"⚠️ {dorm}：尚未送出"
            )

            if st.button(
                f"送出 {dorm} 點名",
                key=f"submit_{dorm}",
            ):

                try:

                    success = record_submission(
                        dorm,
                        login_name,
                    )

                    if success:

                        load_rollcall_records.clear()

                        st.success(
                            f"{dorm} 點名已送出"
                        )

                        st.rerun()

                    else:

                        st.info(
                            f"{dorm} 今天已經送出過了。"
                        )

                except Exception as e:

                    st.error(
                        f"送出失敗：{e}"
                    )

    # =====================================================
    # 00:00 統計
    # =====================================================

    st.divider()

    st.subheader(
        f"{target_date.strftime('%Y-%m-%d')} 點名統計"
    )

    leaders = load_leader_list()
    records = load_rollcall_records()

    # -----------------------------------------------------
    # 每一個「樓長 + 宿舍」視為一個應送出項目
    # -----------------------------------------------------

    expected_count = len(leaders)

    submitted_count = 0

    status_rows = []

    for _, row in leaders.iterrows():

        dorm = normalize_dorm(
            row["宿舍"]
        )

        name = normalize_text(
            row["姓名"]
        )

        submitted = has_submitted(
            records,
            dorm,
            name,
            target_date,
        )

        if submitted:
            submitted_count += 1

        status_rows.append({
            "宿舍": dorm,
            "樓長": name,
            "狀態": (
                "已送出"
                if submitted
                else "未送出"
            ),
        })

    not_submitted_count = (
        expected_count
        - submitted_count
    )

    # -----------------------------------------------------
    # 統計數字
    # -----------------------------------------------------

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "應送出樓長",
        f"{expected_count} 人"
    )

    col2.metric(
        "已送出",
        f"{submitted_count} 人"
    )

    col3.metric(
        "未送出",
        f"{not_submitted_count} 人"
    )

    # -----------------------------------------------------
    # 明細
    # -----------------------------------------------------

    result_df = pd.DataFrame(
        status_rows
    )

    if not result_df.empty:

        st.dataframe(
            result_df,
            use_container_width=True,
            hide_index=True,
        )

        missing_df = result_df[
            result_df["狀態"] == "未送出"
        ]

        if not missing_df.empty:

            st.warning(
                f"⚠️ 尚有 "
                f"{len(missing_df)} "
                f"位樓長未送出點名"
            )