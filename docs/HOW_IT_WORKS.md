# How it works

The loader in `obd_analysis.py` reads each CSV with a flexible delimiter (`,`, `;`, or tab) and tries to normalize common OBD export headers. It strips punctuation and compares names against known aliases such as `RPM`, `Engine Coolant Temperature(°C)`, `Control module voltage(V)`, `STFT`, and `LTFT`. If a column name clearly says it is Fahrenheit, the value is converted from °F to °C before the rule checks run. Unsupported columns are reported but not guessed.

## Rule checks and thresholds

The project uses an internal `LIMITS` dictionary for generic screening thresholds. These are intentionally simple defaults and are not a substitute for manufacturer service information.

- Cooling: warning at `coolant_warning_c = 105.0 °C`, critical at `115.0 °C`, and underheat flag at `75.0 °C`.
- Charging / battery: running voltage low warning at `13.2 V`, critical at `12.0 V`, high at `15.0 V`, and instability threshold at `0.4 V` standard deviation.
- Fuel trim: warning at `10.0 %`, critical at `20.0 %`.
- Idle: low idle threshold `600 rpm`, high idle threshold `1100 rpm`, rough idle coefficient of variation threshold `5.0 %`, and RPM dips below local median by more than `150 rpm` trigger a warning.

### Cooling

The code checks the highest coolant value in a log. If it crosses `115 °C`, the finding is marked `critical`. A peak above `105 °C` is a warning. This is a broad screen for overheating risk rather than a specific diagnosis.

### Charging / battery

The project inspects median running voltage, high/low threshold crossings, and standard deviation while the engine is running. It also looks at cranking voltage and engine-off voltage when those samples are available. This helps catch weak battery/charging behavior but it cannot prove a charging fault.

### Fuel system

Short-term and long-term fuel trim values are combined per row by summing the available percentages. The median combined value is then compared with `±10 %` and `±20 %` screening limits. A large positive value points to a lean-side correction; a large negative value points to a rich-side correction.

### Engine / idle

Idle is scored only when there are at least 10 plausible idle samples. The code uses RPM and vehicle speed to approximate an idle segment, then looks at median idle RPM, roughness, and repeated dips below the local median. If the idle range is outside `600–1100 rpm`, or the variation is above `5%` of the median, a warning is added.

## Scoring

Each supported system starts at `100`. Rule findings subtract `5` for info, `15` for warning, and `30` for critical. The system score is floored at `0`, and overall health is the rounded average of the supported systems. Missing systems are excluded rather than assumed healthy.

## Anomaly detection

Isolation Forest runs only when there are at least `50` complete rows and at least `2` usable sensor types. The logic uses the supported numeric columns in `SIGNALS` and flags unusual multivariate patterns. An anomaly is a data-pattern warning, not a mechanical fault.

## Trend projections

Trend estimates are calculated only when there are at least `3` dated logs, either from filenames such as `YYYY-MM-DD` or from timestamp/date columns. The project uses simple linear projections for coolant peak, running voltage, and fuel-trim median. It reports the slope and the approximate number of days before a warning threshold is crossed, but it clearly labels the result as indicative only.

## Worked example

The sample data in [data/sample/session_1.csv](../data/sample/session_1.csv) contains a synthetic log with common OBD headers such as `Engine Coolant Temperature(°C)`, `Control module voltage(V)`, `Short Term Fuel Trim Bank 1(%)`, and `Engine RPM(rpm)`. The loader reads it with the right delimiter, converts each recognized column to a normalized signal, and then checks its max/min values against the generic thresholds. The result is a short, human-readable health summary and a static dashboard image rather than a diagnosis.
