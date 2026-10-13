"""Regression tests for Streamlit dashboard outputs."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from obd_predictive import streamlit_dashboard


class StreamlitDashboardTests(unittest.TestCase):
    def test_analysis_returns_image_for_each_log_and_saves_latest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"

            def write_named_image(log, output_path: Path) -> None:
                output_path.write_bytes(log.path.name.encode("utf-8"))

            with (
                patch.object(streamlit_dashboard, "OUTPUT_DIR", output_dir),
                patch.object(streamlit_dashboard, "render_dashboard", side_effect=write_named_image),
            ):
                logs, _, images, failures = streamlit_dashboard._analyze_files(
                    [
                        ("older.csv", b"RPM\n700\n"),
                        ("newer.csv", b"RPM\n800\n"),
                    ],
                    None,
                )

            self.assertEqual(failures, [])
            self.assertEqual([image.decode("utf-8") for image in images], ["older.csv", "newer.csv"])
            self.assertEqual((output_dir / "dashboard.png").read_bytes(), b"newer.csv")
            self.assertEqual([log.path.name for log in logs], ["older.csv", "newer.csv"])


if __name__ == "__main__":
    unittest.main()
