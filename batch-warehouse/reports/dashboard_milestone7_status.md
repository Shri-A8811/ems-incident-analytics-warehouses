# Milestone 7 — warehouse dashboard and findings

## Status

Complete. The dashboard summaries are queried from the PostgreSQL warehouse for the January 2024–June 2026 period. Deliverables include the browser dashboard, a Power BI Desktop report, eight imported summary tables, and ten evidence-based findings. The Power BI report has two pages: Demand Overview (monthly demand, demand by borough, and average incident response by borough) and Patterns and Call Types (call type counts and weekday demand table).

## Deliverables

- `dashboards/index.html` — self-contained local dashboard page; open it in a browser. It uses the PNG charts stored in `dashboards/figures/`.
- `dashboards/EMS_Dispatch_PowerBI_Dashboard.pbix` — Power BI Desktop report using the summary CSVs in this folder.
- `dashboards/*.csv` — eight summary datasets that power the visuals; these can also be imported into Power BI.
- `dashboards/figures/*.png` — six chart images.
- `reports/dashboard_findings.md` — ten findings calculated from warehouse summaries, with an additional monthly observation and interpretation notes.
- `etl/build_dashboard.py` — repeatable export and chart-building script. With Docker/PostgreSQL running, use `python etl/build_dashboard.py` from the project folder.

## Power BI chart details

- The enhanced report is `dashboards/EMS_Dispatch_PowerBI_Dashboard_Enhanced.pbix`. It adds four KPI cards, a color scaled weekday and hour heatmap, an hourly demand chart, and a disposition breakdown. The borough response comparison is labeled in minutes and includes valid record counts in its tooltip. The overall dispatch and response KPIs weight the borough averages by their valid record counts.
- Remaining assignment dashboard items include average travel time, high-priority and long-response counts, severity-level breakdowns, a response-time trend, dispatch-area analysis, and a demand map.

- The monthly trend uses a `MonthStart` date calculated from `year_number` and `month_number`, so the timeline runs chronologically across January 2024–June 2026.
- The call type bar chart shows the top 10 source call type codes ranked by incident count.

## Data and interpretation notes

- The dashboard aggregates 4,035,659 historical incidents.
- Incident response averages include only rows marked valid by the source and with a recorded duration. Sample counts are retained in the CSV tables.
- Borough response comparisons exclude the small unknown category. The demand chart still shows it.
- The source borough category `RICHMOND / STATEN ISLAND` is retained as published.
- Counts are not population-adjusted. The dashboard is descriptive and is not a live dispatch monitor.
- Severity codes remain labels; the findings do not assign them clinical meaning.

## Software note

The `.pbix` report is saved locally in `dashboards/EMS_Dispatch_PowerBI_Dashboard.pbix`. It uses imported CSV summary tables, so it does not require a database connection to open. The browser dashboard and chart images remain available as a second way to review the findings.
