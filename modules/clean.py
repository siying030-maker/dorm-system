import streamlit as st
import pandas as pd

from datetime import date

from core.google_api import open_sheet


CLEAN_SHEET = {
    "上學期": {
        "男一": "https://docs.google.com/spreadsheets/d/1S2axgu2BWP8HnEs0RJdDcccdD1bvPdH26qrx3c4DeWo/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1RcRTslmv4s_C_7AH-WuqtLrty9l0A7YECvaGJETnpis/edit",
        "女一": "https://docs.google.com/spreadsheets/d/1U9bdg8CWASheYE7XxLt5p-otLDxKiotju4s72Car9rk/edit",
        "女ㄧ": "https://docs.google.com/spreadsheets/d/1U9bdg8CWASheYE7XxLt5p-otLDxKiotju4s72Car9rk/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1jNbe--UINl7NS6dpBU82AZJuT6wQ9VwVAlglyG7infQ/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1Vrst2-bqPE7flCIXeAI-lyN51Os9QwStx388DWx11w8/edit"
    },
    "下學期": {
        "男一": "https://docs.google.com/spreadsheets/d/1JSJx0cLdUxfIeYoe6dldeBe3Xeewm3uuIYrJkeYi_A8/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1KpqeWBWIR0g6RxZ_oFUFXbn34PbH7r18UI9NBsfWIPY/edit",
        "女一": "https://docs.google.com/spreadsheets/d/1Nf7U106SxRZUu1pb35Fu2xrN2BTV80lit43BcgE6GnA/edit",
        "女ㄧ": "https://docs.google.com/spreadsheets/d/1Nf7U106SxRZUu1pb35Fu2xrN2BTV80lit43BcgE6GnA/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1NVt6M8SVc64zmRmxh268NlZqzT3JLpcGwuRBlkCe8oE/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1y2YB118Xg2Mq8w6NeabTXgZ-n1gN56kCalyJ5KlMk1I/edit"
    }
}

CLEAN_RESULT_URL = "https://docs.google.com/spreadsheets/d/1ojWln4x5MGTqZZfGe3ySbd8-g6FwTsMff2tonx5tCRc/edit?usp=sharing"

FLOOR_OPTIONS = {
    "女一": ["1F", "2F", "3F", "5F", "6F", "7F"],
    "女ㄧ": ["1F", "2F", "3F", "5F", "6F", "7F"],
    "女二": ["1F", "2F", "3F"],
    "女三": ["6F"],
    "男一": ["0F", "1F", "2F", "3F", "4F", "5F"],
    "男三": ["3F", "4F", "5F"]
}

DORM_PREFIX = {
    "女一": "81",
    "女ㄧ": "81",
    "女二": "82",
    "女三": "83",
    "男一": "82",
    "男三": "83"
}


def normalize_dorm(dorm):
    return str(dorm).strip().replace("ㄧ", "一")


def normalize_room(value):
    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    return value


def get_floor_sheet_name(dorm, floor):
    dorm = normalize_dorm(dorm)
    prefix = DORM_PREFIX.get(dorm, "")
    return f"{prefix}-{floor}"


def get_manage_dorm_options():
    manage_dorms = st.session_state.get("manage_dorms", "")

    if manage_dorms:
        dorm_options = [
            normalize_dorm(d)
            for d in manage_dorms.replace("，", ",").split(",")
            if d.strip()
        ]
    else:
        dorm_options = [
            normalize_dorm(st.session_state.get("dorm", ""))
        ]

    return list(dict.fromkeys(dorm_options))


def find_col(df, keywords):
    columns = list(df.columns)

    for k in keywords:
        for c in columns:
            if str(c).strip() == k:
                return c

    for k in keywords:
        for c in columns:
            if k in str(c):
                return c

    return None


def find_student_id_col(df):
    columns = list(df.columns)

    # 最高優先：真正的「學號」
    for c in columns:
        if str(c).strip() == "學號":
            return c

    # 第二優先：正式學號
    for c in columns:
        if "正式" in str(c) and "學號" in str(c):
            return c

    # 不要抓「替代」
    for c in columns:
        if "學號" in str(c) and "替代" not in str(c):
            return c

    return None


