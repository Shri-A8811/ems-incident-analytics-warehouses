"""Export reproducible dashboard summaries from PostgreSQL and build a local HTML dashboard."""
from __future__ import annotations

import csv
import html
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import psycopg2
from psycopg2.extras import DictCursor


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboards"
FIG = OUT / "figures"
REPORTS = ROOT / "reports"
OUT.mkdir(exist_ok=True)
FIG.mkdir(exist_ok=True)


def read_local_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


QUERIES = {
    "monthly_demand": """
        SELECT d.year_number, d.month_number, d.month_name,
               count(*)::bigint AS incidents
        FROM ems_dw.fact_ems_incident f
        JOIN ems_dw.dim_date d ON d.date_key=f.incident_date_key
        WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
        GROUP BY d.year_number,d.month_number,d.month_name
        ORDER BY d.year_number,d.month_number
    """,
    "borough_performance": """
        SELECT coalesce(l.borough,'Other / missing') AS borough,
               count(*)::bigint AS incidents,
               count(*) FILTER (WHERE f.valid_incident_response='Y'
                  AND f.incident_response_seconds IS NOT NULL)::bigint AS valid_incident_response_count,
               round(avg(f.incident_response_seconds) FILTER
                  (WHERE f.valid_incident_response='Y' AND f.incident_response_seconds IS NOT NULL),1)
                  AS avg_incident_response_seconds,
               count(*) FILTER (WHERE f.valid_dispatch_response='Y'
                  AND f.dispatch_response_seconds IS NOT NULL)::bigint AS valid_dispatch_response_count,
               round(avg(f.dispatch_response_seconds) FILTER
                  (WHERE f.valid_dispatch_response='Y' AND f.dispatch_response_seconds IS NOT NULL),1)
                  AS avg_dispatch_response_seconds
        FROM ems_dw.fact_ems_incident f
        JOIN ems_dw.dim_location l ON l.location_key=f.location_key
        WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
        GROUP BY l.borough ORDER BY incidents DESC
    """,
    "hourly_demand": """
        SELECT t.hour_number, count(*)::bigint AS incidents
        FROM ems_dw.fact_ems_incident f
        JOIN ems_dw.dim_time t ON t.time_key=f.incident_time_key
        WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
        GROUP BY t.hour_number ORDER BY t.hour_number
    """,
    "weekday_demand": """
        SELECT d.day_of_week_number, d.day_name, count(*)::bigint AS incidents
        FROM ems_dw.fact_ems_incident f
        JOIN ems_dw.dim_date d ON d.date_key=f.incident_date_key
        WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
        GROUP BY d.day_of_week_number,d.day_name ORDER BY d.day_of_week_number
    """,
    "top_call_types": """
        SELECT c.source_call_type_code, coalesce(c.call_type_description,c.source_call_type_code) AS description,
               count(*)::bigint AS incidents,
               count(*) FILTER (WHERE f.valid_incident_response='Y'
                  AND f.incident_response_seconds IS NOT NULL)::bigint AS valid_response_count,
               round(avg(f.incident_response_seconds) FILTER
                  (WHERE f.valid_incident_response='Y' AND f.incident_response_seconds IS NOT NULL),1)
                  AS avg_incident_response_seconds
        FROM ems_dw.fact_ems_incident f
        JOIN ems_dw.dim_call_type c ON c.call_type_key=f.initial_call_type_key
        WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
        GROUP BY c.source_call_type_code,c.call_type_description
        ORDER BY incidents DESC
    """,
    "day_hour_demand": """
        SELECT d.day_of_week_number,d.day_name,t.hour_number,count(*)::bigint AS incidents
        FROM ems_dw.fact_ems_incident f
        JOIN ems_dw.dim_date d ON d.date_key=f.incident_date_key
        JOIN ems_dw.dim_time t ON t.time_key=f.incident_time_key
        WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
        GROUP BY d.day_of_week_number,d.day_name,t.hour_number
        ORDER BY d.day_of_week_number,t.hour_number
    """,
    "dispositions": """
        SELECT coalesce(d.source_disposition_code,'(missing)') AS disposition_code,
               coalesce(d.source_description,'') AS description,count(*)::bigint AS incidents
        FROM ems_dw.fact_ems_incident f
        LEFT JOIN ems_dw.dim_disposition d ON d.disposition_key=f.disposition_key
        WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
        GROUP BY d.source_disposition_code,d.source_description ORDER BY incidents DESC
    """,
    "severity_transitions": """
        SELECT count(*)::bigint AS incidents,
               count(*) FILTER (WHERE i.source_severity_code IS DISTINCT FROM z.source_severity_code)::bigint
                 AS changed_severity
        FROM ems_dw.fact_ems_incident f
        LEFT JOIN ems_dw.dim_severity i ON i.severity_key=f.initial_severity_key
        LEFT JOIN ems_dw.dim_severity z ON z.severity_key=f.final_severity_key
        WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
    """,
}


