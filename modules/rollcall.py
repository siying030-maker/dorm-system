import pandas as pd
import streamlit as st

from datetime import datetime
from core.google_api import rate_limit


@st.cache_data(ttl=1800)
def load_rollcall_data(_rollcall_source):

    data = {}

    if not isinstance(_rollcall_source, list):
        rollcall_sources = [_rollcall_source]
    else:
        rollcall_sources = _rollcall_source

    for rollcall_ss in rollcall_sources:

        for ws in rollcall_ss.worksheets():

            try:
                try:
                    datetime.strptime(ws.title, "%Y-%m-%d")
                except:
                    datetime.strptime(ws.title, "%Y/%m/%d")

                rate_limit()
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

                df = df[
                    df["狀態"].isin(["缺", "未入住"])
                ].copy()

                if "姓名" in df.columns:
                    df = df[
                        df["姓名"]
                        .astype(str)
                        .str.strip() != ""
                    ]

                if df.empty:
                    continue

                key = ws.title.replace("/", "-")

                if key in data:
                    data[key] = pd.concat(
                        [data[key], df],
                        ignore_index=True
                    )
                else:
                    data[key] = df

            except:
                continue

    return data


def show_rollcall(rollcall_ss, mode="daily"):

    data = load_rollcall_data(rollcall_ss)

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


def show_daily(data, dates, search):

    st.header("每日點名未到名單")

    found = False

    for d in dates:

        df = data[d].copy()

        if search:
            df = df[
                df["學號"]
                .astype(str)
                .str.contains(search, na=False)
                |
                df["姓名"]
                .astype(str)
                .str.contains(search, na=False)
            ]

        if df.empty:
            continue

        found = True

        st.subheader(d)

        show_cols = [
            c for c in [
                "宿舍",
                "樓層",
                "房號",
                "床位",
                "學號",
                "姓名",
                "狀態"
            ]
            if c in df.columns
        ]

        show = df[show_cols]

        if "學號" in df.columns and "狀態" in df.columns:

            unlive_ids = df[
                df["狀態"] == "未入住"
            ]["學號"].astype(str).tolist()

            style_df = show.style.apply(
                lambda row: [
                    "color:red;font-weight:bold"
                    if (
                        "學號" in row.index
                        and str(row["學號"]) in unlive_ids
                    )
                    else ""
                    for _ in row
                ],
                axis=1
            )

            st.dataframe(
                style_df,
                use_container_width=True
            )

        else:

            st.dataframe(
                show,
                use_container_width=True
            )

    if not found:
        st.info("本月無資料")