"""Interactive browser dashboard for uploaded OBD-II CSV logs."""

from __future__ import annotations

from pathlib import Path
import tempfile

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .obd_analysis import LogAnalysis, SIGNALS, analyze_log, build_report, health_summary
from .obd_dashboard import CHART_SIGNALS, render_dashboard


ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = ROOT / "data" / "sample"
OUTPUT_DIR = ROOT / "output"
SYSTEMS = ("Cooling", "Charging / Battery", "Fuel system", "Engine / Idle")


def _analyze_files(files: list[tuple[str, bytes]], interval_days: float | None) -> tuple[list[LogAnalysis], str, list[bytes], list[str]]:
    """Analyze uploaded bytes in a temporary folder and persist CLI-compatible outputs."""
    logs: list[LogAnalysis] = []
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="obd-dashboard-") as temp:
        temp_dir = Path(temp)
        for index, (name, contents) in enumerate(files):
            path = temp_dir / f"{index:03d}" / Path(name).name
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(contents)
                logs.append(analyze_log(path))
            except (OSError, UnicodeError, pd.errors.ParserError, ValueError) as error:
                failures.append(f"{name}: {error}")
        if not logs:
            return [], "", [], failures

        report = build_report(logs, failures, interval_days)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = OUTPUT_DIR / "report.txt"
        image_path = OUTPUT_DIR / "dashboard.png"
        report_path.write_text(report, encoding="utf-8")
        dashboard_images: list[bytes] = []
        for index, log in enumerate(logs):
            temp_image_path = temp_dir / f"dashboard-{index}.png"
            render_dashboard(log, temp_image_path)
            dashboard_images.append(temp_image_path.read_bytes())
        image_path.write_bytes(dashboard_images[-1])
        return logs, report, dashboard_images, failures


def _render_sensor_chart(log: LogAnalysis, signal_key: str) -> go.Figure:
    values = log.frame[signal_key]
    if "elapsed_s" in log.frame and log.frame["elapsed_s"].notna().any():
        x_values = log.frame["elapsed_s"]
        x_title = "Elapsed time (s)"
    else:
        x_values = pd.Series(range(len(log.frame)), index=log.frame.index)
        x_title = "Sample"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_values,
        y=values,
        mode="lines",
        name=SIGNALS[signal_key][0],
        line={"color": "#276fbf", "width": 1.5},
        connectgaps=False,
    ))
    if log.anomalies is not None and log.anomalies.any():
        anomaly_mask = log.anomalies.reindex(values.index, fill_value=False) & values.notna()
        if anomaly_mask.any():
            fig.add_trace(go.Scatter(
                x=x_values[anomaly_mask],
                y=values[anomaly_mask],
                mode="markers",
                name="Anomaly (unusual pattern)",
                marker={"color": "#c1121f", "symbol": "x", "size": 9},
            ))
    fig.update_layout(
        title=SIGNALS[signal_key][0],
        xaxis_title=x_title,
        yaxis_title=SIGNALS[signal_key][1],
        height=460,
        hovermode="x unified",
        template="plotly_white",
        legend={"orientation": "h", "y": 1.08},
        margin={"l": 30, "r": 20, "t": 70, "b": 40},
    )
    return fig


