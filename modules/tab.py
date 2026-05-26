def build_tabs(role, is_main):

    tab_names = []

    if role in ["舍監", "行政"]:
        tab_names += [
            "連三天不假外宿",
            "每日缺席名單"
        ]

    if role == "行政":
        tab_names += [
            "上學期門禁",
            "下學期門禁",
            "整潔比賽(檢視)"
        ]

    if role == "樓長":
        tab_names += [
            "點名系統",
            "每日缺席名單"
        ]

        if is_main:
            tab_names += ["整潔比賽"]

    return list(dict.fromkeys(tab_names))