"""Generate three clearly labeled synthetic OBD-II demo logs in the project folder."""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = ROOT / "data" / "sample"
RNG = np.random.default_rng(7)
SESSIONS = [
    (88.0, 14.4, 0.5, 8, 0),
    (91.0, 14.2, 2.0, 14, 1),
    (95.0, 13.9, 4.5, 22, 2),
    (100.0, 13.6, 8.0, 30, 3),
    (105.0, 13.1, 12.0, 36, 5),
]
SAMPLES = 900


def make_session(coolant_steady: float, voltage: float, ltft: float, idle_noise: int, dips: int) -> pd.DataFrame:
    """Build one synthetic OBD sample log with controlled health trends."""
    seconds = np.arange(SAMPLES)
    drive = np.clip((seconds - 120) / 60, 0, 1) * np.clip((780 - seconds) / 60, 0, 1)
    speed = drive * (45 + 25 * np.sin(seconds / 55.0) ** 2) + RNG.normal(0, 1.0, SAMPLES) * drive
    speed = np.clip(speed, 0, None)
    rpm = np.where(speed < 1, 780 + RNG.normal(0, idle_noise, SAMPLES), 750 + speed * 38 + RNG.normal(0, 40, SAMPLES))
    for index in np.concatenate((
        RNG.choice(np.arange(5, 110), dips, replace=False),
        RNG.choice(np.arange(790, 890), dips, replace=False),
    )) if dips else []:
        rpm[index] -= RNG.uniform(150, 260)
    coolant = coolant_steady - (coolant_steady - 35.0) * np.exp(-seconds / 260.0) + RNG.normal(0, 0.4, SAMPLES)
    load = 22 + speed * 0.45 + RNG.normal(0, 2, SAMPLES)
    stft = RNG.normal(0, 2.0, SAMPLES)
    ltft_series = ltft + RNG.normal(0, 0.4, SAMPLES)
    volts = voltage + RNG.normal(0, 0.05 + (14.2 - voltage) * 0.15, SAMPLES)
    return pd.DataFrame({
        "Seconds": seconds,
        "Engine RPM(rpm)": rpm.round(0),
        "Vehicle speed(km/h)": speed.round(1),
        "Engine Coolant Temperature(°C)": coolant.round(1),
        "Engine Load(%)": load.round(1),
        "Short Term Fuel Trim Bank 1(%)": stft.round(1),
        "Long Term Fuel Trim Bank 1(%)": ltft_series.round(1),
        "Control module voltage(V)": volts.round(2),
        "Data Type": "SYNTHETIC DEMONSTRATION - NOT REAL VEHICLE DATA",
    })


def main() -> None:
    """Generate the bundled sample CSV logs used for demonstration and testing."""
    print("Generating SYNTHETIC demonstration data only (not real vehicle measurements).")
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    for number, settings in enumerate(SESSIONS, start=1):
        path = SAMPLE_DIR / f"session_{number}.csv"
        frame = make_session(*settings)
        frame.to_csv(path, index=False)
        print(f"Wrote {path.name}: {len(frame)} synthetic rows")
    print(f"Created {len(SESSIONS)} demo logs showing a gradual shift from healthy to more stressed conditions.")


if __name__ == "__main__":
    main()
