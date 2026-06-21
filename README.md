# dkb-to-ynab4

## Description
dkb-to-ynab4 is a small offline utility for converting DKB AG bank statement CSVs into legacy YNAB4-compatible CSV files. It supports DKB Girokonto and VISA exports, cleans up common DKB/PayPal memo formats, and converts German number and date formats for import into YNAB4.

If you need a general multi-bank converter or YNAB API import for modern web YNAB, consider [bank2ynab](https://github.com/bank2ynab/bank2ynab). This project intentionally focuses on DKB exports and the legacy YNAB4 desktop import workflow.

## Installation
Clone the repository and install dependencies:

```bash
git clone https://github.com/dirrgang/dkb-to-ynab4.git
cd dkb-to-ynab4
pip install -r requirements.txt
```

You can also install it as a local command:

```bash
pip install .
dkb-to-ynab4 <input-file.csv>
```

The older `ynabifier` command is still installed as a compatibility alias.

## Usage
Run `dkb-to-ynab4` with the file path. The account type is autodetected from the CSV header:

```bash
dkb-to-ynab4 <input-file.csv>
```

You can also pass the account type explicitly:

```bash
dkb-to-ynab4 Girokonto <input-file.csv>
dkb-to-ynab4 VISA <input-file.csv>
```

To convert the newest matching DKB export in a directory, use `--latest`:

```bash
dkb-to-ynab4 --latest ~/Downloads
```

The output file will be saved in the same directory with `-ynab.csv` appended to the original filename. To choose a different output directory:

```bash
dkb-to-ynab4 --latest ~/Downloads --output-dir ~/YNAB/imports
```

To export only rows on or after a given date:

```bash
dkb-to-ynab4 <input-file.csv> --since 2026-06-01
```

Supported `--since` formats are `YYYY-MM-DD`, `DD.MM.YYYY`, and `DD.MM.YY`.

By default, dkb-to-ynab4 uses DKB's `Buchungsdatum` as the YNAB transaction date. To use `Wertstellung` instead:

```bash
dkb-to-ynab4 <input-file.csv> --date-field Wertstellung
```

Preview the converted CSV without writing a file:

```bash
dkb-to-ynab4 --dry-run <input-file.csv>
```

When running directly from a source checkout without installing, use the Python module name:

```bash
python -m dkb_to_ynab4 <input-file.csv>
```

The installed command is named `dkb-to-ynab4`; the Python module uses underscores because Python module names cannot contain hyphens.

## Development
Run the test suite with:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## License
GPL-3.0 License - see LICENSE file.

## Contributing
Contributions are welcome. Please adhere to conventional coding standards.

## Authors and Acknowledgment
Developed by Dennis Irrgang. Thanks to all contributors.

## Contact
For questions or feedback, please open an issue on the GitHub repository.
