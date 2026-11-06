"""Regression tests for CSV handling, scoring, trends, and dashboard rendering."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from matplotlib.image import imread
import pandas as pd

from obd_predictive.obd_analysis import (
    LogAnalysis,
    analyze_log,
    estimate_trends,
    health_summary,
    load_log,
    match_columns,
)
from obd_predictive.obd_dashboard import render_dashboard


class OBDAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_csv(self, name: str, contents: str) -> Path:
        path = self.root / name
        path.write_text(contents, encoding="utf-8")
        return path

    def test_matches_common_app_export_headers(self) -> None:
        matched, _ = match_columns([
            "Engine RPM(rpm)",
            "Engine Coolant Temperature(°C)",
            "Control module voltage(V)",
            "Short Term Fuel Trim Bank 1(%)",
            "Long Term Fuel Trim Bank 1(%)",
            "Engine Load(%)",
        ])
        self.assertEqual(
            set(matched),
            {"rpm", "coolant_c", "voltage_v", "stft_pct", "ltft_pct", "load_pct"},
        )

    def test_converts_fahrenheit_and_parses_semicolon_csv(self) -> None:
        path = self.write_csv("coolant.csv", "Coolant Temp (°F);RPM\n32;700\n212;800\n")
        log = load_log(path)
        self.assertEqual(log.frame["coolant_c"].tolist(), [0.0, 100.0])
        self.assertEqual(log.frame["rpm"].tolist(), [700, 800])

    def test_unsupported_columns_are_reported_without_scoring(self) -> None:
        path = self.write_csv("unsupported.csv", "latitude,comment\n51.5,unknown\n")
        log = analyze_log(path)
        self.assertEqual(log.scores, {})
        self.assertTrue(any("No supported sensor columns" in note for note in log.warnings))
        self.assertIsNotNone(log.anomalies)
        score, _ = health_summary(log)
        self.assertIsNone(score)

    def test_health_summary_labels_and_unscored_message(self) -> None:
        for value, label in ((85, "GOOD"), (84, "FAIR"), (65, "FAIR"), (64, "POOR")):
            log = LogAnalysis(self.root / "scored.csv", pd.DataFrame(), {}, scores={"system": value})
            self.assertEqual(health_summary(log), (value, label))

        log = LogAnalysis(self.root / "unscored.csv", pd.DataFrame(), {})
        self.assertEqual(health_summary(log), (None, "Not scored (no supported sensor data)"))

    def test_bundled_logs_have_trends_and_expected_latest_score(self) -> None:
        sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample"
        logs = [analyze_log(sample_dir / f"session_{number}.csv") for number in range(1, 6)]
        trends = "\n".join(estimate_trends(logs, 30))

        self.assertIn("Coolant peak", trends)
        self.assertIn("Running voltage", trends)
        self.assertIn("Fuel trim", trends)
        self.assertEqual(health_summary(logs[-1]), (85, "GOOD"))

    def test_synthetic_csv_is_marked_as_demo_data(self) -> None:
        path = self.write_csv(
            "sample.csv",
            "RPM,Data Type\n750,SYNTHETIC DEMONSTRATION - NOT REAL VEHICLE DATA\n",
        )
        log = load_log(path)
        self.assertTrue(log.synthetic)
        self.assertNotIn("Data Type", " ".join(log.warnings))

    def test_three_dated_logs_produce_trend_projection(self) -> None:
        logs = [
            analyze_log(self.write_csv(f"2026-01-0{day}.csv", f"Coolant Temperature (°C)\n{value}\n"))
            for day, value in ((1, 80), (2, 85), (3, 90))
        ]
        trend = "\n".join(estimate_trends(logs, None))
        self.assertIn("Coolant peak", trend)
        self.assertIn("about", trend)

    def test_fewer_than_three_logs_omit_projections(self) -> None:
        logs = [
            analyze_log(self.write_csv(f"coolant-{index}.csv", "Coolant Temperature (°C)\n85\n"))
            for index in range(2)
        ]
        self.assertEqual(
            estimate_trends(logs, 30),
            ["Life estimates omitted: at least three logs are required."],
        )

    def test_unavailable_idle_analysis_is_not_scored(self) -> None:
        path = self.write_csv(
            "moving.csv",
            "RPM,Vehicle Speed\n" + "".join("2000,60\n" for _ in range(12)),
        )
        log = analyze_log(path)
        self.assertNotIn("Engine / Idle", log.scores)
        self.assertNotIn("idle_rpm_median", log.metrics)
        self.assertTrue(any("Idle behavior was not scored" in warning for warning in log.warnings))

    def test_fuel_trim_values_are_combined_not_averaged(self) -> None:
        path = self.write_csv(
            "fuel-trim.csv",
            "STFT,LTFT\n" + "".join("30,0\n" for _ in range(12)),
        )
        log = analyze_log(path)
        fuel_findings = [finding for finding in log.findings if finding.system == "Fuel system"]
        self.assertEqual(len(fuel_findings), 1)
        self.assertEqual(fuel_findings[0].severity, "critical")
        self.assertEqual(log.metrics["fuel_trim_median_pct"], 30.0)

    def test_dashboard_image_is_written_and_decodes(self) -> None:
        path = self.write_csv(
            "sensors.csv",
            "Seconds,Engine RPM,Vehicle Speed,Engine Coolant Temperature (°C)\n"
            + "".join(f"{second},{750 + second},{0 if second < 5 else 10},{80 + second / 10}\n" for second in range(20)),
        )
        log = analyze_log(path)
        image_path = self.root / "output" / "dashboard.png"
        render_dashboard(log, image_path)
        self.assertTrue(image_path.is_file())
        image = imread(image_path)
        self.assertGreater(image.shape[0], 500)
        self.assertGreater(image.shape[1], 500)

    def test_dashboard_renders_anomalies_without_elapsed_time(self) -> None:
        rows = ["RPM,Coolant Temperature (°C)"]
        rows.extend("750,80" for _ in range(99))
        rows.append("5000,180")
        log = analyze_log(self.write_csv("anomalies.csv", "\n".join(rows) + "\n"))
        self.assertIsNotNone(log.anomalies)
        self.assertTrue(log.anomalies.any())

        image_path = self.root / "output" / "anomalies.png"
        render_dashboard(log, image_path)
        self.assertTrue(image_path.is_file())


if __name__ == "__main__":
    unittest.main()
