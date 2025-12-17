import re
from typing import Optional, Dict
from user_sql import get_today_sales, get_customer_outstanding, get_stock_item


def safe_dict_get(d: dict, key: str, default=None):
    try:
        return d.get(key, default) if d else default
    except:
        return default


def generate_reply(text: Optional[str], intent: Optional[Dict] = None) -> str:
    """
    Business-rule reply generator.
    Returns TEXT ONLY.
    Return empty string "" to allow LLM fallback.
    """

    t = (text or "").lower().strip()
    if not t:
        return "I could not hear anything. Please try again."

    # =====================================================
    # INTENT HANDLING (HIGH CONFIDENCE ONLY)
    # =====================================================
    if intent:
        name = safe_dict_get(intent, "intent")
        params = safe_dict_get(intent, "params") or {}
        confidence = safe_dict_get(intent, "confidence", 0.0)

        # low confidence → LLM
        if confidence < 0.70:
            return ""

        # -------------------------------------------------
        # ✅ TODAY SALES (NO DOWNLOAD, NO NAVIGATION)
        # -------------------------------------------------
        if name == "today_sales":
            try:
                sales = get_today_sales() or {}
                total = sales.get("total_sales", 0)
                orders = sales.get("orders", 0)
                pending = sales.get("pending", 0)

                return (
                    f"Today's sales are {total} rupees from {orders} orders. "
                    f"{pending} orders are pending."
                )
            except Exception as e:
                print(f"Today sales error: {e}")
                return "Unable to fetch today's sales. Please try again."

        # -------------------------------------------------
        # ✅ DOWNLOAD SALES REPORT (NAVIGATION ONLY)
        # -------------------------------------------------
        if name == "download_sales_report":
            return "Downloading today's sales report. Please wait."

        # -------------------------------------------------
        # OTHER INTENTS
        # -------------------------------------------------
        if name == "open_sales_screen":
            return "Opening the sales screen for you."

        if name == "check_task_status":
            return "Checking your task status for today."

        if name == "search_user":
            uid = safe_dict_get(params, "user_id")
            if uid:
                return f"Opening details for user {uid}."
            return ""

        if name == "stock_check":
            item = safe_dict_get(params, "item")
            if item:
                data = get_stock_item(item) or {}
                return f"We have {data.get('qty', 0)} units of {item} in stock."
            return "Which item do you want to check?"

        if name == "outstanding_check":
            cust = safe_dict_get(params, "customer_name")
            if cust:
                data = get_customer_outstanding(cust) or {}
                return f"{cust} has {data.get('pending', 0)} rupees outstanding."
            return "Which customer?"

        if name == "smalltalk":
            return "Hello! How can I help you today?"

        return ""

    # =====================================================
    # FALLBACK (NO INTENT MATCHED)
    # =====================================================

    # ❌ DO NOT auto-download here
    # Only informational sales
    if re.search(r"\b(today|today's)\b.*\b(sales)\b", t):
        try:
            s = get_today_sales() or {}
            return (
                f"Today's sales are {s.get('total_sales', 0)} rupees "
                f"from {s.get('orders', 0)} orders."
            )
        except:
            return "Unable to fetch today's sales."

    return ""
