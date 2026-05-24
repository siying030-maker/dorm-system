# ==================================================
# TAB1
# ==================================================

with tab1:

    st.header("連三天不假外宿")

    col1, col2 = st.columns(2)

    with col1:

        selected_month = st.selectbox(
            "選擇月份",
            month_options,
            index=0
        )

    with col2:

        keyword = st.text_input(
            "搜尋學號 / 姓名"
        )

    filtered_dates = [
        d for d in dates
        if d.startswith(selected_month)
    ]

    groups = [
        filtered_dates[i:i+3]
        for i in range(
            0,
            len(filtered_dates),
            3
        )
    ]

    for g in groups:

        if len(g) < 3:
            continue

        all_d = []

        for d in g:

            df = data.get(d)

            if df is None:
                continue

            if "狀態" not in df.columns:
                continue

            temp = df[
                df["狀態"]
                .astype(str)
                .str.strip() == "缺"
            ].copy()

            temp["日期"] = d

            all_d.append(temp)

        if not all_d:
            continue

        full_df = pd.concat(all_d)

        res = (
            full_df.groupby(
                ["房號", "學號", "姓名"]
            )["日期"]
            .nunique()
            .reset_index()
        )

        res = res[
            res["日期"] == 3
        ]

        if keyword:

            res = res[
                res["學號"]
                .astype(str)
                .str.contains(keyword, na=False)
                |
                res["姓名"]
                .astype(str)
                .str.contains(keyword, na=False)
            ]

        st.subheader(
            f"{g[0]} ~ {g[-1]}"
        )

        if res.empty:

            st.info(
                f"{g[0]} ~ {g[-1]} 此三天無人連三天不假外宿"
            )

        else:

            # 只顯示 房號 學號 姓名
            show_res = res[
                ["房號", "學號", "姓名"]
            ]

            st.dataframe(
                show_res,
                use_container_width=True
            )

# ==================================================
# TAB2
# ==================================================

with tab2:

    st.header("每天點名不到名單")

    col1, col2 = st.columns(2)

    with col1:

        selected_month = st.selectbox(
            "選擇月份 ",
            month_options,
            index=0
        )

    with col2:

        keyword = st.text_input(
            "搜尋學號 / 姓名 "
        )

    filtered_dates = [
        d for d in dates
        if d.startswith(selected_month)
    ]

    all_miss = []

    for d in filtered_dates:

        df = data.get(d)

        if df is None:
            continue

        if "狀態" not in df.columns:
            continue

        miss = df[
            df["狀態"]
            .astype(str)
            .str.strip() == "缺"
        ].copy()

        if keyword:

            miss = miss[
                miss["學號"]
                .astype(str)
                .str.contains(keyword, na=False)
                |
                miss["姓名"]
                .astype(str)
                .str.contains(keyword, na=False)
            ]

        if miss.empty:
            continue

        st.subheader(d)

        # 只顯示 房號 學號 姓名
        show = miss[
            ["房號", "學號", "姓名"]
        ]

        st.dataframe(
            show,
            use_container_width=True
        )

        all_miss.append(show)

    # ==================================================
    # 常缺席
    # ==================================================

    if all_miss:

        st.divider()

        st.subheader(
            "🔥 常缺席名單"
        )

        total = pd.concat(all_miss)

        freq = (
            total.groupby(
                ["房號", "學號", "姓名"]
            )
            .size()
            .reset_index(name="缺席次數")
        )

        freq["狀態"] = freq[
            "缺席次數"
        ].apply(
            lambda x:
            "🔴 常缺席"
            if x >= 3
            else ""
        )

        freq = freq.sort_values(
            by="缺席次數",
            ascending=False
        )

        st.dataframe(
            freq,
            use_container_width=True
        )

# ==================================================
# TAB3
# ==================================================

with tab3:

    st.header("上學期門禁")

    file = st.file_uploader(
        "上傳上學期門禁 Excel",
        type=["xlsx"],
        key="upper"
    )

    if file:

        result, c, n = analyze_gate(
            file,
            UPPER_GATE_URL
        )

        st.subheader("一般刷卡資料")

        # 只顯示 房號 學號 姓名
        st.dataframe(
            n[["房號", "學號", "姓名"]],
            use_container_width=True
        )

        st.subheader("白卡刷卡資料")

        # 只顯示 房號 學號 姓名
        st.dataframe(
            c[["房號", "學號", "姓名"]],
            use_container_width=True
        )

        st.download_button(
            "下載刷卡資料.xlsx",
            to_excel(n),
            "刷卡資料.xlsx"
        )

        st.download_button(
            "下載白卡刷卡資料.xlsx",
            to_excel(c),
            "白卡刷卡資料.xlsx"
        )

# ==================================================
# TAB4
# ==================================================

with tab4:

    st.header("下學期門禁")

    file = st.file_uploader(
        "上傳下學期門禁 Excel",
        type=["xlsx"],
        key="lower"
    )

    if file:

        result, c, n = analyze_gate(
            file,
            LOWER_GATE_URL
        )

        st.subheader("一般刷卡資料")

        # 只顯示 房號 學號 姓名
        st.dataframe(
            n[["房號", "學號", "姓名"]],
            use_container_width=True
        )

        st.subheader("白卡刷卡資料")

        # 只顯示 房號 學號 姓名
        st.dataframe(
            c[["房號", "學號", "姓名"]],
            use_container_width=True
        )

        st.download_button(
            "下載刷卡資料.xlsx",
            to_excel(n),
            "刷卡資料.xlsx"
        )

        st.download_button(
            "下載白卡刷卡資料.xlsx",
            to_excel(c),
            "白卡刷卡資料.xlsx"
        )