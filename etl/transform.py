"""Loss-aware normalization and explicit analytical eligibility rules."""
import json

from .validate import number, parse_date, text

MONEY_SCALE = 1_000_000  # GBP millionths; avoids binary-floating-point monetary totals.
MAX_INTEGER = 2**63 - 1
BLOCKING_FLAGS = ("invalid_invoice_ids", "invalid_product_codes", "invalid_dates",
                  "invalid_quantities", "invalid_prices", "invalid_customer_ids")


def transform_record(sheet, row_number, row, payload, fingerprint, duplicate, flags):
    flags = dict(flags)
    reasons = ["quality:" + key for key in BLOCKING_FLAGS if flags[key]]
    # These are explicit scope exclusions, not necessarily bad source records.
    for key in ("zero_quantities", "negative_prices", "zero_prices"):
        if flags[key]:
            reasons.append("business:" + key)
    quantity = None if flags["invalid_quantities"] else int(number(row["Quantity"]))
    price = number(row["Price"])
    price_micros = amount = None
    if price is not None:
        scaled = price * MONEY_SCALE
        if scaled != scaled.to_integral_value() or abs(scaled) > MAX_INTEGER:
            reasons.append("quality:unsupported_price_precision_or_range")
        else:
            price_micros = int(scaled)
            if quantity is not None:
                amount = quantity * price_micros
                if abs(amount) > MAX_INTEGER:
                    reasons.append("quality:amount_overflow")
                    amount = None
    timestamp = parse_date(row["InvoiceDate"])
    invoice = text(row["Invoice"])
    normalized = (
        sheet, row_number, payload, fingerprint, int(duplicate),
        invoice.upper() if invoice else None, text(row["StockCode"]), text(row["Description"]),
        text(row["Customer ID"]), text(row["Country"]),
        timestamp.isoformat() if timestamp else None, quantity, price_micros, amount,
        int(flags["cancelled_transactions"]), json.dumps([k for k, v in flags.items() if v]),
        json.dumps(reasons), int(not reasons),
    )
    return normalized, reasons
