# =========================================
# 點名系統（完整最終版）
# =========================================

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date

# =========================================
# Google 認證
# =========================================

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)

gc = gspread.authorize(creds)

# =========================================
# 學期點名表
# =========================================

ATTENDANCE_SHEETS = {

    "上學期": {
        "女一": "https://docs.google.com/spreadsheets/d/1U9bdg8CWASheYE7XxLt5p-otLDxKiotju4s72Car9rk/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1jNbe--UINl7NS6dpBU82AZJuT6wQ9VwVAlglyG7infQ/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1Vrst2-bqPE7flCIXeAI-lyN51Os9QwStx388DWx11w8/edit",
        "男一": "https://docs.google.com/spreadsheets/d/1S2axgu2BWP8HnEs0RJdDcccdD1bvPdH26qrx3c4DeWo/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1RcRTslmv4s_C_7AH-WuqtLrty9l0A7YECvaGJETnpis/edit",
    },

    "下學期": {
        "女一": "https://docs.google.com/spreadsheets/d/1Nf7U106SxRZUu1pb35Fu2xrN2BTV80lit43BcgE6GnA/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1NVt6M8SVc64zmRmxh268NlZqzT3JLpcGwuRBlkCe8oE/edit",
        "女三": "https://docs.google.com/spreadsheets/d/1y2YB118Xg2Mq8w6NeabTXgZ-n1gN56kCalyJ5KlMk1I/edit",
        "男一": "https://docs.google.com/spreadsheets/d/1JSJx0cLdUxfIeYoe6dldeBe3Xeewm3uuIYrJkeYi_A8/edit",
        "男三": "https://docs.google.com/spreadsheets/d/1KpqeWBWIR0g6RxZ_oFUFXbn34PbH7r18UI9NBsfWIPY/edit",
    }
}

# =========================================
# 寒假 / 暑假
# =========================================

VACATION_SHEETS = {

    "寒假": {
        "女一": "https://docs.google.com/spreadsheets/d/1svJOTt-BQmws2Xsy2e3mrHrsqZAi_GD1rYX4t2LxE6Y/edit",
        "女二": "https://docs.google.com/spreadsheets/d/17TqcEpi_6O-qsO5ZFl17GvO91yU2LgmN36sjO_Zbbi8/edit",
        "男一": "https://docs.google.com/spreadsheets/d/1xX2DBG8z5jGSthFdnLqsn5yhz-8JmLmTK_7VUVqHGmo/edit",
    },

    "暑假": {
        "女一": "https://docs.google.com/spreadsheets/d/1kxfciu8TMwnQuwzA94H0c6cY3ClgRuRijzYwM4qEtt8/edit",
        "女二": "https://docs.google.com/spreadsheets/d/1cXDLQM5F3lWwBlM_KRn1dhGfOviLfcJmAFiXBxp36u8/edit",
        "男一": "https://docs.google.com/spreadsheets/d/1WpBP8lCWUdTm-SAIIplFOGdpBjv5vLsuCXb8tDCXx9Y/edit",
    }
}

# =========================================
# 宿舍判斷
# =========================================

DORM_GENDER = {
    "女一": "女生",
    "女二": "女生",
    "女三": "女生",
    "男一": "男生",
    "男三": "男生",
}

# =========================================
# 工具
# =========================================

def extract_sheet_id(url):
    return url.split("/d/")[1].split("/")[0]


def normalize_dorm(dorm):
    return dorm.replace("宿", "")


def get_attendance_url(term, dorm):

    dorm = normalize_dorm(dorm)

    if term in ["上學期", "下學期"]:
        return ATTENDANCE_SHEETS[term].get(dorm, "")

    if term in ["寒假", "暑假"]:
        return VACATION_SHEETS[term].get(dorm, "")

    return ""


def get_login_dorm():

    if "dorm" in st.session_state:
        return st.session_state["dorm"]

    return "女一"


def get_floor_options(dorm):

    if dorm == "女一":
        return ["1F", "2F", "3F", "5F", "6F", "7F"]

    if dorm == "女二":
        return ["0F", "1F", "2F", "3F", "4F", "5F"]

    if dorm == "女三":
        return ["3F", "4F", "5F", "6F"]

    if dorm == "男一":
        return ["0F", "1F", "2F", "3F"]

    if dorm == "男三":
        return ["3F", "4F", "5F"]

    return []


