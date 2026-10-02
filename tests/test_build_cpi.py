"""Tests for the annual Portuguese CPI reference builder."""

import json
from pathlib import Path
import tempfile
import unittest

from src.data.build_cpi import (
    ANNUAL_PATTERN,
    INDICATOR,
    METADATA_FILE,
    YEARS,
    build_cpi_reference,
)


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class CpiBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.raw_dir = Path(self.temp_dir.name)
        metadata = [
            {
                "IndicadorCod": INDICATOR,
                "Periodic": "Anual",
                "PrimeiroPeriodo": "1948",
                "UltimoPeriodo": "2025",
                "Sucesso": {"Verdadeiro": [{"Msg": "OK"}]},
            }
        ]
        _write(self.raw_dir / METADATA_FILE, metadata)
        values = [84.825, 91.469, 95.412, 97.717, 100.0]
        for year, value in zip(YEARS, values, strict=True):
            payload = [
                {
                    "IndicadorCod": INDICATOR,
                    "Dados": {
                        str(year): [
                            {
                                "geocod": "1",
                                "geodsg": "Continente",
                                "dim_3": "T",
                                "dim_3_t": "Total",
                                "valor": str(value),
                            },
                            {
                                "geocod": "PT",
                                "geodsg": "Portugal",
                                "dim_3": "T",
                                "dim_3_t": "Total",
                                "valor": str(value),
                            },
                        ]
                    },
                    "Sucesso": {"Verdadeiro": [{"Msg": "OK"}]},
                }
            ]
            _write(self.raw_dir / ANNUAL_PATTERN.format(year=year), payload)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_builds_one_row_per_year_and_2025_factors(self):
        result = build_cpi_reference(self.raw_dir)
        self.assertEqual(result["year"].tolist(), YEARS)
        self.assertEqual(result["cpi_index_2025_base"].tolist(), [84.825, 91.469, 95.412, 97.717, 100.0])
        self.assertAlmostEqual(result.iloc[0]["inflation_adjustment_to_2025"], 100 / 84.825)
        self.assertEqual(result.iloc[-1]["inflation_adjustment_to_2025"], 1.0)

    def test_rejects_missing_portugal_total(self):
        path = self.raw_dir / ANNUAL_PATTERN.format(year=2023)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload[0]["Dados"]["2023"][1]["dim_3"] = "001"
        _write(path, payload)
        with self.assertRaisesRegex(ValueError, "one Portugal-total"):
            build_cpi_reference(self.raw_dir)


class CpiIntegrationTests(unittest.TestCase):
    raw_dir = Path(__file__).resolve().parents[1] / "data" / "raw"

    @unittest.skipUnless(
        (raw_dir / METADATA_FILE).exists(), "CPI raw snapshots not present"
    )
    def test_current_official_snapshot(self):
        result = build_cpi_reference(self.raw_dir)
        self.assertEqual(len(result), 5)
        self.assertEqual(result.loc[result["year"].eq(2025), "cpi_index_2025_base"].iloc[0], 100)
        self.assertTrue(result["cpi_index_2025_base"].is_monotonic_increasing)


if __name__ == "__main__":
    unittest.main()
