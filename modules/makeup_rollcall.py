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


# =========================================================
# 性別處理
# =========================================================

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
    """
    嘗試從登入資訊判斷使用者性別。

    優先順序：
    1. gender
    2. supervisor_type
    3. dorm
    """

    gender = st.session_state.get("gender", "")
    gender = normalize_gender(gender)

    if gender:
        return gender

    supervisor_type = st.session_state.get("supervisor_type", "")
    gender = normalize_gender(supervisor_type)

    if gender:
        return gender

    dorm = st.session_state.get("dorm", "")
    gender = normalize_gender(dorm)

    if gender:
        return gender

    return ""


def get_allowed_genders():
    """
    判斷目前登入帳號可以查看男生或女生資料。

    行政：
        可查看全部性別。

    舍監／樓長：
        依登入帳號的性別限制。
    """

    role = st.session_state.get("role", "")

    if role == "行政":
        return ["男生", "女生"]

    login_gender = get_login_gender()

    if login_gender == "男":
        return ["男生"]

    if login_gender == "女":
        return ["女生"]

    return []


# =========================================================
# 一般文字處理
# =========================================================

def normalize_text(value):
    return str(value).strip()


# =========================================================
# 宿舍名稱標準化
# =========================================================

def _normalize_dorm_name(value):
    """
    統一宿舍名稱。

    例如：
        女一宿 -> 女一
        女二宿 -> 女二
        男一宿 -> 男一
        ㄧ -> 一
    """

    value = str(value).strip()

    if not value:
        return ""

    value = (
        value
        .replace("ㄧ", "一")
        .replace("女一宿", "女一")
        .replace("女二宿", "女二")
        .replace("女三宿", "女三")
        .replace("男一宿", "男一")
        .replace("男二宿", "男二")
        .replace("男三宿", "男三")
        .replace("81宿_男", "女一一樓")
    )

    return value


def canonical_dorm(value):
    """
    將登入帳號的宿舍名稱轉成統一格式。
    """

    value = str(value).strip()

    if not value:
        return ""

    value = value.replace("ㄧ", "一")

    aliases = {
        "女一宿": "女一",
        "女二宿": "女二",
        "女三宿": "女三",
        "男一宿": "男一",
        "男二宿": "男二",
        "男三宿": "男三",
        "81宿_男": "女一一樓",
    }

    return aliases.get(value, value)


# =========================================================
# 載入「需補點名單」
# =========================================================

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

    now = datetime.now(ZoneInfo("Asia/Taipei"))

    if now.hour < 6:
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

    df.columns = df.columns.astype(str).str.strip()

    # -----------------------------------------------------
    # 必須有狀態欄位
    # -----------------------------------------------------

    if "狀態" not in df.columns:
        return pd.DataFrame()

    df["狀態"] = (
        df["狀態"]
        .astype(str)
        .str.strip()
    )

    # -----------------------------------------------------
    # 只顯示「缺」與「未入住」
    # -----------------------------------------------------

    df = df[
        df["狀態"].isin(["缺", "未入住"])
    ].copy()

    if df.empty:
        return pd.DataFrame()

    # -----------------------------------------------------
    # 性別
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 來源 Sheet
    # -----------------------------------------------------

    df["來源Sheet"] = ws.title

    # -----------------------------------------------------
    # 日期
    # -----------------------------------------------------

    if "日期" not in df.columns:
        df["日期"] = target_date.strftime("%Y-%m-%d")

    # -----------------------------------------------------
    # 過濾空學號
    # -----------------------------------------------------

    if "學號" in df.columns:
        df = df[
            df["學號"]
            .astype(str)
            .str.strip() != ""
        ]

    # -----------------------------------------------------
    # 過濾空姓名
    # -----------------------------------------------------

    if "姓名" in df.columns:
        df = df[
            df["姓名"]
            .astype(str)
            .str.strip() != ""
        ]

    return df.reset_index(drop=True)


# =========================================================
# 找欄位
# =========================================================

def find_col_index(headers, col_name):

    for i, h in enumerate(headers, start=1):

        if str(h).strip() == col_name:
            return i

    return None


# =========================================================
# 依性別取得點名總表
# =========================================================

def get_rollcall_url_by_gender(gender):

    gender = normalize_gender(gender)

    if gender == "女":
        return ROLLCALL_GIRL_URL

    if gender == "男":
        return ROLLCALL_BOY_URL

    raise Exception("無法判斷性別")


# =========================================================
# 依性別取得需補點名單
# =========================================================

