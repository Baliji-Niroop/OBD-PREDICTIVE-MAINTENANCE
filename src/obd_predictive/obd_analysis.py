"""Column matching, transparent OBD checks, health scoring, and trend estimates."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import re

import numpy as np
import pandas as pd


# Generic screening limits only; consult the vehicle's service data for its own limits.
LIMITS = {
    "coolant_warning_c": 105.0,
    "coolant_critical_c": 115.0,
    "coolant_underheat_c": 75.0,
    "running_voltage_low_v": 13.2,
    "running_voltage_critical_v": 12.0,
    "running_voltage_high_v": 15.0,
    "voltage_instability_sd_v": 0.4,
    "engine_off_voltage_low_v": 12.2,
    "cranking_voltage_low_v": 9.6,
    "fuel_trim_warning_pct": 10.0,
    "fuel_trim_critical_pct": 20.0,
    "idle_rpm_low": 600.0,
    "idle_rpm_high": 1100.0,
    "rough_idle_cv_pct": 5.0,
    "rpm_dip_below_local_median": 150.0,
}

SIGNALS = {
    "rpm": ("Engine speed", "rpm", "RPM"),
    "coolant_c": ("Coolant temperature", "°C", "Coolant temperature"),
    "voltage_v": ("Module/battery voltage", "V", "Voltage"),
    "stft_pct": ("Short-term fuel trim", "%", "Fuel trim"),
    "ltft_pct": ("Long-term fuel trim", "%", "Fuel trim"),
    "load_pct": ("Engine load", "%", "Engine load"),
    "speed_kph": ("Vehicle speed", "km/h", "Vehicle speed"),
}

ALIASES = {
    "rpm": ("rpm", "engine speed", "engine rpm", "revolutions per minute"),
    "coolant_c": ("coolant temperature", "coolant temp", "engine coolant", "ect"),
    "voltage_v": ("voltage", "battery voltage", "module voltage", "control module voltage"),
    "stft_pct": ("short term fuel trim", "short term trim", "stft"),
    "ltft_pct": ("long term fuel trim", "long term trim", "ltft"),
    "load_pct": ("engine load", "calculated load", "absolute load"),
    "speed_kph": ("vehicle speed", "speed"),
}


@dataclass
class Finding:
    system: str
    severity: str
    title: str
    evidence: str
    explanation: str
    penalty: int = 0


@dataclass
class LogAnalysis:
    path: Path
    frame: pd.DataFrame
    source_columns: dict[str, str]
    findings: list[Finding] = field(default_factory=list)
    scores: dict[str, int] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    anomalies: pd.Series | None = None
    anomaly_note: str = ""
    log_date: date | None = None
    warnings: list[str] = field(default_factory=list)
    synthetic: bool = False


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def match_columns(columns: list[str]) -> tuple[dict[str, str], list[str]]:
    """Map common app-export header variations to supported canonical readings."""
    matches: dict[str, str] = {}
    used: set[str] = set()
    for canonical, phrases in ALIASES.items():
        ranked: list[tuple[int, str]] = []
        for column in columns:
            normalized = _norm(column)
            for phrase in phrases:
                p = _norm(phrase)
                if normalized == p:
                    ranked.append((0, column))
                    break
                if p in normalized:
                    ranked.append((1, column))
                    break
                words = p.split()
                if len(words) == 1 and words[0] in normalized.split():
                    ranked.append((2, column))
                    break
        ranked.sort(key=lambda pair: (pair[0], columns.index(pair[1])))
        for _, column in ranked:
            if column not in used:
                matches[canonical] = column
                used.add(column)
                break
    return matches, [column for column in columns if column not in used]


def _find_log_date(path: Path, frame: pd.DataFrame) -> date | None:
    match = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})", path.stem)
    if match:
        try:
            return date(*(int(part) for part in match.groups()))
        except ValueError:
            pass
    for column in frame.columns:
        name = _norm(str(column))
        if "timestamp" in name or "datetime" in name or name in {"date", "date time"}:
            parsed = pd.to_datetime(frame[column], errors="coerce").dropna()
            if not parsed.empty:
                return parsed.median().date()
    return None


def load_log(path: Path) -> LogAnalysis:
    """Read one CSV and normalize recognized sensor columns without inventing data."""
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        sample = handle.read(8192)
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        delimiter = ","
    raw = pd.read_csv(path, sep=delimiter, encoding="utf-8-sig", encoding_errors="replace")
    if raw.empty or len(raw.columns) == 0:
        raise ValueError("CSV contains no data rows or columns.")
    synthetic = False
    synthetic_metadata: set[str] = set()
    for candidate in raw.columns:
        name = _norm(str(candidate))
        if "synthetic" in name or name in {"data type", "data origin", "data source"}:
            if raw[candidate].astype(str).str.contains("synthetic", case=False, na=False).any():
                synthetic = True
                synthetic_metadata.add(str(candidate))
    matches, unmatched = match_columns([str(column) for column in raw.columns])
    time_columns = {"seconds", "elapsed seconds", "time seconds", "time s"}
    unmatched = [
        column for column in unmatched
        if _norm(column) not in time_columns and column not in synthetic_metadata
    ]
    data: dict[str, pd.Series] = {}
    for canonical, source in matches.items():
        values = pd.to_numeric(raw[source], errors="coerce").replace([np.inf, -np.inf], np.nan)
        normalized_source = _norm(source)
        if canonical == "coolant_c" and (
            "fahrenheit" in normalized_source
            or "degree f" in normalized_source
            or normalized_source.endswith(" f")
        ):
            values = (values - 32.0) * (5.0 / 9.0)
        data[canonical] = values
    frame = pd.DataFrame(data)
    for candidate in raw.columns:
        if _norm(str(candidate)) in time_columns:
            frame["elapsed_s"] = pd.to_numeric(raw[candidate], errors="coerce")
            break
    log = LogAnalysis(
        path=path,
        frame=frame,
        source_columns=matches,
        log_date=_find_log_date(path, raw),
        synthetic=bool(synthetic),
    )
    if not matches:
        log.warnings.append("No supported sensor columns were recognized; no sensor-based analysis is possible.")
    if unmatched:
        log.warnings.append("Unrecognized columns were not analyzed: " + ", ".join(unmatched[:15]))
    all_missing = [SIGNALS[key][0] for key in matches if frame[key].notna().sum() == 0]
    if all_missing:
        log.warnings.append("Recognized columns contained no usable numeric values: " + ", ".join(all_missing))
    return log


def _add(log: LogAnalysis, system: str, severity: str, title: str, evidence: str, explanation: str) -> None:
    penalty = {"critical": 30, "warning": 15, "info": 5}.get(severity, 0)
    log.findings.append(Finding(system, severity, title, evidence, explanation, penalty))


def _valid_values(log: LogAnalysis, key: str) -> pd.Series:
    if key not in log.frame:
        return pd.Series(dtype=float)
    return log.frame[key].dropna()


def _diagnose_cooling(log: LogAnalysis) -> None:
    values = _valid_values(log, "coolant_c")
    if values.empty:
        return
    peak = float(values.max())
    log.metrics["coolant_peak_c"] = peak
    if peak >= LIMITS["coolant_critical_c"]:
        _add(log, "Cooling", "critical", "Very high coolant temperature",
             f"Peak {peak:.1f} °C; generic critical screening limit {LIMITS['coolant_critical_c']:.0f} °C.",
             "Stop safely if the vehicle is overheating; sensor data alone cannot identify the cause.")
    elif peak >= LIMITS["coolant_warning_c"]:
        _add(log, "Cooling", "warning", "High coolant temperature",
             f"Peak {peak:.1f} °C; generic warning screening limit {LIMITS['coolant_warning_c']:.0f} °C.",
             "Temperature is elevated; check vehicle-specific guidance and investigate if it persists.")
    if len(values) >= 20:
        start = float(values.iloc[: max(5, len(values) // 10)].median())
        end = float(values.iloc[-max(5, len(values) // 10):].median())
        duration = float(log.frame.get("elapsed_s", pd.Series(dtype=float)).max()) if "elapsed_s" in log.frame else 0.0
        if duration >= 300 and start < 60 and end < LIMITS["coolant_underheat_c"]:
            _add(log, "Cooling", "warning", "Possible slow warm-up / under-temperature pattern",
                 f"Initial median {start:.1f} °C, final median {end:.1f} °C after {duration / 60:.1f} minutes.",
                 "A thermostat stuck open is one possibility, but ambient conditions, trip length, and sensor accuracy also matter.")


def _diagnose_charging(log: LogAnalysis) -> None:
    voltage = _valid_values(log, "voltage_v")
    if voltage.empty:
        return
    rpm_available = "rpm" in log.frame and log.frame["rpm"].notna().any()
    if not rpm_available:
        log.warnings.append("Voltage was present but RPM was unavailable; running, stopped-engine, and cranking voltage checks were omitted because operating context is unknown.")
        return
    rpm = log.frame["rpm"]
    running = voltage[(rpm.reindex(voltage.index) > 500).fillna(False)]
    if not running.empty:
        median = float(running.median())
        log.metrics["running_voltage_median_v"] = median
        if median < LIMITS["running_voltage_critical_v"]:
            _add(log, "Charging / Battery", "critical", "Very low voltage while engine is running",
                 f"Median {median:.2f} V across {len(running)} running-engine samples.",
                 "Charging output appears low in these samples; wiring, alternator behavior, battery condition, and measurement context need checks.")
        elif median < LIMITS["running_voltage_low_v"]:
            _add(log, "Charging / Battery", "warning", "Low voltage while engine is running",
                 f"Median {median:.2f} V; generic screening threshold {LIMITS['running_voltage_low_v']:.1f} V.",
                 "Charging voltage may be low; smart-charging systems and vehicle-specific specifications can differ.")
        elif median > LIMITS["running_voltage_high_v"]:
            _add(log, "Charging / Battery", "warning", "High voltage while engine is running",
                 f"Median {median:.2f} V; generic screening threshold {LIMITS['running_voltage_high_v']:.1f} V.",
                 "Voltage is high for this generic check; verify with vehicle-specific service information.")
        elif float(running.max()) > LIMITS["running_voltage_high_v"]:
            _add(log, "Charging / Battery", "warning", "Brief high voltage while engine is running",
                 f"Peak {running.max():.2f} V across {len(running)} running-engine samples; generic screening threshold {LIMITS['running_voltage_high_v']:.1f} V.",
                 "A brief high reading may reflect a transient, electrical load, or logging artifact; verify before drawing conclusions.")
        spread = float(running.std()) if len(running) > 1 else 0.0
        if spread >= LIMITS["voltage_instability_sd_v"]:
            _add(log, "Charging / Battery", "warning", "Unstable running voltage",
                 f"Standard deviation {spread:.2f} V across {len(running)} samples.",
                 "Large variation can reflect charging changes, electrical loads, noisy data, or logging artifacts.")
    if "rpm" in log.frame:
        cranking = voltage[(rpm.reindex(voltage.index) >= 50) & (rpm.reindex(voltage.index) <= 500)]
        if len(cranking) >= 2 and float(cranking.min()) < LIMITS["cranking_voltage_low_v"]:
            _add(log, "Charging / Battery", "warning", "Low voltage during possible cranking",
                 f"Minimum {cranking.min():.2f} V across {len(cranking)} samples with RPM 50–500.",
                 "This may indicate weak cranking voltage, but only if these samples truly cover engine cranking.")
        stopped = voltage[(rpm.reindex(voltage.index) < 50).fillna(False)]
        if len(stopped) >= 5 and float(stopped.median()) < LIMITS["engine_off_voltage_low_v"]:
            _add(log, "Charging / Battery", "warning", "Low voltage with engine stopped",
                 f"Median {stopped.median():.2f} V for {len(stopped)} stopped-engine samples.",
                 "A low resting reading can be associated with a discharged or aged battery; verify after the vehicle rests.")


def _diagnose_fuel(log: LogAnalysis) -> None:
    trims = [key for key in ("stft_pct", "ltft_pct") if key in log.frame]
    if not trims:
        return
    combined = log.frame[trims].sum(axis=1, min_count=1).dropna()
    if combined.empty:
        return
    median = float(combined.median())
    log.metrics["fuel_trim_median_pct"] = median
    limit = LIMITS["fuel_trim_critical_pct"] if abs(median) >= LIMITS["fuel_trim_critical_pct"] else LIMITS["fuel_trim_warning_pct"]
    if abs(median) >= LIMITS["fuel_trim_warning_pct"]:
        direction = "positive / lean-side" if median > 0 else "negative / rich-side"
        severity = "critical" if abs(median) >= LIMITS["fuel_trim_critical_pct"] else "warning"
        _add(log, "Fuel system", severity, f"Fuel trim is strongly {direction}",
             f"Median available trim {median:+.1f}%; generic screening threshold ±{limit:.0f}%.",
             "Fuel-trim correction can have several causes; this is not proof of a vacuum leak, fuel-pressure issue, or other specific fault.")


def _diagnose_engine(log: LogAnalysis) -> None:
    rpm = _valid_values(log, "rpm")
    if rpm.empty:
        return
    if "speed_kph" in log.frame:
        idle_mask = log.frame["speed_kph"].fillna(np.inf) <= 2.0
        idle_mask &= log.frame["rpm"].between(400, 1600)
        idle = log.frame.loc[idle_mask, "rpm"].dropna()
    else:
        idle = rpm[rpm.between(400, 1200)]
    if len(idle) < 10:
        log.warnings.append("Idle behavior was not scored: fewer than 10 plausible idle samples (or no usable idle segment).")
        return
    median = float(idle.median())
    sd = float(idle.std()) if len(idle) > 1 else 0.0
    cv_pct = sd / median * 100 if median else 0.0
    log.metrics["idle_rpm_median"] = median
    log.metrics["idle_roughness_pct"] = cv_pct
    if median < LIMITS["idle_rpm_low"] or median > LIMITS["idle_rpm_high"]:
        _add(log, "Engine / Idle", "warning", "Idle speed outside generic range",
             f"Median idle {median:.0f} rpm; generic range {LIMITS['idle_rpm_low']:.0f}–{LIMITS['idle_rpm_high']:.0f} rpm.",
             "Idle speed depends on temperature, accessories, transmission state, and vehicle calibration.")
    if cv_pct >= LIMITS["rough_idle_cv_pct"]:
        _add(log, "Engine / Idle", "warning", "High idle-speed variation",
             f"Idle standard deviation {sd:.0f} rpm ({cv_pct:.1f}% of median).",
             "Variation can be misfire-like but can also come from normal load changes, sensor noise, or unstable operating conditions.")
    window = max(5, min(15, (len(idle) // 2) * 2 + 1))
    local_median = idle.rolling(window=window, center=True, min_periods=3).median()
    dips = (idle < local_median - LIMITS["rpm_dip_below_local_median"]).sum()
    if dips >= 3:
        _add(log, "Engine / Idle", "warning", "Repeated idle RPM dips",
             f"{int(dips)} idle samples fell more than {LIMITS['rpm_dip_below_local_median']:.0f} rpm below the local median.",
             "RPM dips can be misfire-like; confirm with diagnostic trouble codes and inspection rather than treating this as a confirmed misfire.")


def _score(log: LogAnalysis) -> None:
    systems = {
        "Cooling": "coolant_c",
        "Charging / Battery": "voltage_v",
        "Fuel system": ("stft_pct", "ltft_pct"),
        "Engine / Idle": "rpm",
    }
    for system, required in systems.items():
        keys = (required,) if isinstance(required, str) else required
        if not any(key in log.frame and log.frame[key].notna().any() for key in keys):
            continue
        if system == "Engine / Idle" and "idle_rpm_median" not in log.metrics:
            continue
        penalty = sum(f.penalty for f in log.findings if f.system == system)
        log.scores[system] = max(0, 100 - penalty)


def _detect_anomalies(log: LogAnalysis) -> None:
    features = [key for key in SIGNALS if key in log.frame and log.frame[key].notna().any()]
    usable = log.frame[features].dropna() if len(features) >= 2 else pd.DataFrame()
    if len(features) < 2 or len(usable) < 50:
        log.anomalies = pd.Series(False, index=log.frame.index)
        log.anomaly_note = f"Not run: requires at least 2 usable sensor types and 50 complete rows (found {len(features)} types, {len(usable)} rows)."
        return
    from sklearn.ensemble import IsolationForest

    model = IsolationForest(
        contamination=0.03,
        random_state=42,
        n_estimators=50,
        n_jobs=1,
    )
    labels = model.fit_predict(usable)
    log.anomalies = pd.Series(False, index=log.frame.index)
    log.anomalies.loc[usable.index] = labels == -1
    count = int((labels == -1).sum())
    log.anomaly_note = f"Isolation Forest flagged {count} of {len(usable)} complete rows ({count / len(usable) * 100:.1f}%)."
    if count:
        _add(log, "Data pattern", "info", "Unusual multivariate readings flagged",
             log.anomaly_note,
             "An anomaly is an unusual combination of recorded sensor values, not necessarily a fault.")


def analyze_log(path: Path) -> LogAnalysis:
    log = load_log(path)
    _diagnose_cooling(log)
    _diagnose_charging(log)
    _diagnose_fuel(log)
    _diagnose_engine(log)
    _detect_anomalies(log)
    _score(log)
    return log


def _trend_value(log: LogAnalysis, parameter: str) -> float | None:
    if parameter == "coolant":
        return log.metrics.get("coolant_peak_c")
    if parameter == "voltage":
        return log.metrics.get("running_voltage_median_v")
    if parameter == "fuel_trim":
        return log.metrics.get("fuel_trim_median_pct")
    return None


def estimate_trends(logs: list[LogAnalysis], interval_days: float | None) -> list[str]:
    """Return linear, explicitly indicative warning-limit projections where dated."""
    if len(logs) < 3:
        return ["Life estimates omitted: at least three logs are required."]
    if interval_days is not None:
        dates = [index * interval_days for index in range(len(logs))]
        date_label = f"assumed {interval_days:g}-day spacing"
    elif all(log.log_date is not None for log in logs):
        origin = logs[0].log_date
        dates = [(log.log_date - origin).days for log in logs]  # type: ignore[operator]
        date_label = "dates read from filenames or timestamp columns"
        if len(set(dates)) != len(dates):
            return ["Life estimates omitted: log dates must be distinct (or provide --interval-days)."]
    else:
        return ["Life estimates omitted: logs need dates in filenames/timestamps or --interval-days."]
    if any(later <= earlier for earlier, later in zip(dates, dates[1:])):
        return ["Life estimates omitted: logs must be ordered oldest first with increasing dates."]

    configs = (
        ("Coolant peak", "coolant", LIMITS["coolant_warning_c"], "°C", "upper"),
        ("Running voltage", "voltage", LIMITS["running_voltage_low_v"], "V", "lower"),
        ("Fuel trim", "fuel_trim", LIMITS["fuel_trim_warning_pct"], "%", "positive"),
    )
    lines = [f"Straight-line projections ({date_label}; indicative only):"]
    found = False
    for label, key, limit, unit, direction in configs:
        observations = [(x, _trend_value(log, key)) for x, log in zip(dates, logs)]
        observations = [(x, y) for x, y in observations if y is not None and np.isfinite(y)]
        if len(observations) < 3:
            continue
        x = np.array([item[0] for item in observations], dtype=float)
        y = np.array([item[1] for item in observations], dtype=float)
        slope, _ = np.polyfit(x, y, 1)
        current = float(y[-1])
        crossed = current >= limit if direction == "upper" else (
            current <= limit if direction == "lower" else abs(current) >= limit
        )
        toward = (direction == "upper" and slope > 0) or (direction == "lower" and slope < 0) or (
            direction == "positive" and ((current >= 0 and slope > 0) or (current < 0 and slope < 0))
        )
        trend = f"{slope:+.3g} {unit}/day"
        series = " → ".join(f"{value:.2f}" for value in y)
        if crossed:
            estimate = "already at/past the screening limit"
        elif toward and slope != 0:
            target = limit if direction != "positive" or current >= 0 else -limit
            days = (target - current) / slope
            estimate = f"about {days:.0f} days" if days >= 0 else "no forward crossing projected"
        else:
            estimate = "no crossing projected from this trend"
        lines.append(f"- {label}: {series} {unit}; trend {trend}; limit {limit:g} {unit}; {estimate}.")
        found = True
    if not found:
        lines.append("No selected parameter had usable measurements in all three dated logs.")
    lines.append("These are simple linear extrapolations from a few logs, not remaining-useful-life predictions.")
    return lines


def health_summary(log: LogAnalysis) -> tuple[int | None, str]:
    if not log.scores:
        return None, "Not scored (no supported sensor data)"
    score = round(sum(log.scores.values()) / len(log.scores))
    label = "GOOD" if score >= 85 else "FAIR" if score >= 65 else "POOR"
    return score, label


def build_report(
    logs: list[LogAnalysis],
    failed_inputs: list[str],
    interval_days: float | None,
) -> str:
    latest = logs[-1]
    lines = [
        "OBD-II PREDICTIVE MAINTENANCE AND FAULT DIAGNOSIS",
        "=" * 68,
        "Screening aid only: sensor patterns do not confirm mechanical faults.",
        "",
        "INPUT COVERAGE",
        "-" * 68,
    ]
    for index, log in enumerate(logs, start=1):
        label = " — SYNTHETIC DEMO, NOT REAL VEHICLE DATA" if log.synthetic else ""
        lines.append(f"Log {index}: {log.path.name}" + (f" ({log.log_date.isoformat()})" if log.log_date else " (date unavailable)") + label)
        lines.append("  Readings analyzed: " + (", ".join(SIGNALS[key][0] for key in log.source_columns) or "none"))
        lines.append(f"  Data rows: {len(log.frame)}; Isolation Forest: {log.anomaly_note}")
        lines.extend("  Note: " + warning for warning in log.warnings)
    if failed_inputs:
        lines.append("Unreadable inputs: " + "; ".join(failed_inputs))
    lines.extend(["", "HEALTH SCORES (latest log)", "-" * 68])
    score, label = health_summary(latest)
    for system in ("Cooling", "Charging / Battery", "Fuel system", "Engine / Idle"):
        value = latest.scores.get(system)
        lines.append(f"  {system:<24} {value:>3}/100" if value is not None else f"  {system:<24} Not scored (required readings unavailable)")
    lines.append(f"  Overall vehicle health: {score}/100 — {label}" if score is not None else "  Overall vehicle health: Not scored")
    lines.extend([
        "",
        "HOW SCORES ARE CALCULATED",
        "-" * 68,
        "Each supported system starts at 100. Generic rule findings subtract 15 points for a warning,",
        "30 for critical, or 5 for informational. The system score is floored at 0. Overall health is",
        "the rounded mean of supported systems only; unsupported systems are excluded, not treated as healthy.",
        "Cooling uses coolant temperature; Charging/Battery uses voltage; Fuel uses STFT/LTFT;",
        "Engine/Idle uses RPM and, when present, vehicle speed to identify idle samples.",
        "Anomaly flags do not change health scores. Limits are generic screening defaults in obd_analysis.py.",
        "",
        "FINDINGS (latest log)",
        "-" * 68,
    ])
    if latest.findings:
        for finding in latest.findings:
            lines.extend([
                f"[{finding.severity.upper()}] {finding.system}: {finding.title}",
                f"  Evidence: {finding.evidence}",
                f"  Meaning: {finding.explanation}",
            ])
    else:
        lines.append("No configured rules triggered. This does not prove the vehicle has no faults.")
    lines.extend(["", "TREND-BASED WARNING-LIMIT ESTIMATES", "-" * 68])
    lines.extend(estimate_trends(logs, interval_days))
    lines.extend([
        "",
        "ASSUMPTIONS AND LIMITATIONS",
        "-" * 68,
        "CSV readings are matched by common header names; unmatched and nonnumeric readings are not analyzed.",
        "Logs must be supplied oldest first. --interval-days assigns equally spaced dates when provided.",
        "Generic thresholds cannot replace vehicle-specific service information, proper test conditions,",
        "diagnostic trouble codes, or inspection. Sampling gaps, sensor errors, driving conditions and repairs",
        "can materially change the readings. Seek professional help for overheating, stalling, or unsafe behavior.",
        "Synthetic demo logs are artificial and are never a real vehicle diagnosis.",
        "",
    ])
    return "\n".join(lines)
