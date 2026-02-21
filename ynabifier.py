#!/usr/bin/env python3
"""Convert DKB CSV export files to YNAB-compatible CSV files."""

import argparse
import csv
import re
import sys
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional


class AccountType(Enum):
    GIROKONTO = "Girokonto"
    VISA = "VISA"


YNAB_FIELDNAMES = ["Date", "Payee", "Category", "Memo", "Outflow", "Inflow"]
PAYPAL_PREFIX = "PayPal Europe S.a.r.l."


@contextmanager
def open_csv_reader(filename: str, offset: int) -> Iterator[csv.DictReader]:
    """Open a CSV file and yield a DictReader that starts after an offset."""
    with open(filename, mode="r", encoding="utf-8", newline="") as csvfile:
        sample = csvfile.read(1024)
        csvfile.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";"

        for _ in range(offset):
            csvfile.readline()

        yield csv.DictReader(csvfile, dialect=dialect)


def convert_german_to_american(number_string: str) -> Optional[float]:
    """Convert a number from German format to a float."""
    cleaned = re.sub(r"[^\d,.\-]", "", number_string)
    cleaned = cleaned.replace(".", "").replace(",", ".")

    try:
        return float(cleaned)
    except ValueError:
        return None


def convert_date_format(date_str: str) -> str:
    """Convert date from common DKB formats to DD/MM/YY format."""
    for fmt in ("%d.%m.%y", "%d.%m.%Y"):
        try:
            date_obj = datetime.strptime(date_str, fmt)
            return date_obj.strftime("%d/%m/%y")
        except ValueError:
            continue
    return date_str


def extract_paypal_store(memo: str) -> str:
    """
    Extract the store name from a PayPal memo string.
    Looks for 'Ihr Einkauf bei <store>'.
    """
    if not memo:
        return ""
    match = re.search(r"Ihr Einkauf bei\s+(.+?)(?:,|$)", memo)
    if match:
        return match.group(1).strip()
    return ""


def normalize_text(value: str) -> str:
    """Trim and collapse internal whitespace."""
    return " ".join(value.split())


def normalize_payee(payee: str, memo: str) -> str:
    """Normalize PayPal payees to the store name if available."""
    if payee.strip().startswith(PAYPAL_PREFIX):
        store = extract_paypal_store(memo)
        if store:
            return store
    return payee


def parse_amount(amount: str) -> Optional[float]:
    """Parse amount from German-formatted number strings."""
    return convert_german_to_american(amount)


def format_amount(amount: float) -> str:
    """Format an amount with two decimal places."""
    return f"{amount:.2f}"


def build_row(date: str, payee: str, memo: str, amount: float) -> Dict[str, object]:
    """Build an output row for YNAB."""
    if amount > 0:
        outflow = ""
        inflow = format_amount(amount)
    elif amount < 0:
        outflow = format_amount(abs(amount))
        inflow = ""
    else:
        outflow = ""
        inflow = ""

    return {
        "Date": date,
        "Payee": payee,
        "Category": "",
        "Memo": memo,
        "Outflow": outflow,
        "Inflow": inflow,
    }


def convert(filename: str, filetype: AccountType) -> Path:
    """Convert the file given by filename according to the given type. Export to the same directory."""
    if filetype == AccountType.VISA:
        offset = 6
    elif filetype == AccountType.GIROKONTO:
        offset = 4
    else:
        raise ValueError(f"Unsupported account type: {filetype}")

    source_path = Path(filename).expanduser().resolve()
    export_path = source_path.with_name(f"{source_path.stem}-ynab.csv")

    with open_csv_reader(str(source_path), offset) as reader, open(
        export_path, mode="w", encoding="utf-8", newline=""
    ) as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=YNAB_FIELDNAMES)
        writer.writeheader()

        for row in reader:
            date = convert_date_format(row.get("Wertstellung", "").strip())

            if filetype == AccountType.VISA:
                payee = normalize_text(row.get("Beschreibung", ""))
                memo = normalize_text(row.get("", ""))
                amount = parse_amount(row.get("Betrag (EUR)", ""))
                if amount is None:
                    continue
                payee = normalize_text(normalize_payee(payee, memo))
                writer.writerow(build_row(date, payee, memo, amount))
            elif filetype == AccountType.GIROKONTO:
                amount = parse_amount(row.get("Betrag (€)", ""))
                if amount is None:
                    continue
                if amount > 0:
                    payee = row.get("Zahlungspflichtige*r", "")
                else:
                    payee = row.get("Zahlungsempfänger*in", "")
                memo = row.get("Verwendungszweck", "")
                payee = normalize_text(payee)
                memo = normalize_text(memo)
                payee = normalize_text(normalize_payee(payee, memo))
                writer.writerow(build_row(date, payee, memo, amount))

    return export_path


def main() -> None:
    """Convert .csv files into YNAB4 compatible .csv files."""
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTION] [FILE]...",
        description="Convert DKB CSV export files to YNAB4 compatible CSV files.",
    )

    parser.add_argument(
        "-v", "--version", action="version", version=f"{parser.prog} 0.1.0"
    )

    parser.add_argument("account_type", type=AccountType, choices=list(AccountType))
    parser.add_argument("file", help="Filename")

    args = parser.parse_args()

    try:
        export_path = convert(args.file, args.account_type)
        print(f"Exported: {export_path}")

    except FileNotFoundError as err:
        print(f"{sys.argv[0]}: {args.file}: {err.strerror}", file=sys.stderr)
        raise SystemExit(1) from err
    except IsADirectoryError as err:
        print(f"{sys.argv[0]}: {args.file}: {err.strerror}", file=sys.stderr)
        raise SystemExit(1) from err


if __name__ == "__main__":
    main()
