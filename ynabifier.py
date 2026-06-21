#!/usr/bin/env python3
"""Convert DKB CSV export files to YNAB-compatible CSV files."""

import argparse
import csv
import logging
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Iterator, Optional


class AccountType(Enum):
    GIROKONTO = "Girokonto"
    VISA = "VISA"


YNAB_FIELDNAMES = ["Date", "Payee", "Category", "Memo", "Outflow", "Inflow"]
PAYPAL_PREFIX = "PayPal Europe S.a.r.l."
DEFAULT_EXPORT_SUFFIX = "-ynab.csv"
DEFAULT_DRY_RUN_LIMIT = 10
DKB_EXPORT_FILENAME_PATTERN = re.compile(
    r"^(?P<date>\d{2}-\d{2}-\d{4})_Umsatzliste_"
    r"(?P<account>Girokonto|VISA)_(?!.*-ynab\.csv$).+\.csv$",
    re.IGNORECASE,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Summary of a conversion run."""

    export_path: Path
    rows_written: int
    rows_skipped: int


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


def sniff_dkb_header(filename: str) -> Optional[list[str]]:
    """Return the header row for a DKB export if found."""
    with open(filename, mode="r", encoding="utf-8", newline="") as csvfile:
        for line in csvfile:
            if "Buchungsdatum" in line and "Wertstellung" in line:
                reader = csv.reader([line], delimiter=";")
                return next(reader)
    return None


def detect_account_type(filename: str) -> AccountType:
    """Detect account type based on the header fields."""
    header = sniff_dkb_header(filename)
    if not header:
        raise ValueError("Unable to detect account type: header row not found.")

    header_set = set(header)
    if {"Zahlungspflichtige*r", "Zahlungsempfänger*in", "Betrag (€)"} <= header_set:
        return AccountType.GIROKONTO
    if {"Beschreibung", "Betrag (EUR)"} <= header_set:
        return AccountType.VISA

    raise ValueError("Unable to detect account type from header columns.")


def resolve_input_file(path: str, latest: bool = False) -> Path:
    """Resolve a file path, or pick the latest matching DKB export when requested."""
    input_path = Path(path).expanduser()
    if not input_path.is_dir():
        return input_path
    if not latest:
        raise ValueError(
            f"{input_path} is a directory. "
            "Use --latest to select the newest DKB export automatically."
        )

    candidates: list[tuple[datetime, Path]] = []
    for child in input_path.iterdir():
        if not child.is_file():
            continue
        match = DKB_EXPORT_FILENAME_PATTERN.match(child.name)
        if not match:
            continue
        try:
            export_date = datetime.strptime(match.group("date"), "%d-%m-%Y")
        except ValueError:
            continue
        candidates.append((export_date, child))

    if not candidates:
        raise ValueError(
            f"No DKB export files matching the expected naming scheme found in {input_path}."
        )

    return max(candidates, key=lambda item: (item[0], item[1].name))[1]


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


def parse_dkb_date(date_str: str) -> Optional[date]:
    """Parse a DKB transaction date."""
    for fmt in ("%d.%m.%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def parse_since_date(date_str: str) -> date:
    """Parse a --since date."""
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError("Invalid --since date. Use YYYY-MM-DD, DD.MM.YYYY, or DD.MM.YY.")


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


def build_ynab_row(
    source_row: Dict[str, str], filetype: AccountType
) -> Optional[Dict[str, object]]:
    """Build a YNAB row from a DKB source row, or skip invalid amount rows."""
    date_value = convert_date_format(source_row.get("Wertstellung", "").strip())

    if filetype == AccountType.VISA:
        payee = normalize_text(source_row.get("Beschreibung", ""))
        memo = normalize_text(source_row.get("", ""))
        amount = parse_amount(source_row.get("Betrag (EUR)", ""))
        if amount is None:
            return None
        payee = normalize_text(normalize_payee(payee, memo))
        return build_row(date_value, payee, memo, amount)

    if filetype == AccountType.GIROKONTO:
        amount = parse_amount(source_row.get("Betrag (€)", ""))
        if amount is None:
            return None
        if amount > 0:
            payee = source_row.get("Zahlungspflichtige*r", "")
        else:
            payee = source_row.get("Zahlungsempfänger*in", "")
        memo = source_row.get("Verwendungszweck", "")
        payee = normalize_text(payee)
        memo = normalize_text(memo)
        payee = normalize_text(normalize_payee(payee, memo))
        return build_row(date_value, payee, memo, amount)

    raise ValueError(f"Unsupported account type: {filetype}")


def should_include_row(source_row: Dict[str, str], since: Optional[date]) -> bool:
    """Return whether a source row should be included after date filtering."""
    if since is None:
        return True
    transaction_date = parse_dkb_date(source_row.get("Wertstellung", "").strip())
    return bool(transaction_date and transaction_date >= since)


def validate_columns(fieldnames: Optional[list[str]], required: list[str]) -> None:
    """Ensure required columns exist in the CSV header."""
    if not fieldnames:
        raise ValueError("Missing CSV header row.")
    missing = [name for name in required if name not in fieldnames]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")


def get_required_columns(filetype: AccountType) -> list[str]:
    """Return required column names for a given account type."""
    if filetype == AccountType.VISA:
        return ["Wertstellung", "Beschreibung", "Betrag (EUR)"]
    if filetype == AccountType.GIROKONTO:
        return [
            "Wertstellung",
            "Zahlungspflichtige*r",
            "Zahlungsempfänger*in",
            "Verwendungszweck",
            "Betrag (€)",
        ]
    raise ValueError(f"Unsupported account type: {filetype}")


def get_default_export_path(source_path: Path) -> Path:
    """Return the default export path for a source file."""
    return source_path.with_name(f"{source_path.stem}{DEFAULT_EXPORT_SUFFIX}")


def resolve_output_path(
    source_path: Path, output: Optional[Path] = None, output_dir: Optional[Path] = None
) -> Path:
    """Resolve the output path from CLI output options."""
    if output and output_dir:
        raise ValueError("Use either --output or --output-dir, not both.")
    if output:
        return output.expanduser().resolve()
    if output_dir:
        directory = output_dir.expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{source_path.stem}{DEFAULT_EXPORT_SUFFIX}"
    return get_default_export_path(source_path)


def get_account_offset(filetype: AccountType) -> int:
    """Return the number of pre-header rows for the account type."""
    if filetype == AccountType.VISA:
        return 6
    if filetype == AccountType.GIROKONTO:
        return 4
    raise ValueError(f"Unsupported account type: {filetype}")


def convert_with_summary(
    filename: str,
    filetype: AccountType,
    output: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    since: Optional[date] = None,
) -> ConversionResult:
    """Convert the file given by filename and return a summary."""
    offset = get_account_offset(filetype)

    source_path = Path(filename).expanduser().resolve()
    export_path = resolve_output_path(source_path, output=output, output_dir=output_dir)
    rows_written = 0
    rows_skipped = 0

    with open_csv_reader(str(source_path), offset) as reader, open(
        export_path, mode="w", encoding="utf-8", newline=""
    ) as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=YNAB_FIELDNAMES)
        writer.writeheader()
        validate_columns(
            list(reader.fieldnames) if reader.fieldnames else None,
            get_required_columns(filetype),
        )

        for row in reader:
            if not should_include_row(row, since):
                rows_skipped += 1
                continue

            output_row = build_ynab_row(row, filetype)
            if output_row is None:
                rows_skipped += 1
                continue

            writer.writerow(output_row)
            rows_written += 1

    return ConversionResult(export_path, rows_written, rows_skipped)


def convert(
    filename: str, filetype: AccountType, output: Optional[Path] = None
) -> Path:
    """Convert the file given by filename according to the given type."""
    result = convert_with_summary(filename, filetype, output=output)
    return result.export_path


def preview(
    filename: str,
    filetype: AccountType,
    limit: int = DEFAULT_DRY_RUN_LIMIT,
    since: Optional[date] = None,
) -> ConversionResult:
    """Write a preview of the converted rows to stdout."""
    offset = get_account_offset(filetype)
    rows_written = 0
    rows_skipped = 0

    with open_csv_reader(filename, offset) as reader:
        validate_columns(
            list(reader.fieldnames) if reader.fieldnames else None,
            get_required_columns(filetype),
        )
        writer = csv.DictWriter(sys.stdout, fieldnames=YNAB_FIELDNAMES)
        writer.writeheader()
        for row in reader:
            if not should_include_row(row, since):
                rows_skipped += 1
                continue

            output_row = build_ynab_row(row, filetype)
            if output_row is None:
                rows_skipped += 1
                continue

            writer.writerow(output_row)
            rows_written += 1

            if rows_written >= limit:
                break

    return ConversionResult(Path(filename), rows_written, rows_skipped)


def main() -> None:
    """Convert .csv files into YNAB4 compatible .csv files."""
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTION] [FILE]...",
        description="Convert DKB CSV export files to YNAB4 compatible CSV files.",
    )

    parser.add_argument(
        "-v", "--version", action="version", version=f"{parser.prog} 0.1.0"
    )

    parser.add_argument(
        "account_type",
        nargs="?",
        type=AccountType,
        choices=list(AccountType),
        help="Account type (autodetected if omitted).",
    )
    parser.add_argument("file", help="Filename")
    parser.add_argument(
        "-o",
        "--output",
        help="Output filename (defaults to input name with -ynab.csv).",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory (defaults to the input file directory).",
    )
    parser.add_argument(
        "--since",
        help=(
            "Only export rows on or after this date "
            "(YYYY-MM-DD, DD.MM.YYYY, or DD.MM.YY)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print a preview to stdout instead of writing a file.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_DRY_RUN_LIMIT,
        help="Number of rows to print for --dry-run.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="If FILE is a directory, use the newest matching DKB export in it.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )

    args = parser.parse_args()

    try:
        logging.basicConfig(
            level=logging.DEBUG if args.verbose else logging.INFO,
            format="%(levelname)s: %(message)s",
        )
        input_file = resolve_input_file(args.file, latest=args.latest)
        LOGGER.debug("Input file: %s", input_file)
        if args.latest:
            print(f"Selected input: {input_file}", file=sys.stderr)

        filetype = args.account_type or detect_account_type(str(input_file))
        LOGGER.debug("Detected account type: %s", filetype.value)
        since = parse_since_date(args.since) if args.since else None

        if args.dry_run:
            if args.output or args.output_dir:
                raise ValueError(
                    "--output and --output-dir cannot be used with --dry-run."
                )
            result = preview(str(input_file), filetype, args.limit, since=since)
            print(
                f"Preview rows: {result.rows_written}; rows skipped: {result.rows_skipped}",
                file=sys.stderr,
            )
            return

        output = Path(args.output) if args.output else None
        output_dir = Path(args.output_dir) if args.output_dir else None
        result = convert_with_summary(
            str(input_file),
            filetype,
            output=output,
            output_dir=output_dir,
            since=since,
        )
        print(f"Exported: {result.export_path}")
        print(f"Rows written: {result.rows_written}")
        print(f"Rows skipped: {result.rows_skipped}")
        print(f"Account type: {filetype.value}")

    except FileNotFoundError as err:
        print(f"{sys.argv[0]}: {args.file}: {err.strerror}", file=sys.stderr)
        raise SystemExit(1) from err
    except IsADirectoryError as err:
        print(f"{sys.argv[0]}: {args.file}: {err.strerror}", file=sys.stderr)
        raise SystemExit(1) from err
    except ValueError as err:
        print(f"{sys.argv[0]}: {err}", file=sys.stderr)
        raise SystemExit(2) from err


if __name__ == "__main__":
    main()
