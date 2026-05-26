import pandas as pd
import streamlit as st

from datetime import datetime
from core.google_api import rate_limit


# ==================================================
# 載入點名資料
# ==================================================

@st.cache_data(ttl=300)
def load_rollcall_data(_rollcall_ss):

    data = {}

    for ws in _rollcall_ss.worksheets():

        try:

            datetime.strptime(
                ws.title,
                "%Y-%m-%d"
            )

            rate_limit()

            values = ws.get_all_values()

            if len(values) <= 1:
                continue

            df = pd.DataFrame(
                values[1:],
                columns=values[0]
            )

            df.columns = (
                df.columns.str.strip()
            )

            # ==================================================
            # 必須有狀態欄
            # ==================================================

            if "狀態" not in df.columns:
                continue

            df["狀態"] = (
                df["狀態"]
                .astype(str)
                .str.strip()
            )

            # ==================================================
            # 只保留 缺 / 未入住
            # ==================================================

            df = df[
                df["狀態"]
                .isin([
                    "缺",
                    "未入住"
                ])
            ].copy()

            # ==================================================
            # 清除空姓名
            # ==================================================

            if "姓名" in df.columns:

                df = df[
                    df["姓名"]
                    .astype(str)
                    .str.strip() != ""
                ]

            data[ws.title] = df

        except:
            continue

    return data


# ==================================================
# 顯示頁面
# ==================================================

def show_rollcall(rollcall_ss, mode="daily"):

    data = load_rollcall_data(rollcall_ss)

    if len(data) == 0:
        st.warning("沒有資料")
        return

    # ==================================================
    # 月份
    # ==================================================

    all_months = sorted(list(set([

        d[:7]

        for d in data.keys()

    ])), reverse=True)

    current_month = datetime.now().strftime("%Y-%m")

    default_index = 0

    if current_month in all_months:
        default_index = all_months.index(current_month)

    month = st.selectbox(
        "月份",
        all_months,
        index=default_index
    )

    # ==================================================
    # 搜尋
    # ==================================================

    search = st.text_input(
        "搜尋學號 / 姓名",
        key=f"search_{mode}"
    )

    # ==================================================
    # 日期
    # ==================================================

    dates = sorted([

        d for d in data.keys()

        if d.startswith(month)

    ], reverse=True)

    # ==================================================
    # 每日缺席名單
    # ==================================================

    if mode == "daily":

        st.header("每日缺席名單")

        found = False

        for d in dates:

            df = data[d].copy()

            # 搜尋
            if search:

                df = df[

                    (
                        df["學號"]
                        .astype(str)
                        .str.contains(search)
                    )

                    |

                    (
                        df["姓名"]
                        .astype(str)
                        .str.contains(search)
                    )

                ]

            if df.empty:
                continue

            found = True

            st.subheader(d)

            show = df[
                ["房號", "學號", "姓名"]
            ]

            # ==================================================
            # 未入住紅字
            # ==================================================

            unlive_ids = df[
                df["狀態"] == "未入住"
            ]["學號"].astype(str).tolist()

            style_df = show.style.apply(

                lambda row: [

                    "color:red;font-weight:bold"
                    if str(row["學號"]) in unlive_ids
                    else ""

                    for _ in row

                ],

                axis=1
            )

            st.dataframe(
                style_df,
                use_container_width=True
            )

        if not found:
            st.info("本月無資料")

    # ==================================================
    # 連三天不假外宿
    # ==================================================

    elif mode == "three_days":

        st.header("連三天不假外宿")

        found = False

        for i in range(len(dates) - 2):

            group = dates[i:i+3]

            dfs = []

            for d in group:

                df = data[d].copy()

                df["日期"] = d

                dfs.append(df)

            total = pd.concat(dfs)

            # ==================================================
            # 連三天
            # ==================================================

            res = (
                total.groupby(
                    ["房號", "學號", "姓名"]
                )["日期"]
                .nunique()
                .reset_index()
            )

            res = res[
                res["日期"] == 3
            ]

            # 搜尋
            if search:

                res = res[

                    (
                        res["學號"]
                        .astype(str)
                        .str.contains(search)
                    )

                    |

                    (
                        res["姓名"]
                        .astype(str)
                        .str.contains(search)
                    )

                ]

            if not res.empty:

                found = True

                show = res[
                    ["房號", "學號", "姓名"]
                ]

                st.subheader(
                    f"{group[0]} ~ {group[-1]}"
                )

                # ==================================================
                # 未入住紅字
                # ==================================================

                unlive_ids = []

                for d in group:

                    temp = data[d]

                    temp = temp[
                        temp["狀態"] == "未入住"
                    ]

                    unlive_ids.extend(
                        temp["學號"]
                        .astype(str)
                        .tolist()
                    )

                style_df = show.style.apply(

                    lambda row: [

                        "color:red;font-weight:bold"
                        if str(row["學號"]) in unlive_ids
                        else ""

                        for _ in row

                    ],

                    axis=1
                )

                st.dataframe(
                    style_df,
                    use_container_width=True
                )

        if not found:
            st.info("無連續三天不假外宿")