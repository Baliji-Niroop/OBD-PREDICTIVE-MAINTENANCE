# How it works

The loader in `obd_analysis.py` reads each CSV with a flexible delimiter (`,`, `;`, or tab) and tries to normalize common OBD export headers. It strips punctuation and compares names against known aliases such as `RPM`, `Engine Coolant Temperature(°C)`, `Control module voltage(V)`, `STFT`, and `LTFT`. If a column name clearly says it is Fahrenheit, the value is converted from °F to °C before the rule checks run. Unsupported columns are reported but not guessed.

## Rule checks and thresholds

The project uses an internal `LIMITS` dictionary for generic screening thresholds. These are intentionally simple defaults and are not a substitute for manufacturer service information.

- Cooling: warning at `coolant_warning_c = 105.0 °C`, critical at `115.0 °C`, and underheat flag at `75.0 °C`.
- Charging / battery: running voltage low warning at `13.2 V`, critical at `12.0 V`, high at `15.0 V`, instability threshold at `0.4 V` standard deviation, `engine_off_voltage_low_v = 12.2 V`, and `cranking_voltage_low_v = 9.6 V`.
- Fuel trim: warning at `10.0 %`, critical at `20.0 %`.
- Idle: low idle threshold `600 rpm`, high idle threshold `1100 rpm`, rough idle coefficient of variation threshold `5.0 %`, and RPM dips below local median by more than `150 rpm` trigger a warning.

### Cooling

The code checks the highest coolant value in a log. If it crosses `115 °C`, the finding is marked `critical`. A peak above `105 °C` is a warning. This is a broad screen for overheating risk rather than a specific diagnosis.

### Charging / battery

The project inspects median running voltage, high/low threshold crossings, and standard deviation while the engine is running. It checks possible cranking voltage when at least two samples have RPM from 50 to 500; a minimum below `cranking_voltage_low_v` (`9.6 V`) triggers a warning. It checks engine-off voltage when at least five samples have RPM below 50; a median below `engine_off_voltage_low_v` (`12.2 V`) triggers a warning. These checks help screen battery/charging behavior but cannot prove a fault.

### Fuel system

Short-term and long-term fuel trim values are combined per row by summing the available percentages. The median combined value is then compared with `±10 %` and `±20 %` screening limits. A large positive value points to a lean-side correction; a large negative value points to a rich-side correction.

### Engine / idle

Idle is scored only when there are at least 10 plausible idle samples. The code uses RPM and vehicle speed to approximate an idle segment, then looks at median idle RPM, roughness, and repeated dips below the local median. If the idle range is outside `600–1100 rpm`, or the variation is above `5%` of the median, a warning is added.

## Scoring

Each supported system starts at `100`. Rule findings subtract `5` for info, `15` for warning, and `30` for critical. The system score is floored at `0`, and overall health is the rounded average of the supported systems. Missing systems are excluded rather than assumed healthy.

Overall labels are GOOD at `85` or higher, FAIR from `65` through `84`, and POOR below `65`. The label comes only from the average score, so a log can show a few warnings and still be GOOD.

## Anomaly detection

Isolation Forest runs only when there are at least `50` complete rows and at least `2` usable sensor types. The logic uses the supported numeric columns in `SIGNALS` and flags unusual multivariate patterns. An anomaly is a data-pattern warning, not a mechanical fault.

The Isolation Forest is configured with contamination = 0.03, so it always marks about 3% of complete rows as unusual by design. The count (e.g. 27 of 900) is a fixed share, not a measured fault rate. Use the marked points to see WHERE patterns are unusual, not HOW MANY faults exist.

## Trend projections

Trend estimates are calculated only when there are at least `3` dated logs, either from filenames such as `YYYY-MM-DD` or from timestamp/date columns. The project uses simple linear projections for coolant peak, running voltage, and fuel-trim median. It reports the slope and the approximate number of days before a warning threshold is crossed, but it clearly labels the result as indicative only.

## Worked example

The latest bundled log, [data/sample/session_5.csv](../data/sample/session_5.csv), has a median running voltage of `13.10 V`, below `13.2 V`, so Charging scores `85`. Its median combined fuel trim is `+11.9%`, above `10%`, so Fuel scores `85`. Idle standard deviation is `57 rpm` (`7.4%` of the median), above `5%`, and there are `9` RPM dips, giving Engine / Idle two warnings and a score of `70`. The coolant peak is `103.5 °C`, below `105 °C`, so Cooling scores `100`. The overall score is `round(mean(100, 85, 85, 70)) = 85`, labeled GOOD.

## Demo data

The five bundled logs are synthetic and show a gradual decline: coolant peak rises from `87.6` to `103.5 °C`, running voltage falls from `14.40` to `13.10 V`, and fuel trim rises from `0.5` to `11.9%`. This sequence demonstrates the trend feature. `obd-make-samples` regenerates the logs with a fixed random seed.
