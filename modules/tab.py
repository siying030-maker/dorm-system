def build_tabs(role, is_main):

    tab_names = []

    
    if role in ["舍監"]:
        tab_names += [
            "每日點名未到名單",
            "補點名單",
            "獎懲查詢",
            "密碼表"
        ]
    
    
    if role == "行政":
        tab_names += [
            "每日點名未到名單",
            "上學期門禁",
            "下學期門禁",
            "整潔比賽(檢視)",
            "獎懲查詢",
            "密碼表"
        ]

    if role == "樓長":
        tab_names += [
            "點名系統",
            "補點名單",
            "每日點名未到名單",
            "密碼表",
            "網路查詢",
            "離宿",
            "獎懲查詢"
        ]

        if is_main:
            tab_names += ["整潔比賽"]

    if role == "生輔工讀":
        tab_names = ["密碼表"]

    return list(dict.fromkeys(tab_names))