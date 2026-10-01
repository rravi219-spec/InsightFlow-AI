"""Explicit value validation; classification is separate from exclusion policy."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re


def text(value):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            number = Decimal(str(value))
            if number.is_finite() and number == number.to_integral_value():
                return str(int(number))
        except (InvalidOperation, ValueError):
            pass
    return str(value).strip() or None


def number(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def parse_date(value):
    if isinstance(value, datetime):
        return value if value.tzinfo is None else None
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.strip())
            return result if result.tzinfo is None else None
        except ValueError:
            return None
    # Do not guess Excel serial dates or ambiguous day/month text.
    return None


def classify(row):
    invoice = text(row["Invoice"])
    product = text(row["StockCode"])
    customer = text(row["Customer ID"])
    quantity = number(row["Quantity"])
    price = number(row["Price"])
    timestamp = parse_date(row["InvoiceDate"])
    flags = {
        "missing_customer_ids": customer is None,
        "invalid_customer_ids": customer is not None and not bool(re.fullmatch(r"\d+", customer)),
        "cancelled_transactions": bool(invoice and invoice.upper().startswith("C")),
        "invalid_invoice_ids": invoice is None or not bool(re.fullmatch(r"C?\d+", invoice.upper())),
        # Alphanumeric and special charge codes are valid business keys, not just digit-only SKUs.
        "invalid_product_codes": product is None,
        "invalid_dates": timestamp is None,
        "invalid_quantities": quantity is None or quantity != quantity.to_integral_value() or abs(quantity) > 2**31 - 1,
        "negative_quantities": quantity is not None and quantity < 0,
        "zero_quantities": quantity is not None and quantity == 0,
        "invalid_prices": price is None,
        "negative_prices": price is not None and price < 0,
        "zero_prices": price is not None and price == 0,
        "missing_descriptions": text(row["Description"]) is None,
        "missing_countries": text(row["Country"]) is None,
    }
    return flags
