import pdfplumber
import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from collections import Counter


@dataclass
class Transaction:
    date: str
    description: str
    debit: str
    credit: str
    balance: str


MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}


def parse_date(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    parts = raw.split()
    if len(parts) != 3:
        return ""
    month, day, year = parts
    m = MONTH_MAP.get(month)
    if not m:
        return ""
    return f"{year}-{m}-{day.zfill(2)}"


def parse_amount(raw: str) -> str:
    if not raw or not raw.strip():
        return ""
    cleaned = raw.replace("AUD", "").replace(",", "").strip()
    if not cleaned:
        return ""
    try:
        val = Decimal(cleaned)
        return str(val)
    except InvalidOperation:
        return ""


def extract_page_transactions(page) -> list[Transaction]:
    tables = page.extract_tables()
    transactions = []

    for table in tables:
        for row in table:
            if not row or len(row) < 5:
                continue

            date_raw = (row[0] or "").strip()
            details_raw = (row[1] or "").strip()
            credit_raw = (row[2] or "").strip()
            debit_raw = (row[3] or "").strip()
            balance_raw = (row[4] or "").strip()

            # Skip header/title rows
            if date_raw == "Date" or details_raw == "Details":
                continue
            if "AUD Account" in date_raw:
                continue
            # Skip summary table rows
            skip_keywords = [
                "Starting balance on", "Total deposits", "Total payouts",
                "Ending balance on", "Minimum", "Maximum",
            ]
            if any(kw in date_raw for kw in skip_keywords):
                continue

            # Handle Starting/Ending balance special rows
            if not date_raw and details_raw in ("Starting balance", "Ending balance"):
                balance = parse_amount(balance_raw)
                transactions.append(Transaction(
                    date="",
                    description=details_raw,
                    debit="",
                    credit="",
                    balance=balance,
                ))
                continue

            # Must have a valid date
            if not date_raw:
                continue

            date = parse_date(date_raw)
            if not date:
                continue

            description = " ".join(details_raw.split())
            credit = parse_amount(credit_raw)
            debit = parse_amount(debit_raw)
            balance = parse_amount(balance_raw)

            transactions.append(Transaction(
                date=date,
                description=description,
                debit=debit,
                credit=credit,
                balance=balance,
            ))

    return transactions


def validate_balances(transactions: list[Transaction]) -> list[str]:
    errors = []
    for i in range(1, len(transactions)):
        try:
            prev_bal = Decimal(transactions[i - 1].balance) if transactions[i - 1].balance else Decimal(0)
            cur_debit = Decimal(transactions[i].debit) if transactions[i].debit else Decimal(0)
            cur_credit = Decimal(transactions[i].credit) if transactions[i].credit else Decimal(0)
            actual_bal = Decimal(transactions[i].balance) if transactions[i].balance else Decimal(0)
            expected = prev_bal + cur_credit - cur_debit

            if abs(expected - actual_bal) > Decimal("0.015"):
                errors.append(
                    f"Row {i + 1}: {transactions[i].date} {transactions[i].description[:40]} "
                    f"expected={expected} actual={actual_bal}"
                )
        except (InvalidOperation, ValueError):
            continue
    return errors


def calculate_summary(transactions: list[Transaction]) -> dict:
    txn_rows = [t for t in transactions if t.description not in ("Starting balance", "Ending balance")]

    total_debits = sum(Decimal(t.debit) for t in txn_rows if t.debit)
    total_credits = sum(Decimal(t.credit) for t in txn_rows if t.credit)

    starting = next((t for t in transactions if t.description == "Starting balance"), None)
    ending = next((t for t in transactions if t.description == "Ending balance"), None)

    dates = [t.date for t in txn_rows if t.date]
    date_from = min(dates) if dates else ""
    date_to = max(dates) if dates else ""

    type_counts = Counter()
    for t in txn_rows:
        if t.description:
            ttype = t.description.split()[0]
            type_counts[ttype] += 1

    balance_errors = validate_balances(transactions)

    return {
        "total_transactions": len(txn_rows),
        "total_credits": str(total_credits),
        "total_debits": str(total_debits),
        "starting_balance": starting.balance if starting else "0.00",
        "ending_balance": ending.balance if ending else "",
        "date_range": {"from": date_from, "to": date_to},
        "balance_errors": len(balance_errors),
        "type_breakdown": dict(type_counts.most_common()),
    }


def write_csv(transactions: list[Transaction], output_path: Path) -> Path:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["Date", "Description", "Debit", "Credit", "Balance"])
        for t in transactions:
            writer.writerow([t.date, t.description, t.debit, t.credit, t.balance])
    return output_path
