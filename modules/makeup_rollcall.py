import streamlit as st
import pandas as pd

from core.google_api import open_sheet
from core.config import (
    NEED_MAKEUP_GIRL_URL,
    NEED_MAKEUP_BOY_URL,
    ROLLCALL_GIRL_URL,
    ROLLCALL_BOY_URL,
)


def get_allowed_genders():

    role = st.session_state.get("role", "")
    supervisor_type = st.session_state.get("supervisor_type", "")
    dorm = st.session_state.get("dorm", "")

    if role == "行政":
        return ["女生", "男生"]

    if role == "舍監":

        if supervisor_type == "男舍監":
            return ["男生"]

        if supervisor_type == "女舍監":
            return ["女生"]

    if role == "樓長":

        if str(dorm).startswith("男"):
            return ["男生"]

        if str(dorm).startswith("女"):
            return ["女生"]

    return []


@st.cache_data(ttl=300)
def load_need_makeup_source(gender):

    source_url = (
        NEED_MAKEUP_GIRL_URL
        if gender == "女生"
        else NEED_MAKEUP_BOY_URL
    )

    ss = open_sheet(source_url)

    dfs = []

    for ws in ss.worksheets():

        try:

            values = ws.get_all_values()

            if len(values) <= 1:
                continue

            df = pd.DataFrame(
                values[1:],
                columns=values[0]
            )

            df.columns = df.columns.astype(str).str.strip()

            if "狀態" not in df.columns:
                continue

            df["狀態"] = (
                df["狀態"]
                .astype(str)
                .str.strip()
            )

            # 只抓樓長點名為缺的人
            df = df[
                df["狀態"] == "缺"
            ].copy()

            if df.empty:
                continue

            df["性別"] = gender
            df["來源Sheet"] = ws.title

            dfs.append(df)

        except:
            continue

    if dfs:
        return pd.concat(
            dfs,
            ignore_index=True
        )

    return pd.DataFrame()


def find_col_index(headers, col_name):

    for i, h in enumerate(headers, start=1):

        if str(h).strip() == col_name:
            return i

    return None


def update_rollcall_status_to_makeup(gender, target_row):

    rollcall_url = (
        ROLLCALL_GIRL_URL
        if gender == "女生"
        else ROLLCALL_BOY_URL
    )

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

        raise Exception(
            f"點名總表找不到 Sheet：{sheet_name}"
        )

    values = ws.get_all_values()

    if len(values) <= 1:
        raise Exception("點名總表沒有資料")

    headers = values[0]

    sid_col = find_col_index(
        headers,
        "學號"
    )

    status_col = find_col_index(
        headers,
        "狀態"
    )

    date_col = find_col_index(
        headers,
        "日期"
    )

    if sid_col is None:
        raise Exception("點名總表找不到「學號」欄位")

    if status_col is None:
        raise Exception("點名總表找不到「狀態」欄位")

    for row_index, row in enumerate(values[1:], start=2):

        row_sid = ""

        if len(row) >= sid_col:
            row_sid = str(row[sid_col - 1]).strip()

        row_date = ""

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

    raise Exception(
        f"點名總表找不到此學生：{sid}"
    )


def update_need_makeup_status_to_done(gender, target_row):

    source_url = (
        NEED_MAKEUP_GIRL_URL
        if gender == "女生"
        else NEED_MAKEUP_BOY_URL
    )

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

        raise Exception(
            f"需補點名單找不到 Sheet：{sheet_name}"
        )

    values = ws.get_all_values()

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

        if len(row) >= sid_col:
            row_sid = str(row[sid_col - 1]).strip()

        row_date = ""

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


def show_makeup_rollcall():

    st.header("補點名單")

    allowed_genders = get_allowed_genders()

    if not allowed_genders:

        st.warning("沒有補點名單權限")
        return

    dfs = []

    for gender in allowed_genders:

        df = load_need_makeup_source(gender)

        if not df.empty:
            dfs.append(df)

    if not dfs:

        st.warning("目前沒有須補點資料")
        return

    df = pd.concat(
        dfs,
        ignore_index=True
    )

    role = st.session_state.get("role", "")
    dorm = st.session_state.get("dorm", "")

    # 樓長只看自己宿舍
    if role == "樓長" and "宿舍" in df.columns:

        df = df[
            df["宿舍"]
            .astype(str)
            .str.contains(
                str(dorm),
                na=False
            )
        ]

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
            "性別",
            "日期",
            "宿舍",
            "樓層",
            "房號",
            "床位",
            "學號",
            "姓名",
            "狀態",
            "備註",
            "來源Sheet"
        ]
        if c in df.columns
    ]

    st.dataframe(
        df[show_cols],
        use_container_width=True
    )

    st.divider()

    st.subheader("補點完成")

    options = []

    for i, row in df.iterrows():

        label = (
            f'{row.get("性別", "")}｜'
            f'{row.get("日期", "")}｜'
            f'{row.get("房號", "")}｜'
            f'{row.get("學號", "")}｜'
            f'{row.get("姓名", "")}'
        )

        options.append(
            (i, label)
        )

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

    if st.button(
        "確認補點完成",
        key="submit_makeup"
    ):

        try:

            target_row = df.loc[
                selected_index
            ].to_dict()

            gender = target_row.get(
                "性別",
                ""
            )

            # 1. 點名總表：缺 → 已補點
            update_rollcall_status_to_makeup(
                gender,
                target_row
            )

            # 2. 需補點名單也改成已補點，避免重複顯示
            update_need_makeup_status_to_done(
                gender,
                target_row
            )

            st.cache_data.clear()

            st.success("已將狀態更新為：已補點")

        except Exception as e:

            st.error(f"更新失敗：{e}")