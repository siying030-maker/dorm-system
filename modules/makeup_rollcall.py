import streamlit as st
import pandas as pd

from datetime import date

from core.google_api import (
    open_sheet,
    get_worksheet,
    get_all_values,
    update_cell,
)

from core.config import (
    NEED_MAKEUP_GIRL_URL,
    NEED_MAKEUP_BOY_URL,
    ROLLCALL_GIRL_URL,
    ROLLCALL_BOY_URL,
    ROLLCALL_SHEET_URL,
)

def normalize_gender(value):

    value = str(value).strip()

    if value in ["男", "男生"]:
        return "男"

    if value in ["女", "女生"]:
        return "女"

    if "男" in value:
        return "男"

    if "女" in value:
        return "女"

    return ""


def gender_to_label(gender):

    gender = normalize_gender(gender)

    if gender == "男":
        return "男生"

    if gender == "女":
        return "女生"

    return ""


def get_login_gender():

    gender = st.session_state.get("gender", "")

    gender = normalize_gender(gender)

    if gender:
        return gender

    supervisor_type = st.session_state.get(
        "supervisor_type",
        ""
    )

    gender = normalize_gender(supervisor_type)

    if gender:
        return gender

    dorm = st.session_state.get("dorm", "")

    gender = normalize_gender(dorm)

    if gender:
        return gender

    return ""


def get_allowed_genders():

    role = st.session_state.get("role", "")

    if role == "行政":
        return []

    login_gender = get_login_gender()

    if login_gender == "男":
        return ["男生"]

    if login_gender == "女":
        return ["女生"]

    return []


def normalize_text(value):

    return str(value).strip()


@st.cache_data(ttl=15, show_spinner=False)
@st.cache_data(ttl=15, show_spinner=False)
def load_need_makeup_source(gender):
    """從男女來源同步後的 ROLLCALL_SHEET_URL 讀取當日缺／未入住資料。"""
    ss = open_sheet(ROLLCALL_SHEET_URL)
    today = str(date.today())
    candidates = [today, today.replace("-", "/")]
    ws = None
    for name in candidates:
        try:
            ws = get_worksheet(ss, name)
            break
        except Exception:
            pass
    if ws is None:
        return pd.DataFrame()

    values = get_all_values(ws)
    if len(values) <= 1:
        return pd.DataFrame()
    df = pd.DataFrame(values[1:], columns=[str(x).strip() for x in values[0]])
    if "狀態" not in df.columns or "學號" not in df.columns or "姓名" not in df.columns:
        return pd.DataFrame()

    df["狀態"] = df["狀態"].astype(str).str.strip()
    df = df[df["狀態"].isin(["缺", "未入住"])].copy()
    if df.empty:
        return pd.DataFrame()

    target_gender = normalize_gender(gender)
    if "性別" in df.columns:
        df["性別"] = df["性別"].astype(str).map(normalize_gender)
        df = df[df["性別"] == target_gender].copy()
        df["性別"] = df["性別"].map(lambda x: "男生" if x == "男" else "女生")
    else:
        df["性別"] = gender

    df["來源Sheet"] = ws.title
    df["日期"] = ws.title
    df = df[df["學號"].astype(str).str.strip() != ""]
    df = df[df["姓名"].astype(str).str.strip() != ""]
    return df

def find_col_index(headers, col_name):

    for i, h in enumerate(headers, start=1):

        if str(h).strip() == col_name:
            return i

    return None


def get_rollcall_url_by_gender(gender):

    gender = normalize_gender(gender)

    if gender == "女":
        return ROLLCALL_GIRL_URL

    if gender == "男":
        return ROLLCALL_BOY_URL

    raise Exception("無法判斷性別")


def get_need_makeup_url_by_gender(gender):

    gender = normalize_gender(gender)

    if gender == "女":
        return NEED_MAKEUP_GIRL_URL

    if gender == "男":
        return NEED_MAKEUP_BOY_URL

    raise Exception("無法判斷性別")


def update_rollcall_status_to_makeup(gender, target_row):
    """將統一點名單總表中的學生狀態改為「已補點」。"""
    ss = open_sheet(ROLLCALL_SHEET_URL)
    sheet_name = str(target_row.get("日期", target_row.get("來源Sheet", ""))).strip()
    sid = str(target_row.get("學號", "")).strip()
    dorm = str(target_row.get("宿舍", "")).strip()

    if not sheet_name:
        raise Exception("補點資料沒有日期")
    try:
        ws = get_worksheet(ss, sheet_name)
    except Exception:
        raise Exception(f"點名單總表找不到 Sheet：{sheet_name}")

    values = get_all_values(ws)
    if len(values) <= 1:
        raise Exception("點名單總表沒有資料")
    headers = [str(x).strip() for x in values[0]]
    sid_col = find_col_index(headers, "學號")
    status_col = find_col_index(headers, "狀態")
    dorm_col = find_col_index(headers, "宿舍")
    if sid_col is None or status_col is None:
        raise Exception("點名單總表找不到「學號」或「狀態」欄位")

    for row_index, row in enumerate(values[1:], start=2):
        row_sid = str(row[sid_col-1]).strip() if len(row) >= sid_col else ""
        row_dorm = str(row[dorm_col-1]).strip() if dorm_col and len(row) >= dorm_col else ""
        if row_sid == sid and (not dorm_col or row_dorm == dorm):
            update_cell(ws, row_index, status_col, "已補點")
            return True
    raise Exception(f"點名單總表找不到此學生：{sid}")

