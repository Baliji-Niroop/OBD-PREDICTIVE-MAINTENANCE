"""Matplotlib dashboard rendering for the OBD-II analysis results."""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .obd_analysis import LogAnalysis, SIGNALS, health_summary


COLORS = {"critical": "#b42318", "warning": "#d97706", "info": "#2563eb"}
CHART_SIGNALS = ("rpm", "coolant_c", "voltage_v", "stft_pct", "ltft_pct", "load_pct", "speed_kph")


def render_dashboard(log: LogAnalysis, output_path: Path) -> None:
    """Render health, latest-log findings, sensor charts, and anomaly markers."""
    available = [key for key in CHART_SIGNALS if key in log.frame and log.frame[key].notna().any()]
    rows = max(1, (len(available) + 1) // 2)
    fig = plt.figure(figsize=(15, 7 + rows * 3.0), facecolor="#f5f7fa")
    grid = fig.add_gridspec(rows + 2, 2, height_ratios=[0.58, 1.05] + [2.0] * rows, hspace=0.5, wspace=0.28)
    header = fig.add_subplot(grid[0, :])
    header.axis("off")
    score, label = health_summary(log)
    score_text = f"{score}/100  {label}" if score is not None else "Not scored"
    header.text(0.01, 0.72, "OBD-II VEHICLE HEALTH DASHBOARD", fontsize=20, weight="bold", color="#14213d")
    header.text(0.01, 0.22, f"Log: {log.path.name}     Overall health: {score_text}", fontsize=12, color="#35445d")
    if log.synthetic:
        header.text(0.99, 0.72, "SYNTHETIC DEMO — NOT REAL VEHICLE DATA", ha="right",
                    fontsize=11, weight="bold", color="#b42318")

    score_axis = fig.add_subplot(grid[1, 0])
    score_axis.axis("off")
    score_axis.set_title("System health scores", loc="left", fontsize=14, weight="bold")
    systems = ("Cooling", "Charging / Battery", "Fuel system", "Engine / Idle")
    for row, system in enumerate(systems):
        value = log.scores.get(system)
        text = f"{value}/100" if value is not None else "Not scored"
        score_axis.text(0.02, 0.84 - row * 0.22, f"{system:<23} {text}", fontsize=12, family="monospace",
                        color="#157347" if value is not None and value >= 85 else "#a15c00" if value is not None and value >= 65 else "#35445d")

    finding_axis = fig.add_subplot(grid[1, 1])
    finding_axis.axis("off")
    finding_axis.set_title("Log findings", loc="left", fontsize=14, weight="bold")
    findings = log.findings[:4]
    if not findings:
        finding_axis.text(0.02, 0.82, "No configured rules triggered.", fontsize=10)
        finding_axis.text(0.02, 0.62, "This does not prove the vehicle has no faults.", fontsize=9, color="#555")
    for index, finding in enumerate(findings):
        y = 0.86 - index * 0.22
        color = COLORS.get(finding.severity, "#35445d")
        finding_axis.text(0.02, y, f"{finding.severity.upper()}: {finding.title}", fontsize=10, weight="bold", color=color)
        finding_axis.text(0.02, y - 0.09, finding.evidence[:110], fontsize=8, color="#35445d")
    if len(log.findings) > len(findings):
        finding_axis.text(0.02, 0.02, f"+ {len(log.findings) - len(findings)} more; see report.txt", fontsize=9)

    if log.anomaly_note:
        fig.text(0.04, 0.955, log.anomaly_note + " An anomaly is not necessarily a fault.",
                 fontsize=9, color="#555", va="top")

    for index, key in enumerate(available):
        ax = fig.add_subplot(grid[2 + index // 2, index % 2])
        values = log.frame[key]
        if "elapsed_s" in log.frame and log.frame["elapsed_s"].notna().any():
            x = log.frame["elapsed_s"]
            x_label = "Elapsed time (s)"
        else:
            x = range(len(log.frame))
            x_label = "Sample"
        ax.plot(x, values, linewidth=1.0, color="#276fbf", label=SIGNALS[key][0])
        ax.set_title(SIGNALS[key][0], loc="left", fontsize=12, weight="bold")
        ax.set_ylabel(SIGNALS[key][1])
        ax.set_xlabel(x_label)
        ax.grid(True, alpha=0.25)
        if log.anomalies is not None and log.anomalies.any():
            mask = log.anomalies.reindex(values.index, fill_value=False) & values.notna()
            if mask.any():
                ax.scatter(x[mask] if hasattr(x, "__getitem__") else [i for i, selected in enumerate(mask) if selected],
                           values[mask], color="#c1121f", s=26, marker="x", label="Anomaly", zorder=3)
                ax.legend(loc="best", fontsize=8)
    if not available:
        ax = fig.add_subplot(grid[2, :])
        ax.axis("off")
        ax.text(0.05, 0.6, "No supported numeric sensor readings are available to chart.", fontsize=13)

    fig.text(0.04, 0.012, "Screening aid only — sensor data cannot confirm a mechanical fault. Check vehicle-specific service limits.",
             fontsize=9, color="#555")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)
