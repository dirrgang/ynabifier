import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ynabifier import (
    build_row,
    convert_date_format,
    convert_german_to_american,
    extract_paypal_store,
    normalize_text,
    resolve_input_file,
)


class TestYnabifierHelpers(unittest.TestCase):
    def test_convert_german_to_american(self) -> None:
        self.assertEqual(convert_german_to_american("1.234,56"), 1234.56)
        self.assertEqual(convert_german_to_american("-0,5"), -0.5)
        self.assertIsNone(convert_german_to_american("not a number"))

    def test_convert_date_format(self) -> None:
        self.assertEqual(convert_date_format("19.02.26"), "19/02/26")
        self.assertEqual(convert_date_format("19.02.2026"), "19/02/26")
        self.assertEqual(convert_date_format("19/02/26"), "19/02/26")

    def test_extract_paypal_store(self) -> None:
        memo = "foo, Ihr Einkauf bei Store Name, bar"
        self.assertEqual(extract_paypal_store(memo), "Store Name")
        self.assertEqual(extract_paypal_store(""), "")

    def test_normalize_text(self) -> None:
        self.assertEqual(normalize_text("Hello   World"), "Hello World")
        self.assertEqual(normalize_text("  A  B  "), "A B")

    def test_build_row(self) -> None:
        row = build_row("19/02/26", "Payee", "Memo", -12.5)
        self.assertEqual(row["Outflow"], "12.50")
        self.assertEqual(row["Inflow"], "")
        row = build_row("19/02/26", "Payee", "Memo", 12.5)
        self.assertEqual(row["Outflow"], "")
        self.assertEqual(row["Inflow"], "12.50")

    def test_resolve_input_file_picks_latest_matching_export(self) -> None:
        with TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            older = directory / "21-02-2026_Umsatzliste_Girokonto_DE51120300001015074436.csv"
            latest = directory / "21-06-2026_Umsatzliste_Girokonto_DE51120300001015074436.csv"
            ignored_output = (
                directory
                / "22-06-2026_Umsatzliste_Girokonto_DE51120300001015074436-ynab.csv"
            )
            for path in (older, latest, ignored_output):
                path.write_text("", encoding="utf-8")

            self.assertEqual(resolve_input_file(str(directory), latest=True), latest)

    def test_resolve_input_file_requires_matching_export_in_directory(self) -> None:
        with TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            (directory / "statement.csv").write_text("", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "No DKB export files"):
                resolve_input_file(str(directory), latest=True)

    def test_resolve_input_file_requires_latest_for_directory(self) -> None:
        with TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            export = directory / "21-06-2026_Umsatzliste_Girokonto_DE51120300001015074436.csv"
            export.write_text("", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Use --latest"):
                resolve_input_file(str(directory))


if __name__ == "__main__":
    unittest.main()
