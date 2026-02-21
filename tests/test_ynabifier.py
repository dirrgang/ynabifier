import unittest

from ynabifier import (
    build_row,
    convert_date_format,
    convert_german_to_american,
    extract_paypal_store,
    normalize_text,
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


if __name__ == "__main__":
    unittest.main()
