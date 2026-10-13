# OBD-II Predictive Maintenance and Fault Diagnosis

A local Windows-friendly screening tool for OBD-II CSV exports. It creates explainable health scores, diagnostic findings, interactive sensor plots, anomaly markers, and indicative trend projections. Sensor patterns do **not** confirm mechanical faults.

## Project layout

```text
OBD PREDICTIVE/
├── app.py                         Streamlit app entry point
├── pyproject.toml                 Package metadata and CLI commands
├── requirements.txt               Python dependencies
├── scripts/windows/               Windows launchers and shortcut setup
├── data/
│   ├── sample/                    Clearly labeled synthetic demonstration CSVs
│   └── uploads/                   Suggested home for your original CSV logs
├── tests/                         Automated regression tests
└── src/obd_predictive/            Analysis package, rules, charts, CLI, and app
```

The project virtual environment is created in `.venv/` and is not mixed with system Python. Generated dashboard images and text reports go in `output/` when the app runs. Place original logs in `data/uploads/`; upload them in oldest-first order in the browser dashboard. The app reads the uploaded bytes without changing your original files.

## Simplest way to start

1. Double-click `scripts\windows\Setup_Update_And_Run.bat` the first time. It creates `.venv`, upgrades pip and the project dependencies, and opens the dashboard.
2. After setup, use `scripts\windows\Launch_Dashboard.bat` for normal starts without upgrading dependencies.
3. To add Windows desktop shortcuts, right-click `scripts\windows\Create_Desktop_Shortcuts.ps1` and choose **Run with PowerShell**, or run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\windows\Create_Desktop_Shortcuts.ps1
   ```

   This adds **OBD-II Dashboard** (normal launch) and **OBD-II Dashboard - Setup and Update** shortcuts to your Windows Desktop.

The update launcher needs an internet connection when dependencies must be installed or updated. The normal launcher uses the existing project environment. Close the dashboard terminal or press `Ctrl+C` there to stop the local server. The app is local and normally opens at `http://localhost:8501`.

## Manual installation and commands

Python 3.10 or newer is required. The setup launcher uses the Windows Python Launcher (`py`) if available, or falls back to a `python` command on PATH:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
obd-make-samples
python -m streamlit run app.py
```

Generate three labeled synthetic logs any time:

```powershell
obd-make-samples
```

Analyze logs using the command line (paths are supplied oldest first):

```powershell
obd-diagnosis .\data\uploads\old.csv .\data\uploads\new.csv
obd-diagnosis .\data\uploads\session_1.csv .\data\uploads\session_2.csv .\data\uploads\session_3.csv --interval-days 30
```

The CLI writes `output\dashboard.png` and `output\report.txt`. Override the output folder with `--output-dir`. For browser use, choose **Bundled synthetic demo** or **Upload CSV logs**, select CSVs oldest first, optionally enter the number of days between logs, and press **Analyze logs**. The interactive view lets you switch between logs, review findings and column coverage, inspect individual sensor charts, and download both outputs.

Trend projections require at least three sequential logs with distinct increasing dates. Dates may be in filenames (`YYYY-MM-DD` or `YYYY_MM_DD`) or date/timestamp columns. If dates are unavailable, supply `--interval-days` to the CLI or enter the interval in the browser dashboard.

## Supported readings

Headers are matched case-insensitively, with tolerance for punctuation and common Torque Pro, Car Scanner, and OBD Fusion variations:

| Reading | Example headers |
|---|---|
| Engine RPM | `RPM`, `Engine RPM(rpm)`, `Engine speed` |
| Coolant temperature | `Coolant Temperature`, `Engine Coolant Temperature(°C)`, `ECT`; Fahrenheit-labeled headers are converted to °C |
| Module/battery voltage | `Voltage`, `Control module voltage(V)`, `Battery Voltage` |
| Short-term fuel trim | `STFT`, `Short Term Fuel Trim Bank 1(%)` |
| Long-term fuel trim | `LTFT`, `Long Term Fuel Trim Bank 1(%)` |
| Engine load | `Engine Load(%)`, `Calculated Load` |
| Vehicle speed | `Vehicle speed(km/h)`, `Vehicle Speed` |

Unknown columns and nonnumeric readings are reported instead of being guessed. Logs with partial sensor coverage are still analyzed for the readings they contain.

## Interpreting the results

* Each supported system starts at 100 points; a warning deducts 15, critical finding 30, and informational finding 5 (floor 0). Overall health is the rounded average of supported systems; missing systems are excluded, not assumed healthy.
* Cooling, charging/battery, fuel, and idle scores use coolant temperature, voltage, fuel trims, and engine RPM/vehicle speed respectively. Fuel trim is combined per sample by adding available short- and long-term percentages; idle is scored only when at least 10 plausible idle samples are available.
* Rule findings show severity, evidence, and a qualified explanation. The rules are generic screening defaults, not vehicle-specific specifications. Limits can be adjusted in `LIMITS` within `src/obd_predictive/obd_analysis.py`.
* Isolation Forest is used only when there are at least 50 complete rows across at least two sensor types. An anomaly is an unusual pattern, not necessarily a fault.
* Trend estimates are straight-line projections from a small number of logs. They are indicative only—not guaranteed remaining useful life. Driving conditions, gaps, repairs, and sensor quality can change the trend.
* The bundled logs are synthetic and explicitly marked in their CSV contents, report, and dashboard. They are for demonstration only and are never a real vehicle diagnosis.
* Check vehicle-specific service information. Get professional help for overheating, stalling, or unsafe behavior.

## Outputs and troubleshooting

* `output\dashboard.png` — static health and sensor-chart image for the latest analyzed log. In the browser, the preview and downloaded image follow the currently selected log.
* `output\report.txt` — plain-language scores, findings, input coverage, assumptions, and available trends.
* Browser dashboard — interactive sensor selection, anomaly markers, per-log inspection, coverage, and file downloads.
* Regression tests can be run with `python -m unittest discover -s tests -v` from an activated project environment.

If setup fails, verify Python is installed (`py -3 --version` or `python --version`) and check the internet connection, then rerun `scripts\windows\Setup_Update_And_Run.bat`. Errors opening malformed CSVs are listed by the CLI or dashboard; if no input can be read, the analysis reports that instead of producing an empty success result.