def fetch_all() -> dict[str, list[dict]]:
    read_local_env()
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD was not found in the local ignored .env file.")
    conn = psycopg2.connect(
        host="127.0.0.1", port=5435, dbname="ems_dw", user="ems_admin", password=password,
        connect_timeout=8,
    )
    try:
        results: dict[str, list[dict]] = {}
        with conn.cursor(cursor_factory=DictCursor) as cur:
            for name, query in QUERIES.items():
                cur.execute(query)
                results[name] = [dict(row) for row in cur.fetchall()]
        return results
    finally:
        conn.close()


def save_csv(name: str, rows: list[dict]) -> None:
    path = OUT / f"{name}.csv"
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(rows)


NAVY = "#15324b"
BLUE = "#2878a8"
TEAL = "#16a6a1"
GOLD = "#f2b84b"
RED = "#df6b57"
MUTED = "#607384"


def style_ax(ax, title: str) -> None:
    ax.set_title(title, loc="left", color=NAVY, fontweight="bold", fontsize=13, pad=14)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#d8e1e8")
    ax.tick_params(colors=MUTED, labelsize=9, left=False, bottom=False)
    ax.grid(axis="y", color="#e8eef2", linewidth=0.8)
    ax.set_axisbelow(True)


def build_charts(data: dict[str, list[dict]]) -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": "white", "axes.facecolor": "white"})
    monthly = data["monthly_demand"]
    labels = [f"{r['month_name'][:3]} {str(r['year_number'])[-2:]}" for r in monthly]
    values = [int(r["incidents"]) for r in monthly]
    fig, ax = plt.subplots(figsize=(12, 4.2))
    style_ax(ax, "EMS incidents by month")
    ax.plot(range(len(values)), values, color=BLUE, linewidth=2.5, marker="o", markersize=3.3)
    ax.fill_between(range(len(values)), values, min(values) - 3000, color=BLUE, alpha=.08)
    ax.set_xticks(range(0, len(labels), 2), labels[::2], rotation=35, ha="right")
    ax.set_ylabel("Incidents")
    fig.tight_layout()
    fig.savefig(FIG / "monthly_demand.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    boroughs = data["borough_performance"]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    style_ax(ax, "Incidents by borough")
    names = [str(r["borough"]) for r in boroughs]
    vals = [int(r["incidents"]) for r in boroughs]
    bars = ax.barh(names[::-1], vals[::-1], color=[BLUE, TEAL, GOLD, RED, "#7489a6", "#b7c7d1"][:len(vals)][::-1])
    ax.set_xlabel("Incidents")
    ax.grid(axis="x", color="#e8eef2")
    ax.grid(axis="y", visible=False)
    ax.bar_label(bars, labels=[f"{v/1e6:.2f}M" for v in vals[::-1]], padding=4, color=NAVY, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "borough_demand.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    known_boroughs = {"BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "RICHMOND / STATEN ISLAND"}
    resp = [r for r in boroughs
            if r["avg_incident_response_seconds"] is not None
            and str(r["borough"]).upper() in known_boroughs]
    resp.sort(key=lambda r: float(r["avg_incident_response_seconds"]), reverse=True)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    style_ax(ax, "Average incident response time by borough")
    names = [str(r["borough"]) for r in resp]
    mins = [float(r["avg_incident_response_seconds"]) / 60 for r in resp]
    bars = ax.barh(names[::-1], mins[::-1], color=RED)
    ax.set_xlabel("Minutes (source-valid response records only)")
    ax.grid(axis="x", color="#e8eef2")
    ax.grid(axis="y", visible=False)
    ax.bar_label(bars, labels=[f"{v:.1f} min" for v in mins[::-1]], padding=4, color=NAVY, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "response_by_borough.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    hours = data["hourly_demand"]
    fig, ax = plt.subplots(figsize=(10, 3.8))
    style_ax(ax, "Incident volume by hour of day")
    xs = [int(r["hour_number"]) for r in hours]
    ys = [int(r["incidents"]) for r in hours]
    ax.plot(xs, ys, color=TEAL, linewidth=2.8, marker="o", markersize=4)
    ax.fill_between(xs, ys, color=TEAL, alpha=.1)
    ax.set_xticks(range(0, 24, 2), [f"{h:02d}:00" for h in range(0, 24, 2)])
    ax.set_xlabel("Hour")
    ax.set_ylabel("Incidents")
    fig.tight_layout()
    fig.savefig(FIG / "hourly_demand.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    types = data["top_call_types"][:10]
    types = types[::-1]
    fig, ax = plt.subplots(figsize=(9, 5))
    style_ax(ax, "Ten most frequent initial call types")
    names = [str(r["source_call_type_code"]) for r in types]
    vals = [int(r["incidents"]) for r in types]
    bars = ax.barh(names, vals, color=BLUE)
    ax.set_xlabel("Incidents")
    ax.grid(axis="x", color="#e8eef2")
    ax.grid(axis="y", visible=False)
    ax.bar_label(bars, labels=[f"{v/1000:.0f}k" for v in vals], padding=4, color=NAVY, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "top_call_types.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    heat = data["day_hour_demand"]
    matrix = np.zeros((7, 24), dtype=float)
    for r in heat:
        matrix[int(r["day_of_week_number"]) - 1, int(r["hour_number"])] = int(r["incidents"])
    fig, ax = plt.subplots(figsize=(12, 4.3))
    image = ax.imshow(matrix, aspect="auto", cmap="YlGnBu")
    ax.set_title("Demand by weekday and hour", loc="left", color=NAVY, fontweight="bold", fontsize=13, pad=14)
    ax.set_xticks(range(0, 24, 2), [f"{h:02d}:00" for h in range(0, 24, 2)])
    ax.set_yticks(range(7), [str(r["day_name"]) for r in data["weekday_demand"]])
    ax.set_xlabel("Hour of day")
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.spines[:].set_visible(False)
    cbar = fig.colorbar(image, ax=ax, pad=.012)
    cbar.set_label("Incidents")
    fig.tight_layout()
    fig.savefig(FIG / "weekday_hour_heatmap.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def make_findings(data: dict[str, list[dict]]) -> str:
    monthly = data["monthly_demand"]
    boroughs = data["borough_performance"]
    hours = data["hourly_demand"]
    weekdays = data["weekday_demand"]
    types = data["top_call_types"]
    dispos = data["dispositions"]
    trans = data["severity_transitions"][0]
    total = sum(int(x["incidents"]) for x in monthly)
    peak_hour = max(hours, key=lambda x: int(x["incidents"]))
    peak_day = max(weekdays, key=lambda x: int(x["incidents"]))
    high_b = boroughs[0]
    known_boroughs = [b for b in boroughs if str(b["borough"]).upper() in
                      {"BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "RICHMOND / STATEN ISLAND"}]
    low_b = min(known_boroughs, key=lambda x: int(x["incidents"]))
    high_resp = max(known_boroughs,
                    key=lambda x: float(x["avg_incident_response_seconds"]))
    low_resp = min(known_boroughs,
                   key=lambda x: float(x["avg_incident_response_seconds"]))
    common = types[0]
    robust_types = [t for t in types if int(t["valid_response_count"]) >= 1000 and t["avg_incident_response_seconds"] is not None]
    longest = max(robust_types, key=lambda x: float(x["avg_incident_response_seconds"]))
    leading_disp = dispos[0]
    changed = int(trans["changed_severity"])
    all_n = int(trans["incidents"])
    month = max(monthly, key=lambda x: int(x["incidents"]))
    share = lambda n: 100 * int(n) / total
    findings = [
        f"The warehouse contains {total:,} incidents in the selected January 2024–June 2026 period.",
        f"The busiest clock hour is {int(peak_hour['hour_number']):02d}:00–{int(peak_hour['hour_number']):02d}:59, with {int(peak_hour['incidents']):,} incidents.",
        f"{peak_day['day_name']} has the largest weekday total, at {int(peak_day['incidents']):,} incidents.",
        f"{high_b['borough']} has the most incidents: {int(high_b['incidents']):,} ({share(high_b['incidents']):.1f}% of all records).",
        f"{low_b['borough']} has the smallest borough total: {int(low_b['incidents']):,} ({share(low_b['incidents']):.1f}%).",
        f"The highest borough average incident response is {float(high_resp['avg_incident_response_seconds'])/60:.1f} minutes in {high_resp['borough']} (n={int(high_resp['valid_incident_response_count']):,} valid records).",
        f"The lowest borough average incident response is {float(low_resp['avg_incident_response_seconds'])/60:.1f} minutes in {low_resp['borough']} (n={int(low_resp['valid_incident_response_count']):,} valid records).",
        f"{common['source_call_type_code']} is the most common initial call type, with {int(common['incidents']):,} incidents ({share(common['incidents']):.1f}%).",
        f"Among call types with at least 1,000 valid response records, {longest['source_call_type_code']} has the highest mean incident response ({float(longest['avg_incident_response_seconds'])/60:.1f} minutes; n={int(longest['valid_response_count']):,}).",
        f"Initial and final severity codes differ on {changed:,} incidents ({100*changed/all_n:.1f}%). This is a code transition, not a clinical interpretation.",
        f"Disposition {leading_disp['disposition_code']} is most frequent, at {int(leading_disp['incidents']):,} incidents ({share(leading_disp['incidents']):.1f}%).",
        f"The busiest month is {month['month_name']} {month['year_number']} ({int(month['incidents']):,} incidents).",
    ]
    text = "# Dashboard findings\n\n"
    text += "These are descriptive patterns in historical dispatch records. Counts are not population-adjusted, and differences do not establish causes. Response averages use only rows marked valid by the source and are shown with sample sizes. Borough comparisons below exclude missing/unknown borough values.\n\n"
    text += "## Ten evidence-based findings\n\n"
    text += "\n".join(f"{i}. {line}" for i, line in enumerate(findings[:10], 1))
    text += "\n\n## Additional observation\n\n" + findings[11] + "\n"
    return text


def build_html(data: dict[str, list[dict]]) -> None:
    monthly = data["monthly_demand"]
    boroughs = data["borough_performance"]
    total = sum(int(row["incidents"]) for row in monthly)
    peak_hour = max(data["hourly_demand"], key=lambda x: int(x["incidents"]))
    peak_borough = boroughs[0]
    valid_resp = sum(int(r["valid_incident_response_count"]) for r in boroughs)
    weighted_response = sum(float(r["avg_incident_response_seconds"] or 0) * int(r["valid_incident_response_count"]) for r in boroughs) / max(valid_resp, 1)
    monthly_html = html.escape(f"{monthly[0]['month_name']} {monthly[0]['year_number']}–{monthly[-1]['month_name']} {monthly[-1]['year_number']}")
    cards = [
        ("TOTAL INCIDENTS", f"{total:,}", monthly_html),
        ("BUSIEST HOUR", f"{int(peak_hour['hour_number']):02d}:00–{int(peak_hour['hour_number']):02d}:59", f"{int(peak_hour['incidents']):,} records"),
        ("HIGHEST DEMAND BOROUGH", str(peak_borough["borough"]), f"{int(peak_borough['incidents']):,} records"),
        ("AVG VALID INCIDENT RESPONSE", f"{weighted_response/60:.1f} min", f"{valid_resp:,} valid records"),
    ]
    card_html = "".join(f'<article class="kpi"><div>{html.escape(k)}</div><strong>{html.escape(v)}</strong><small>{d}</small></article>' for k,v,d in cards)
    chart_specs = [
        ("Monthly demand", "figures/monthly_demand.png", "Incident counts by calendar month."),
        ("Demand by borough", "figures/borough_demand.png", "Counts use the source borough categories; Richmond / Staten Island is retained as supplied."),
        ("Incident response time", "figures/response_by_borough.png", "Average incident response time, using only source-valid records. Sample counts are in the companion CSV."),
        ("Demand across the day", "figures/hourly_demand.png", "Counts grouped by the incident clock hour."),
        ("Most common call types", "figures/top_call_types.png", "Top ten initial call-type categories."),
        ("Weekday and hour pattern", "figures/weekday_hour_heatmap.png", "Darker cells indicate more dispatch records."),
    ]
    charts = "".join(f'<section class="chart"><h2>{html.escape(title)}</h2><img src="{src}" alt="{html.escape(title)} chart"><p>{html.escape(note)}</p></section>' for title,src,note in chart_specs)
    content = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NYC EMS Dispatch | Warehouse Dashboard</title>
<style>
:root{{--navy:#15324b;--blue:#2878a8;--teal:#16a6a1;--bg:#f2f6f8;--muted:#607384;--line:#dfe7ec}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--navy);font:15px/1.5 'Segoe UI',Arial,sans-serif}}
header{{background:linear-gradient(110deg,#12324b,#1b607b);color:white;padding:28px max(22px,calc((100vw - 1220px)/2)) 30px}}
header p{{margin:4px 0 0;color:#d6e8f0}}h1{{font-size:26px;margin:0}}.tag{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#9ee8df;font-weight:700}}
main{{max-width:1220px;margin:24px auto;padding:0 20px}}.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}}
.kpi,.chart,.note{{background:white;border:1px solid var(--line);border-radius:12px;box-shadow:0 4px 14px #15324b0b}}
.kpi{{padding:17px 18px}}.kpi div{{font-size:11px;letter-spacing:.08em;color:var(--muted);font-weight:700}}.kpi strong{{display:block;font-size:27px;margin:6px 0 2px}}.kpi small{{color:var(--muted)}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.chart{{padding:18px 18px 12px;min-width:0}}.chart h2{{font-size:17px;margin:0 0 10px}}.chart img{{display:block;width:100%;height:auto}}.chart p{{font-size:12px;color:var(--muted);margin:8px 0 0}}
.note{{margin:16px 0;padding:16px 18px;color:#3d5567}}.note strong{{color:var(--navy)}}a{{color:var(--blue)}}footer{{max-width:1220px;margin:0 auto;padding:0 20px 25px;font-size:12px;color:var(--muted)}}
@media(max-width:850px){{.kpis{{grid-template-columns:1fr 1fr}}.grid{{grid-template-columns:1fr}}}}@media(max-width:480px){{.kpis{{grid-template-columns:1fr}}}}
</style></head><body>
<header><div class="tag">EMS Dispatch Data Warehouse</div><h1>New York City incident overview</h1><p>Historical dispatch records · {monthly_html} · Source: FDNY / NYC Open Data</p></header>
<main><div class="kpis">{card_html}</div><div class="grid">{charts}</div>
<aside class="note"><strong>How to read this dashboard:</strong> response averages include only incidents whose matching source-validity flag is Y, with non-null durations. Record counts are not adjusted for borough population, staffing, or exposure; differences show patterns, not causes. Severity codes are shown as categories without assigning clinical meaning.</aside>
<aside class="note">Download the <a href="../reports/dashboard_findings.md">ten evidence-based findings</a> or browse the <a href=".">CSV tables used by this dashboard</a>. The dashboard is built from PostgreSQL aggregates and the images in this folder.</aside></main>
<footer>Project dashboard preview · Generated from the local PostgreSQL EMS warehouse. This is an analysis of historical records, not a live dispatch monitoring tool.</footer>
</body></html>'''
    (OUT / "index.html").write_text(content, encoding="utf-8")


def main() -> None:
    data = fetch_all()
    for name, rows in data.items():
        save_csv(name, rows)
    build_charts(data)
    build_html(data)
    (REPORTS / "dashboard_findings.md").write_text(make_findings(data), encoding="utf-8")
    print(f"Dashboard created with {sum(len(rows) for rows in data.values())} aggregate rows across {len(data)} exports.")
    print(f"Output: {OUT / 'index.html'}")


if __name__ == "__main__":
    main()
