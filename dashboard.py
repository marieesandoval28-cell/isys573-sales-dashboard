"""
ISYS 573 Sales Dashboard
========================
Reads data/sales.csv and generates an interactive HTML report with:
  - Quarter filter dropdown (Q1 / Q2 / Q3 / Q4 / Full Year)
  - Revenue by region (bar chart)
  - Monthly revenue trend (line chart)
  - Revenue by category (pie chart)
  - Top 10 products by revenue (horizontal bar)
  - Summary KPI cards

Usage:
    python dashboard.py                      # outputs dashboard.html
    python dashboard.py --output report.html # custom output path
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs
import plotly.express as px
from plotly.subplots import make_subplots


DATA_PATH = Path(__file__).parent / "data" / "sales.csv"


def load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load and validate the sales CSV."""
    if not path.exists():
        raise FileNotFoundError(f"Sales data not found: {path}")
    df = pd.read_csv(path, parse_dates=["date"])
    required = {"date", "region", "category", "product",
                "units_sold", "unit_price", "revenue", "channel"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    df["quarter"] = df["date"].dt.quarter.map(
        {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    )
    df["month"] = df["date"].dt.to_period("M").astype(str)
    return df


def build_region_bar(df: pd.DataFrame) -> go.Figure:
    """Revenue by region — horizontal bar chart."""
    summary = (
        df.groupby("region")["revenue"]
        .sum()
        .reset_index()
        .sort_values("revenue", ascending=True)   # ascending so largest is at top
    )
    colors = ["#9B59B6", "#02C39A", "#F4A261", "#00B4D8"]
    fig = go.Figure()
    for index, row in summary.reset_index(drop=True).iterrows():
        fig.add_trace(go.Bar(
            x=[row["revenue"]],
            y=[row["region"]],
            orientation="h",
            marker_color=colors[index % len(colors)],
            hovertemplate="<b>%{y}</b><br>Revenue: $%{x:,.0f}<extra></extra>",
            showlegend=False,
        ))
    fig.update_layout(
        title="Revenue by Region",
        plot_bgcolor="white",
        xaxis=dict(tickprefix="$", tickformat=",.0f", title="Total Revenue ($)"),
        yaxis=dict(title="Region"),
        showlegend=False,
        margin=dict(t=50, b=30, l=80),
    )
    return fig


def build_monthly_line(df: pd.DataFrame) -> go.Figure:
    """Monthly revenue trend — line chart."""
    monthly = (
        df.groupby("month")["revenue"]
        .sum()
        .reset_index()
        .sort_values("month")
    )
    fig = px.line(
        monthly, x="month", y="revenue",
        markers=True,
        labels={"revenue": "Revenue ($)", "month": "Month"},
        title="Monthly Revenue Trend",
        color_discrete_sequence=["#2196F3"],
    )
    fig.update_layout(plot_bgcolor="white",
                      yaxis=dict(tickprefix="$", tickformat=",.0f"),
                      margin=dict(t=50, b=30))
    fig.update_traces(
        hovertemplate="<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>",
        line=dict(width=2.5)
    )
    return fig


def build_category_pie(df: pd.DataFrame) -> go.Figure:
    """Revenue by product category — pie chart."""
    cat = df.groupby("category")["revenue"].sum().reset_index()
    fig = px.pie(
        cat, names="category", values="revenue",
        color_discrete_sequence=px.colors.qualitative.Pastel,
        title="Revenue by Category",
        hole=0.35,
    )
    fig.update_traces(
        textposition="inside", textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>Revenue: $%{value:,.0f}<br>Share: %{percent}<extra></extra>"
    )
    fig.update_layout(margin=dict(t=50, b=10))
    return fig


def build_top_products(df: pd.DataFrame, n: int = 10) -> go.Figure:
    """Top N products by revenue — horizontal bar chart."""
    top = (
        df.groupby("product")["revenue"]
        .sum()
        .nlargest(n)
        .reset_index()
        .sort_values("revenue")
    )
    fig = px.bar(
        top, x="revenue", y="product",
        orientation="h",
        color="revenue",
        color_continuous_scale="Blues",
        labels={"revenue": "Revenue ($)", "product": "Product"},
        title=f"Top {n} Products by Revenue",
    )
    fig.update_layout(
        coloraxis_showscale=False,
        plot_bgcolor="white",
        xaxis=dict(tickprefix="$", tickformat=",.0f"),
        margin=dict(t=50, b=30)
    )
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>Revenue: $%{x:,.0f}<extra></extra>"
    )
    return fig


def kpi_card_html(label: str, value: str, color: str = "#2196F3") -> str:
    """Render a single KPI card as HTML."""
    return f"""
    <div style="background:#fff;border-radius:8px;padding:20px 24px;
                box-shadow:0 2px 8px rgba(0,0,0,.08);text-align:center;
                border-top:4px solid {color};flex:1;min-width:160px;">
      <div style="font-size:13px;color:#666;font-weight:600;
                  text-transform:uppercase;letter-spacing:.5px;">{label}</div>
      <div style="font-size:28px;font-weight:700;color:#1a1a2e;margin-top:6px;">{value}</div>
    </div>"""


def build_html(df: pd.DataFrame) -> str:
    """
    Assemble the full dashboard HTML with quarter-filter dropdown.
    All charts are rendered as divs; JavaScript swaps the Plotly JSON
    when the user changes the dropdown selection.
    """
    quarters = ["Full Year", "Q1", "Q2", "Q3", "Q4"]
    chart_data: dict[str, dict] = {}

    for q in quarters:
        subset = df if q == "Full Year" else df[df["quarter"] == q]
        if subset.empty:
            # Placeholder for quarters with no data
            empty = go.Figure()
            empty.update_layout(title="No data for this period")
            chart_data[q] = {
                "region": empty.to_json(),
                "monthly": empty.to_json(),
                "category": empty.to_json(),
                "top_products": empty.to_json(),
                "total_revenue": "$0",
                "total_orders": "0",
                "avg_order": "$0",
                "top_region": "—",
            }
            continue

        total_rev = subset["revenue"].sum()
        total_orders = len(subset)
        avg_order = total_rev / total_orders if total_orders else 0
        top_region = (
            subset.groupby("region")["revenue"].sum().idxmax()
            if not subset.empty else "—"
        )

        chart_data[q] = {
            "region":       build_region_bar(subset).to_json(),
            "monthly":      build_monthly_line(subset).to_json(),
            "category":     build_category_pie(subset).to_json(),
            "top_products": build_top_products(subset).to_json(),
            "total_revenue": f"${total_rev:,.0f}",
            "total_orders":  f"{total_orders:,}",
            "avg_order":     f"${avg_order:,.0f}",
            "top_region":    top_region,
        }

    # Serialize all chart data to embed in HTML
    import json
    chart_json = json.dumps(chart_data)
    plotly_js = get_plotlyjs()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>ISYS 573 · Retail Sales Dashboard</title>
  <script>{plotly_js}</script>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0;}}
    :root{{
      color-scheme:light dark;
    }}
    body{{
      --bg:#f4f6f9;
      --surface:#fff;
      --surface-strong:#f9fbfd;
      --text:#1a1a2e;
      --muted:#666;
      --subtle:#8DA9C4;
      --border:#e0e6ed;
      --shadow:0 2px 8px rgba(0,0,0,.07);
      --focus:#2196F3;
      font-family:'Segoe UI',Arial,sans-serif;
      background:var(--bg);
      color:var(--text);
      transition:background .2s ease,color .2s ease;
    }}
    body[data-theme="dark"]{{
      --bg:#111827;
      --surface:#1f2937;
      --surface-strong:#273449;
      --text:#f3f4f6;
      --muted:#cbd5e1;
      --subtle:#bfdbfe;
      --border:#374151;
      --shadow:0 2px 12px rgba(0,0,0,.28);
      --focus:#60A5FA;
    }}
    header{{background:linear-gradient(135deg,#0D1B2A 0%,#1E3A5F 100%);
            color:#fff;padding:24px 32px;display:flex;
            align-items:center;justify-content:space-between;}}
    header h1{{font-size:22px;font-weight:700;}}
    header p{{font-size:13px;color:var(--subtle);margin-top:4px;}}
    .header-meta{{font-size:12px;color:var(--subtle);text-align:right;}}
    .filter-bar{{background:var(--surface);padding:14px 32px;
                 border-bottom:1px solid var(--border);
                 display:flex;align-items:center;gap:16px;flex-wrap:wrap;}}
    .filter-bar label{{font-size:14px;font-weight:600;color:var(--text);}}
    .filter-group{{display:flex;align-items:center;gap:10px;}}
    .filter-status{{font-size:13px;color:var(--muted);margin-left:8px;}}
    select{{padding:8px 14px;border:1.5px solid #cdd8e3;border-radius:6px;
            font-size:14px;background:var(--surface-strong);cursor:pointer;
            color:var(--text);}}
    select:focus{{outline:none;border-color:var(--focus);}}
    .theme-toggle{{margin-left:auto;padding:8px 14px;border:1.5px solid var(--border);
                   border-radius:6px;background:var(--surface-strong);color:var(--text);
                   cursor:pointer;font-size:14px;font-weight:600;}}
    .theme-toggle:hover{{border-color:var(--focus);}}
    .theme-toggle:focus{{outline:2px solid var(--focus);outline-offset:2px;}}
    .kpis{{display:flex;gap:16px;flex-wrap:wrap;padding:24px 32px 8px;}}
    .kpi-card{{background:var(--surface);border-radius:8px;padding:18px 22px;
               box-shadow:var(--shadow);text-align:center;border-top:4px solid;
               flex:1;min-width:150px;}}
    .kpi-label{{font-size:12px;color:var(--muted);font-weight:600;
                text-transform:uppercase;letter-spacing:.4px;}}
    .kpi-value{{font-size:26px;font-weight:700;color:var(--text);margin-top:5px;}}
    .charts-grid{{display:grid;
                  grid-template-columns:1fr 1fr;
                  gap:20px;padding:16px 32px 32px;}}
    .chart-card{{background:var(--surface);border-radius:10px;
                 padding:8px;box-shadow:var(--shadow);}}
    @media(max-width:800px){{
      header{{align-items:flex-start;gap:14px;flex-direction:column;}}
      .header-meta{{text-align:left;}}
      .charts-grid{{grid-template-columns:1fr;}}
      .theme-toggle{{margin-left:0;}}
    }}
    footer{{text-align:center;padding:16px;font-size:12px;color:var(--muted);
            border-top:1px solid var(--border);background:var(--surface);}}
  </style>
</head>
<body data-theme="light">

<header>
  <div>
    <h1>🛒 Retail Sales Dashboard</h1>
    <p>ISYS 573 · Generative AI and LLMs for Business · SFSU</p>
  </div>
  <div class="header-meta">
    Data: 2024 Retail Sales<br>500 transactions · 4 regions · 6 categories
  </div>
</header>

<div class="filter-bar">
  <div class="filter-group">
    <label for="qFilter">📅 Filter by Quarter:</label>
    <select id="qFilter" onchange="applyFilter(this.value)">
      {"".join(f'<option value="{q}">{q}</option>' for q in quarters)}
    </select>
    <span id="filterLabel" class="filter-status"></span>
  </div>
  <button class="theme-toggle" id="themeToggle" type="button"
          aria-label="Switch to dark mode" aria-pressed="false"
          onclick="toggleTheme()">Dark mode</button>
</div>

<div class="kpis" id="kpiRow"></div>

<div class="charts-grid">
  <div class="chart-card"><div id="chartRegion"  style="height:340px;"></div></div>
  <div class="chart-card"><div id="chartMonthly" style="height:340px;"></div></div>
  <div class="chart-card"><div id="chartCategory"    style="height:340px;"></div></div>
  <div class="chart-card"><div id="chartTopProducts" style="height:340px;"></div></div>
</div>

<footer>
  Built with Python · Pandas · Plotly &nbsp;|&nbsp;
  ISYS 573 AugOps Demo &nbsp;|&nbsp;
  github.com/[your-handle]/isys573-sales-dashboard
</footer>

<script>
const DATA = {chart_json};

const KPI_COLORS = ["#2196F3","#4CAF50","#FF9800","#9C27B0"];
const KPI_LABELS = ["Total Revenue","Transactions","Avg Transaction","Top Region"];
const KPI_KEYS   = ["total_revenue","total_orders","avg_order","top_region"];
const THEME_COLORS = {{
  light: {{
    paper: "#fff",
    plot: "#fff",
    text: "#1a1a2e",
    grid: "#e5e7eb",
    zero: "#d1d5db"
  }},
  dark: {{
    paper: "#1f2937",
    plot: "#1f2937",
    text: "#f3f4f6",
    grid: "#374151",
    zero: "#4b5563"
  }}
}};

let currentTheme = "light";

function themedAxis(axis, colors) {{
  return {{
    ...axis,
    color: colors.text,
    gridcolor: colors.grid,
    linecolor: colors.zero,
    zerolinecolor: colors.zero,
    title: {{
      ...(axis && axis.title ? axis.title : {{}}),
      font: {{color: colors.text}}
    }}
  }};
}}

function themeLayout(layout) {{
  const colors = THEME_COLORS[currentTheme];
  return {{
    ...layout,
    paper_bgcolor: colors.paper,
    plot_bgcolor: colors.plot,
    font: {{...(layout.font || {{}}), color: colors.text}},
    title: {{
      ...(layout.title || {{}}),
      font: {{...((layout.title || {{}}).font || {{}}), color: colors.text}}
    }},
    legend: {{
      ...(layout.legend || {{}}),
      font: {{...((layout.legend || {{}}).font || {{}}), color: colors.text}}
    }},
    xaxis: themedAxis(layout.xaxis || {{}}, colors),
    yaxis: themedAxis(layout.yaxis || {{}}, colors)
  }};
}}

function renderChart(elementId, chartJson) {{
  const figure = JSON.parse(chartJson);
  Plotly.react(elementId, figure.data, themeLayout(figure.layout), {{responsive:true}});
}}

function applyFilter(quarter) {{
  const d = DATA[quarter];

  // KPI cards
  const kpiRow = document.getElementById("kpiRow");
  kpiRow.innerHTML = KPI_KEYS.map((k,i) => `
    <div class="kpi-card" style="border-top-color:${{KPI_COLORS[i]}};">
      <div class="kpi-label">${{KPI_LABELS[i]}}</div>
      <div class="kpi-value">${{d[k]}}</div>
    </div>`).join("");

  // Charts
  renderChart("chartRegion", d.region);
  renderChart("chartMonthly", d.monthly);
  renderChart("chartCategory", d.category);
  renderChart("chartTopProducts", d.top_products);

  document.getElementById("filterLabel").textContent =
    quarter === "Full Year" ? "Showing all 2024 data" : `Showing ${{quarter}} 2024 only`;
}}

function setTheme(theme) {{
  currentTheme = theme;
  document.body.dataset.theme = theme;

  const toggle = document.getElementById("themeToggle");
  const isDark = theme === "dark";
  toggle.textContent = isDark ? "Light mode" : "Dark mode";
  toggle.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
  toggle.setAttribute("aria-pressed", String(isDark));

  applyFilter(document.getElementById("qFilter").value);
}}

function toggleTheme() {{
  setTheme(currentTheme === "dark" ? "light" : "dark");
}}

// Initialise on load
setTheme("light");
</script>
</body>
</html>"""
    return html


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ISYS 573 Sales Dashboard")
    parser.add_argument("--data",   default=str(DATA_PATH), help="Path to sales CSV")
    parser.add_argument("--output", default="dashboard.html", help="Output HTML file")
    args = parser.parse_args()

    print(f"Loading data from {args.data} …")
    df = load_data(Path(args.data))
    print(f"  {len(df)} rows · {df['region'].nunique()} regions · "
          f"{df['category'].nunique()} categories")

    print("Building dashboard …")
    html = build_html(df)

    out = Path(args.output)
    out.write_text(html, encoding="utf-8")
    print(f"✅  Dashboard saved → {out.resolve()}")
    print(f"   Open in browser: file://{out.resolve()}")


if __name__ == "__main__":
    main()