def get_need_makeup_url_by_gender(gender):

    gender = normalize_gender(gender)

    if gender == "女":
        return NEED_MAKEUP_GIRL_URL

    if gender == "男":
        return NEED_MAKEUP_BOY_URL

    raise Exception("無法判斷性別")


# =========================================================
# 將點名總表狀態改成「已補點」
# =========================================================

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

        ws = get_worksheet(
            ss,
            sheet_name
        )

        values = get_all_values(ws)

    except Exception:

        raise Exception(
            f"點名總表找不到 Sheet：{sheet_name}"
        )

    if len(values) <= 1:

        raise Exception(
            "點名總表沒有資料"
        )

    headers = values[0]

    sid_col = find_col_index(
        headers,
        "學號"
    )

    status_col = find_col_index(
        headers,
        "狀態"
    )

    date_col = find_col_index(
        headers,
        "日期"
    )

    if sid_col is None:

        raise Exception(
            "點名總表找不到「學號」欄位"
        )

    if status_col is None:

        raise Exception(
            "點名總表找不到「狀態」欄位"
        )

    for row_index, row in enumerate(
        values[1:],
        start=2
    ):

        row_sid = ""
        row_date = ""

        if len(row) >= sid_col:

            row_sid = str(
                row[sid_col - 1]
            ).strip()

        if date_col and len(row) >= date_col:

            row_date = str(
                row[date_col - 1]
            ).strip()

        if row_sid == sid:

            if (
                date_col is None
                or row_date == rollcall_date
            ):

                update_cell(
                    ws,
                    row_index,
                    status_col,
                    "已補點"
                )

                return True

    raise Exception(
        f"點名總表找不到此學生：{sid}"
    )


# =========================================================
# 將「需補點名單」狀態改成「已補點」
# =========================================================

def update_need_makeup_status_to_done(
    gender,
    target_row
):

    source_url = get_need_makeup_url_by_gender(
        gender
    )

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

        ws = get_worksheet(
            ss,
            sheet_name
        )

        values = get_all_values(ws)

    except Exception:

        raise Exception(
            f"需補點名單找不到 Sheet：{sheet_name}"
        )

    if len(values) <= 1:
        return

    headers = values[0]

    sid_col = find_col_index(
        headers,
        "學號"
    )

    status_col = find_col_index(
        headers,
        "狀態"
    )

    date_col = find_col_index(
        headers,
        "日期"
    )

    if sid_col is None or status_col is None:
        return

    for row_index, row in enumerate(
        values[1:],
        start=2
    ):

        row_sid = ""
        row_date = ""

        if len(row) >= sid_col:

            row_sid = str(
                row[sid_col - 1]
            ).strip()

        if date_col and len(row) >= date_col:

            row_date = str(
                row[date_col - 1]
            ).strip()

        if row_sid == sid:

            if (
                date_col is None
                or row_date == rollcall_date
            ):

                update_cell(
                    ws,
                    row_index,
                    status_col,
                    "已補點"
                )

                return


# =========================================================
# 整理補點資料的宿舍欄位
# =========================================================

def _prepare_dorm_column(df):
    """
    整理補點資料中的：

    平常宿舍：
        宿舍
        宿舍別
        宿舍名稱
        宿別
        住宿宿舍

    假日宿舍：
        假日宿舍別
        假日宿舍
        假日宿舍名稱
        假日宿別
        假日住宿宿舍

    寒假宿舍：
        寒假宿舍別
        寒假宿舍
        寒假宿舍名稱
        寒假宿別
        寒假住宿宿舍

    暑假宿舍：
        暑假宿舍別
        暑假宿舍
        暑假宿舍名稱
        暑假宿別
        暑假住宿宿舍
    """

    result = df.copy()

    # =====================================================
    # 平常宿舍
    # =====================================================

    if "宿舍" in result.columns:

        source_col = "宿舍"

    else:

        source_col = None

        for candidate in [
            "宿舍別",
            "宿舍名稱",
            "宿別",
            "住宿宿舍",
        ]:

            if candidate in result.columns:

                source_col = candidate
                break

        if source_col is not None:

            result["宿舍"] = result[
                source_col
            ]

        else:

            result["宿舍"] = ""

    result["宿舍"] = (
        result["宿舍"]
        .apply(_normalize_dorm_name)
    )

    # =====================================================
    # 假日宿舍
    # =====================================================

    holiday_col = None

    for candidate in [
        "假日宿舍別",
        "假日宿舍",
        "假日宿舍名稱",
        "假日宿別",
        "假日住宿宿舍",
    ]:

        if candidate in result.columns:

            holiday_col = candidate
            break

    if holiday_col is not None:

        result["假日宿舍"] = (
            result[holiday_col]
            .apply(_normalize_dorm_name)
        )

    else:

        result["假日宿舍"] = ""

    # =====================================================
    # 寒假宿舍
    # =====================================================

    winter_col = None

    for candidate in [
        "寒假宿舍別",
        "寒假宿舍",
        "寒假宿舍名稱",
        "寒假宿別",
        "寒假住宿宿舍",
    ]:

        if candidate in result.columns:

            winter_col = candidate
            break

    if winter_col is not None:

        result["寒假宿舍"] = (
            result[winter_col]
            .apply(_normalize_dorm_name)
        )

    else:

        result["寒假宿舍"] = ""

    # =====================================================
    # 暑假宿舍
    # =====================================================

    summer_col = None

    for candidate in [
        "暑假宿舍別",
        "暑假宿舍",
        "暑假宿舍名稱",
        "暑假宿別",
        "暑假住宿宿舍",
    ]:

        if candidate in result.columns:

            summer_col = candidate
            break

    if summer_col is not None:

        result["暑假宿舍"] = (
            result[summer_col]
            .apply(_normalize_dorm_name)
        )

    else:

        result["暑假宿舍"] = ""

    return result


