# ynabifier

## Description
ynabifier is a Python utility for converting DKB AG bank statement CSVs into YNAB-compatible CSV files. It supports DKB Girokonto and VISA exports. The script converts German number and date formats and restructures the data for import into YNAB.

## Installation
Clone the repository and install dependencies:

```bash
git clone https://github.com/dirrgang/ynabifier.git
cd ynabifier
pip install -r requirements.txt
```

You can also install it as a local command:

```bash
pip install .
ynabifier <input-file.csv>
```

## Usage
Run `ynabifier.py` with the file path. The account type is autodetected from the CSV header:

```bash
python ynabifier.py <input-file.csv>
```

You can also pass the account type explicitly:

```bash
python ynabifier.py Girokonto <input-file.csv>
python ynabifier.py VISA <input-file.csv>
```

To convert the newest matching DKB export in a directory, use `--latest`:

```bash
python ynabifier.py --latest ~/Downloads
```

The output file will be saved in the same directory with `-ynab.csv` appended to the original filename. To choose a different output directory:

```bash
python ynabifier.py --latest ~/Downloads --output-dir ~/YNAB/imports
```

To export only rows on or after a given date:

```bash
python ynabifier.py <input-file.csv> --since 2026-06-01
```

Supported `--since` formats are `YYYY-MM-DD`, `DD.MM.YYYY`, and `DD.MM.YY`.

Preview the converted CSV without writing a file:

```bash
python ynabifier.py --dry-run <input-file.csv>
```

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
