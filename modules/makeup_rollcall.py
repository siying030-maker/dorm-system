import streamlit as st
import pandas as pd

from datetime import datetime, timedelta
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
    ROLLCALL_SHEET_URL,
)


# =========================================================
# 基本工具
# =========================================================

def normalize_gender(value):
    value = str(value).strip()

    if value in ["男", "男生", "男性"]:
        return "男"

    if value in ["女", "女生", "女性"]:
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


def normalize_text(value):
    return str(value).strip()


def canonical_dorm(value):
    """
    統一宿舍名稱。
    """

    value = (
        str(value)
        .strip()
        .replace("ㄧ", "一")
        .replace(" ", "")
    )

    aliases = {
        "女一宿": "女一",
        "女二宿": "女二",
        "女三宿": "女三",
        "女一樓": "女一一樓",
        "女一一樓宿": "女一一樓",
        "男一宿": "男一",
        "男二宿": "男二",
        "男三宿": "男三",
    }

    return aliases.get(value, value)


# =========================================================
# 登入者性別
# =========================================================

def get_login_gender():

    # 1. 直接讀 gender
    gender = st.session_state.get(
        "gender",
        ""
    )

    gender = normalize_gender(
        gender
    )

    if gender:
        return gender

    # 2. 舍監類型
    supervisor_type = st.session_state.get(
        "supervisor_type",
        ""
    )

    gender = normalize_gender(
        supervisor_type
    )

    if gender:
        return gender

    # 3. 宿舍
    dorm = st.session_state.get(
        "dorm",
        ""
    )

    gender = normalize_gender(
        dorm
    )

    if gender:
        return gender

    # 4. 管理宿舍
    for key in [
        "manage_dorms",
        "winter_dorms",
        "summer_dorms",
    ]:

        value = st.session_state.get(
            key,
            ""
        )

        gender = normalize_gender(
            value
        )

        if gender:
            return gender

    return ""


def get_allowed_genders():

    role = str(
        st.session_state.get(
            "role",
            ""
        )
    ).strip()

    # -----------------------------------------
    # 行政
    # -----------------------------------------

    if role == "行政":
        return [
            "男生",
            "女生",
        ]

    # -----------------------------------------
    # 取得登入者性別
    # -----------------------------------------

    login_gender = get_login_gender()

    if login_gender == "男":
        return ["男生"]

    if login_gender == "女":
        return ["女生"]

    return []


# =========================================================
# 日期判斷
# =========================================================

def get_makeup_target_date():
    """
    補點資料日期：

    00:00～11:59
        → 前一天

    12:00～23:59
        → 當天
    """

    now = datetime.now(
        ZoneInfo("Asia/Taipei")
    )

    if now.hour < 12:
        return now.date() - timedelta(days=1)

    return now.date()


# =========================================================
# 讀取統一點名總表
# =========================================================

@st.cache_data(
    ttl=15,
    show_spinner=False
)
def load_need_makeup_source(gender):
    """
    從統一點名總表 ROLLCALL_SHEET_URL
    讀取目前需要補點的學生。

    狀態：
    - 缺
    - 未入住

    日期：
    - 00:00～11:59 → 前一天
    - 12:00 起 → 當天
    """

    ss = open_sheet(
        ROLLCALL_SHEET_URL
    )

    target_date = get_makeup_target_date()

    date_formats = [
        target_date.strftime("%Y-%m-%d"),
        target_date.strftime("%Y/%m/%d"),
    ]

    ws = None

    for sheet_name in date_formats:

        try:

            ws = get_worksheet(
                ss,
                sheet_name
            )

            break

        except Exception:
            pass

    if ws is None:
        return pd.DataFrame()

    values = get_all_values(ws)

    if not values or len(values) <= 1:
        return pd.DataFrame()

    headers = [
        str(x).strip()
        for x in values[0]
    ]

    df = pd.DataFrame(
        values[1:],
        columns=headers
    )

    # =====================================================
    # 必要欄位
    # =====================================================

    required_columns = [
        "學號",
        "姓名",
        "狀態",
    ]

    for col in required_columns:

        if col not in df.columns:
            return pd.DataFrame()

    # =====================================================
    # 狀態
    # =====================================================

    df["狀態"] = (
        df["狀態"]
        .astype(str)
        .str.strip()
    )

    df = df[
        df["狀態"].isin(
            [
                "缺",
                "未入住",
            ]
        )
    ].copy()

    if df.empty:
        return pd.DataFrame()

    # =====================================================
    # 性別
    # =====================================================

    target_gender = normalize_gender(
        gender
    )

    # 如果統一點名表本身有性別欄位
    if "性別" in df.columns:

        df["性別"] = (
            df["性別"]
            .astype(str)
            .map(normalize_gender)
        )

        df = df[
            df["性別"] == target_gender
        ].copy()

    else:

        # 統一點名表沒有性別
        # 因為這裡是由男生／女生來源分開讀取
        # 所以直接使用傳入的 gender
        df["性別"] = target_gender

    if df.empty:
        return pd.DataFrame()

    # =====================================================
    # 統一顯示文字
    # =====================================================

    df["性別"] = df["性別"].map(
        lambda x:
            "男生"
            if normalize_gender(x) == "男"
            else "女生"
            if normalize_gender(x) == "女"
            else str(x)
    )

    # =====================================================
    # 日期
    # =====================================================

    df["來源Sheet"] = ws.title
    df["日期"] = ws.title

    # =====================================================
    # 清除空白學生
    # =====================================================

    df["學號"] = (
        df["學號"]
        .astype(str)
        .str.strip()
    )

    df["姓名"] = (
        df["姓名"]
        .astype(str)
        .str.strip()
    )

    df = df[
        (df["學號"] != "")
        &
        (df["姓名"] != "")
    ].copy()

    return df.reset_index(
        drop=True
    )


