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
    for c in df.columns:
        for k in keywords:
            if k in c:
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

        if bed_col is None:
            st.warning(f"{sheet_name} 找不到床位欄位")
            st.write("目前欄位：", list(df.columns))
            continue

        sid_col = find_col(df, ["學號"])
        class_col = find_col(df, ["班級", "班"])
        name_col = find_col(df, ["姓名", "名字"])

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
            "樓層": [floor] * len(res),
            "房號": [room] * len(res),
            "床位": res[bed_col].apply(normalize_room).tolist(),
            "學號": res[sid_col].astype(str).tolist() if sid_col else [""] * len(res),
            "班級": res[class_col].astype(str).tolist() if class_col else [""] * len(res),
            "姓名": res[name_col].astype(str).tolist() if name_col else [""] * len(res),
        })

        result.append(temp)

    if result:
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
            "床位",
            "學號",
            "班級",
            "姓名"
        ])

    for _, r in total.iterrows():
        ws.append_row([
            school_year,
            semester,
            contest,
            rank,
            dorm,
            r.get("樓層", ""),
            r.get("房號", ""),
            r.get("床位", ""),
            r.get("學號", ""),
            r.get("班級", ""),
            r.get("姓名", "")
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
        sheet_name = get_floor_sheet_name(dorm, floor)

        rooms[floor] = st.text_input(
            f"{floor} 房號（讀取 {sheet_name}）",
            key=f"clean_room_{dorm}_{floor}_{semester}_{contest}_{rank}"
        )

    query_key = f"clean_result_{dorm}_{semester}_{contest}_{rank}"

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

    st.divider()
    st.subheader("名單確認")

    st.dataframe(
        total[
            [
                "樓層",
                "房號",
                "床位",
                "學號",
                "班級",
                "姓名"
            ]
        ],
        use_container_width=True
    )

    if st.button(
        "儲存到試算表",
        key=f"save_clean_{dorm}_{semester}_{contest}_{rank}"
    ):

        if school_year.strip() == "":
            st.error("請先輸入學年")
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

            st.success("已成功儲存到整潔比賽試算表")

        except Exception as e:
            st.error(str(e))


def show_clean_view():

    st.header("整潔比賽(檢視)")

    try:
        ss = open_sheet(CLEAN_RESULT_URL)
        ws = ss.worksheet("整潔比賽")

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

        st.dataframe(
            df,
            use_container_width=True
        )

    except Exception as e:
        st.error(str(e))