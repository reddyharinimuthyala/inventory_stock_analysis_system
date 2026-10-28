"""Small unit tests for the stock calculation rules.

Run with: python -m unittest discover -s tests
These tests don't need a live MySQL database.
"""
import unittest


def calculate_stock(opening, incoming, outgoing):
    if min(opening, incoming, outgoing) < 0:
        raise ValueError("Stock quantities cannot be negative.")
    result = opening + incoming - outgoing
    if result < 0:
        raise ValueError("Stock cannot become negative.")
    return result


class StockLogicTests(unittest.TestCase):
    def test_opening_stock_only(self):
        self.assertEqual(calculate_stock(10, 0, 0), 10)

    def test_stock_in_and_out(self):
        self.assertEqual(calculate_stock(10, 7, 4), 13)

    def test_reject_negative_result(self):
        with self.assertRaises(ValueError):
            calculate_stock(5, 0, 6)

    def test_reject_negative_quantity(self):
        with self.assertRaises(ValueError):
            calculate_stock(5, -1, 0)


if __name__ == "__main__":
    unittest.main()
