# Architecture

This project is a lightweight local analysis pipeline for OBD-II CSV exports. A CSV is read into a pandas DataFrame, supported columns are mapped to standard signals, rule-based checks are applied, health scores are computed, and the results are rendered either as a CLI report or a browser dashboard. The code is intentionally small and transparent so that a user can trace each stage from raw readings to a final health summary.

For the verified rule thresholds and scoring cutoffs, see [HOW_IT_WORKS.md](HOW_IT_WORKS.md).

| File | Responsibility | Key functions / symbols |
|---|---|---|
| [src/obd_predictive/obd_analysis.py](../src/obd_predictive/obd_analysis.py) | Core parsing, rule checks, scoring, anomaly detection, trend estimates | `load_log`, `match_columns`, `analyze_log`, `estimate_trends`, `build_report` |
| [src/obd_predictive/obd_dashboard.py](../src/obd_predictive/obd_dashboard.py) | Static dashboard image | `render_dashboard` |
| [src/obd_predictive/streamlit_dashboard.py](../src/obd_predictive/streamlit_dashboard.py) | Browser UI and file upload flow | `_analyze_files`, `_show_results`, `main` |
| [src/obd_predictive/obd_diagnosis.py](../src/obd_predictive/obd_diagnosis.py) | CLI entry point | `parse_args`, `main` |
| [src/obd_predictive/make_sample_data.py](../src/obd_predictive/make_sample_data.py) | Synthetic demo CSV generation | `make_session`, `main` |
| [app.py](../app.py) | Simple Streamlit launcher | `main` |

```text
CSV input
  -> load_log() reads file and detects delimiter / time column
  -> match_columns() maps common header names to canonical signals
  -> rule checks add findings (coolant, voltage, fuel trim, idle)
  -> _score() turns findings into 0-100 system scores
  -> _detect_anomalies() runs Isolation Forest when conditions are met
  -> estimate_trends() projects simple warning-limit trends with dated logs
  -> build_report() writes a plain-language summary
  -> dashboard/report outputs are displayed or saved
```
