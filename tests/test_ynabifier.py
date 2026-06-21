import unittest
import os
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from ynabifier import (
    AccountType,
    build_ynab_row,
    build_row,
    clean_dkb_party,
    convert_date_format,
    convert_german_to_american,
    extract_paypal_store,
    normalize_text,
    normalize_transaction_details,
    parse_since_date,
    resolve_input_file,
    resolve_output_path,
    should_include_row,
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
        refund_memo = "foo, Ihr Einkauf bei Store Name/ABBUCHUNG VOM PAYPAL-KONTO"
        self.assertEqual(extract_paypal_store(refund_memo), "Store Name")
        self.assertEqual(
            extract_paypal_store("foo, Ihr Einkauf bei Alza.cz a.s."),
            "Alza.cz a.s.",
        )
        self.assertEqual(extract_paypal_store(""), "")

    def test_normalize_text(self) -> None:
        self.assertEqual(normalize_text("Hello   World"), "Hello World")
        self.assertEqual(normalize_text("  A  B  "), "A B")

    def test_clean_dkb_party_strips_padded_address(self) -> None:
        self.assertEqual(
            clean_dkb_party(
                "eBay S.a.r.l.                                                         "
                "22-24, Boulevard Royal"
            ),
            "eBay S.a.r.l.",
        )

    def test_normalize_transaction_details_for_paypal_purchase(self) -> None:
        payee, memo = normalize_transaction_details(
            "PayPal Europe S.a.r.l. et Cie S.C.A",
            "1048330207269/PP.5621.PP/. bc GmbH, Ihr Einkauf bei bc GmbH",
            -24.98,
        )

        self.assertEqual(payee, "bc GmbH")
        self.assertEqual(memo, "PayPal purchase, reference 1048330207269")

    def test_normalize_transaction_details_for_paypal_refund(self) -> None:
        payee, memo = normalize_transaction_details(
            "PayPal Europe S.a.r.l. et Cie S.C.A",
            ". IKEA Deutschland GmbH . Co. KG, Ihr Einkauf bei "
            "IKEA Deutschland GmbH . Co. KG/ABBUCHUNG VOM PAYPAL-KONTO "
            "AWV-MELDEPFLICHT BEACHTEN HOTLINE BUNDESBANK (0800) 1234-111",
            158.69,
        )

        self.assertEqual(payee, "IKEA Deutschland GmbH . Co. KG")
        self.assertEqual(memo, "PayPal refund/credit")

    def test_build_row(self) -> None:
        row = build_row("19/02/26", "Payee", "Memo", -12.5)
        self.assertEqual(row["Outflow"], "12.50")
        self.assertEqual(row["Inflow"], "")
        row = build_row("19/02/26", "Payee", "Memo", 12.5)
        self.assertEqual(row["Outflow"], "")
        self.assertEqual(row["Inflow"], "12.50")

    def test_build_ynab_row_strips_girokonto_payee_address(self) -> None:
        row = build_ynab_row(
            {
                "Wertstellung": "19.02.26",
                "Zahlungspflichtige*r": (
                    "eBay S.a.r.l.                                                         "
                    "22-24, Boulevard Royal"
                ),
                "Zahlungsempfänger*in": "Dennis Irrgang",
                "Verwendungszweck": "P.7354160884",
                "Betrag (€)": "61,81",
            },
            AccountType.GIROKONTO,
        )

        self.assertIsNotNone(row)
        self.assertEqual(row["Payee"], "eBay S.a.r.l.")

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

    def test_resolve_input_file_uses_mtime_for_same_date_exports(self) -> None:
        with TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            original = (
                directory
                / "21-06-2026_Umsatzliste_Girokonto_DE51120300001015074436.csv"
            )
            duplicate = (
                directory
                / "21-06-2026_Umsatzliste_Girokonto_DE51120300001015074436 (1).csv"
            )
            original.write_text("", encoding="utf-8")
            duplicate.write_text("", encoding="utf-8")
            os.utime(original, (1000, 1000))
            os.utime(duplicate, (2000, 2000))

            self.assertEqual(resolve_input_file(str(directory), latest=True), duplicate)

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

    def test_parse_since_date_accepts_supported_formats(self) -> None:
        self.assertEqual(parse_since_date("2026-06-21"), date(2026, 6, 21))
        self.assertEqual(parse_since_date("21.06.2026"), date(2026, 6, 21))
        self.assertEqual(parse_since_date("21.06.26"), date(2026, 6, 21))

    def test_parse_since_date_rejects_invalid_format(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid --since date"):
            parse_since_date("06/21/2026")

    def test_should_include_row_filters_by_since_date(self) -> None:
        since = date(2026, 6, 21)

        self.assertTrue(should_include_row({"Wertstellung": "21.06.2026"}, since))
        self.assertTrue(should_include_row({"Wertstellung": "22.06.2026"}, since))
        self.assertFalse(should_include_row({"Wertstellung": "20.06.2026"}, since))
        self.assertFalse(should_include_row({"Wertstellung": "not a date"}, since))

    def test_resolve_output_path_uses_output_dir(self) -> None:
        with TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            source = directory / "21-06-2026_Umsatzliste_Girokonto_DE51120300001015074436.csv"
            output_dir = directory / "ynab"

            self.assertEqual(
                resolve_output_path(source, output_dir=output_dir),
                output_dir.resolve()
                / "21-06-2026_Umsatzliste_Girokonto_DE51120300001015074436-ynab.csv",
            )
            self.assertTrue(output_dir.exists())

    def test_resolve_output_path_rejects_output_and_output_dir(self) -> None:
        with self.assertRaisesRegex(ValueError, "either --output or --output-dir"):
            resolve_output_path(
                Path("statement.csv"),
                output=Path("out.csv"),
                output_dir=Path("exports"),
            )


if __name__ == "__main__":
    unittest.main()
