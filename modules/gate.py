import streamlit as st
import pandas as pd

from io import BytesIO
from datetime import timedelta


def load_sheet_df(ss, name):
    try:
        get_worksheet(ss,name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()


def analyze_gate(file, semester_ss):

    if file is None:
        return None, None, None

    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()

    df["刷卡時間"] = pd.to_datetime(
        df["刷卡時間"],
        errors="coerce"
    )

    df["日期"] = df["刷卡時間"].dt.date

    df = df[
        (df["刷卡時間"].dt.hour >= 0)
        &
        (df["刷卡時間"].dt.hour < 6)
    ].copy()

    df["姓名"] = df["姓名"].astype(str)

    df = df[
        ~df["姓名"]
        .str.upper()
        .str.startswith(("LHU", "Y"))
    ]

    df = df.sort_values(
        ["姓名", "日期", "刷卡時間"]
    )

    selected = []
    threshold = timedelta(minutes=60)

    for (name, date), g in df.groupby(["姓名", "日期"]):

        last = None

        for idx, row in g.iterrows():

            if last is None:
                selected.append(idx)
            else:
                if row["刷卡時間"] - last > threshold:
                    selected.append(idx)

            last = row["刷卡時間"]

    df = df.loc[selected].copy()

    leave = load_sheet_df(semester_ss, "外宿申請")
    long_leave = load_sheet_df(semester_ss, "長期外宿")
    late = load_sheet_df(semester_ss, "長期晚歸")

    status = []

    weekday_map = {
        0: "一",
        1: "二",
        2: "三",
        3: "四",
        4: "五",
        5: "六",
        6: "日"
    }

    for _, r in df.iterrows():

        sid = str(r["學號"]).strip()
        d = pd.to_datetime(r["日期"])
        t = r["刷卡時間"]

        s = "未申請"

        if not leave.empty:

            leave["申請日期"] = pd.to_datetime(
                leave["申請日期"],
                errors="coerce"
            )

            leave["結束日期"] = pd.to_datetime(
                leave["結束日期"],
                errors="coerce"
            )

            m = leave[
                (leave["學號"].astype(str) == sid)
                &
                (leave["申請日期"] <= d)
                &
                (leave["結束日期"] >= d)
            ]

            if not m.empty:
                s = "外宿"

        if not long_leave.empty:

            weekday = weekday_map[d.weekday()]

            m = long_leave[
                (long_leave["學號"].astype(str) == sid)
                &
                (
                    long_leave["星期"]
                    .astype(str)
                    .str.contains(weekday)
                )
            ]

            if not m.empty:
                s = "長期外宿"

        if not late.empty:

            m = late[
                late["學號"]
                .astype(str)
                == sid
            ]

            if not m.empty:

                try:
                    limit = pd.to_datetime(
                        m.iloc[0]["返回時間"]
                    ).time()

                    if t.time() <= limit:
                        s = "晚歸正常"
                    else:
                        s = "晚歸超時"

                except:
                    pass

        status.append(s)

    df["狀態判斷"] = status

    show = ["房號", "學號", "姓名"]

    df_C = df[
        df["姓名"]
        .str.upper()
        .str.startswith("C")
    ][show]

    df_N = df[
        ~df["姓名"]
        .str.upper()
        .str.startswith("C")
    ][show]

    return df, df_C, df_N


def to_excel(df):

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:
        df.to_excel(writer, index=False)

    return output.getvalue()


def show_gate(title, semester_ss, uploader_key):

    st.header(title)

    file = st.file_uploader(
        "上傳門禁 Excel",
        type=["xlsx"],
        key=uploader_key
    )

    if file is None:
        return

    result, c_df, n_df = analyze_gate(
        file,
        semester_ss
    )

    st.subheader("一般刷卡資料")
    st.dataframe(
        n_df,
        use_container_width=True
    )

    st.subheader("白卡刷卡資料")
    st.dataframe(
        c_df,
        use_container_width=True
    )

    st.download_button(
        "下載一般刷卡資料",
        data=to_excel(n_df),
        file_name=f"{title}_一般刷卡資料.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"download_normal_{uploader_key}"
    )

    st.download_button(
        "下載白卡刷卡資料",
        data=to_excel(c_df),
        file_name=f"{title}_白卡刷卡資料.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"download_c_{uploader_key}"
    )