# =========================================================
# 欄位工具
# =========================================================

def find_col_index(
    headers,
    col_name
):

    for i, h in enumerate(
        headers,
        start=1
    ):

        if (
            str(h).strip()
            == col_name
        ):
            return i

    return None


# =========================================================
# 男女舊資料 URL
# =========================================================

def get_rollcall_url_by_gender(gender):

    gender = normalize_gender(
        gender
    )

    if gender == "女":
        return ROLLCALL_GIRL_URL

    if gender == "男":
        return ROLLCALL_BOY_URL

    raise Exception(
        "無法判斷性別"
    )


def get_need_makeup_url_by_gender(gender):

    gender = normalize_gender(
        gender
    )

    if gender == "女":
        return NEED_MAKEUP_GIRL_URL

    if gender == "男":
        return NEED_MAKEUP_BOY_URL

    raise Exception(
        "無法判斷性別"
    )


# =========================================================
# 宿舍判斷
# =========================================================

def _prepare_dorm_column(
    df,
    default_gender=None
):
    """
    根據「性別 + 房號」判斷宿舍。

    女生：
        81 → 女一
        82 → 女二
        83 → 女三

    男生：
        81 → 女一一樓
        82 → 男一
        83 → 男三

    注意：
    統一點名表可能沒有性別欄位，
    但 load_need_makeup_source()
    已經依照男生／女生來源補上「性別」。
    """

    df = df.copy()

    # =====================================================
    # 沒有宿舍欄位 → 建立
    # 有宿舍欄位 → 先整理
    # =====================================================

    if "宿舍" not in df.columns:
        df["宿舍"] = ""

    else:

        df["宿舍"] = (
            df["宿舍"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        df["宿舍"] = df[
            "宿舍"
        ].apply(
            canonical_dorm
        )

    # =====================================================
    # 沒有房號
    # =====================================================

    if "房號" not in df.columns:
        return df

    # =====================================================
    # 判斷每一筆資料的性別
    # =====================================================

    if "性別" in df.columns:

        gender_series = (
            df["性別"]
            .apply(normalize_gender)
        )

    else:

        default_gender = normalize_gender(
            default_gender
        )

        gender_series = pd.Series(
            default_gender,
            index=df.index
        )

    # =====================================================
    # 房號轉文字
    # =====================================================

    room_series = (
        df["房號"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # 清除 Google Sheet 可能出現的 .0
    room_series = room_series.str.replace(
        r"\.0$",
        "",
        regex=True
    )

    # =====================================================
    # 依照性別 + 房號判斷
    # =====================================================

    def get_dorm(
        room,
        gender
    ):

        room = str(room).strip()
        gender = normalize_gender(
            gender
        )

        if not room:
            return ""

        prefix = room[:2]

        # -----------------------------------------
        # 女生
        # -----------------------------------------

        if gender == "女":

            if prefix == "81":
                return "女一"

            if prefix == "82":
                return "女二"

            if prefix == "83":
                return "女三"

        # -----------------------------------------
        # 男生
        # -----------------------------------------

        if gender == "男":

            if prefix == "81":
                return "女一一樓"

            if prefix == "82":
                return "男一"

            if prefix == "83":
                return "男三"

        return ""

    inferred_dorm = pd.Series(
        [
            get_dorm(
                room,
                gender
            )
            for room, gender
            in zip(
                room_series,
                gender_series
            )
        ],
        index=df.index
    )

    # =====================================================
    # 只要原本宿舍空白，就使用推算結果
    # =====================================================

    empty_dorm = (
        df["宿舍"]
        .astype(str)
        .str.strip()
        .eq("")
    )

    df.loc[
        empty_dorm,
        "宿舍"
    ] = inferred_dorm[
        empty_dorm
    ]

    return df


# =========================================================
# 取得樓長允許管理宿舍
# =========================================================

def get_allowed_dorms():

    allowed_dorms = []

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

            item = canonical_dorm(
                item
            )

            if item.endswith("宿"):
                item = item[:-1]

            if item:
                allowed_dorms.append(
                    item
                )

    return list(
        dict.fromkeys(
            allowed_dorms
        )
    )


# =========================================================
# 樓長依房號判斷宿舍
# =========================================================

def infer_dorm_for_leader(
    room,
    gender,
    allowed_dorms
):
    """
    根據：
        性別 + 房號 + 樓長管理宿舍

    判斷宿舍。

    女生：
        81 → 女一
        82 → 女二
        83 → 女三

    男生：
        81 → 女一一樓
        82 → 男一
        83 → 男三
    """

    room = str(room).strip()

    if room.endswith(".0"):
        room = room[:-2]

    if not room:
        return ""

    gender = normalize_gender(
        gender
    )

    allowed_dorms = [
        canonical_dorm(x)
        for x in allowed_dorms
    ]

    prefix = room[:2]

    # =====================================================
    # 女生
    # =====================================================

    if gender == "女":

        if (
            prefix == "81"
            and "女一" in allowed_dorms
        ):
            return "女一"

        if (
            prefix == "82"
            and "女二" in allowed_dorms
        ):
            return "女二"

        if (
            prefix == "83"
            and "女三" in allowed_dorms
        ):
            return "女三"

    # =====================================================
    # 男生
    # =====================================================

    if gender == "男":

        if (
            prefix == "81"
            and "女一一樓" in allowed_dorms
        ):
            return "女一一樓"

        if (
            prefix == "82"
            and "男一" in allowed_dorms
        ):
            return "男一"

        if (
            prefix == "83"
            and "男三" in allowed_dorms
        ):
            return "男三"

    return ""


# =========================================================
# 補點資料權限篩選
# =========================================================

def filter_by_leader_scope(
    df
):

    role = str(
        st.session_state.get(
            "role",
            ""
        )
    ).strip()

    if df.empty:
        return df

    # =====================================================
    # 先整理宿舍
    # =====================================================

    df = _prepare_dorm_column(
        df
    )

    # =====================================================
    # 行政
    # =====================================================

    if role == "行政":
        return df

    # =====================================================
    # 舍監
    # =====================================================

    if role == "舍監":

        supervisor_type = str(
            st.session_state.get(
                "supervisor_type",
                ""
            )
        ).strip()

        login_gender = normalize_gender(
            supervisor_type
        )

        if not login_gender:
            login_gender = get_login_gender()

        if login_gender == "男":

            return df[
                df["宿舍"]
                .astype(str)
                .str.startswith(
                    "男",
                    na=False
                )
            ].copy()

        if login_gender == "女":

            return df[
                df["宿舍"]
                .astype(str)
                .str.startswith(
                    "女",
                    na=False
                )
            ].copy()

        st.warning(
            "無法判斷舍監管理的宿舍性別"
        )

        return df.iloc[0:0].copy()

    # =====================================================
    # 樓長
    # =====================================================

    if role == "樓長":

        allowed_dorms = (
            get_allowed_dorms()
        )

        if not allowed_dorms:

            st.warning(
                "目前帳號沒有設定可管理的宿舍"
            )

            return df.iloc[0:0].copy()

        # =================================================
        # 重新依照「性別 + 房號」建立宿舍
        # =================================================

        df = _prepare_dorm_column(
            df
        )

        # =================================================
        # 如果已經成功判斷宿舍
        # =================================================

        matched = df[
            df["宿舍"].isin(
                allowed_dorms
            )
        ].copy()

        if not matched.empty:
            return matched

        # =================================================
        # 如果還是沒有匹配
        # 再依照樓長管理宿舍 + 性別 + 房號判斷
        # =================================================

        if "房號" not in df.columns:

            st.warning(
                "補點資料沒有「房號」欄位，"
                "無法依樓長管理宿舍篩選。"
            )

            return df.iloc[0:0].copy()

        # =================================================
        # 性別
        # =================================================

        if "性別" in df.columns:

            gender_series = (
                df["性別"]
                .apply(normalize_gender)
            )

        else:

            login_gender = get_login_gender()

            gender_series = pd.Series(
                login_gender,
                index=df.index
            )

        # =================================================
        # 房號
        # =================================================

        df["房號"] = (
            df["房號"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.replace(
                r"\.0$",
                "",
                regex=True
            )
        )

        # =================================================
        # 重新判斷宿舍
        # =================================================

        df["宿舍"] = [
            infer_dorm_for_leader(
                room,
                gender,
                allowed_dorms
            )
            for room, gender
            in zip(
                df["房號"],
                gender_series
            )
        ]

        matched = df[
            df["宿舍"].isin(
                allowed_dorms
            )
        ].copy()

        if not matched.empty:
            return matched

        # =================================================
        # 找不到
        # =================================================

        st.warning(
            "目前補點資料無法判斷符合此樓長帳號的宿舍。"
            f"目前帳號管理宿舍："
            f"{', '.join(allowed_dorms)}"
        )

        return df.iloc[0:0].copy()

    # =====================================================
    # 其他身分
    # =====================================================

    st.warning(
        "目前帳號沒有補點名單權限"
    )

    return df.iloc[0:0].copy()


# =========================================================
# 更新統一點名總表
# =========================================================

def update_rollcall_status_to_makeup(
    gender,
    target_row
):
    """
    統一點名總表：
    將學生狀態改成「已補點」。
    """

    ss = open_sheet(
        ROLLCALL_SHEET_URL
    )

    sheet_name = str(
        target_row.get(
            "日期",
            target_row.get(
                "來源Sheet",
                ""
            )
        )
    ).strip()

    sid = str(
        target_row.get(
            "學號",
            ""
        )
    ).strip()

    dorm = str(
        target_row.get(
            "宿舍",
            ""
        )
    ).strip()

    if not sheet_name:
        raise Exception(
            "補點資料沒有日期"
        )

    try:

        ws = get_worksheet(
            ss,
            sheet_name
        )

    except Exception:

        raise Exception(
            f"點名單總表找不到 Sheet：{sheet_name}"
        )

    values = get_all_values(
        ws
    )

    if len(values) <= 1:
        raise Exception(
            "點名單總表沒有資料"
        )

    headers = [
        str(x).strip()
        for x in values[0]
    ]

    sid_col = find_col_index(
        headers,
        "學號"
    )

    status_col = find_col_index(
        headers,
        "狀態"
    )

    dorm_col = find_col_index(
        headers,
        "宿舍"
    )

    if sid_col is None:
        raise Exception(
            "點名單總表找不到「學號」欄位"
        )

    if status_col is None:
        raise Exception(
            "點名單總表找不到「狀態」欄位"
        )

    for row_index, row in enumerate(
        values[1:],
        start=2
    ):

        row_sid = (
            str(
                row[sid_col - 1]
            ).strip()
            if len(row) >= sid_col
            else ""
        )

        row_dorm = (
            str(
                row[dorm_col - 1]
            ).strip()
            if dorm_col
            and len(row) >= dorm_col
            else ""
        )

        # 有宿舍欄位
        if dorm_col:

            if (
                row_sid == sid
                and (
                    not dorm
                    or canonical_dorm(row_dorm)
                    == canonical_dorm(dorm)
                )
            ):

                update_cell(
                    ws,
                    row_index,
                    status_col,
                    "已補點"
                )

                return True

        # 沒有宿舍欄位
        else:

            if row_sid == sid:

                update_cell(
                    ws,
                    row_index,
                    status_col,
                    "已補點"
                )

                return True

    raise Exception(
        f"點名單總表找不到此學生：{sid}"
    )


# =========================================================
# 更新舊男女補點名單
# =========================================================

def update_need_makeup_status_to_done(
    gender,
    target_row
):
    """
    同步舊的男女補點名單。

    統一點名總表才是主要資料來源。
    如果舊資料更新失敗，不影響主要補點。
    """

    try:

        source_url = (
            get_need_makeup_url_by_gender(
                gender
            )
        )

        ss = open_sheet(
            source_url
        )

        sheet_name = str(
            target_row.get(
                "來源Sheet",
                target_row.get(
                    "日期",
                    ""
                )
            )
        ).strip()

        sid = str(
            target_row.get(
                "學號",
                ""
            )
        ).strip()

        ws = get_worksheet(
            ss,
            sheet_name
        )

        values = get_all_values(
            ws
        )

        if len(values) <= 1:
            return

        headers = [
            str(x).strip()
            for x in values[0]
        ]

        sid_col = find_col_index(
            headers,
            "學號"
        )

        status_col = find_col_index(
            headers,
            "狀態"
        )

        if (
            sid_col is None
            or status_col is None
        ):
            return

        for row_index, row in enumerate(
            values[1:],
            start=2
        ):

            if (
                len(row) >= sid_col
                and
                str(
                    row[sid_col - 1]
                ).strip()
                == sid
            ):

                update_cell(
                    ws,
                    row_index,
                    status_col,
                    "已補點"
                )

                return

    except Exception:
        # 舊資料同步失敗
        # 不影響統一點名總表
        return


# =========================================================
# 顯示補點頁面
# =========================================================

def show_makeup_rollcall():

    st.header("補點名單")

    st.caption(
        "00:00～11:59 顯示前一天資料；"
        "12:00 起切換當天資料。"
        "資料每 15 秒重新讀取。"
    )

    # =====================================================
    # 手動刷新
    # =====================================================

    if st.button(
        "重新整理補點名單",
        key="refresh_makeup"
    ):

        load_need_makeup_source.clear()

        st.rerun()

    # =====================================================
    # 權限
    # =====================================================

    allowed_genders = (
        get_allowed_genders()
    )

    if not allowed_genders:

        st.info(
            "您沒有補點權限"
        )

        return

    # =====================================================
    # 讀取男女資料
    # =====================================================

    dfs = []

    for gender in allowed_genders:

        df = load_need_makeup_source(
            gender
        )

        if not df.empty:
            dfs.append(df)

    if not dfs:

        st.warning(
            "目前沒有「缺／未入住」補點資料"
        )

        return

    df = pd.concat(
        dfs,
        ignore_index=True
    )

    # =====================================================
    # 權限篩選
    # =====================================================

    df = filter_by_leader_scope(
        df
    )

    if df.empty:

        st.info(
            "目前沒有符合您管理範圍的補點資料"
        )

        return

    # =====================================================
    # 搜尋
    # =====================================================

    keyword = st.text_input(
        "搜尋學號 / 姓名 / 房號",
        key="makeup_search"
    )

    if keyword:

        keyword = str(
            keyword
        ).strip()

        condition = pd.Series(
            False,
            index=df.index
        )

        for col in [
            "學號",
            "姓名",
            "房號",
            "床位",
        ]:

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

        df = df[
            condition
        ]

    if df.empty:

        st.info(
            "查無符合條件的補點名資料"
        )

        return

    # =====================================================
    # 顯示資料
    # =====================================================

    show_cols = [
        c
        for c in [
            "床位",
            "學號",
            "班級",
            "姓名",
            "房號",
            "宿舍",
            "狀態",
            "備註",
        ]
        if c in df.columns
    ]

    st.dataframe(
        df[show_cols],
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # =====================================================
    # 補點完成
    # =====================================================

    st.subheader(
        "補點完成"
    )

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

        options.append(
            (
                i,
                label
            )
        )

    if not options:

        st.info(
            "目前沒有可以補點的學生"
        )

        return

    selected_label = st.selectbox(
        "選擇已補點學生",
        [
            x[1]
            for x in options
        ],
        key="makeup_selected"
    )

    selected_index = [
        x[0]
        for x in options
        if x[1] == selected_label
    ][0]

    # =====================================================
    # 確認補點
    # =====================================================

    if st.button(
        "確認補點完成",
        key="submit_makeup"
    ):

        try:

            target_row = (
                df.loc[
                    selected_index
                ].to_dict()
            )

            gender = (
                target_row.get(
                    "性別",
                    ""
                )
            )

            # ---------------------------------------------
            # 1. 更新統一點名總表
            # ---------------------------------------------

            update_rollcall_status_to_makeup(
                gender,
                target_row
            )

            # ---------------------------------------------
            # 2. 同步舊男女補點名單
            # ---------------------------------------------

            update_need_makeup_status_to_done(
                gender,
                target_row
            )

            # ---------------------------------------------
            # 3. 清除快取
            # ---------------------------------------------

            load_need_makeup_source.clear()

            # ---------------------------------------------
            # 4. 重新整理
            # ---------------------------------------------

            st.success(
                "已將狀態更新為：已補點"
            )

            st.rerun()

        except Exception as e:

            st.error(
                f"更新失敗：{e}"
            )