# =========================================================
# 舊資料：從整列資料推測宿舍
# =========================================================

def _infer_dorm_from_row(
    row,
    allowed_dorms
):
    """
    舊資料沒有宿舍欄位時，
    嘗試從整列資料找出宿舍名稱。

    只接受帳號本身被允許管理的宿舍，
    避免擴大樓長權限。
    """

    text = " ".join(
        str(value)
        .strip()
        .replace("ㄧ", "一")
        for value in row.tolist()
        if str(value).strip()
    )

    for dorm in allowed_dorms:

        if dorm and dorm in text:

            return dorm

    return ""


# =========================================================
# 樓長／舍監／行政權限篩選
# =========================================================

def filter_by_leader_scope(df):

    role = str(
        st.session_state.get(
            "role",
            ""
        )
    ).strip()

    if df.empty:
        return df

    # =====================================================
    # 先整理宿舍資料
    # =====================================================

    result = _prepare_dorm_column(df)

    # =====================================================
    # 行政
    # =====================================================

    if role == "行政":

        return result

    # =====================================================
    # 舍監
    #
    # 舍監主要依性別管理。
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

        dorm_has_value = (
            result["宿舍"]
            .astype(str)
            .str.strip()
            .ne("")
            .any()
        )

        if not dorm_has_value:

            if login_gender in ["男", "女"]:

                return result

            st.warning(
                "無法判斷舍監管理的宿舍性別"
            )

            return result.iloc[0:0].copy()

        if login_gender == "男":

            return result[
                result["宿舍"]
                .str.startswith(
                    "男",
                    na=False
                )
            ].copy()

        if login_gender == "女":

            return result[
                result["宿舍"]
                .str.startswith(
                    "女",
                    na=False
                )
            ].copy()

        st.warning(
            "無法判斷舍監管理的宿舍性別"
        )

        return result.iloc[0:0].copy()

    # =====================================================
    # 樓長
    #
    # 只查看登入帳號被指派的宿舍。
    #
    # 判斷：
    #
    # 平常宿舍 OR
    # 假日宿舍 OR
    # 寒假宿舍 OR
    # 暑假宿舍
    #
    # 只要其中一個符合，就可以看到。
    # =====================================================

    if role == "樓長":

        allowed_dorms = []

        # -------------------------------------------------
        # 從登入資訊取得可管理宿舍
        # -------------------------------------------------

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

                item = canonical_dorm(item)

                if item:

                    allowed_dorms.append(item)

        # -------------------------------------------------
        # 去除重複
        # -------------------------------------------------

        allowed_dorms = list(
            dict.fromkeys(
                allowed_dorms
            )
        )

        if not allowed_dorms:

            st.warning(
                "目前帳號沒有設定可管理的宿舍"
            )

            return result.iloc[0:0].copy()

        # =================================================
        # 重要：
        #
        # 平常宿舍 OR 假日宿舍 OR 寒假宿舍 OR 暑假宿舍
        # =================================================

        matched = result[
            result["宿舍"].isin(
                allowed_dorms
            )
            |
            result["假日宿舍"].isin(
                allowed_dorms
            )
            |
            result["寒假宿舍"].isin(
                allowed_dorms
            )
            |
            result["暑假宿舍"].isin(
                allowed_dorms
            )
        ].copy()

        # -------------------------------------------------
        # 有找到資料
        # -------------------------------------------------

        if not matched.empty:

            return matched

        # =================================================
        # 舊版資料相容
        #
        # 如果新版宿舍欄位完全沒有資料，
        # 才嘗試從整列資料推測。
        # =================================================

        all_dorm_columns_empty = (
            result["宿舍"]
            .astype(str)
            .str.strip()
            .eq("")
            .all()
            and
            result["假日宿舍"]
            .astype(str)
            .str.strip()
            .eq("")
            .all()
            and
            result["寒假宿舍"]
            .astype(str)
            .str.strip()
            .eq("")
            .all()
            and
            result["暑假宿舍"]
            .astype(str)
            .str.strip()
            .eq("")
            .all()
        )

        if all_dorm_columns_empty:

            inferred = result.apply(
                lambda row:
                    _infer_dorm_from_row(
                        row,
                        allowed_dorms
                    ),
                axis=1,
            )

            if (
                inferred
                .astype(str)
                .str.strip()
                .ne("")
                .any()
            ):

                result["宿舍"] = inferred

                return result[
                    result["宿舍"].isin(
                        allowed_dorms
                    )
                ].copy()

        # -------------------------------------------------
        # 找不到
        # -------------------------------------------------

        st.warning(
            "目前補點資料沒有可辨識的宿舍資訊，"
            "因此無法安全依樓長權限篩選。"
            "請確認點名資料是否包含「宿舍」、"
            "「假日宿舍別」、「寒假宿舍別」"
            "或「暑假宿舍別」。"
        )

        return result.iloc[0:0].copy()

    # =====================================================
    # 其他角色
    # =====================================================

    st.warning(
        "目前帳號沒有補點名單權限"
    )

    return result.iloc[0:0].copy()


