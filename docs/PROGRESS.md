# Project progress

## Phase 1 — Data format
- [x] Confirmed the project reads OBD-II CSV exports with common app-style headers.
- [x] Kept the input format simple: CSV logs, optional date names, and numeric sensor values.

## Phase 2 — Data loader
- [x] Added CSV reading and delimiter detection.
- [x] Matched common headers to normalized signal names.
- [x] Converted Fahrenheit coolant readings before analysis.

## Phase 3 — Rule checks
- [x] Added cooling checks for overheating and underheat risk.
- [x] Added charging and battery checks for voltage deviations.
- [x] Added fuel trim warnings for lean/rich drift.
- [x] Added idle and RPM-based engine checks.

## Phase 4 — Health scoring
- [x] Created a transparent scoring model from rule findings.
- [x] Kept scores at the supported-system level instead of inventing vehicle-wide conclusions.

## Phase 5 — Anomaly detection
- [x] Added Isolation Forest-based unusual-pattern detection.
- [x] Kept anomaly warnings separate from fault claims.

## Phase 6 — Trend projection
- [x] Added date detection from filenames and timestamp columns.
- [x] Added straight-line trend estimates for dated logs.
- [x] Labeled the output as indicative and not a life prediction.

## Phase 7 — CLI workflow
- [x] Added a command-line diagnosis tool.
- [x] Added a synthetic data generator for demo runs.

## Phase 8 — Dashboard
- [x] Added a static matplotlib dashboard image.
- [x] Added an interactive Streamlit dashboard for uploaded logs.

## Phase 9 — Tests
- [x] Added regression tests for analysis, trends, and dashboard rendering.
- [x] Kept checks focused on the current behavior and supported CSV flows.

## Phase 10 — Launchers and packaging
- [x] Added Windows helper scripts for setup and launch.
- [x] Added editable package metadata and a dev install route.

## Phase 11 — Documentation
- [x] Reworked the main README for a quick first-time understanding.
- [x] Added architecture, rule details, and progress notes.
- [x] Added repo hygiene and project-entry improvements.

## Phase 12 — Polish
- [x] Expanded the synthetic demo dataset to five logs.
- [x] Fixed anomaly-plot rendering when logs have no elapsed-time column.
- [x] Added continuous integration tests.
- [x] Added a changelog.
