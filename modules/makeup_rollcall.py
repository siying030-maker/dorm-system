import streamlit as st
import pandas as pd
from datetime import datetime

from core.google_api import open_sheet
from core.config import (
    MAKEUP_GIRL_SOURCE_URL,
    MAKEUP_BOY_SOURCE_URL,
    MAKEUP_GIRL_DONE_URL,
    MAKEUP_BOY_DONE_URL,
)


def read_all_sheets(url):
    ss = open_sheet(url)
    dfs = []

    for ws in ss.worksheets():
        try:
            values = ws.get_all_values()

            if len(values) <= 1:
                continue

            df = pd.DataFrame(values[1:], columns=values[0])
            df.columns = df.columns.astype(str).str.strip()
            df["來源Sheet"] = ws.title

            dfs.append(df)

        except:
            continue

    if dfs:
        return pd.concat(dfs, ignore_index=True)

    return pd.DataFrame()


def save_done(gender, row, note):
    if gender == "女生":
        ss = open_sheet(MAKEUP_GIRL_DONE_URL)
    else:
        ss = open_sheet(MAKEUP_BOY_DONE_URL)

    sheet_name = datetime.now().strftime("%Y-%m-%d")

    try:
        ws = ss.worksheet(sheet_name)
    except:
        ws = ss.add_worksheet(title=sheet_name, rows=2000, cols=20)
        ws.append_row([
            "補點完成時間",
            "日期",
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

    gender = st.selectbox(
        "性別",
        ["女生", "男生"],
        key="makeup_gender"
    )

    source_url = MAKEUP_GIRL_SOURCE_URL if gender == "女生" else MAKEUP_BOY_SOURCE_URL

    df = read_all_sheets(source_url)

    if df.empty:
        st.warning("沒有須補點資料")
        return

    if "狀態" in df.columns:
        df = df[
            df["狀態"].astype(str).str.strip().isin(["缺", "未入住"])
        ]

    keyword = st.text_input(
        "搜尋學號 / 姓名 / 房號",
        key="makeup_search"
    )

    if keyword:
        keyword = str(keyword).strip()

        condition = False

        for col in ["學號", "姓名", "房號", "床位"]:
            if col in df.columns:
                condition = condition | df[col].astype(str).str.contains(keyword, na=False)

        df = df[condition]

    if df.empty:
        st.info("查無須補點資料")
        return

    show_cols = [
        c for c in ["日期", "宿舍", "樓層", "房號", "床位", "學號", "姓名", "狀態", "備註", "來源Sheet"]
        if c in df.columns
    ]

    st.dataframe(
        df[show_cols],
        use_container_width=True
    )

    st.divider()
    st.subheader("補點完成登記")

    options = []

    for i, row in df.iterrows():
        label = f'{row.get("日期", "")}｜{row.get("房號", "")}｜{row.get("學號", "")}｜{row.get("姓名", "")}'
        options.append((i, label))

    selected_label = st.selectbox(
        "選擇要補點完成的學生",
        [x[1] for x in options],
        key="makeup_selected"
    )

    selected_index = [
        x[0] for x in options
        if x[1] == selected_label
    ][0]

    note = st.text_input(
        "補點備註",
        key="makeup_note"
    )

    if st.button("送出補點完成", key="submit_makeup"):
        row = df.loc[selected_index].to_dict()

        try:
            save_done(gender, row, note)
            st.success("補點完成已回傳至新的試算表")
        except Exception as e:
            st.error(f"儲存失敗：{e}")