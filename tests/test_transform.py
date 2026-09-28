"""Synthetic structure tests; these fixtures make no claims about INE."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.data.transform import select_records, transform


class TransformTests(unittest.TestCase):
    def test_nested_envelope_selects_record_list(self):
        records = [{"synthetic_code": "001"}]
        payload = [{"metadata": "test", "nested": {"period": records}}]
        self.assertEqual(select_records(payload), (records, "/0/nested/period"))

    def test_multiple_lists_fail_with_candidate_paths(self):
        with self.assertRaisesRegex(ValueError, "/first.* /second|/first.*'/second"):
            select_records({"first": [{"a": 1}], "second": [{"b": 2}]})

    def test_explicit_pointer_handles_escaped_keys(self):
        records = [{"a": 1}]
        self.assertEqual(select_records({"a/b": {"~key": records}}, "/a~1b/~0key"), (records, "/a~1b/~0key"))

    def test_invalid_or_non_record_path_fails(self):
        for path in ("missing", "/missing", "/0/-1", "/0/key"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                select_records([{"key": 1}], path)

    def test_scalar_list_is_not_guessed_as_records(self):
        with self.assertRaises(ValueError):
            select_records([1, 2, 3])

    def test_empty_root_list_is_supported(self):
        self.assertEqual(select_records([]), ([], ""))

    def test_csv_and_explicit_semantic_summary_preserve_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "synthetic.json"
            payload = [{"code": "001", "period": "2024", "amount": 1, "detail": {"x": 1}},
                       {"code": "002", "period": "2024", "amount": None, "detail": None}]
            original = json.dumps(payload).encode()
            raw.write_bytes(original)
            output = io.StringIO()
            with redirect_stdout(output):
                path = transform(raw, root / "processed", municipality_column="code", year_column="period", value_column="amount")
            frame = pd.read_csv(path, dtype={"code": str})
            self.assertEqual(frame["code"].tolist(), ["001", "002"])
            self.assertEqual(json.loads(frame.loc[0, "detail"]), {"x": 1})
            self.assertEqual(raw.read_bytes(), original)
            self.assertIn("Total rows: 2", output.getvalue())
            self.assertIn("Unique municipalities (code, supplied mapping): 2", output.getvalue())
            self.assertIn("Years found (period, supplied mapping): ['2024']", output.getvalue())
            self.assertIn("Missing measurement values (amount): 1", output.getvalue())
            with self.assertRaises(FileExistsError):
                transform(raw, root / "processed")

    def test_unknown_semantic_column_does_not_write_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "synthetic.json"
            raw.write_text('[{"a": 1}]')
            with self.assertRaisesRegex(ValueError, "does not exist"):
                transform(raw, root / "processed", value_column="invented")
            self.assertFalse((root / "processed").exists())


if __name__ == "__main__":
    unittest.main()