# =========================================================
# 顯示補點名單
# =========================================================

def show_makeup_rollcall():

    st.header("補點名單")

    st.caption(
        "00:00～05:59 顯示前一天資料；"
        "06:00 起切換當天資料，"
        "並每 15 秒自動刷新。"
    )

    # =====================================================
    # 手動重新整理
    # =====================================================

    if st.button(
        "重新整理補點名單",
        key="refresh_makeup"
    ):

        load_need_makeup_source.clear()

        st.rerun()

    # =====================================================
    # 性別權限
    # =====================================================

    allowed_genders = get_allowed_genders()

    if not allowed_genders:

        st.info(
            "您沒有補點權限"
        )

        return

    # =====================================================
    # 讀取男／女補點資料
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

    # =====================================================
    # 合併
    # =====================================================

    df = pd.concat(
        dfs,
        ignore_index=True
    )

    # =====================================================
    # 權限篩選
    # =====================================================

    df = filter_by_leader_scope(df)

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

        df = df[condition]

    # =====================================================
    # 查無資料
    # =====================================================

    if df.empty:

        st.info(
            "查無符合條件的補點名資料"
        )

        return

    # =====================================================
    # 顯示欄位
    # =====================================================

    show_cols = [
        c
        for c in [
            "床位",
            "學號",
            "班級",
            "姓名",
            "宿舍",
            "假日宿舍",
            "寒假宿舍",
            "暑假宿舍",
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

    # =====================================================
    # 補點完成
    # =====================================================

    st.divider()

    st.subheader(
        "補點完成"
    )

    # =====================================================
    # 建立學生選項
    # =====================================================

    options = []

    for i, row in df.iterrows():

        label = (
            f'{row.get("性別", "")}｜'
            f'{row.get("日期", "")}｜'
            f'{row.get("宿舍", "")}｜'
            f'{row.get("假日宿舍", "")}｜'
            f'{row.get("房號", "")}｜'
            f'{row.get("學號", "")}｜'
            f'{row.get("姓名", "")}'
        )

        options.append(
            (i, label)
        )

    # =====================================================
    # 下拉選單
    # =====================================================

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

    # =====================================================
    # 確認補點
    # =====================================================

    if st.button(
        "確認補點完成",
        key="submit_makeup"
    ):

        try:

            target_row = df.loc[
                selected_index
            ].to_dict()

            gender = target_row.get(
                "性別",
                ""
            )

            # -------------------------------------------------
            # 更新點名總表
            # -------------------------------------------------

            update_rollcall_status_to_makeup(
                gender,
                target_row
            )

            # -------------------------------------------------
            # 更新需補點名單
            # -------------------------------------------------

            update_need_makeup_status_to_done(
                gender,
                target_row
            )

            # -------------------------------------------------
            # 清除快取
            # -------------------------------------------------

            load_need_makeup_source.clear()

            st.success(
                "已將狀態更新為：已補點"
            )

            st.rerun()

        except Exception as e:

            st.error(
                f"更新失敗：{e}"
            )