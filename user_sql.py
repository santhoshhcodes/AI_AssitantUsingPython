def get_today_sales():
    """Get today's sales data"""
    # In real implementation, this would query your database
    return {
        "total_sales": 120000,
        "orders": 10,
        "pending": 2
    }

def get_customer_outstanding(name):
    """Get customer outstanding amount"""
    # In real implementation, this would query your database
    return {
        "customer": name,
        "pending": 30000
    }

def get_stock_item(item):
    """Get stock quantity for an item"""
    # In real implementation, this would query your database
    return {
        "item": item,
        "qty": 250
    }