@st.cache_data(ttl=1800)
def load_clean_floor_sheet(url, sheet_name):

    try:
        ss = open_sheet(url)

        sheet_names = [ws.title for ws in ss.worksheets()]

        if sheet_name not in sheet_names:
            st.warning(f"找不到 Sheet：{sheet_name}")
            st.write("目前試算表分頁：", sheet_names)
            return pd.DataFrame()

        ws = ss.worksheet(sheet_name)
        values = ws.get_all_values()

        if len(values) == 0:
            return pd.DataFrame()

        headers = values[0]

        fixed_headers = []
        used = {}

        for i, h in enumerate(headers):
            h = str(h).strip()

            if h == "":
                h = f"欄位_{i}"

            if h in used:
                used[h] += 1
                h = f"{h}_{used[h]}"
            else:
                used[h] = 0

            fixed_headers.append(h)

        df = pd.DataFrame(
            values[1:],
            columns=fixed_headers
        )

        df.columns = df.columns.astype(str).str.strip()

        return df

    except Exception as e:
        st.error(f"{sheet_name} 讀取失敗：{e}")
        return pd.DataFrame()


def query_clean(semester, dorm, rooms):

    dorm = normalize_dorm(dorm)

    if semester not in CLEAN_SHEET:
        st.warning("找不到學期設定")
        return pd.DataFrame()

    if dorm not in CLEAN_SHEET[semester]:
        st.warning(f"找不到 {dorm} 的住宿名單試算表")
        return pd.DataFrame()

    url = CLEAN_SHEET[semester][dorm]
    result = []

    for floor, room in rooms.items():

        room = normalize_room(room)

        if room == "":
            continue

        sheet_name = get_floor_sheet_name(dorm, floor)

        df = load_clean_floor_sheet(
            url,
            sheet_name
        )

        if df.empty:
            st.warning(f"{floor} 找不到 Sheet：{sheet_name}，或此 Sheet 沒資料")
            continue

        bed_col = find_col(df, ["床位"])
        sid_col = find_student_id_col(df)
        name_col = find_col(df, ["姓名", "名字"])

        if bed_col is None:
            st.warning(f"{sheet_name} 找不到床位欄位")
            st.write("目前欄位：", list(df.columns))
            continue

        df["_床位比對"] = df[bed_col].apply(normalize_room)

        res = df[
            df["_床位比對"]
            .astype(str)
            .str.startswith(room + "-")
        ].copy()

        if res.empty:
            st.warning(f"{sheet_name} 查無房號：{room}")
            continue

        temp = pd.DataFrame({
            "房號": [room] * len(res),
            "學號": res[sid_col].astype(str).tolist() if sid_col else [""] * len(res),
            "姓名": res[name_col].astype(str).tolist() if name_col else [""] * len(res),
        })

        temp = temp[
            temp["姓名"]
            .astype(str)
            .str.strip() != ""
        ]

        if not temp.empty:
            result.append(temp)

    if result:
        return pd.concat(result, ignore_index=True)

    return pd.DataFrame()


def save_clean_result(total, school_year, semester, contest, rank, dorm):

    dorm = normalize_dorm(dorm)
    sheet_name = str(school_year).strip()

    ss = open_sheet(CLEAN_RESULT_URL)

    try:
        ws = ss.worksheet(sheet_name)

    except:
        ws = ss.add_worksheet(
            title=sheet_name,
            rows=5000,
            cols=20
        )

        ws.append_row([
            "學年",
            "學期",
            "次數",
            "名次",
            "宿舍",
            "房號",
            "學號",
            "姓名"
        ])

    for _, r in total.iterrows():

        if str(r.get("姓名", "")).strip() == "":
            continue

        ws.append_row([
            school_year,
            semester,
            contest,
            rank,
            dorm,
            r.get("房號", ""),
            r.get("學號", ""),
            r.get("姓名", "")
        ])