def build_sheet_name(dorm, floor):

    mapping = {
        "女一": "81",
        "女二": "82",
        "女三": "83",
        "男一": "82",
        "男三": "83",
    }

    code = mapping.get(dorm, "")

    return f"{code}-{floor}"


# =========================================
# 讀取一般學期資料
# =========================================

def load_normal_sheet(ws):

    values = ws.get_all_values()

    if len(values) < 2:
        return pd.DataFrame()

    headers = values[0]
    data = values[1:]

    df = pd.DataFrame(data, columns=headers)

    room_col = None
    student_col = None
    name_col = None

    for c in df.columns:

        if "床位" in c or "房號" in c:
            room_col = c

        if "學號" in c:
            student_col = c

        if "姓名" in c:
            name_col = c

    if not room_col or not name_col:
        return pd.DataFrame()

    result = pd.DataFrame()

    result["房號"] = df[room_col].astype(str).str.extract(r"(\d{5})")

    if student_col:
        result["學號"] = df[student_col]

    else:
        result["學號"] = ""

    result["姓名"] = df[name_col]

    result = result[
        result["姓名"].astype(str).str.strip() != ""
    ]

    return result.reset_index(drop=True)


# =========================================
# 讀取寒暑假資料
# =========================================

def load_vacation_sheet(ws):

    values = ws.get_all_values()

    if len(values) < 2:
        return pd.DataFrame()

    headers = values[0]
    data = values[1:]

    df = pd.DataFrame(data, columns=headers)

    room_col = None
    student_col = None
    name_col = None

    for c in df.columns:

        if c == "房號":
            room_col = c

        if "學號" in c:
            student_col = c

        if "姓名" in c:
            name_col = c

    if not room_col or not name_col:
        return pd.DataFrame()

    result = pd.DataFrame()

    result["房號"] = df[room_col]

    if student_col:
        result["學號"] = df[student_col]
    else:
        result["學號"] = ""

    result["姓名"] = df[name_col]

    result = result[
        result["姓名"].astype(str).str.strip() != ""
    ]

    return result.reset_index(drop=True)

# =========================================
# UI
# =========================================

st.title("點名系統")

term = st.selectbox(
    "點名類型",
    ["上學期", "下學期", "寒假", "暑假"]
)

dorm_options = ["女一", "女二", "女三", "男一", "男三"]

# 寒暑假限制
if term in ["寒假", "暑假"]:

    dorm_options = [
        d for d in dorm_options
        if d in VACATION_SHEETS[term]
    ]

dorm = st.selectbox(
    "宿舍",
    dorm_options
)

gender = DORM_GENDER[dorm]

st.text_input(
    "性別",
    value=gender,
    disabled=True
)

floor = st.selectbox(
    "樓層",
    get_floor_options(dorm)
)

attendance_date = st.date_input(
    "點名日期",
    value=date.today()
)

sheet_name = build_sheet_name(dorm, floor)

st.info(f"將讀取 Sheet：{sheet_name}")

# =========================================
# 載入點名名單
# =========================================

if st.button("載入點名名單"):

    try:

        url = get_attendance_url(term, dorm)

        if not url:
            st.error("找不到宿舍對應試算表")
            st.stop()

        sheet_id = extract_sheet_id(url)

        sh = gc.open_by_key(sheet_id)

        ws = sh.worksheet(sheet_name)

        # 寒暑假
        if term in ["寒假", "暑假"]:
            df = load_vacation_sheet(ws)

        # 一般學期
        else:
            df = load_normal_sheet(ws)

        if df.empty:
            st.warning("查無學生資料")
            st.stop()

        st.success(f"成功載入 {len(df)} 筆資料")

        st.dataframe(
            df,
            use_container_width=True
        )

    except Exception as e:

        st.error(f"""
查無學生資料，請確認：

1. 試算表有分享給 service account
2. Sheet 名稱正確
3. 資料欄位包含：
   房號 / 學號 / 姓名

錯誤：
{e}
""")