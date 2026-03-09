import pdfplumber
import csv
import re
from dataclasses import dataclass
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

MONTH_FULL = {
    "January": "01", "February": "02", "March": "03", "April": "04",
    "May": "05", "June": "06", "July": "07", "August": "08",
    "September": "09", "October": "10", "November": "11", "December": "12",
}


def parse_amount_generic(raw: str) -> str:
    """Parse amount from various formats: '$1,234.56', '1234.56 AUD', '-1,000.00', etc."""
    if not raw or not raw.strip():
        return ""
    cleaned = raw.replace("AUD", "").replace("USD", "").replace("$", "").replace(",", "").strip()
    if not cleaned:
        return ""
    try:
        val = Decimal(cleaned)
        return str(abs(val))
    except InvalidOperation:
        return ""


def is_negative_amount(raw: str) -> bool:
    """Check if an amount string represents a negative value."""
    if not raw:
        return False
    cleaned = raw.replace(",", "").replace("$", "").strip()
    return cleaned.startswith("-") or cleaned.startswith("(")


# ---------------------------------------------------------------------------
# TABLE-BASED EXTRACTION (Airwallex and similar)
# ---------------------------------------------------------------------------

def parse_date_table(raw: str) -> str:
    """Parse 'Mon DD YYYY' format."""
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


def extract_page_transactions_table(page) -> list[Transaction]:
    """Extract transactions from table-based PDFs (e.g., Airwallex)."""
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

            if date_raw == "Date" or details_raw == "Details":
                continue
            if "AUD Account" in date_raw:
                continue
            skip_keywords = [
                "Starting balance on", "Total deposits", "Total payouts",
                "Ending balance on", "Minimum", "Maximum",
            ]
            if any(kw in date_raw for kw in skip_keywords):
                continue

            if not date_raw and details_raw in ("Starting balance", "Ending balance"):
                balance = parse_amount_generic(balance_raw)
                transactions.append(Transaction(
                    date="", description=details_raw,
                    debit="", credit="", balance=balance,
                ))
                continue

            if not date_raw:
                continue

            date = parse_date_table(date_raw)
            if not date:
                continue

            description = " ".join(details_raw.split())
            credit = parse_amount_generic(credit_raw)
            debit = parse_amount_generic(debit_raw)
            balance = parse_amount_generic(balance_raw)

            transactions.append(Transaction(
                date=date, description=description,
                debit=debit, credit=credit, balance=balance,
            ))

    return transactions


# ---------------------------------------------------------------------------
# TEXT-BASED EXTRACTION (Bank of America and similar)
# ---------------------------------------------------------------------------

# Matches lines like: 12/08/25 Counter Credit 11,700.00
# or: 12/09/25 Zelle payment to ALEX RAMIREZ Conf# ahgm82jjm -1,999.00
TEXT_TXN_PATTERN = re.compile(
    r"^(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+([\-\$]?[\d,]+\.\d{2})\s*$"
)

# Matches date formats: MM/DD/YY or MM/DD/YYYY
def parse_date_text(raw: str, year_hint: str = "") -> str:
    """Parse 'MM/DD/YY' or 'MM/DD/YYYY' format."""
    raw = raw.strip()
    parts = raw.split("/")
    if len(parts) != 3:
        return ""
    month, day, year = parts
    if len(year) == 2:
        year = f"20{year}"
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def extract_text_transactions(pdf) -> list[Transaction]:
    """Extract transactions from text-based PDFs (e.g., Bank of America)."""
    all_text = ""
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            all_text += text + "\n"

    transactions = []

    # Try to extract starting and ending balance from summary
    starting_match = re.search(
        r"[Bb]eginning balance.*?\$?([\d,]+\.\d{2})", all_text
    )
    ending_match = re.search(
        r"[Ee]nding balance.*?\$?([\d,]+\.\d{2})", all_text
    )

    if starting_match:
        transactions.append(Transaction(
            date="", description="Starting balance",
            debit="", credit="",
            balance=parse_amount_generic(starting_match.group(1)),
        ))

    # Detect sections: deposits/credits vs withdrawals/debits
    current_section = ""
    lines = all_text.split("\n")

    for line in lines:
        line_stripped = line.strip()
        lower = line_stripped.lower()

        # Detect section headers
        if "deposits and other credits" in lower or "deposits/credits" in lower:
            current_section = "credit"
            continue
        elif "withdrawals and other debits" in lower or "withdrawals/debits" in lower:
            current_section = "debit"
            continue
        elif "checks" in lower and ("paid" in lower or "date" in lower or "number" in lower):
            current_section = "debit"
            continue
        elif "daily ledger balance" in lower or "service fee summary" in lower:
            current_section = ""
            continue
        elif re.match(r"^total\s+", lower):
            continue

        # Try to match transaction lines
        match = TEXT_TXN_PATTERN.match(line_stripped)
        if match and current_section:
            date_raw = match.group(1)
            description = match.group(2).strip()
            amount_raw = match.group(3).strip()

            date = parse_date_text(date_raw)
            amount = parse_amount_generic(amount_raw)
            is_neg = is_negative_amount(amount_raw)

            if not date or not amount:
                continue

            # Determine debit vs credit
            if current_section == "credit" and not is_neg:
                transactions.append(Transaction(
                    date=date, description=description,
                    debit="", credit=amount, balance="",
                ))
            else:
                transactions.append(Transaction(
                    date=date, description=description,
                    debit=amount, credit="", balance="",
                ))

    if ending_match:
        transactions.append(Transaction(
            date="", description="Ending balance",
            debit="", credit="",
            balance=parse_amount_generic(ending_match.group(1)),
        ))

    # Try to compute running balances if we have starting balance
    if transactions and transactions[0].description == "Starting balance" and transactions[0].balance:
        running = Decimal(transactions[0].balance)
        for t in transactions[1:]:
            if t.description == "Ending balance":
                continue
            credit = Decimal(t.credit) if t.credit else Decimal(0)
            debit = Decimal(t.debit) if t.debit else Decimal(0)
            running = running + credit - debit
            t.balance = str(running)

    return transactions


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def extract_page_transactions(page) -> list[Transaction]:
    """Extract from a single page using table-based method."""
    return extract_page_transactions_table(page)


def detect_format(pdf) -> str:
    """Detect if PDF uses tables or text-based format."""
    # Check first few pages for tables
    for i in range(min(5, len(pdf.pages))):
        tables = pdf.pages[i].extract_tables()
        for table in tables:
            for row in table:
                if row and len(row) >= 5:
                    # Check if it looks like a transaction table
                    details = (row[1] or "").strip()
                    if details in ("Details",) or "Account Activity" in (row[0] or ""):
                        return "table"
    return "text"


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
            ttype = t.description.split()[0] if t.description.split() else "Other"
            type_counts[ttype] += 1

    balance_errors = validate_balances(transactions)

    return {
        "total_transactions": len(txn_rows),
        "total_credits": str(total_credits) if total_credits else "0",
        "total_debits": str(total_debits) if total_debits else "0",
        "starting_balance": starting.balance if starting and starting.balance else "0",
        "ending_balance": ending.balance if ending and ending.balance else "0",
        "date_range": {"from": date_from, "to": date_to},
        "balance_errors": len(balance_errors),
        "type_breakdown": dict(type_counts.most_common()) if type_counts else {"Transactions": len(txn_rows)},
    }


def write_csv(transactions: list[Transaction], output_path: Path) -> Path:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["Date", "Description", "Debit", "Credit", "Balance"])
        for t in transactions:
            writer.writerow([t.date, t.description, t.debit, t.credit, t.balance])
    return output_path