def _show_results(logs: list[LogAnalysis], report: str, dashboard_images: list[bytes], failures: list[str]) -> None:
    labels = [f"{index + 1}. {log.path.name}" for index, log in enumerate(logs)]
    selected_label = st.selectbox("Choose a log to inspect", labels, index=len(labels) - 1)
    selected_index = labels.index(selected_label)
    selected = logs[selected_index]
    dashboard_png = dashboard_images[selected_index]
    score, score_label = health_summary(selected)

    if selected.synthetic:
        st.warning("SYNTHETIC DEMONSTRATION DATA — these readings are artificial and are not a real vehicle diagnosis.")
    st.subheader(f"Vehicle health — {selected.path.name}")
    if score is not None:
        columns = st.columns(5)
        columns[0].metric("Overall", f"{score}/100", score_label)
        for column, system in zip(columns[1:], SYSTEMS):
            value = selected.scores.get(system)
            column.metric(system, f"{value}/100" if value is not None else "Not scored")
    else:
        st.info("Overall health was not scored because no supported numeric readings are available.")
    st.caption("Scores cover supported systems only. They are screening indicators, not a confirmed diagnosis.")

    findings_tab, charts_tab, coverage_tab, report_tab = st.tabs(
        ["Findings", "Sensor charts", "Input coverage", "Report and downloads"]
    )
    with findings_tab:
        if selected.findings:
            for finding in selected.findings:
                with st.expander(f"{finding.severity.upper()} · {finding.system} · {finding.title}", expanded=True):
                    st.markdown(f"**Evidence:** {finding.evidence}")
                    st.markdown(f"**What it may mean:** {finding.explanation}")
                    st.markdown(f":{ 'red' if finding.severity == 'critical' else 'orange' if finding.severity == 'warning' else 'blue' }[{finding.severity.title()} screening finding]")
        else:
            st.success("No configured rules triggered for this log. That does not prove there are no faults.")
        st.info(selected.anomaly_note + " An unusual pattern is not necessarily a fault.")
    with charts_tab:
        available = [key for key in CHART_SIGNALS if key in selected.frame and selected.frame[key].notna().any()]
        if available:
            signal_key = st.selectbox(
                "Sensor reading",
                available,
                format_func=lambda key: f"{SIGNALS[key][0]} ({SIGNALS[key][1]})",
            )
            st.plotly_chart(_render_sensor_chart(selected, signal_key), width="stretch")
            st.caption("Red × markers indicate Isolation Forest anomalies: unusual multivariate patterns, not confirmed faults.")
        else:
            st.info("No supported numeric sensor readings are available to chart.")
    with coverage_tab:
        coverage = pd.DataFrame([
            {"Sensor reading": SIGNALS[key][0], "CSV column": column, "Numeric samples": int(selected.frame[key].notna().sum())}
            for key, column in selected.source_columns.items()
        ])
        if coverage.empty:
            st.warning("No supported sensor columns were recognized.")
        else:
            st.dataframe(coverage, width="stretch", hide_index=True)
        st.write(f"Rows in log: **{len(selected.frame)}**")
        for warning in selected.warnings:
            st.warning(warning)
        if failures:
            st.write("Files skipped:")
            for failure in failures:
                st.error(failure)
    with report_tab:
        st.download_button(
            "Download plain-language report",
            data=report.encode("utf-8"),
            file_name="report.txt",
            mime="text/plain",
        )
        st.download_button(
            "Download dashboard image",
            data=dashboard_png,
            file_name="dashboard.png",
            mime="image/png",
        )
        st.caption(
            f"The report and latest-log image are saved in: {OUTPUT_DIR}. "
            "The preview and downloaded image match the selected log."
        )
        st.image(dashboard_png, caption="Static dashboard image generated alongside the interactive view.", width="stretch")
        with st.expander("Read full report"):
            st.text(report)


def main() -> None:
    st.set_page_config(
        page_title="OBD-II Vehicle Health",
        page_icon="🚘",
        layout="wide",
    )
    st.title("OBD-II Predictive Maintenance Dashboard")
    st.write("Upload OBD-II CSV logs to review health scores, evidence-based findings, sensor trends, and unusual readings.")
    st.caption("Screening aid only — sensor readings cannot confirm mechanical faults. Check vehicle-specific service data.")

    mode = st.radio("Log source", ("Bundled synthetic demo", "Upload CSV logs"), horizontal=True)
    interval_days = st.number_input(
        "Days between logs (optional)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        help="Enter a positive interval to project trends when at least three logs are supplied. Leave at 0 to use dates in filenames or CSV date columns.",
    )
    if mode == "Bundled synthetic demo":
        files = []
        for number in range(1, 4):
            path = SAMPLE_DIR / f"session_{number}.csv"
            if path.is_file():
                files.append((path.name, path.read_bytes()))
        if files:
            st.warning("The included demo logs are synthetic, not real vehicle readings.")
        else:
            st.error("Bundled demo CSVs are missing. Run `obd-make-samples` or upload your own files.")
    else:
        uploaded = st.file_uploader(
            "Select CSV logs oldest first",
            type=["csv"],
            accept_multiple_files=True,
            help="Select logs in chronological order. Files with dates in their names are labeled in the report.",
        )
        files = [(item.name, item.getvalue()) for item in uploaded] if uploaded else []
        if files:
            st.caption("Analysis uses the order shown below, oldest to newest.")
            st.write(" → ".join(name for name, _ in files))

    analyze = st.button("Analyze logs", type="primary", disabled=not files)
    if analyze:
        with st.spinner("Analyzing CSV logs and building the dashboard..."):
            logs, report, image, failures = _analyze_files(files, interval_days or None)
        if logs:
            st.session_state["obd_logs"] = logs
            st.session_state["obd_report"] = report
            st.session_state["obd_dashboard_images"] = image
            st.session_state["obd_failures"] = failures
        else:
            st.error("No input CSV could be analyzed.")
            for failure in failures:
                st.error(failure)

    if "obd_logs" in st.session_state:
        _show_results(
            st.session_state["obd_logs"],
            st.session_state["obd_report"],
            st.session_state["obd_dashboard_images"],
            st.session_state["obd_failures"],
        )


if __name__ == "__main__":
    main()
