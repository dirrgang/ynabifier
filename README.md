# ynabifier

## Description
ynabifier is a Python utility for converting DKB AG bank statement CSVs into YNAB4 compatible CSV files. It supports different account types, including "Girokonto," "VISA," and "Girokonto (Neu)." The script processes the input CSV file, converting numeric formats from German to American standards and restructuring the data to fit YNAB4 requirements.

## Installation
Clone the repository and install dependencies:

```bash
git clone https://github.com/dirrgang/ynabifier.git
cd ynabifier
pip install -r requirements.txt
```

## Usage
Run `ynabifier.py` with the account type and the file path:

```bash
python ynabifier.py <AccountType> <input-file.csv>
```
Supported account types are GIROKONTO, VISA, and GIROKONTO_NEU. The output file will be saved in the same directory with '-ynab.csv' appended to the original filename.

## License
GPL-3.0 License - see LICENSE file.

## Contributing
Contributions are welcome. Please adhere to conventional coding standards.

## Authors and Acknowledgment
Developed by Dennis Irrgang. Thanks to all contributors.

## Contact
For questions or feedback, please open an issue on the GitHub repository.
