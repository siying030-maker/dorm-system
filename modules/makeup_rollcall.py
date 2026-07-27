import streamlit as st
import pandas as pd

from datetime import date

from core.google_api import (
    open_sheet,
    get_worksheet,
    get_all_values,
    update_cell,
)

from core.config import (
    NEED_MAKEUP_GIRL_URL,
    NEED_MAKEUP_BOY_URL,
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


def gender_to_label(gender):

    gender = normalize_gender(gender)

    if gender == "男":
        return "男生"

    if gender == "女":
        return "女生"

    return ""


def get_login_gender():

    gender = st.session_state.get("gender", "")

    gender = normalize_gender(gender)

    if gender:
        return gender

    supervisor_type = st.session_state.get(
        "supervisor_type",
        ""
    )

    gender = normalize_gender(supervisor_type)

    if gender:
        return gender

    dorm = st.session_state.get("dorm", "")

    gender = normalize_gender(dorm)

    if gender:
        return gender

    return ""


def get_allowed_genders():

    role = st.session_state.get("role", "")

    if role == "行政":
        return []

    login_gender = get_login_gender()

    if login_gender == "男":
        return ["男生"]

    if login_gender == "女":
        return ["女生"]

    return []


def normalize_text(value):

    return str(value).strip()


@st.cache_data(ttl=15, show_spinner=False)
def load_need_makeup_source(gender):
    source_url = (
        NEED_MAKEUP_GIRL_URL
        if gender == "女生"
        else NEED_MAKEUP_BOY_URL
    )

    ss = open_sheet(source_url)

    today1 = str(date.today())
    today2 = today1.replace("-", "/")

    ws = None

    for sheet_name in [today1, today2]:

        try:
            ws = get_worksheet(ss, sheet_name)
            values = get_all_values(ws)
            break

        except:
            pass

    if ws is None:
        return pd.DataFrame()

    from core.google_api import get_all_values

    values = get_all_values(ws)

    if len(values) <= 1:
        return pd.DataFrame()

    df = pd.DataFrame(
        values[1:],
        columns=values[0]
    )

    df.columns = df.columns.astype(str).str.strip()

    if "狀態" not in df.columns:
        return pd.DataFrame()

    df["狀態"] = (
        df["狀態"]
        .astype(str)
        .str.strip()
    )

    df = df[
        df["狀態"] == "缺"
    ].copy()

    if df.empty:
        return pd.DataFrame()

    if "性別" in df.columns:

        df["性別"] = (
            df["性別"]
            .astype(str)
            .map(normalize_gender)
        )

        target_gender = normalize_gender(gender)

        df = df[
            df["性別"] == target_gender
        ].copy()

        df["性別"] = df["性別"].map(
            lambda x: "男生" if x == "男" else "女生"
        )

    else:

        df["性別"] = gender

    df["來源Sheet"] = ws.title

    df = df[
        df["學號"]
        .astype(str)
        .str.strip() != ""
    ]

    df = df[
        df["姓名"]
        .astype(str)
        .str.strip() != ""
    ]

    return df


def find_col_index(headers, col_name):

    for i, h in enumerate(headers, start=1):

        if str(h).strip() == col_name:
            return i

    return None


def get_rollcall_url_by_gender(gender):

    gender = normalize_gender(gender)

    if gender == "女":
        return ROLLCALL_GIRL_URL

    if gender == "男":
        return ROLLCALL_BOY_URL

    raise Exception("無法判斷性別")


def get_need_makeup_url_by_gender(gender):

    gender = normalize_gender(gender)

    if gender == "女":
        return NEED_MAKEUP_GIRL_URL

    if gender == "男":
        return NEED_MAKEUP_BOY_URL

    raise Exception("無法判斷性別")


def update_rollcall_status_to_makeup(gender, target_row):

    rollcall_url = get_rollcall_url_by_gender(gender)

    ss = open_sheet(rollcall_url)

    sheet_name = str(
        target_row.get("來源Sheet", "")
    ).strip()

    sid = str(
        target_row.get("學號", "")
    ).strip()

    rollcall_date = str(
        target_row.get("日期", "")
    ).strip()

    try:
        ws = get_worksheet(ss, sheet_name)
        values = get_all_values(ws)

    except:
        raise Exception(f"點名總表找不到 Sheet：{sheet_name}")

    from core.google_api import get_all_values

    values = get_all_values(ws)

    if len(values) <= 1:
        raise Exception("點名總表沒有資料")

    headers = values[0]

    sid_col = find_col_index(headers, "學號")
    status_col = find_col_index(headers, "狀態")
    date_col = find_col_index(headers, "日期")

    if sid_col is None:
        raise Exception("點名總表找不到「學號」欄位")

    if status_col is None:
        raise Exception("點名總表找不到「狀態」欄位")

    for row_index, row in enumerate(values[1:], start=2):

        row_sid = ""
        row_date = ""

        if len(row) >= sid_col:
            row_sid = str(row[sid_col - 1]).strip()

        if date_col and len(row) >= date_col:
            row_date = str(row[date_col - 1]).strip()

        if row_sid == sid:

            if date_col is None or row_date == rollcall_date:

                update_cell(
                    ws,
                    row_index,
                    status_col,
                    "已補點",
                )

                return True

    raise Exception(f"點名總表找不到此學生：{sid}")


def update_need_makeup_status_to_done(gender, target_row):

    source_url = get_need_makeup_url_by_gender(gender)

    ss = open_sheet(source_url)

    sheet_name = str(
        target_row.get("來源Sheet", "")
    ).strip()

    sid = str(
        target_row.get("學號", "")
    ).strip()

    rollcall_date = str(
        target_row.get("日期", "")
    ).strip()

    try:
        ws = get_worksheet(ss, sheet_name)
        values = get_all_values(ws)

    except:
        raise Exception(f"需補點名單找不到 Sheet：{sheet_name}")

    from core.google_api import get_all_values

    values = get_all_values(ws)

    if len(values) <= 1:
        return

    headers = values[0]

    sid_col = find_col_index(headers, "學號")
    status_col = find_col_index(headers, "狀態")
    date_col = find_col_index(headers, "日期")

    if sid_col is None or status_col is None:
        return

    for row_index, row in enumerate(values[1:], start=2):

        row_sid = ""
        row_date = ""

        if len(row) >= sid_col:
            row_sid = str(row[sid_col - 1]).strip()

        if date_col and len(row) >= date_col:
            row_date = str(row[date_col - 1]).strip()

        if row_sid == sid:

            if date_col is None or row_date == rollcall_date:

                update_cell(
                    ws,
                    row_index,
                    status_col,
                    "已補點",
                )

                return


def filter_by_leader_scope(df):

    role = str(st.session_state.get("role", "")).strip()

    if df.empty:
        return df

    if "宿舍" not in df.columns:
        st.warning(
            "目前補點資料沒有「宿舍」欄位，無法依宿舍權限篩選。"
            "請使用新版點名系統重新儲存缺席資料。"
        )
        return df.iloc[0:0].copy()

    result = df.copy()
    result["宿舍"] = (
        result["宿舍"]
        .astype(str)
        .str.strip()
        .str.replace("ㄧ", "一", regex=False)
    )

    # 行政：可查看全部宿舍
    if role == "行政":
        return result

    # 舍監：依男舍監／女舍監篩選
    if role == "舍監":
        supervisor_type = str(
            st.session_state.get("supervisor_type", "")
        ).strip()

        login_gender = normalize_gender(supervisor_type)

        if not login_gender:
            login_gender = get_login_gender()

        if login_gender == "男":
            return result[
                result["宿舍"].str.startswith("男", na=False)
            ].copy()

        if login_gender == "女":
            return result[
                result["宿舍"].str.startswith("女", na=False)
            ].copy()

        st.warning("無法判斷舍監管理的宿舍性別")
        return result.iloc[0:0].copy()

    # 樓長：只查看登入帳號被指派的宿舍
    if role == "樓長":
        allowed_dorms = []

        for state_key in [
            "dorm",
            "manage_dorms",
            "winter_dorms",
            "summer_dorms",
        ]:
            raw_value = st.session_state.get(state_key, "")

            for item in str(raw_value).replace("，", ",").split(","):
                item = item.strip().replace("ㄧ", "一")

                if item:
                    allowed_dorms.append(item)

        allowed_dorms = list(dict.fromkeys(allowed_dorms))

        if not allowed_dorms:
            st.warning("目前帳號沒有設定可管理的宿舍")
            return result.iloc[0:0].copy()

        return result[
            result["宿舍"].isin(allowed_dorms)
        ].copy()

    # 其他身分不顯示補點資料
    st.warning("目前帳號沒有補點名單權限")
    return result.iloc[0:0].copy()


def show_makeup_rollcall():

    st.header("補點名單")

    

    if st.button("重新整理補點名單", key="refresh_makeup"):
        load_need_makeup_source.clear()
        st.rerun()

    allowed_genders = get_allowed_genders()

    if not allowed_genders:
        st.info("您沒有補點權限")
        return

    dfs = []

    for gender in allowed_genders:

        df = load_need_makeup_source(gender)

        if not df.empty:
            dfs.append(df)

    if not dfs:
        st.warning("目前沒有當日須補點資料")
        return

    df = pd.concat(
        dfs,
        ignore_index=True
    )

    df = filter_by_leader_scope(df)

    keyword = st.text_input(
        "搜尋學號 / 姓名 / 房號",
        key="makeup_search"
    )

    if keyword:

        keyword = str(keyword).strip()

        condition = pd.Series(
            False,
            index=df.index
        )

        for col in ["學號", "姓名", "房號", "床位"]:

            if col in df.columns:

                condition = (
                    condition
                    |
                    df[col]
                    .astype(str)
                    .str.contains(
                        keyword,
                        na=False
                    )
                )

        df = df[condition]

    if df.empty:
        st.info("查無符合條件的補點名資料")
        return

    show_cols = [
    c for c in [
        "床位",
        "學號",
        "班級",
        "姓名",
        "狀態",
        "備註"
    ]
    if c in df.columns
]

    st.dataframe(
        df[show_cols],
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    st.subheader("補點完成")

    options = []

    for i, row in df.iterrows():

        label = (
            f'{row.get("性別", "")}｜'
            f'{row.get("日期", "")}｜'
            f'{row.get("宿舍", "")}｜'
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
        x[0]
        for x in options
        if x[1] == selected_label
    ][0]

    if st.button("確認補點完成", key="submit_makeup"):

        try:
            target_row = df.loc[
                selected_index
            ].to_dict()

            gender = target_row.get(
                "性別",
                ""
            )

            update_rollcall_status_to_makeup(
                gender,
                target_row
            )

            update_need_makeup_status_to_done(
                gender,
                target_row
            )

            load_need_makeup_source.clear()
            st.rerun()

            st.success("已將狀態更新為：已補點")

        except Exception as e:
            st.error(f"更新失敗：{e}")