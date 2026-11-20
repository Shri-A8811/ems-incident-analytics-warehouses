# EMS dispatch exploratory data analysis

## Scope and rules

This exploratory analysis uses 4,035,659 incidents created from January 2024 through June 2026. The raw profiles are saved as CSV tables in this folder. Response-time averages use only records whose matching source validity flag is `Y`. Counts describe this dataset; they do not adjust for population, exposure or staffing. They show association, not cause.

## Demand over time

- The busiest clock hour was **14:00-14:59**, with **216,775 incidents**. The next busiest was 15:00-15:59, with 216,674.
- Monday had the most incidents (**592,381**). Sunday had the fewest (**544,299**).
- The busiest month was **May 2024** (**144,021**). The quietest was **February 2025** (**119,980**).
- Quarterly counts are available in `incidents_by_quarter.csv`; the busiest quarter was **2024 Q2** (415,690), and the lowest was **2026 Q1** (386,941).

See `incidents_by_hour.csv`, `incidents_by_weekday.csv`, `incidents_by_month.csv`, and `incidents_by_quarter.csv`. The month chart is `figures/incidents_by_month.png`.

## Incident types and severity

- The most common initial call type was **INJURY** (**489,693**, 12.1%). The most common final call type was **SICK** (**485,853**, 12.0%). The source code descriptions are in `docs/reference/call_type_descriptions.csv`.
- Initial severity code **5** was most common (960,324, 23.8%). Final severity code **5** was also most common (964,575, 23.9%). The FDNY description workbook defines severity as a priority segment but does not explain the code meanings, so this analysis keeps them as categories without assigning an order or medical meaning.
- Initial and final severity codes differ on **500,882 incidents** (12.4%). The full 72-pair table is `severity_transitions.csv`; disposition comparisons are in `severity_change_by_disposition.csv`.
- Disposition **82** (transporting patient) appears 2,444,628 times (60.6%); **93** (refused medical aid) appears 708,016 times (17.5%). See `docs/reference/incident_disposition_codes.csv`.

## Borough demand and response time

- Brooklyn had the most records (**1,114,292**, 27.6%). Staten Island/Richmond had 173,379 (4.3%). These are raw totals, not population-adjusted rates.
- Among records with a valid response-time flag, mean incident response was about **20.95 minutes in the Bronx** (1,257 seconds) and **10.44 minutes in Staten Island/Richmond** (626 seconds). The overall median was **9.52 minutes** (571 seconds).
- Initial call type SICK averaged 1,485 seconds (24.75 minutes) on valid rows. EDP averaged 1,619 seconds (26.98 minutes). Long-tailed values affect means, so use the distributions and sample counts alongside averages.

See `response_by_borough.csv`, `response_by_initial_call_type.csv`, and `response_by_borough_initial_call_type.csv` for counts and averages. The figures `response_time_histograms.png` and `response_time_boxplots.png` use log(1 + seconds) so their long right tails do not hide the main distributions. The boxplot hides individual outlier points for readability; the counts remain in `numeric_summary.csv` and `timing_by_validity_flag.csv`.

## Initial interpretation

Demand is highest in the early afternoon in these records. Borough and call-type averages differ, but this descriptive analysis does not explain why. A later dashboard should show both incident volume and valid-response averages, and should keep the validity flags visible in its metric definitions. It should not describe an average response-time difference as an effect caused by call type or borough.