def show_clean():

    st.header("整潔比賽")

    # ==========================
    # 自動判斷目前整潔比賽
    # ==========================

    setting = get_current_clean_setting()

    if setting is None:
        st.warning("目前不在整潔比賽可輸入期間")
        return

    clean_term = setting["學期"]        # 例如：115-1
    contest = setting["第幾次"]         # 第一次

    school_year = clean_term.split("-")[0]

    semester = (
        "上學期"
        if clean_term.split("-")[1] == "1"
        else "下學期"
    )

    st.info(
        f"""
目前學年：{school_year}

目前學期：{semester}

目前整潔比賽：{contest}

比賽日期：{setting["整潔比賽日期"]}

可輸入期間：{setting["可輸入期間"]}
"""
    )

    # ==========================
    # 宿舍
    # ==========================

    dorm_options = get_manage_dorm_options()

    if len(dorm_options) == 0:
        st.warning("沒有可管理的宿舍")
        return

    dorm = st.selectbox(
        "宿舍",
        dorm_options,
        key="clean_dorm_select"
    )

    st.subheader(f"宿舍：{dorm}")

    # ==========================
    # 名次（保留人工選）
    # ==========================

    rank = st.selectbox(
        "名次",
        ["第一名", "第二名", "第三名"],
        key="clean_rank"
    )

    # ==========================
    # 樓層房號
    # ==========================

    floors = FLOOR_OPTIONS.get(dorm, [])

    if len(floors) == 0:
        st.warning("此宿舍沒有樓層設定")
        return

    st.divider()
    st.subheader("各樓層房號")

    rooms = {}

    for floor in floors:

        sheet_name = get_floor_sheet_name(
            dorm,
            floor
        )

        rooms[floor] = st.text_input(
            f"{floor} 房號（讀取 {sheet_name}）",
            key=f"clean_room_{dorm}_{floor}_{semester}_{contest}_{rank}"
        )

    # ==========================
    # 查詢
    # ==========================

    query_key = (
        f"clean_result_{dorm}_{semester}_{contest}_{rank}"
    )

    if st.button(
        "查詢名單",
        key=f"query_clean_{dorm}_{semester}_{contest}_{rank}"
    ):

        total = query_clean(
            semester,
            dorm,
            rooms
        )

        st.session_state[query_key] = total

        if total.empty:
            st.warning("查無資料，請確認房號是否存在於該樓層 Sheet")
        else:
            st.success("查詢成功")

    total = st.session_state.get(
        query_key,
        pd.DataFrame()
    )

    if total.empty:
        st.info("請輸入房號後按「查詢名單」")
        return

    # ==========================
    # 顯示名單
    # ==========================

    st.divider()
    st.subheader("名單確認")

    st.dataframe(
        total[
            [
                "房號",
                "學號",
                "姓名"
            ]
        ],
        use_container_width=True
    )

    # ==========================
    # 儲存
    # ==========================

    if st.button(
        "儲存到試算表",
        key=f"save_clean_{dorm}_{semester}_{contest}_{rank}"
    ):

        try:

            save_clean_result(
                total,
                school_year,
                semester,
                contest,
                rank,
                dorm
            )

            st.success("已成功儲存到整潔比賽試算表")

        except Exception as e:
            st.error(str(e))


def show_clean_view():

    st.header("整潔比賽(檢視)")

    try:
        ss = open_sheet(CLEAN_RESULT_URL)

        sheet_names = [
            ws.title
            for ws in ss.worksheets()
        ]

        if len(sheet_names) == 0:
            st.info("尚無資料")
            return

        school_year = st.selectbox(
            "學年",
            sheet_names,
            key="view_clean_school_year"
        )

        ws = ss.worksheet(school_year)

        values = ws.get_all_values()

        if len(values) <= 1:
            st.info("尚無資料")
            return

        df = pd.DataFrame(
            values[1:],
            columns=values[0]
        )

        semester = st.selectbox(
            "學期",
            ["全部", "上學期", "下學期"],
            key="view_clean_semester"
        )

        contest = st.selectbox(
            "第幾次",
            ["全部", "第一次", "第二次", "第三次"],
            key="view_clean_contest"
        )

        rank = st.selectbox(
            "名次",
            ["全部", "第一名", "第二名", "第三名"],
            key="view_clean_rank"
        )

        if semester != "全部":
            df = df[df["學期"] == semester]

        if contest != "全部":
            df = df[df["次數"] == contest]

        if rank != "全部":
            df = df[df["名次"] == rank]

        show_cols = [
            "宿舍",
            "名次",
            "房號",
            "學號",
            "姓名"
        ]

        for col in show_cols:
            if col not in df.columns:
                df[col] = ""

        st.dataframe(
            df[show_cols],
            use_container_width=True
        )

    except Exception as e:
        st.error(str(e))

@st.cache_data(ttl=600)
def get_current_clean_setting():

    ss = open_sheet(CLEAN_RESULT_URL)
    ws = ss.worksheet("整潔比賽時判斷")

    values = ws.get_all_values()

    if len(values) <= 1:
        return None

    df = pd.DataFrame(
        values[1:],
        columns=values[0]
    )

    df.columns = df.columns.astype(str).str.strip()

    today = date.today()

    for _, row in df.iterrows():

        period = str(row.get("可輸入期間", "")).strip()

        if "~" not in period:
            continue

        start_text, end_text = period.split("~")

        start_date = pd.to_datetime(
            start_text.strip(),
            errors="coerce"
        )

        end_date = pd.to_datetime(
            end_text.strip(),
            errors="coerce"
        )

        if pd.isna(start_date) or pd.isna(end_date):
            continue

        if start_date.date() <= today <= end_date.date():

            return {
                "學期": str(row.get("學期", "")).strip(),
                "第幾次": str(row.get("第幾次", "")).strip(),
                "整潔比賽日期": str(row.get("整潔比賽日期", "")).strip(),
                "可輸入期間": period,
            }

    return None