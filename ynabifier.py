#!/usr/bin/env python3
"""
Module Docstring.
"""

import argparse
import csv
import os
import sys
from enum import Enum


class AccountType(Enum):
    GIROKONTO = "Girokonto"
    VISA = "VISA"
    GIROKONTO_NEU = "Girokonto (Neu)"


def open_file(filename: str, offset: int) -> csv.DictReader:
    """Open a CSV file and return a DictReader."""
    csvfile = open(filename, mode="r", encoding="utf-8")

    dialect = csv.Sniffer().sniff(csvfile.read(1024))
    csvfile.seek(0)

    for _ in range(offset):
        csvfile.readline()

    return csv.DictReader(csvfile, dialect=dialect)


def convert_german_to_american(number_string):
    """Convert a number from German format to American format."""
    # Entfernen der deutschen Tausendertrennzeichen
    number_string = number_string.replace('.', '')
    # Konvertieren des deutschen Dezimaltrennzeichens in das amerikanische
    number_string = number_string.replace(',', '.')

    try:
        # Konvertieren in float und Zurückgeben des Werts
        return float(number_string)
    except ValueError:
        # Falls die Eingabe nicht in eine Zahl umgewandelt werden kann
        return None



def convert(filename: str, filetype: AccountType) -> None:
    """Convert the file given by filename according to the given type. Export to the same directory."""

    if filetype == AccountType.GIROKONTO or filetype == AccountType.VISA:
        reader = open_file(filename, 6)
    elif filetype == AccountType.GIROKONTO_NEU:
        reader = open_file(filename, 4)

    basename_without_ext = os.path.splitext(
        os.path.basename(os.path.abspath(filename))
    )[0]
    export_filename = f"{basename_without_ext}-ynab.csv"
    export_filename = os.path.join(os.path.dirname(filename), export_filename)

    with open(export_filename, mode="w", encoding="utf-8") as csvfile:
        fieldnames = ["Date", "Payee", "Memo", "Amount"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for row in reader:
            if filetype == AccountType.GIROKONTO:
                writer.writerow(
                    {
                        "Date": row["Wertstellung"],
                        "Payee": row["Auftraggeber / Begünstigter"],
                        "Memo": row["Verwendungszweck"],
                        "Amount": row["Betrag (EUR)"],
                    }
                )
            elif filetype == AccountType.VISA:
                writer.writerow(
                    {
                        "Date": row["Wertstellung"],
                        "Payee": row["Beschreibung"],
                        "Memo": row[""],
                        "Amount": row["Betrag (EUR)"],
                    }
                )
            elif filetype == AccountType.GIROKONTO_NEU:
                value = convert_german_to_american(row["Betrag (€)"])
                if value > 0:
                    writer.writerow(
                        {
                            "Date": row["Wertstellung"],
                            "Payee": row["Zahlungspflichtige*r"],
                            "Memo": row["Verwendungszweck"],
                            "Amount": value,
                        }
                    )
                else:
                    writer.writerow(
                        {
                            "Date": row["Wertstellung"],
                            "Payee": row["Zahlungsempfänger*in"],
                            "Memo": row["Verwendungszweck"],
                            "Amount": value,
                        }
                    )


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
        convert(args.file, args.account_type)

    except FileNotFoundError as err:
        print(f"{sys.argv[0]}: {args.file}: {err.strerror}", file=sys.stderr)
    except IsADirectoryError as err:
        print(f"{sys.argv[0]}: {args.file}: {err.strerror}", file=sys.stderr)


if __name__ == "__main__":
    main()
