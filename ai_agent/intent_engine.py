import re
from typing import Optional, Dict


def detect_intent(text: str) -> Optional[Dict]:
    try:
        t = (text or "").lower().strip()
        if not t:
            return None
    except Exception:
        return None

    try:
        # ==================================================
        # 1️⃣ EXPLICIT DOWNLOAD SALES REPORT (ONLY)
        # ==================================================
        if re.search(r"\b(download|export|save)\b", t) and re.search(
            r"\b(sales|sales report|report)\b", t
        ):
            return {
                "intent": "download_sales_report",
                "params": {},
                "confidence": 0.95,
            }

        # ==================================================
        # 2️⃣ TODAY SALES (INFO ONLY – NO DOWNLOAD)
        # ==================================================
        if re.search(r"\b(today|todays|today's)\b", t) and re.search(
            r"\b(sales)\b", t
        ):
            return {
                "intent": "today_sales",
                "params": {},
                "confidence": 0.90,
            }

        # ==================================================
        # 3️⃣ OPEN SALES SCREEN (NO DOWNLOAD)
        # ==================================================
        if re.search(r"\b(open|go|show|display)\b", t) and re.search(
            r"\b(sales screen|sales page|sales)\b", t
        ):
            return {
                "intent": "open_sales_screen",
                "params": {},
                "confidence": 0.85,
            }

        # ==================================================
        # TASK STATUS
        # ==================================================
        if re.search(r"\b(task|work|job)\b", t) and re.search(
            r"\b(status|pending|done|complete|check)\b", t
        ):
            return {
                "intent": "check_task_status",
                "params": {},
                "confidence": 0.85,
            }

        # ==================================================
        # USER SEARCH
        # ==================================================
        m = re.search(r"\b(user|employee|emp|id)\s*[#:]?\s*(\d+)\b", t)
        if m:
            return {
                "intent": "search_user",
                "params": {"user_id": m.group(2)},
                "confidence": 0.9,
            }

        # ==================================================
        # OUTSTANDING CHECK
        # ==================================================
        if re.search(r"\b(outstanding|pending)\b", t):
            name = re.sub(
                r"\b(outstanding|pending|amount|check|for|of)\b",
                "",
                t,
            ).strip()

            return {
                "intent": "outstanding_check",
                "params": {"customer_name": name},
                "confidence": 0.85 if len(name) > 1 else 0.7,
            }

        # ==================================================
        # STOCK CHECK
        # ==================================================
        if re.search(r"\b(stock|available|inventory|qty|quantity)\b", t):
            item = re.sub(
                r"\b(stock|available|inventory|qty|quantity|check|get|how|much|show|have|for|of)\b",
                "",
                t,
            ).strip()

            return {
                "intent": "stock_check",
                "params": {"item": item},
                "confidence": 0.85 if len(item) > 1 else 0.7,
            }

        # ==================================================
        # GREETING
        # ==================================================
        if t in ("hi", "hello", "hey", "hello there", "hi there"):
            return {
                "intent": "smalltalk",
                "params": {},
                "confidence": 0.99,
            }

        return None

    except Exception:
        return None
