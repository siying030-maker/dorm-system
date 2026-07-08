import streamlit as st
import pandas as pd

from datetime import date
from core.google_api import open_sheet
from core.config import (
    NEED_MAKEUP_GIRL_URL,
    NEED_MAKEUP_BOY_URL,
    ROLLCALL_GIRL_URL,
    ROLLCALL_BOY_URL,
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


@st.cache_data(ttl=10, show_spinner=False)
def load_need_makeup_source(gender):
    source_url = (
        NEED_MAKEUP_GIRL_URL
        if gender == "女生"
        else NEED_MAKEUP_BOY_URL
    )

    ss = open_sheet(source_url)

    today1 = str(date.today())
    today2 = today1.replace("-", "/")

    ws = None

    for sheet_name in [today1, today2]:

        try:
            ws = ss.worksheet(sheet_name)
            break

        except:
            pass

    if ws is None:
        return pd.DataFrame()

    from core.google_api import get_all_values

    values = get_all_values(ws)

    if len(values) <= 1:
        return pd.DataFrame()

    df = pd.DataFrame(
        values[1:],
        columns=values[0]
    )

    df.columns = df.columns.astype(str).str.strip()

    if "狀態" not in df.columns:
        return pd.DataFrame()

    df["狀態"] = (
        df["狀態"]
        .astype(str)
        .str.strip()
    )

    df = df[
        df["狀態"] == "缺"
    ].copy()

    if df.empty:
        return pd.DataFrame()

    if "性別" in df.columns:

        df["性別"] = (
            df["性別"]
            .astype(str)
            .map(normalize_gender)
        )

        target_gender = normalize_gender(gender)

        df = df[
            df["性別"] == target_gender
        ].copy()

        df["性別"] = df["性別"].map(
            lambda x: "男生" if x == "男" else "女生"
        )

    else:

        df["性別"] = gender

    df["來源Sheet"] = ws.title

    df = df[
        df["學號"]
        .astype(str)
        .str.strip() != ""
    ]

    df = df[
        df["姓名"]
        .astype(str)
        .str.strip() != ""
    ]

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

    rollcall_url = get_rollcall_url_by_gender(gender)

    ss = open_sheet(rollcall_url)

    sheet_name = str(
        target_row.get("來源Sheet", "")
    ).strip()

    sid = str(
        target_row.get("學號", "")
    ).strip()

    rollcall_date = str(
        target_row.get("日期", "")
    ).strip()

    try:
        ws = ss.worksheet(sheet_name)

    except:
        raise Exception(f"點名總表找不到 Sheet：{sheet_name}")

    from core.google_api import get_all_values

    values = get_all_values(ws)

    if len(values) <= 1:
        raise Exception("點名總表沒有資料")

    headers = values[0]

    sid_col = find_col_index(headers, "學號")
    status_col = find_col_index(headers, "狀態")
    date_col = find_col_index(headers, "日期")

    if sid_col is None:
        raise Exception("點名總表找不到「學號」欄位")

    if status_col is None:
        raise Exception("點名總表找不到「狀態」欄位")

    for row_index, row in enumerate(values[1:], start=2):

        row_sid = ""
        row_date = ""

        if len(row) >= sid_col:
            row_sid = str(row[sid_col - 1]).strip()

        if date_col and len(row) >= date_col:
            row_date = str(row[date_col - 1]).strip()

        if row_sid == sid:

            if date_col is None or row_date == rollcall_date:

                ws.update_cell(
                    row_index,
                    status_col,
                    "已補點"
                )

                return True

    raise Exception(f"點名總表找不到此學生：{sid}")


def update_need_makeup_status_to_done(gender, target_row):

    source_url = get_need_makeup_url_by_gender(gender)

    ss = open_sheet(source_url)

    sheet_name = str(
        target_row.get("來源Sheet", "")
    ).strip()

    sid = str(
        target_row.get("學號", "")
    ).strip()

    rollcall_date = str(
        target_row.get("日期", "")
    ).strip()

    try:
        ws = ss.worksheet(sheet_name)

    except:
        raise Exception(f"需補點名單找不到 Sheet：{sheet_name}")

    from core.google_api import get_all_values

    values = get_all_values(ws)

    if len(values) <= 1:
        return

    headers = values[0]

    sid_col = find_col_index(headers, "學號")
    status_col = find_col_index(headers, "狀態")
    date_col = find_col_index(headers, "日期")

    if sid_col is None or status_col is None:
        return

    for row_index, row in enumerate(values[1:], start=2):

        row_sid = ""
        row_date = ""

        if len(row) >= sid_col:
            row_sid = str(row[sid_col - 1]).strip()

        if date_col and len(row) >= date_col:
            row_date = str(row[date_col - 1]).strip()

        if row_sid == sid:

            if date_col is None or row_date == rollcall_date:

                ws.update_cell(
                    row_index,
                    status_col,
                    "已補點"
                )

                return


def filter_by_leader_scope(df):

    role = st.session_state.get("role", "")

    if role != "樓長":
        return df

    dorm = normalize_text(
        st.session_state.get("dorm", "")
    )

    manage_dorms = normalize_text(
        st.session_state.get("manage_dorms", "")
    )

    winter_dorms = normalize_text(
        st.session_state.get("winter_dorms", "")
    )

    summer_dorms = normalize_text(
        st.session_state.get("summer_dorms", "")
    )

    allowed_keywords = []

    for value in [
        dorm,
        manage_dorms,
        winter_dorms,
        summer_dorms,
        "寒假",
        "暑假"
    ]:

        for item in str(value).replace("，", ",").split(","):

            item = item.strip()

            if item:
                allowed_keywords.append(item)

    allowed_keywords = list(dict.fromkeys(allowed_keywords))

    if not allowed_keywords:
        return df

    if "宿舍" not in df.columns:
        return df

    condition = pd.Series(
        False,
        index=df.index
    )

    for keyword in allowed_keywords:

        condition = (
            condition
            |
            df["宿舍"]
            .astype(str)
            .str.contains(
                keyword,
                na=False
            )
        )

    return df[condition]


def show_makeup_rollcall():

    st.header("補點名單")

    if st.button("重新整理補點名單", key="refresh_makeup"):
        st.cache_data.clear()
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

            st.cache_data.clear()

            st.success("已將狀態更新為：已補點")

        except Exception as e:
            st.error(f"更新失敗：{e}")