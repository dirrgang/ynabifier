#!/usr/bin/env python3
"""
Module Docstring
"""

__author__ = "Dennis Irrgang"
__version__ = "0.1.0"
__license__ = "AGPL-3.0"


import sys
import argparse
import csv
import os


def init_argparse() -> argparse.ArgumentParser:
    '''Initialises argparser for CLI use.'''
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTION] [FILE]...",

        description="Convert Anki cards from an .apkg deck into Obsidian compatible markdown files."
    )

    parser.add_argument(
        "-v", "--version", action="version",
        version=f"{parser.prog} {__version__}"
    )

    parser.add_argument('files', nargs='*')

    return parser


def open_file(filename: str, offset: int) -> csv.DictReader:
    '''Opens a CSV file and returns a DictReader'''
    csvfile = open(filename)
    dialect = csv.Sniffer().sniff(csvfile.read(1024))

    csvfile.seek(0)

    for _ in range(offset):
        csvfile.readline()

    return csv.DictReader(csvfile, dialect=dialect)


def convert(filename: str, type: str) -> None:
    '''Converts the file given by filename according to the given type. Exports to same directory'''

    reader = open_file(filename, 6)

    basename_without_ext = os.path.splitext(
        os.path.basename(os.path.abspath(filename)))[0]

    dirname = os.path.dirname(__file__)
    export_filename = f'{basename_without_ext}-ynab.csv'
    export_filename = os.path.join(
        dirname, export_filename)

    with open(export_filename, mode="w", encoding='utf-8') as csvfile:
        fieldnames = ["Date", "Payee", "Memo", "Amount"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            if type == "Girokonto":
                writer.writerow({'Date': row['Wertstellung'], 'Payee': row['Auftraggeber / Begünstigter'],
                                'Memo': row['Verwendungszweck'], 'Amount': row['Betrag (EUR)']})
            elif type == "VISA":
                writer.writerow({'Date': row['Wertstellung'], 'Payee': row['Beschreibung'],
                                'Memo': row[''], 'Amount': row['Betrag (EUR)']})


def main() -> None:
    """Converts .csv files into YNAB4 compatible .csv files.
    Parameters:
    None (passed through CLI, see argparse/help)
    Returns:
    None
   """

    parser = argparse.ArgumentParser(
        description='Convert CSVs to YNAB4 compatibility')

    parser.add_argument('account_type', metavar='type', type=str)
    parser.add_argument('file', metavar='file', help='Filename')

    args = parser.parse_args()

    try:
        convert(args.file, args.account_type)

    except (FileNotFoundError, IsADirectoryError) as err:

        print(f"{sys.argv[0]}: {args.file}: {err.strerror}", file=sys.stderr)


if __name__ == "__main__":
    main()