def update_need_makeup_status_to_done(gender, target_row):
    """同步舊的男女補點名單；統一總表才是主要來源。"""
    try:
        source_url = get_need_makeup_url_by_gender(gender)
        ss = open_sheet(source_url)
        sheet_name = str(target_row.get("來源Sheet", target_row.get("日期", ""))).strip()
        sid = str(target_row.get("學號", "")).strip()
        ws = get_worksheet(ss, sheet_name)
        values = get_all_values(ws)
        if len(values) <= 1: return
        headers = [str(x).strip() for x in values[0]]
        sid_col = find_col_index(headers, "學號")
        status_col = find_col_index(headers, "狀態")
        if sid_col is None or status_col is None: return
        for row_index, row in enumerate(values[1:], start=2):
            if len(row) >= sid_col and str(row[sid_col-1]).strip() == sid:
                update_cell(ws, row_index, status_col, "已補點")
                return
    except Exception:
        return

def filter_by_leader_scope(df):

    role = str(st.session_state.get("role", "")).strip()

    if df.empty:
        return df

    if "宿舍" not in df.columns:
        st.warning(
            "目前補點資料沒有「宿舍」欄位，無法依宿舍權限篩選。"
            "請使用新版點名系統重新儲存缺席資料。"
        )
        return df.iloc[0:0].copy()

    result = df.copy()
    result["宿舍"] = (
        result["宿舍"]
        .astype(str)
        .str.strip()
        .str.replace("ㄧ", "一", regex=False)
    )

    # 行政：可查看全部宿舍
    if role == "行政":
        return result

    # 舍監：依男舍監／女舍監篩選
    if role == "舍監":
        supervisor_type = str(
            st.session_state.get("supervisor_type", "")
        ).strip()

        login_gender = normalize_gender(supervisor_type)

        if not login_gender:
            login_gender = get_login_gender()

        if login_gender == "男":
            return result[
                result["宿舍"].str.startswith("男", na=False)
            ].copy()

        if login_gender == "女":
            return result[
                result["宿舍"].str.startswith("女", na=False)
            ].copy()

        st.warning("無法判斷舍監管理的宿舍性別")
        return result.iloc[0:0].copy()

    # 樓長：只查看登入帳號被指派的宿舍
    if role == "樓長":
        allowed_dorms = []

        for state_key in [
            "dorm",
            "manage_dorms",
            "winter_dorms",
            "summer_dorms",
        ]:
            raw_value = st.session_state.get(state_key, "")

            for item in str(raw_value).replace("，", ",").split(","):
                item = item.strip().replace("ㄧ", "一")

                if item:
                    allowed_dorms.append(item)

        allowed_dorms = list(dict.fromkeys(allowed_dorms))

        if not allowed_dorms:
            st.warning("目前帳號沒有設定可管理的宿舍")
            return result.iloc[0:0].copy()

        return result[
            result["宿舍"].isin(allowed_dorms)
        ].copy()

    # 其他身分不顯示補點資料
    st.warning("目前帳號沒有補點名單權限")
    return result.iloc[0:0].copy()


def show_makeup_rollcall():

    st.header("補點名單")

    

    if st.button("重新整理補點名單", key="refresh_makeup"):
        load_need_makeup_source.clear()
        st.rerun()

    allowed_genders = get_allowed_genders()

    if not allowed_genders:
        st.info("您沒有補點權限")
        return

    dfs = []

    for gender in allowed_genders:

        df = load_need_makeup_source(gender)

        if not df.empty:
            dfs.append(df)

    if not dfs:
        st.warning("目前沒有當日須補點資料")
        return

    df = pd.concat(
        dfs,
        ignore_index=True
    )

    df = filter_by_leader_scope(df)

    keyword = st.text_input(
        "搜尋學號 / 姓名 / 房號",
        key="makeup_search"
    )

    if keyword:

        keyword = str(keyword).strip()

        condition = pd.Series(
            False,
            index=df.index
        )

        for col in ["學號", "姓名", "房號", "床位"]:

            if col in df.columns:

                condition = (
                    condition
                    |
                    df[col]
                    .astype(str)
                    .str.contains(
                        keyword,
                        na=False
                    )
                )

        df = df[condition]

    if df.empty:
        st.info("查無符合條件的補點名資料")
        return

    show_cols = [
    c for c in [
        "床位",
        "學號",
        "班級",
        "姓名",
        "狀態",
        "備註"
    ]
    if c in df.columns
]

    st.dataframe(
        df[show_cols],
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    st.subheader("補點完成")

    options = []

    for i, row in df.iterrows():

        label = (
            f'{row.get("性別", "")}｜'
            f'{row.get("日期", "")}｜'
            f'{row.get("宿舍", "")}｜'
            f'{row.get("房號", "")}｜'
            f'{row.get("學號", "")}｜'
            f'{row.get("姓名", "")}'
        )

        options.append((i, label))

    selected_label = st.selectbox(
        "選擇已補點學生",
        [x[1] for x in options],
        key="makeup_selected"
    )

    selected_index = [
        x[0]
        for x in options
        if x[1] == selected_label
    ][0]

    if st.button("確認補點完成", key="submit_makeup"):

        try:
            target_row = df.loc[
                selected_index
            ].to_dict()

            gender = target_row.get(
                "性別",
                ""
            )

            update_rollcall_status_to_makeup(
                gender,
                target_row
            )

            update_need_makeup_status_to_done(
                gender,
                target_row
            )

            load_need_makeup_source.clear()
            st.rerun()

            st.success("已將狀態更新為：已補點")

        except Exception as e:
            st.error(f"更新失敗：{e}")