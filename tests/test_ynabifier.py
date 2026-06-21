import os
import unittest
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
    format_permission_error,
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
            extract_paypal_store("foo, Ihr Einkauf bei Example Shop Ltd."),
            "Example Shop Ltd.",
        )
        self.assertEqual(
            extract_paypal_store(
                "1000000000000/PP.5621.PP/. PAYPAL-ZAHLUNG UBER LASTSCHRIFT "
                "an recipient.example"
            ),
            "recipient.example",
        )
        self.assertEqual(extract_paypal_store(""), "")

    def test_normalize_text(self) -> None:
        self.assertEqual(normalize_text("Hello   World"), "Hello World")
        self.assertEqual(normalize_text("  A  B  "), "A B")

    def test_clean_dkb_party_strips_padded_address(self) -> None:
        self.assertEqual(
            clean_dkb_party(
                "Example Marketplace S.a.r.l.                                         "
                "Example Street 1"
            ),
            "Example Marketplace S.a.r.l.",
        )

    def test_clean_dkb_party_keeps_ordinary_spacing(self) -> None:
        self.assertEqual(clean_dkb_party("Foo  Bar GmbH"), "Foo Bar GmbH")

    def test_normalize_transaction_details_for_paypal_purchase(self) -> None:
        payee, memo = normalize_transaction_details(
            "PayPal Europe S.a.r.l. et Cie S.C.A",
            "1000000000001/PP.5621.PP/. Example Store GmbH, "
            "Ihr Einkauf bei Example Store GmbH",
            -24.98,
        )

        self.assertEqual(payee, "Example Store GmbH")
        self.assertEqual(memo, "PayPal purchase, reference 1000000000001")

    def test_normalize_transaction_details_for_paypal_refund(self) -> None:
        payee, memo = normalize_transaction_details(
            "PayPal Europe S.a.r.l. et Cie S.C.A",
            ". Example Retail GmbH . Co. KG, Ihr Einkauf bei "
            "Example Retail GmbH . Co. KG/ABBUCHUNG VOM PAYPAL-KONTO "
            "AWV-MELDEPFLICHT BEACHTEN HOTLINE BUNDESBANK (0800) 1234-111",
            158.69,
        )

        self.assertEqual(payee, "Example Retail GmbH . Co. KG")
        self.assertEqual(memo, "PayPal refund/credit")

    def test_normalize_transaction_details_for_alternate_paypal_format(self) -> None:
        payee, memo = normalize_transaction_details(
            "PayPal (Europe) S.a r.l. et Cie, S.C.A.",
            "1000000000002 PP.5621.PP . Example Food UG (haftungsbeschrankt), "
            "Ihr Einkauf bei Example Food UG (haftungsbeschrankt)",
            -9.0,
            "1000000000002 PP.5621.PP PAYPAL",
        )

        self.assertEqual(payee, "Example Food UG (haftungsbeschrankt)")
        self.assertEqual(memo, "PayPal purchase, reference 1000000000002")

    def test_normalize_transaction_details_for_paypal_reference_without_memo(self) -> None:
        payee, memo = normalize_transaction_details(
            "PayPal (Europe) S.a r.l. et Cie, S.C.A.",
            "",
            -87.05,
            "1000000000003 PP.5621.PP PAYPAL",
        )

        self.assertEqual(payee, "PayPal (Europe) S.a r.l. et Cie, S.C.A.")
        self.assertEqual(memo, "PayPal purchase, reference 1000000000003")

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
                    "Example Marketplace S.a.r.l.                                         "
                    "Example Street 1"
                ),
                "Zahlungsempfänger*in": "Example Account Holder",
                "Verwendungszweck": "P.1000000000",
                "Betrag (€)": "61,81",
            },
            AccountType.GIROKONTO,
        )

        self.assertIsNotNone(row)
        self.assertEqual(row["Payee"], "Example Marketplace S.a.r.l.")

    def test_resolve_input_file_picks_latest_matching_export(self) -> None:
        with TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            older = directory / "21-02-2026_Umsatzliste_Girokonto_DE00000000000000000000.csv"
            latest = directory / "21-06-2026_Umsatzliste_Girokonto_DE00000000000000000000.csv"
            ignored_output = (
                directory
                / "22-06-2026_Umsatzliste_Girokonto_DE00000000000000000000-ynab.csv"
            )
            for path in (older, latest, ignored_output):
                path.write_text("", encoding="utf-8")

            self.assertEqual(resolve_input_file(str(directory), latest=True), latest)

    def test_resolve_input_file_uses_mtime_for_same_date_exports(self) -> None:
        with TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            original = (
                directory
                / "21-06-2026_Umsatzliste_Girokonto_DE00000000000000000000.csv"
            )
            duplicate = (
                directory
                / "21-06-2026_Umsatzliste_Girokonto_DE00000000000000000000 (1).csv"
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
            export = directory / "21-06-2026_Umsatzliste_Girokonto_DE00000000000000000000.csv"
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
            source = directory / "21-06-2026_Umsatzliste_Girokonto_DE00000000000000000000.csv"
            output_dir = directory / "ynab"

            self.assertEqual(
                resolve_output_path(source, output_dir=output_dir),
                output_dir.resolve()
                / "21-06-2026_Umsatzliste_Girokonto_DE00000000000000000000-ynab.csv",
            )
            self.assertTrue(output_dir.exists())

    def test_resolve_output_path_rejects_output_and_output_dir(self) -> None:
        with self.assertRaisesRegex(ValueError, "either --output or --output-dir"):
            resolve_output_path(
                Path("statement.csv"),
                output=Path("out.csv"),
                output_dir=Path("exports"),
            )

    def test_format_permission_error_mentions_open_file(self) -> None:
        err = PermissionError(13, "Permission denied", "statement-ynab.csv")

        self.assertEqual(
            format_permission_error(err),
            "statement-ynab.csv: permission denied. "
            "Close the file if it is open and try again.",
        )


if __name__ == "__main__":
    unittest.main()
