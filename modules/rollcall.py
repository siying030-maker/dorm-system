import pandas as pd
import streamlit as st

from datetime import datetime

from core.google_api import (
    open_sheet,
    get_all_values,
    get_worksheets,
    get_values,
)

from core.config import (
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


def get_login_gender():
    gender = normalize_gender(st.session_state.get("gender", ""))

    if gender:
        return gender

    supervisor_type = st.session_state.get("supervisor_type", "")
    gender = normalize_gender(supervisor_type)

    if gender:
        return gender

    dorm = st.session_state.get("dorm", "")
    gender = normalize_gender(dorm)

    return gender


def is_date_sheet(title):
    for fmt in ["%Y-%m-%d", "%Y/%m/%d"]:
        try:
            datetime.strptime(str(title), fmt)
            return True
        except:
            pass

    return False


def normalize_sheet_date(title):
    return str(title).replace("/", "-")


@st.cache_data(ttl=60, show_spinner=False)
def load_rollcall_data():

    data = {}

    sources = [
        ("女", "女生", ROLLCALL_GIRL_URL),
        ("男", "男生", ROLLCALL_BOY_URL),
    ]

    for gender_value, gender_label, url in sources:

        try:
            rollcall_ss = open_sheet(url)

            worksheets = get_worksheets(rollcall_ss)

            date_worksheets = [
                ws
                for ws in worksheets
                if is_date_sheet(ws.title)
            ]

            date_worksheets = sorted(
                date_worksheets,
                key=lambda ws: normalize_sheet_date(ws.title),
                reverse=True
            )

            # 只讀最近 40 天
            date_worksheets = date_worksheets[:40]

            for ws in date_worksheets:

                try:
                    values = get_values(
                        ws,
                        "A:K"
                    )

                    if len(values) <= 1:
                        continue

                    headers = [
                        str(value).strip()
                        for value in values[0]
                    ]

                    df = pd.DataFrame(
                        values[1:],
                        columns=headers
                    )

                    df.columns = (
                        df.columns
                        .astype(str)
                        .str.strip()
                    )

                    if "狀態" not in df.columns:
                        continue

                    df["狀態"] = (
                        df["狀態"]
                        .astype(str)
                        .str.strip()
                    )

                    df = df[
                        ~df["狀態"].isin(
                            ["已補點", "補", ""]
                        )
                    ].copy()

                    if "性別" in df.columns:
                        df["性別"] = (
                            df["性別"]
                            .astype(str)
                            .map(normalize_gender)
                        )

                        df = df[
                            df["性別"] == gender_value
                        ].copy()

                    df["性別"] = gender_label

                    if "學號" in df.columns:
                        df = df[
                            df["學號"]
                            .astype(str)
                            .str.strip()
                            .ne("")
                        ].copy()

                    if "姓名" in df.columns:
                        df = df[
                            df["姓名"]
                            .astype(str)
                            .str.strip()
                            .ne("")
                        ].copy()

                    if df.empty:
                        continue

                    key = normalize_sheet_date(
                        ws.title
                    )

                    if key in data:
                        data[key] = pd.concat(
                            [data[key], df],
                            ignore_index=True
                        )
                    else:
                        data[key] = df

                except Exception:
                    continue

        except Exception as error:
            st.warning(
                f"{gender_label}點名總表讀取失敗：{error}"
            )

    return data

def filter_by_permission(df):

    role = st.session_state.get("role", "")

    if role == "行政":
        return df

    login_gender = get_login_gender()

    if login_gender:
        gender_label = "男生" if login_gender == "男" else "女生"

        if "性別" in df.columns:
            df = df[
                df["性別"].astype(str).str.strip() == gender_label
            ]

    if role == "樓長":

        allowed_keywords = []

        for value in [
            st.session_state.get("dorm", ""),
            st.session_state.get("manage_dorms", ""),
            st.session_state.get("winter_dorms", ""),
            st.session_state.get("summer_dorms", ""),
            "寒假",
            "暑假"
        ]:
            for item in str(value).replace("，", ",").split(","):
                item = item.strip()
                if item:
                    allowed_keywords.append(item)

        allowed_keywords = list(dict.fromkeys(allowed_keywords))

        if allowed_keywords and "宿舍" in df.columns:
            condition = pd.Series(False, index=df.index)

            for keyword in allowed_keywords:
                condition = (
                    condition
                    |
                    df["宿舍"]
                    .astype(str)
                    .str.contains(keyword, na=False)
                )

            df = df[condition]

    return df


def show_rollcall(_unused=None, mode="daily"):

    data = load_rollcall_data()

    if len(data) == 0:
        st.warning("沒有資料")
        return

    all_months = sorted(
        list(set([d[:7] for d in data.keys()])),
        reverse=True
    )

    current_month = datetime.now().strftime("%Y-%m")

    default_index = 0

    if current_month in all_months:
        default_index = all_months.index(current_month)

    month = st.selectbox(
        "月份",
        all_months,
        index=default_index,
        key=f"{mode}_month"
    )

    search = st.text_input(
        "搜尋學號 / 姓名",
        key=f"{mode}_search"
    )

    dates = sorted(
        [
            d
            for d in data.keys()
            if d.startswith(month)
        ],
        reverse=True
    )

    show_daily(
        data,
        dates,
        search
    )

    if st.button("重新整理每日未到名單"):
        load_rollcall_data.clear()
        st.rerun()


def show_daily(data, dates, search):

    st.header("每日點名未到名單")

    found = False

    for d in dates:

        df = data[d].copy()

        df = filter_by_permission(df)

        if search:
            search = str(search).strip()

            condition = pd.Series(False, index=df.index)

            for col in ["學號", "姓名"]:
                if col in df.columns:
                    condition = (
                        condition
                        |
                        df[col]
                        .astype(str)
                        .str.contains(search, na=False)
                    )

            df = df[condition]

        if df.empty:
            continue

        found = True

        st.subheader(d)

        show_cols = [
            c for c in [
                "性別",
                "床位",
                "學號",
                "班級",
                "姓名",
                "狀態",
                "備註"
            ]
            if c in df.columns
        ]

        show = df[show_cols].copy()

        st.dataframe(
            show,
            use_container_width=True,
            hide_index=True
        )

    if not found:
        st.info("本月無資料")


    load_rollcall_data.clear()
    st.rerun()