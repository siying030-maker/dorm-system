import streamlit as st
import pandas as pd

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

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


def canonical_dorm(value):
    value = str(value).strip().replace("ㄧ", "一")
    aliases = {
        "女一宿": "女一",
        "女二宿": "女二",
        "女三宿": "女三",
        "男一宿": "男一",
        "男三宿": "男三",
        "81宿_男": "女一一樓",
    }
    return aliases.get(value, value)


@st.cache_data(ttl=15, show_spinner=False)
def load_need_makeup_source(gender):
    """
    補點名單：
    - 「缺」與「未入住」都顯示。
    - 00:00～05:59 使用前一天的點名資料。
    - 06:00 起切換成當天資料。
    - 每 15 秒重新抓取一次 Google Sheet。
    """

    source_url = (
        NEED_MAKEUP_GIRL_URL
        if gender == "女生"
        else NEED_MAKEUP_BOY_URL
    )

    ss = open_sheet(source_url)

    # 00:00～11:59 仍屬前一天的補點時段
    now = datetime.now(ZoneInfo("Asia/Taipei"))

    if now.hour < 12:
        target_date = now.date() - timedelta(days=1)
    else:
        target_date = now.date()

    date_formats = [
        target_date.strftime("%Y-%m-%d"),
        target_date.strftime("%Y/%m/%d"),
    ]

    ws = None
    values = None

    for sheet_name in date_formats:
        try:
            ws = get_worksheet(ss, sheet_name)
            values = get_all_values(ws)
            break
        except Exception:
            pass

    if ws is None:
        return pd.DataFrame()

    if not values or len(values) <= 1:
        return pd.DataFrame()

    df = pd.DataFrame(
        values[1:],
        columns=values[0]
    )

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
    )

    if "狀態" not in df.columns:
        return pd.DataFrame()

    df["狀態"] = (
        df["狀態"]
        .astype(str)
        .str.strip()
    )

    # 「缺」＋「未入住」都列入補點名單
    df = df[
        df["狀態"].isin(["缺", "未入住"])
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

    if "日期" not in df.columns:
        df["日期"] = target_date.strftime("%Y-%m-%d")

    if "學號" in df.columns:
        df = df[
            df["學號"]
            .astype(str)
            .str.strip() != ""
        ]

    if "姓名" in df.columns:
        df = df[
            df["姓名"]
            .astype(str)
            .str.strip() != ""
        ]

    return df.reset_index(drop=True)


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


def _prepare_dorm_column(df):
    """
    補點資料沒有宿舍欄位時，
    依登入者性別 + 房號判斷宿舍。

    男生：
        81xxx / 82xxx -> 男一
        83xxx -> 男三

    女生：
        依目前女生宿舍房號規則處理。

    如果資料本身已有宿舍欄位，優先使用原本資料。
    """

    result = df.copy()

    # ==========================================
    # 1. 如果原本有宿舍欄位，直接使用
    # ==========================================
    source_col = None

    for candidate in [
        "宿舍",
        "宿舍別",
        "宿舍名稱",
        "宿別",
        "住宿宿舍",
    ]:
        if candidate in result.columns:
            source_col = candidate
            break

    if source_col is not None:
        result["宿舍"] = result[source_col]

    else:
        result["宿舍"] = ""

    # ==========================================
    # 2. 統一宿舍名稱
    # ==========================================
    result["宿舍"] = (
        result["宿舍"]
        .astype(str)
        .str.strip()
        .str.replace("ㄧ", "一", regex=False)
        .str.replace("女一宿", "女一", regex=False)
        .str.replace("女二宿", "女二", regex=False)
        .str.replace("女三宿", "女三", regex=False)
        .str.replace("男一宿", "男一", regex=False)
        #.str.replace("男二宿", "男", regex=False)
        .str.replace("男三宿", "男三", regex=False)
    )

    # ==========================================
    # 3. 沒有宿舍資料 → 從房號判斷
    # ==========================================
    if "房號" not in result.columns:
        return result

    login_gender = get_login_gender()

    def infer_dorm_from_room(room):
        room = str(room).strip()

        if not room:
            return ""

        # 例如 82301 -> 82
        prefix = room[:2]

        # ------------------------------------------
        # 男生
        # ------------------------------------------
        if login_gender == "男":

            if prefix in ["81", "82"]:
                return "男一"

            if prefix == "83":
                return "男三"

        # ------------------------------------------
        # 女生
        # ------------------------------------------
        elif login_gender == "女":

            if prefix in ["81", "82"]:
                return "女一"

            if prefix in ["82"]:
                return "女二"

            if prefix == "83":
                return "女三"

        return ""

    inferred_dorm = result["房號"].apply(
        infer_dorm_from_room
    )

    # 只有原本沒有宿舍的資料才補上
    empty_dorm = (
        result["宿舍"]
        .astype(str)
        .str.strip()
        .eq("")
    )

    result.loc[empty_dorm, "宿舍"] = (
        inferred_dorm[empty_dorm]
    )

    return result


def _infer_dorm_from_row(row, allowed_dorms):
    """
    舊資料沒有宿舍欄位時，嘗試從整列資料找出宿舍名稱。
    只接受帳號本身被允許管理的宿舍，避免擴大樓長權限。
    """
    text = " ".join(
        str(value).strip().replace("ㄧ", "一")
        for value in row.tolist()
        if str(value).strip()
    )

    for dorm in allowed_dorms:
        if dorm and dorm in text:
            return dorm

    return ""


def filter_by_leader_scope(df):
    role = str(st.session_state.get("role", "")).strip()

    if df.empty:
        return df

    result = df.copy()

    # ==================================================
    # 先處理宿舍欄位
    # ==================================================
    result = _prepare_dorm_column(result)

    # ==================================================
    # 行政：全部可以看
    # ==================================================
    if role == "行政":
        return result

    # ==================================================
    # 舍監：依登入性別查看男／女資料
    # ==================================================
    if role == "舍監":

        supervisor_type = str(
            st.session_state.get("supervisor_type", "")
        ).strip()

        login_gender = normalize_gender(supervisor_type)

        if not login_gender:
            login_gender = get_login_gender()

        if login_gender not in ["男", "女"]:
            st.warning("無法判斷舍監管理的宿舍性別")
            return result.iloc[0:0].copy()

        # 如果補點資料有宿舍
        if result["宿舍"].astype(str).str.strip().ne("").any():

            if login_gender == "男":
                return result[
                    result["宿舍"].astype(str).str.startswith(
                        "男",
                        na=False
                    )
                ].copy()

            if login_gender == "女":
                return result[
                    result["宿舍"].astype(str).str.startswith(
                        "女",
                        na=False
                    )
                ].copy()

        # 沒有宿舍資訊時，因為男女資料來源本來就是分開的，
        # 直接保留該性別來源的資料
        return result

    # ==================================================
    # 樓長
    # ==================================================
    if role == "樓長":

        allowed_dorms = []

        # 取得樓長被分配的宿舍
        for state_key in [
            "dorm",
            "manage_dorms",
            "winter_dorms",
            "summer_dorms",
        ]:

            raw_value = st.session_state.get(
                state_key,
                ""
            )

            raw_value = (
                str(raw_value)
                .replace("，", ",")
                .replace("、", ",")
                .replace("/", ",")
                .replace("／", ",")
                .replace(";", ",")
                .replace("；", ",")
            )

            for item in raw_value.split(","):

                item = str(item).strip()

                if not item:
                    continue

                item = canonical_dorm(item)

                if item.endswith("宿"):
                    item = item[:-1]

                if item:
                    allowed_dorms.append(item)

        allowed_dorms = list(
            dict.fromkeys(allowed_dorms)
        )

        if not allowed_dorms:
            st.warning("目前帳號沒有設定可管理的宿舍")
            return result.iloc[0:0].copy()

        # ==================================================
        # 如果原始資料有宿舍欄位，直接比對
        # ==================================================
        has_dorm = (
            result["宿舍"]
            .astype(str)
            .str.strip()
            .ne("")
            .any()
        )

        if has_dorm:

            return result[
                result["宿舍"].isin(
                    allowed_dorms
                )
            ].copy()

        # ==================================================
        # 沒有宿舍欄位
        # 改用「房號」判斷
        # ==================================================
        if "房號" not in result.columns:

            st.warning(
                "補點資料沒有「宿舍」或「房號」資訊，"
                "無法依樓長權限篩選。"
            )

            return result.iloc[0:0].copy()

        login_gender = get_login_gender()

        result["房號"] = (
            result["房號"]
            .astype(str)
            .str.strip()
        )

        # ==================================================
        # 男生補點資料
        # ==================================================
        if login_gender == "男":

            def male_dorm_from_room(room):

                room = str(room).strip()

                # 男一
                if room.startswith(("81", "82")):
                    return "男一"

                # 男三
                if room.startswith("83"):
                    return "男三"

                return ""

            result["宿舍"] = result["房號"].apply(
                male_dorm_from_room
            )

        # ==================================================
        # 女生補點資料
        # ==================================================
        elif login_gender == "女":

            def female_dorm_from_room(room):

                room = str(room).strip()

                # 女生目前補點資料如果沒有宿舍欄位，
                # 先依現有樓長權限判斷。
                #
                # 例如帳號只管理女一，
                # 而目前資料沒有宿舍資訊，
                # 不直接把所有女生資料給樓長。

                return ""

            result["宿舍"] = result["房號"].apply(
                female_dorm_from_room
            )

        # ==================================================
        # 再次依樓長允許宿舍篩選
        # ==================================================
        matched = result[
            result["宿舍"].isin(
                allowed_dorms
            )
        ].copy()

        if not matched.empty:
            return matched

        # ==================================================
        # 顯示診斷資訊
        # ==================================================
        st.warning(
            f"目前補點資料無法符合樓長權限。"
            f"目前帳號管理宿舍：{', '.join(allowed_dorms)}"
        )

        return result.iloc[0:0].copy()

    # ==================================================
    # 其他身分
    # ==================================================
    st.warning("目前帳號沒有補點名單權限")

    return result.iloc[0:0].copy()


def show_makeup_rollcall():

    st.header("補點名單")
    st.caption("00:00～11:59 顯示前一天資料；06:00 起切換當天資料，並每 15 秒自動刷新。")

    

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
        st.warning("目前沒有「缺／未入住」補點資料")
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