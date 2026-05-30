import streamlit as st
import pandas as pd
from datetime import datetime

from core.google_api import open_sheet
from core.config import (
    ROLLCALL_GIRL_URL,
    ROLLCALL_BOY_URL,
    MAKEUP_GIRL_DONE_URL,
    MAKEUP_BOY_DONE_URL,
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


@st.cache_data(ttl=1800)
def load_makeup_source(gender):

    source_url = ROLLCALL_GIRL_URL if gender == "女生" else ROLLCALL_BOY_URL
    ss = open_sheet(source_url)

    dfs = []

    for ws in ss.worksheets():

        try:
            values = ws.get_all_values()

            if len(values) <= 1:
                continue

            df = pd.DataFrame(values[1:], columns=values[0])
            df.columns = df.columns.astype(str).str.strip()

            if "狀態" not in df.columns:
                continue

            df["狀態"] = df["狀態"].astype(str).str.strip()

            df = df[df["狀態"] == "缺"].copy()

            if df.empty:
                continue

            df["性別"] = gender
            df["來源Sheet"] = ws.title

            dfs.append(df)

        except:
            continue

    if dfs:
        return pd.concat(dfs, ignore_index=True)

    return pd.DataFrame()


def save_makeup_done(gender, row, note):

    done_url = MAKEUP_GIRL_DONE_URL if gender == "女生" else MAKEUP_BOY_DONE_URL
    ss = open_sheet(done_url)

    sheet_name = datetime.now().strftime("%Y-%m-%d")

    try:
        ws = ss.worksheet(sheet_name)

    except:
        ws = ss.add_worksheet(title=sheet_name, rows=3000, cols=20)
        ws.append_row([
            "補點完成時間",
            "原點名日期",
            "性別",
            "宿舍",
            "樓層",
            "房號",
            "床位",
            "學號",
            "姓名",
            "原狀態",
            "補點結果",
            "備註",
            "來源Sheet"
        ])

    ws.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        row.get("日期", ""),
        gender,
        row.get("宿舍", ""),
        row.get("樓層", ""),
        row.get("房號", ""),
        row.get("床位", ""),
        row.get("學號", ""),
        row.get("姓名", ""),
        row.get("狀態", ""),
        "已補點",
        note,
        row.get("來源Sheet", "")
    ])


def show_makeup_rollcall():

    st.header("補點名單")

    allowed_genders = get_allowed_genders()

    if not allowed_genders:
        st.warning("沒有補點名單權限")
        return

    all_df = []

    for gender in allowed_genders:
        df = load_makeup_source(gender)
        if not df.empty:
            all_df.append(df)

    if not all_df:
        st.warning("目前沒有須補點資料")
        return

    df = pd.concat(all_df, ignore_index=True)

    role = st.session_state.get("role", "")
    dorm = st.session_state.get("dorm", "")

    if role == "樓長" and "宿舍" in df.columns:
        df = df[
            df["宿舍"].astype(str).str.contains(str(dorm), na=False)
        ]

    keyword = st.text_input(
        "搜尋學號 / 姓名 / 房號",
        key="makeup_search"
    )

    if keyword:
        condition = False

        for col in ["學號", "姓名", "房號", "床位"]:
            if col in df.columns:
                condition = condition | df[col].astype(str).str.contains(keyword, na=False)

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

    st.dataframe(df[show_cols], use_container_width=True)

    st.divider()
    st.subheader("補點完成回報")

    options = []

    for i, row in df.iterrows():
        label = (
            f'{row.get("性別", "")}｜'
            f'{row.get("日期", "")}｜'
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
        x[0] for x in options
        if x[1] == selected_label
    ][0]

    note = st.text_input("補點備註", key="makeup_note")

    if st.button("送出補點完成", key="submit_makeup"):

        row = df.loc[selected_index].to_dict()
        gender = row.get("性別", "")

        try:
            save_makeup_done(gender, row, note)
            st.success("補點完成已回傳")
            st.cache_data.clear()

        except Exception as e:
            st.error(f"回傳失敗：{e}")