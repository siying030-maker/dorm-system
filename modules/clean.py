import streamlit as st
import pandas as pd

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
    "男一": ["MB", "1F", "2F", "3F", "4F", "5F"],
    "男三": ["3F", "4F", "5F"]
}


def normalize_dorm(dorm):
    return str(dorm).strip().replace("ㄧ", "一")


def normalize_room(value):
    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    return value


@st.cache_data(ttl=300)
def load_clean_sheet(url):
    try:
        ss = open_sheet(url)
        ws = ss.sheet1

        df = pd.DataFrame(ws.get_all_records())
        df.columns = df.columns.str.strip()

        return df

    except:
        return pd.DataFrame()


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


def query_clean(semester, dorm, rooms):

    dorm = normalize_dorm(dorm)

    if semester not in CLEAN_SHEET:
        return pd.DataFrame()

    if dorm not in CLEAN_SHEET[semester]:
        return pd.DataFrame()

    df = load_clean_sheet(CLEAN_SHEET[semester][dorm])

    if df.empty:
        return pd.DataFrame()

    result = []

    room_col = next(
        (c for c in df.columns if "房" in c),
        None
    )

    if room_col is None:
        return pd.DataFrame()

    df["_房號比對"] = df[room_col].apply(normalize_room)

    for floor, room in rooms.items():

        room = normalize_room(room)

        if room == "":
            continue

        res = df[df["_房號比對"] == room]

        if res.empty:
            st.warning(f"{floor} 查無房號：{room}")
            continue

        show_cols = [
            c for c in df.columns
            if "房" in c or "學號" in c or "姓名" in c
        ]

        temp = res[show_cols].copy()
        temp["樓層"] = floor

        result.append(temp)

    if len(result) > 0:
        return pd.concat(result, ignore_index=True)

    return pd.DataFrame()


def save_clean_result(total, school_year, semester, contest, rank, dorm):

    dorm = normalize_dorm(dorm)

    ss = open_sheet(CLEAN_RESULT_URL)

    try:
        ws = ss.worksheet("整潔比賽")
    except:
        ws = ss.add_worksheet(
            title="整潔比賽",
            rows=5000,
            cols=20
        )

        ws.append_row([
            "學年",
            "學期",
            "次數",
            "名次",
            "宿舍",
            "樓層",
            "房號",
            "學號",
            "姓名"
        ])

    for _, r in total.iterrows():

        room_value = ""
        sid_value = ""
        name_value = ""

        for c in total.columns:

            if "房" in c:
                room_value = r[c]

            if "學號" in c:
                sid_value = r[c]

            if "姓名" in c:
                name_value = r[c]

        ws.append_row([
            school_year,
            semester,
            contest,
            rank,
            dorm,
            r["樓層"],
            room_value,
            sid_value,
            name_value
        ])


def show_clean():

    st.header("整潔比賽")

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

    school_year = st.text_input(
        "學年",
        placeholder="例如：114",
        key="clean_school_year"
    )

    semester = st.selectbox(
        "學期",
        ["上學期", "下學期"],
        key="clean_semester"
    )

    contest = st.selectbox(
        "第幾次",
        ["第一次", "第二次", "第三次"],
        key="clean_contest"
    )

    rank = st.selectbox(
        "名次",
        ["第一名", "第二名", "第三名"],
        key="clean_rank"
    )

    floors = FLOOR_OPTIONS.get(dorm, [])

    if len(floors) == 0:
        st.warning("此宿舍沒有樓層設定")
        return

    st.divider()
    st.subheader("各樓層房號")

    rooms = {}

    for floor in floors:
        rooms[floor] = st.text_input(
            f"{floor} 房號",
            key=f"clean_room_{dorm}_{floor}_{semester}_{contest}_{rank}"
        )

    total = query_clean(
        semester,
        dorm,
        rooms
    )

    if total.empty:
        st.info("請輸入房號查詢資料")
        return

    st.divider()
    st.subheader("名單確認")

    st.dataframe(
        total,
        use_container_width=True
    )

    if st.button(
        "儲存",
        key=f"save_clean_{dorm}_{semester}_{contest}_{rank}"
    ):

        if school_year.strip() == "":
            st.error("請輸入學年")
            return

        try:
            save_clean_result(
                total,
                school_year,
                semester,
                contest,
                rank,
                dorm
            )

            st.success("儲存成功")

        except Exception as e:
            st.error(str(e))


def show_clean_view():

    st.header("整潔比賽(檢視)")

    try:
        ss = open_sheet(CLEAN_RESULT_URL)
        ws = ss.worksheet("整潔比賽")

        df = pd.DataFrame(
            ws.get_all_records()
        )

        if df.empty:
            st.info("尚無資料")
            return

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

        st.dataframe(
            df,
            use_container_width=True
        )

    except Exception as e:
        st.error(str(e))