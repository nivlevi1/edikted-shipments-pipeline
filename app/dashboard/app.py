import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import requests
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
DB_CONN = os.getenv(
    "POSTGRES_CONN",
    "postgresql://postgres:postgres@postgres:5432/warehouse",
)
API_BASE = os.getenv("API_BASE", "http://api:7654")

st.set_page_config(
    page_title="Edikted Shipments",
    layout="wide",
    page_icon="📦",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
[data-testid="metric-container"] {
    background: rgba(124, 58, 237, 0.08);
    border-radius: 12px;
    padding: 0.75rem 1rem;
    border: 1px solid rgba(124, 58, 237, 0.25);
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.6rem;
    font-weight: 700;
}
.section-header {
    border-left: 4px solid #7C3AED;
    padding-left: 12px;
    margin: 1.5rem 0 0.5rem 0;
    font-size: 1.3rem;
    font-weight: 700;
}
.winner-badge {
    background: linear-gradient(135deg, #7C3AED 0%, #EC4899 100%);
    border-radius: 10px;
    padding: 0.75rem 1.25rem;
    color: white;
    font-size: 1.1rem;
    font-weight: 600;
    display: inline-block;
    margin-bottom: 1rem;
}
[data-testid="stDownloadButton"] button {
    border-radius: 8px;
    font-size: 0.8rem;
    padding: 0.25rem 0.75rem;
}
</style>
""",
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def query(sql: str, params=None) -> pd.DataFrame:
    with psycopg2.connect(DB_CONN) as conn:
        return pd.read_sql(sql, conn, params=params)


def dl_btn(df: pd.DataFrame, filename: str, key: str):
    st.download_button(
        f"⬇ {filename}",
        df.to_csv(index=False).encode(),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


def sql_expander(sql: str, caption: str = ""):
    with st.expander("🔍 SQL"):
        if caption:
            st.caption(caption)
        st.code(sql.strip(), language="sql")


def fmt_num(v, prefix="", suffix=""):
    """Abbreviate large numbers for compact display."""
    v = float(v)
    if abs(v) >= 1_000_000:
        return f"{prefix}{v/1_000_000:.2f}M{suffix}"
    if abs(v) >= 1_000:
        return f"{prefix}{v/1_000:.1f}K{suffix}"
    return f"{prefix}{v:.2f}{suffix}"


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — global filters
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎛 Filters")

    # ── Date range ────────────────────────────────────────────────────────────
    date_bounds = query(
        'SELECT MIN("date")::text AS mn, MAX("date")::text AS mx '
        'FROM fact.fact_shipments WHERE "date" IS NOT NULL'
    )
    min_d = pd.to_datetime(date_bounds.iloc[0, 0]).date()
    max_d = pd.to_datetime(date_bounds.iloc[0, 1]).date()

    date_range = st.date_input(
        "📅 Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d
    )
    start_d = date_range[0] if len(date_range) == 2 else min_d
    end_d = date_range[1] if len(date_range) == 2 else max_d

    # ── Carriers ──────────────────────────────────────────────────────────────
    all_carriers_df = query(
        "SELECT DISTINCT carrier FROM fact.fact_shipments "
        "WHERE carrier IS NOT NULL ORDER BY carrier"
    )
    all_carriers = all_carriers_df["carrier"].tolist()
    selected_carriers = st.multiselect(
        "🚚 Carriers", all_carriers, default=all_carriers, key="sidebar_carriers"
    )
    if not selected_carriers:
        selected_carriers = all_carriers

    # ── Services ──────────────────────────────────────────────────────────────
    all_services_df = query(
        "SELECT DISTINCT service FROM fact.fact_shipments "
        "WHERE service IS NOT NULL ORDER BY service"
    )
    all_services = all_services_df["service"].tolist()
    selected_services = st.multiselect(
        "📦 Services", all_services, default=[], key="sidebar_services",
        placeholder="All services",
    )

    # ── Countries ─────────────────────────────────────────────────────────────
    all_countries_df = query(
        "SELECT receiver_country, COUNT(*) AS n FROM fact.fact_shipments "
        "WHERE receiver_country IS NOT NULL "
        "GROUP BY receiver_country ORDER BY n DESC LIMIT 30"
    )
    all_countries = all_countries_df["receiver_country"].tolist()
    selected_countries = st.multiselect(
        "🌍 Destination Country", all_countries, default=[], key="sidebar_countries",
        placeholder="All countries",
    )

    # ── Weight range ──────────────────────────────────────────────────────────
    weight_bounds = query(
        "SELECT FLOOR(MIN(weight_billable))::int AS mn, "
        "CEIL(MAX(weight_billable))::int AS mx "
        "FROM fact.fact_shipments WHERE weight_billable IS NOT NULL"
    )
    w_min = int(weight_bounds.iloc[0, 0])
    w_max = int(weight_bounds.iloc[0, 1])
    weight_range = st.slider(
        "⚖ Billable Weight (lbs)", w_min, w_max, (w_min, w_max), key="sidebar_weight"
    )

    # ── Charge range ──────────────────────────────────────────────────────────
    charge_bounds = query(
        "SELECT FLOOR(MIN(total_charge))::int AS mn, "
        "CEIL(MAX(total_charge))::int AS mx "
        "FROM fact.fact_shipments WHERE total_charge IS NOT NULL AND total_charge >= 0"
    )
    c_min = int(charge_bounds.iloc[0, 0])
    c_max = int(charge_bounds.iloc[0, 1])
    charge_range = st.slider(
        "💵 Total Charge ($)", c_min, c_max, (c_min, c_max), key="sidebar_charge"
    )

    # ── Summary + refresh ────────────────────────────────────────────────────
    st.divider()
    active_days = (end_d - start_d).days + 1
    active_filters = sum([
        len(selected_services) > 0,
        len(selected_countries) > 0,
        weight_range != (w_min, w_max),
        charge_range != (c_min, c_max),
    ])
    st.caption(
        f"**{len(selected_carriers)}** / {len(all_carriers)} carriers  \n"
        f"**{active_days:,}** day window  \n"
        f"**{active_filters}** extra filter(s) active"
    )
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Filter builder
# ─────────────────────────────────────────────────────────────────────────────
def build_where(
    extra_conds: list | None = None,
    extra_params: list | None = None,
) -> tuple[str, tuple]:
    conds: list[str] = ['"date" BETWEEN %s::date AND %s::date']
    params: list = [str(start_d), str(end_d)]

    if len(selected_carriers) < len(all_carriers):
        ph = ",".join(["%s"] * len(selected_carriers))
        conds.append(f"carrier IN ({ph})")
        params.extend(selected_carriers)

    if selected_services:
        ph = ",".join(["%s"] * len(selected_services))
        conds.append(f"service IN ({ph})")
        params.extend(selected_services)

    if selected_countries:
        ph = ",".join(["%s"] * len(selected_countries))
        conds.append(f"receiver_country IN ({ph})")
        params.extend(selected_countries)

    if weight_range != (w_min, w_max):
        conds.append("weight_billable BETWEEN %s AND %s")
        params.extend([weight_range[0], weight_range[1]])

    if charge_range != (c_min, c_max):
        conds.append("total_charge BETWEEN %s AND %s")
        params.extend([charge_range[0], charge_range[1]])

    if extra_conds:
        conds.extend(extra_conds)
    if extra_params:
        params.extend(extra_params)

    return "WHERE " + " AND ".join(conds), tuple(params)


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    '<h1 style="color:#ff71bb;">📦 Edikted Shipments Analytics</h1>',
    unsafe_allow_html=True,
)
st.caption(
    f"Window: **{start_d}** → **{end_d}**  ·  "
    f"Carriers: **{', '.join(selected_carriers[:3])}{'…' if len(selected_carriers) > 3 else ''}**"
)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard", "🔌 API Explorer", "🔍 Data Explorer", "📚 Data Catalog", "💻 SQL Editor"])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Dashboard
# ─────────────────────────────────────────────────────────────────────────────
with tab1:

    # ── KPI Hero ──────────────────────────────────────────────────────────────
    where_kpi, p_kpi = build_where(
        extra_conds=["carrier IS NOT NULL", "total_charge IS NOT NULL",
                     "weight_billable IS NOT NULL"]
    )
    kpi = query(
        f"""
        SELECT
            COUNT(*)                                      AS total_shipments,
            ROUND(SUM(total_charge)::numeric, 2)          AS total_revenue,
            ROUND(SUM(weight_billable)::numeric, 2)       AS total_weight,
            COUNT(DISTINCT carrier)                       AS carriers
        FROM fact.fact_shipments {where_kpi}
        """,
        p_kpi,
    )
    k = kpi.iloc[0]
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    col_k1.metric("Total Shipments", f"{int(k['total_shipments']):,}")
    col_k2.metric("Total Revenue", fmt_num(k["total_revenue"], prefix="$"))
    col_k3.metric("Total Weight", fmt_num(k["total_weight"], suffix=" lbs"))
    col_k4.metric("Active Carriers", int(k["carriers"]))

    # ── Monthly Trend ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📈 Shipment Trend</div>', unsafe_allow_html=True)

    granularity = st.radio(
        "Granularity", ["Day", "Week", "Month"], horizontal=True, index=2, key="trend_gran"
    )
    trunc = {"Day": "day", "Week": "week", "Month": "month"}[granularity]

    where_t, p_t = build_where(extra_conds=['"date" IS NOT NULL', "total_charge IS NOT NULL"])
    trend = query(
        f"""
        SELECT
            DATE_TRUNC('{trunc}', "date")::date::text AS period,
            COUNT(*)                                   AS shipments,
            ROUND(SUM(total_charge)::numeric, 2)       AS revenue
        FROM fact.fact_shipments {where_t}
        GROUP BY DATE_TRUNC('{trunc}', "date")
        ORDER BY 1
        """,
        p_t,
    )

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=trend["period"], y=trend["shipments"], name="Shipments",
        mode="lines+markers", yaxis="y1",
        line=dict(color="#7C3AED", width=2), marker=dict(size=5),
    ))
    fig_trend.add_trace(go.Bar(
        x=trend["period"], y=trend["revenue"], name="Revenue ($)",
        yaxis="y2", opacity=0.35, marker_color="#EC4899",
    ))
    fig_trend.update_layout(
        yaxis=dict(title="Shipments"),
        yaxis2=dict(title="Revenue ($)", overlaying="y", side="right"),
        legend=dict(orientation="h", y=-0.15),
        hovermode="x unified", margin=dict(t=10),
    )
    st.plotly_chart(fig_trend, use_container_width=True)
    sql_expander(
        f"""
SELECT
    DATE_TRUNC('{trunc}', "date")::date AS period,
    COUNT(*)                             AS shipments,
    ROUND(SUM(total_charge)::numeric, 2) AS revenue
FROM fact.fact_shipments
WHERE "date" BETWEEN '{start_d}' AND '{end_d}'
GROUP BY DATE_TRUNC('{trunc}', "date")
ORDER BY 1
        """,
        f"Grouped by {granularity.lower()}. Change radio above to switch granularity.",
    )

    # ── Weekday Heatmap ───────────────────────────────────────────────────────
    st.markdown('<div class="section-header">🗓 Shipment Heatmap (Weekday × Month)</div>', unsafe_allow_html=True)

    where_h, p_h = build_where(extra_conds=['"date" IS NOT NULL'])
    heat = query(
        f"""
        SELECT
            EXTRACT(DOW FROM "date")::int   AS dow,
            EXTRACT(MONTH FROM "date")::int AS month,
            COUNT(*)                        AS shipments
        FROM fact.fact_shipments {where_h}
        GROUP BY 1, 2
        """,
        p_h,
    )
    dow_map = {0:"Sun",1:"Mon",2:"Tue",3:"Wed",4:"Thu",5:"Fri",6:"Sat"}
    mon_map = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
               7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    heat["day_name"]   = heat["dow"].map(dow_map)
    heat["month_name"] = heat["month"].map(mon_map)
    pivot = heat.pivot_table(index="day_name", columns="month_name", values="shipments", fill_value=0)
    day_order = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    mon_order = [m for m in ["Jan","Feb","Mar","Apr","May","Jun",
                              "Jul","Aug","Sep","Oct","Nov","Dec"] if m in pivot.columns]
    pivot = pivot.reindex(
        index=[d for d in day_order if d in pivot.index], columns=mon_order
    )
    fig_heat = px.imshow(
        pivot, color_continuous_scale="Purples", aspect="auto",
        text_auto=True,
        labels=dict(color="Shipments"),
        title="Shipments by Weekday × Month",
    )
    fig_heat.update_traces(textfont_size=11)
    fig_heat.update_layout(margin=dict(t=40))
    st.plotly_chart(fig_heat, use_container_width=True)
    sql_expander(
        f"""
SELECT
    EXTRACT(DOW FROM "date")::int   AS dow,   -- 0=Sun … 6=Sat
    EXTRACT(MONTH FROM "date")::int AS month,
    COUNT(*)                        AS shipments
FROM fact.fact_shipments
WHERE "date" BETWEEN '{start_d}' AND '{end_d}'
GROUP BY 1, 2
        """
    )

    st.divider()

    # ── Q1: Top 3 Dates ───────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Q1 — Top 3 Dates</div>', unsafe_allow_html=True)

    where_q1,  p_q1  = build_where(extra_conds=['"date" IS NOT NULL'])
    where_q1v, p_q1v = build_where(extra_conds=['"date" IS NOT NULL', "total_charge IS NOT NULL"])
    where_q1w, p_q1w = build_where(extra_conds=['"date" IS NOT NULL', "weight_billable IS NOT NULL"])

    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("A · Most Shipments")
        df_q1a = query(
            f'SELECT "date"::text AS date, COUNT(*) AS shipments '
            f'FROM fact.fact_shipments {where_q1} '
            f'GROUP BY "date" ORDER BY shipments DESC LIMIT 3', p_q1)
        st.dataframe(df_q1a, hide_index=True, use_container_width=True)
        dl_btn(df_q1a, "top3_shipments.csv", "dl_q1a")
        sql_expander(
            f"""
SELECT "date", COUNT(*) AS shipments
FROM fact.fact_shipments
WHERE "date" BETWEEN '{start_d}' AND '{end_d}'
GROUP BY "date"
ORDER BY shipments DESC
LIMIT 3
            """
        )

    with c2:
        st.subheader("B · Most Value")
        df_q1b = query(
            f'SELECT "date"::text AS date, ROUND(SUM(total_charge)::numeric,2) AS total_charge '
            f'FROM fact.fact_shipments {where_q1v} '
            f'GROUP BY "date" ORDER BY total_charge DESC LIMIT 3', p_q1v)
        st.dataframe(df_q1b, hide_index=True, use_container_width=True)
        dl_btn(df_q1b, "top3_value.csv", "dl_q1b")
        sql_expander(
            f"""
SELECT "date", ROUND(SUM(total_charge)::numeric, 2) AS total_charge
FROM fact.fact_shipments
WHERE "date" BETWEEN '{start_d}' AND '{end_d}'
  AND total_charge IS NOT NULL
GROUP BY "date"
ORDER BY total_charge DESC
LIMIT 3
            """
        )

    with c3:
        st.subheader("C · Heaviest")
        df_q1c = query(
            f'SELECT "date"::text AS date, ROUND(SUM(weight_billable)::numeric,2) AS total_weight_lbs '
            f'FROM fact.fact_shipments {where_q1w} '
            f'GROUP BY "date" ORDER BY total_weight_lbs DESC LIMIT 3', p_q1w)
        st.dataframe(df_q1c, hide_index=True, use_container_width=True)
        dl_btn(df_q1c, "top3_weight.csv", "dl_q1c")
        sql_expander(
            f"""
SELECT "date", ROUND(SUM(weight_billable)::numeric, 2) AS total_weight_lbs
FROM fact.fact_shipments
WHERE "date" BETWEEN '{start_d}' AND '{end_d}'
  AND weight_billable IS NOT NULL
GROUP BY "date"
ORDER BY total_weight_lbs DESC
LIMIT 3
            """
        )

    st.divider()

    # ── Q2: Top 3 Cities × Top 3 Dates ───────────────────────────────────────
    st.markdown('<div class="section-header">Q2 — Top 3 Cities × Top 3 Dates</div>', unsafe_allow_html=True)
    st.caption("Cities ranked by total_charge; per-city breakdown mirrors Q1 A/B/C")

    where_city, p_city = build_where(
        extra_conds=["receiver_city IS NOT NULL", "total_charge IS NOT NULL"]
    )
    top_cities_df = query(
        f'SELECT receiver_city, ROUND(SUM(total_charge)::numeric,2) AS total_charge '
        f'FROM fact.fact_shipments {where_city} '
        f'GROUP BY receiver_city ORDER BY total_charge DESC LIMIT 3', p_city)

    sql_expander(
        f"""
-- Step 1: rank cities by total charge
SELECT receiver_city, ROUND(SUM(total_charge)::numeric, 2) AS total_charge
FROM fact.fact_shipments
WHERE "date" BETWEEN '{start_d}' AND '{end_d}'
  AND receiver_city IS NOT NULL AND total_charge IS NOT NULL
GROUP BY receiver_city
ORDER BY total_charge DESC
LIMIT 3

-- Step 2: for each city, run Q1 A/B/C with AND receiver_city = '<city>'
        """
    )

    for _, row in top_cities_df.iterrows():
        city = row["receiver_city"]
        st.subheader(f"🏙 {city}  —  ${float(row['total_charge']):,.2f}")
        ca, cb, cc = st.columns(3)

        where_ca, p_ca = build_where(extra_conds=['"date" IS NOT NULL', "receiver_city = %s"], extra_params=[city])
        where_cb, p_cb = build_where(extra_conds=['"date" IS NOT NULL', "total_charge IS NOT NULL", "receiver_city = %s"], extra_params=[city])
        where_cc, p_cc = build_where(extra_conds=['"date" IS NOT NULL', "weight_billable IS NOT NULL", "receiver_city = %s"], extra_params=[city])

        with ca:
            df = query(f'SELECT "date"::text AS date, COUNT(*) AS shipments FROM fact.fact_shipments {where_ca} GROUP BY "date" ORDER BY shipments DESC LIMIT 3', p_ca)
            st.caption("A · Most shipments")
            st.dataframe(df, hide_index=True, use_container_width=True)
        with cb:
            df = query(f'SELECT "date"::text AS date, ROUND(SUM(total_charge)::numeric,2) AS total_charge FROM fact.fact_shipments {where_cb} GROUP BY "date" ORDER BY total_charge DESC LIMIT 3', p_cb)
            st.caption("B · Most value")
            st.dataframe(df, hide_index=True, use_container_width=True)
        with cc:
            df = query(f'SELECT "date"::text AS date, ROUND(SUM(weight_billable)::numeric,2) AS total_weight_lbs FROM fact.fact_shipments {where_cc} GROUP BY "date" ORDER BY total_weight_lbs DESC LIMIT 3', p_cc)
            st.caption("C · Heaviest")
            st.dataframe(df, hide_index=True, use_container_width=True)

    st.divider()

    # ── Q3: Charges vs Weight per Carrier ────────────────────────────────────
    st.markdown('<div class="section-header">Q3 — Total Charges vs Total Weight per Carrier</div>', unsafe_allow_html=True)

    where_q3, p_q3 = build_where(extra_conds=["carrier IS NOT NULL"])
    df_q3 = query(
        f"""
        SELECT carrier,
               ROUND(SUM(total_charge)::numeric,2)    AS total_charge,
               ROUND(SUM(weight_billable)::numeric,2) AS total_weight_lbs
        FROM fact.fact_shipments {where_q3}
        GROUP BY carrier ORDER BY total_charge DESC NULLS LAST
        """, p_q3)

    # Scatter (left) + % share grouped bar (right — replaces dual-axis)
    col_sc, col_sh = st.columns(2)
    with col_sc:
        fig_sc = px.scatter(
            df_q3, x="total_weight_lbs", y="total_charge",
            text="carrier", color="carrier", size="total_charge",
            title="Charges vs Billable Weight",
            labels={"total_weight_lbs": "Total Weight (lbs)", "total_charge": "Total Charge ($)"},
            color_discrete_sequence=px.colors.qualitative.Vivid,
        )
        fig_sc.update_traces(textposition="top center")
        fig_sc.update_layout(showlegend=False, margin=dict(t=40))
        st.plotly_chart(fig_sc, use_container_width=True)

    with col_sh:
        df_pct = df_q3.copy()
        df_pct["charge_pct"] = df_pct["total_charge"] / df_pct["total_charge"].sum() * 100
        df_pct["weight_pct"] = df_pct["total_weight_lbs"] / df_pct["total_weight_lbs"].sum() * 100
        df_pct_sorted = df_pct.sort_values("charge_pct", ascending=False)
        fig_pct = go.Figure()
        fig_pct.add_trace(go.Scatter(
            x=df_pct_sorted["carrier"], y=df_pct_sorted["charge_pct"].round(1),
            name="% of Total Charge", mode="lines+markers+text",
            line=dict(color="#7C3AED", width=2),
            marker=dict(size=9),
            text=df_pct_sorted["charge_pct"].map(lambda v: f"{v:.1f}%"),
            textposition="top center",
        ))
        fig_pct.add_trace(go.Scatter(
            x=df_pct_sorted["carrier"], y=df_pct_sorted["weight_pct"].round(1),
            name="% of Total Weight", mode="lines+markers+text",
            line=dict(color="#EC4899", width=2, dash="dot"),
            marker=dict(size=9),
            text=df_pct_sorted["weight_pct"].map(lambda v: f"{v:.1f}%"),
            textposition="bottom center",
        ))
        fig_pct.update_layout(
            title="Share of Total Charge vs Weight (%)",
            yaxis_title="% of Total",
            legend=dict(orientation="h", y=-0.2),
            margin=dict(t=40),
            hovermode="x unified",
        )
        st.plotly_chart(fig_pct, use_container_width=True)

    dl_btn(df_q3, "carrier_charge_weight.csv", "dl_q3")
    st.dataframe(df_q3, hide_index=True, use_container_width=True)
    sql_expander(
        f"""
SELECT
    carrier,
    ROUND(SUM(total_charge)::numeric, 2)    AS total_charge,
    ROUND(SUM(weight_billable)::numeric, 2) AS total_weight_lbs
FROM fact.fact_shipments
WHERE "date" BETWEEN '{start_d}' AND '{end_d}'
  AND carrier IS NOT NULL
GROUP BY carrier
ORDER BY total_charge DESC
        """,
        "% share chart: each metric divided by its column total × 100."
    )

    st.divider()

    # ── Q4: Highest Charge/Weight Ratio ──────────────────────────────────────
    st.markdown('<div class="section-header">Q4 — Highest Charge / Weight Ratio by Carrier & Service</div>', unsafe_allow_html=True)

    where_q4, p_q4 = build_where(
        extra_conds=["carrier IS NOT NULL", "service IS NOT NULL",
                     "total_charge IS NOT NULL", "weight_billable IS NOT NULL"]
    )
    df_q4 = query(
        f"""
        SELECT carrier, service,
               ROUND((SUM(total_charge)/NULLIF(SUM(weight_billable),0))::numeric,4) AS charge_per_lb,
               ROUND(SUM(total_charge)::numeric,2)    AS total_charge,
               ROUND(SUM(weight_billable)::numeric,2) AS total_weight_lbs,
               COUNT(*) AS shipments
        FROM fact.fact_shipments {where_q4}
        GROUP BY carrier, service
        HAVING SUM(weight_billable) > 0
        ORDER BY charge_per_lb DESC NULLS LAST
        """, p_q4)

    if not df_q4.empty:
        w = df_q4.iloc[0]
        st.markdown(
            f'<div class="winner-badge">🏆 {w["carrier"]} — {w["service"]} — '
            f'${float(w["charge_per_lb"]):.4f} / lb</div>',
            unsafe_allow_html=True,
        )

    col_r1, col_r2 = st.columns(2)

    with col_r1:
        # Heatmap: service × carrier, colored by $/lb — replaces cluttered bar chart
        top_svcs = df_q4.groupby("service")["shipments"].sum().nlargest(12).index
        df_q4_h = df_q4[df_q4["service"].isin(top_svcs)]
        pivot_q4 = df_q4_h.pivot_table(
            index="service", columns="carrier", values="charge_per_lb"
        ).round(2)
        fig_q4_heat = px.imshow(
            pivot_q4,
            color_continuous_scale="Purples",
            text_auto=".4f",
            title="$/lb by Service × Carrier (top 12 services)",
            labels={"color": "$/lb"},
            aspect="auto",
        )
        fig_q4_heat.update_traces(textfont_size=10)
        fig_q4_heat.update_layout(margin=dict(t=40))
        st.plotly_chart(fig_q4_heat, use_container_width=True)

    with col_r2:
        fig_tree = px.treemap(
            df_q4,
            path=["carrier", "service"],
            values="total_charge",
            color="charge_per_lb",
            color_continuous_scale="Purples",
            title="Revenue Breakdown — carrier → service (color = $/lb)",
            labels={"charge_per_lb": "$/lb", "total_charge": "Revenue ($)"},
            custom_data=["charge_per_lb", "shipments"],
        )
        fig_tree.update_traces(
            texttemplate=(
                "<b>%{label}</b><br>"
                "$%{value:,.0f}<br>"
                "%{customdata[0]:.4f} $/lb<br>"
                "%{customdata[1]:,} shipments"
            ),
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Revenue: $%{value:,.2f}<br>"
                "$/lb: %{customdata[0]:.4f}<br>"
                "Shipments: %{customdata[1]:,}<extra></extra>"
            ),
        )
        fig_tree.update_layout(margin=dict(t=40))
        st.plotly_chart(fig_tree, use_container_width=True)

    dl_btn(df_q4, "charge_weight_ratio.csv", "dl_q4")
    st.dataframe(df_q4.head(20), hide_index=True, use_container_width=True)
    sql_expander(
        f"""
SELECT
    carrier,
    service,
    ROUND(
        (SUM(total_charge) / NULLIF(SUM(weight_billable), 0))::numeric, 4
    )                                                    AS charge_per_lb,
    ROUND(SUM(total_charge)::numeric, 2)                 AS total_charge,
    ROUND(SUM(weight_billable)::numeric, 2)              AS total_weight_lbs,
    COUNT(*)                                             AS shipments
FROM fact.fact_shipments
WHERE "date" BETWEEN '{start_d}' AND '{end_d}'
  AND carrier IS NOT NULL AND service IS NOT NULL
  AND total_charge IS NOT NULL AND weight_billable IS NOT NULL
GROUP BY carrier, service
HAVING SUM(weight_billable) > 0
ORDER BY charge_per_lb DESC
        """,
        "Heatmap shows top 12 services by shipment volume. Treemap = revenue split."
    )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — API Explorer
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.header("🔌 REST API Explorer")
    st.markdown(
        f"Base: `{API_BASE}` (port **7654**)  ·  "
        "[Swagger UI →](http://localhost:7654/docs)"
    )

    st.subheader("/total_weight  _(required endpoint)_")
    col_a, col_b, col_c = st.columns([2, 2, 1])
    with col_a:
        sel_carrier = st.selectbox("carrier=", all_carriers, key="api_carrier")
    with col_b:
        # Default to the most recent date in the data, not today
        sel_date = st.date_input("date=", value=max_d, min_value=min_d, max_value=max_d, key="api_date")
    with col_c:
        st.markdown("<br>", unsafe_allow_html=True)
        call_btn = st.button("▶ GET")

    if call_btn:
        with st.spinner("Calling API…"):
            try:
                r = requests.get(
                    f"{API_BASE}/total_weight",
                    params={"carrier": sel_carrier, "date": str(sel_date)},
                    timeout=5,
                )
                st.code(r.text, language="json")
                st.caption(f"HTTP {r.status_code}  ·  {r.elapsed.total_seconds()*1000:.0f} ms")
            except Exception as e:
                st.error(f"Request failed: {e}")

    st.divider()

    st.subheader("Enriched Endpoints")
    endpoint = st.selectbox(
        "Endpoint",
        [
            "/carriers",
            "/carriers/{carrier}/summary",
            "/top-dates?metric=shipments&limit=3",
            "/top-dates?metric=value&limit=3",
            "/top-dates?metric=weight&limit=3",
            "/cities?limit=3",
            "/charge-weight-ratio?limit=10",
            "/health",
        ],
    )
    if "{carrier}" in endpoint:
        path_carrier = st.selectbox("carrier (path param)", all_carriers, key="path_carrier")
        endpoint = endpoint.replace("{carrier}", path_carrier)

    if st.button("▶ GET", key="enrich_get"):
        with st.spinner("Calling API…"):
            try:
                r = requests.get(f"{API_BASE}{endpoint}", timeout=5)
                st.code(r.text, language="json")
                st.caption(f"HTTP {r.status_code}  ·  {r.elapsed.total_seconds()*1000:.0f} ms")
            except Exception as e:
                st.error(f"Request failed: {e}")

    st.divider()
    st.subheader("Endpoint Reference")
    st.markdown(
        """
| Method | Path | Description |
|--------|------|-------------|
| GET | `/total_weight?carrier=X&date=YYYY-MM-DD` | **Required** — total billable weight + charge |
| GET | `/carriers` | All carriers with aggregate stats |
| GET | `/carriers/{carrier}/summary` | Per-carrier: avg, $/lb, date range, service count |
| GET | `/top-dates?metric=shipments\|value\|weight&limit=N` | Top N dates by metric |
| GET | `/cities?limit=N` | Top N cities by total charge |
| GET | `/charge-weight-ratio?limit=N` | Carrier × service ranked by $/lb |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI (auto-generated) |
"""
    )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Data Explorer
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.header("🔍 Data Explorer")

    # ── US State Map ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">🗺 Shipments by US State</div>', unsafe_allow_html=True)

    # No country filter — let choropleth match 2-letter codes naturally
    where_map, p_map = build_where(
        extra_conds=["receiver_state IS NOT NULL", "LENGTH(TRIM(receiver_state)) = 2"]
    )
    state_df = query(
        f"""
        SELECT UPPER(TRIM(receiver_state)) AS state,
               COUNT(*)                   AS shipments,
               ROUND(SUM(total_charge)::numeric, 2) AS total_charge
        FROM fact.fact_shipments {where_map}
        GROUP BY UPPER(TRIM(receiver_state))
        ORDER BY shipments DESC
        """,
        p_map,
    )

    if not state_df.empty:
        map_metric = st.radio("Color by", ["shipments", "total_charge"], horizontal=True)
        fig_map = px.choropleth(
            state_df,
            locations="state",
            locationmode="USA-states",
            color=map_metric,
            scope="usa",
            color_continuous_scale="Purples",
            hover_data=["shipments", "total_charge"],
            title=f"US Shipments by State — {map_metric}",
        )
        fig_map.update_layout(margin=dict(t=40, b=0))
        st.plotly_chart(fig_map, use_container_width=True)
        st.caption(f"{len(state_df)} states found. Only 2-letter US state codes shown.")
        sql_expander(
            f"""
SELECT UPPER(TRIM(receiver_state)) AS state,
       COUNT(*)                    AS shipments,
       ROUND(SUM(total_charge)::numeric, 2) AS total_charge
FROM fact.fact_shipments
WHERE "date" BETWEEN '{start_d}' AND '{end_d}'
  AND receiver_state IS NOT NULL
  AND LENGTH(TRIM(receiver_state)) = 2
GROUP BY UPPER(TRIM(receiver_state))
ORDER BY shipments DESC
            """
        )
    else:
        st.info("No 2-letter state codes found in current filter window.")
        # Debug: show distinct state values
        where_dbg, p_dbg = build_where(extra_conds=["receiver_state IS NOT NULL"])
        sample_states = query(
            f"SELECT DISTINCT receiver_state FROM fact.fact_shipments {where_dbg} LIMIT 20",
            p_dbg,
        )
        if not sample_states.empty:
            st.caption("Sample receiver_state values in data:")
            st.write(sample_states["receiver_state"].tolist())

    st.divider()

    # ── Carrier Comparison ────────────────────────────────────────────────────
    st.markdown('<div class="section-header">⚖ Carrier Comparison</div>', unsafe_allow_html=True)

    cmp_cols_sel = st.columns(2)
    with cmp_cols_sel[0]:
        carrier_a = st.selectbox("Carrier A", all_carriers, index=0, key="cmp_a")
    with cmp_cols_sel[1]:
        carrier_b = st.selectbox(
            "Carrier B", all_carriers, index=min(1, len(all_carriers) - 1), key="cmp_b"
        )

    def carrier_kpi(carrier: str) -> dict:
        where_c, p_c = build_where(
            extra_conds=["carrier = %s", "total_charge IS NOT NULL", "weight_billable IS NOT NULL"],
            extra_params=[carrier],
        )
        df = query(
            f"""
            SELECT
                COUNT(*)                                                              AS shipments,
                ROUND(SUM(total_charge)::numeric, 2)                                  AS revenue,
                ROUND(SUM(weight_billable)::numeric, 2)                               AS weight,
                ROUND(AVG(total_charge)::numeric, 2)                                  AS avg_charge,
                ROUND((SUM(total_charge)/NULLIF(SUM(weight_billable),0))::numeric, 4) AS charge_per_lb
            FROM fact.fact_shipments {where_c}
            """,
            p_c,
        )
        return df.iloc[0].to_dict()

    k_a, k_b = carrier_kpi(carrier_a), carrier_kpi(carrier_b)

    def delta_pct(a, b):
        try:
            d = (float(a) - float(b)) / abs(float(b)) * 100
            return f"{d:+.1f}%"
        except Exception:
            return None

    metrics = [
        ("Shipments", "shipments", ""),
        ("Revenue", "revenue", "$"),
        ("Weight (lbs)", "weight", ""),
        ("Avg Charge", "avg_charge", "$"),
        ("$/lb", "charge_per_lb", "$"),
    ]

    # Per-metric rows: label | A | B  — keeps columns aligned regardless of delta
    hdr_lbl, hdr_a, hdr_b = st.columns([2, 3, 3])
    hdr_lbl.write("")
    hdr_a.markdown(f"**{carrier_a}**")
    hdr_b.markdown(f"**{carrier_b}**")

    for label, key, prefix in metrics:
        val_a = float(k_a[key]) if k_a[key] is not None else 0
        val_b = float(k_b[key]) if k_b[key] is not None else 0
        col_lbl, col_a, col_b = st.columns([2, 3, 3])
        col_lbl.markdown(f"<br><small>{label}</small>", unsafe_allow_html=True)
        col_a.metric("", fmt_num(val_a, prefix=prefix), delta=delta_pct(k_a[key], k_b[key]))
        col_b.metric("", fmt_num(val_b, prefix=prefix))

    st.divider()

    # ── Filterable table ──────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📋 Browse Shipments</div>', unsafe_allow_html=True)

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        carrier_filter = st.selectbox("Carrier", ["All"] + all_carriers, key="exp_carrier")
    with col_f2:
        city_list = query(
            "SELECT DISTINCT receiver_city FROM fact.fact_shipments "
            "WHERE receiver_city IS NOT NULL ORDER BY receiver_city"
        )["receiver_city"].tolist()
        city_filter = st.selectbox("City", ["All"] + city_list)
    with col_f3:
        n_rows = st.slider("Rows", 10, 500, 100)

    extra_conds_exp: list[str] = []
    extra_params_exp: list = []
    if carrier_filter != "All":
        extra_conds_exp.append("carrier = %s")
        extra_params_exp.append(carrier_filter)
    if city_filter != "All":
        extra_conds_exp.append("receiver_city = %s")
        extra_params_exp.append(city_filter)

    where_exp, p_exp = build_where(
        extra_conds=extra_conds_exp or None,
        extra_params=extra_params_exp or None,
    )
    p_exp = p_exp + (n_rows,)

    df_exp = query(
        f"""
        SELECT
            "date", carrier, service,
            receiver_city, receiver_state, receiver_country,
            total_charge, weight_billable,
            join_order_id_fixed, tracking_number
        FROM fact.fact_shipments {where_exp}
        ORDER BY "date" DESC NULLS LAST
        LIMIT %s
        """,
        p_exp,
    )
    dl_btn(df_exp, "shipments_export.csv", "dl_exp")
    st.dataframe(df_exp, hide_index=True, use_container_width=True)
    st.caption(f"{len(df_exp):,} rows shown")


import time
import yaml

# ── Shared catalog loader (used by both tab4 and tab5) ────────────────────────
@st.cache_data(ttl=3600)
def load_catalog() -> dict:
    """
    Loads fact.fact_shipments from dbt schema.yml.
    Falls back to staging description for any column with no fact-level description.
    """
    def parse_model(path: str) -> dict:
        with open(path) as f:
            data = yaml.safe_load(f)
        result = {}
        for model in data.get("models", []):
            cols = {}
            for col in model.get("columns", []):
                raw_tests = col.get("tests", [])
                tests = [
                    t if isinstance(t, str) else list(t.keys())[0]
                    for t in raw_tests
                ]
                cols[col["name"]] = {
                    "column":      col["name"],
                    "description": (col.get("description") or "").strip(),
                    "tests":       ", ".join(tests),
                }
            result[model["name"]] = {
                "description": (model.get("description") or "").strip(),
                "columns":     cols,
            }
        return result

    try:
        stg = parse_model("/app/dbt_models/staging/schema.yml")
    except FileNotFoundError:
        stg = {}
    try:
        fact = parse_model("/app/dbt_models/fact/schema.yml")
    except FileNotFoundError:
        return {"error": "fact/schema.yml not found"}

    fact_model = fact.get("fact_shipments", {})
    stg_model  = stg.get("stg_shipments", {})

    # Merge: fact columns first; fill blank descriptions from staging
    merged_cols = {}
    for name, col in fact_model.get("columns", {}).items():
        desc = col["description"]
        if not desc and name in stg_model.get("columns", {}):
            desc = stg_model["columns"][name]["description"]
        merged_cols[name] = {**col, "description": desc}

    # Add staging-only columns that osmosis hasn't pushed yet (show with ⚠ tag)
    for name, col in stg_model.get("columns", {}).items():
        if name not in merged_cols:
            merged_cols[name] = {**col, "description": col["description"]}

    return {
        "model":       "fact_shipments",
        "schema":      "fact",
        "description": fact_model.get("description", ""),
        "columns":     list(merged_cols.values()),
    }


catalog = load_catalog()

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — Data Catalog
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="section-header">📚 Data Catalog — fact.fact_shipments</div>', unsafe_allow_html=True)

    if "error" in catalog:
        st.error(catalog["error"])
    else:
        with st.expander("Model description", expanded=False):
            st.markdown(catalog["description"] or "_No description_")

        cols_df = pd.DataFrame(catalog["columns"])

        search = st.text_input(
            "🔍 Filter columns", key="catalog_search",
            placeholder="column name or keyword in description…"
        )
        if search:
            mask = cols_df.apply(
                lambda r: search.lower() in r["column"].lower()
                       or search.lower() in r["description"].lower(),
                axis=1,
            )
            cols_df = cols_df[mask]

        st.caption(f"{len(cols_df)} of {len(catalog['columns'])} columns")
        st.dataframe(
            cols_df,
            hide_index=True,
            use_container_width=True,
            height=620,
            column_config={
                "column":      st.column_config.TextColumn("Column", width="medium"),
                "description": st.column_config.TextColumn("Description", width="large"),
                "tests":       st.column_config.TextColumn("Tests", width="small"),
            },
        )
        dl_btn(cols_df, "fact_shipments_catalog.csv", "dl_catalog")

        if st.button("📋 Open in SQL Editor → SELECT * FROM fact.fact_shipments"):
            st.session_state["sql_input"] = "SELECT *\nFROM fact.fact_shipments\nLIMIT 100;"
            st.info("Query loaded — switch to the 💻 SQL Editor tab to run it.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — SQL Editor
# ─────────────────────────────────────────────────────────────────────────────
with tab5:
    st.markdown('<div class="section-header">💻 SQL Editor</div>', unsafe_allow_html=True)
    st.caption("SELECT / WITH / EXPLAIN only · row cap enforced · connects to the same warehouse")

    SUGGESTIONS = {
        "💰 Revenue": [
            ("Top carriers by total revenue",
             "SELECT\n    carrier,\n    COUNT(*)                                      AS shipments,\n    ROUND(SUM(total_charge)::numeric, 2)          AS total_revenue,\n    ROUND(AVG(total_charge)::numeric, 2)          AS avg_charge_per_shipment\nFROM fact.fact_shipments\nWHERE carrier IS NOT NULL\n  AND total_charge IS NOT NULL\nGROUP BY carrier\nORDER BY total_revenue DESC;"),
            ("Monthly revenue trend",
             "SELECT\n    DATE_TRUNC('month', \"date\")::date::text AS month,\n    COUNT(*)                               AS shipments,\n    ROUND(SUM(total_charge)::numeric, 2)   AS revenue\nFROM fact.fact_shipments\nWHERE \"date\" IS NOT NULL\n  AND total_charge IS NOT NULL\nGROUP BY DATE_TRUNC('month', \"date\")\nORDER BY 1;"),
            ("Revenue by source file",
             "SELECT\n    source_file,\n    COUNT(*)                               AS shipments,\n    ROUND(SUM(total_charge)::numeric, 2)   AS revenue,\n    ROUND(AVG(total_charge)::numeric, 2)   AS avg_charge\nFROM fact.fact_shipments\nWHERE source_file IS NOT NULL\nGROUP BY source_file\nORDER BY revenue DESC;"),
            ("Shipments with zero or negative charge",
             "SELECT\n    carrier, service, \"date\"::text AS date,\n    total_charge, weight_billable, tracking_number\nFROM fact.fact_shipments\nWHERE total_charge IS NOT NULL\n  AND total_charge <= 0\nORDER BY total_charge\nLIMIT 100;"),
        ],
        "⚖ Weight & Efficiency": [
            ("Charge per lb by carrier × service",
             "SELECT\n    carrier,\n    service,\n    ROUND(\n        (SUM(total_charge) / NULLIF(SUM(weight_billable), 0))::numeric, 4\n    )                                          AS charge_per_lb,\n    ROUND(SUM(total_charge)::numeric, 2)       AS total_charge,\n    ROUND(SUM(weight_billable)::numeric, 2)    AS total_weight_lbs,\n    COUNT(*)                                   AS shipments\nFROM fact.fact_shipments\nWHERE carrier IS NOT NULL AND service IS NOT NULL\n  AND total_charge IS NOT NULL AND weight_billable IS NOT NULL\nGROUP BY carrier, service\nHAVING SUM(weight_billable) > 0\nORDER BY charge_per_lb DESC;"),
            ("Top 10 heaviest individual shipments",
             "SELECT\n    \"date\"::text AS date, carrier, service,\n    weight_billable, total_charge,\n    receiver_city, receiver_country, tracking_number\nFROM fact.fact_shipments\nWHERE weight_billable IS NOT NULL\nORDER BY weight_billable DESC\nLIMIT 10;"),
            ("Weight distribution buckets per carrier",
             "SELECT\n    carrier,\n    CASE\n        WHEN weight_billable < 1   THEN '< 1 lb'\n        WHEN weight_billable < 5   THEN '1–5 lbs'\n        WHEN weight_billable < 20  THEN '5–20 lbs'\n        WHEN weight_billable < 70  THEN '20–70 lbs'\n        ELSE '70+ lbs'\n    END                                          AS weight_bucket,\n    COUNT(*)                                     AS shipments,\n    ROUND(AVG(total_charge)::numeric, 2)         AS avg_charge\nFROM fact.fact_shipments\nWHERE carrier IS NOT NULL AND weight_billable IS NOT NULL\nGROUP BY carrier, weight_bucket\nORDER BY carrier, MIN(weight_billable);"),
        ],
        "📅 Time": [
            ("Top 5 dates by shipment volume",
             "SELECT\n    \"date\"::text AS date,\n    COUNT(*)     AS shipments,\n    ROUND(SUM(total_charge)::numeric, 2) AS revenue\nFROM fact.fact_shipments\nWHERE \"date\" IS NOT NULL\nGROUP BY \"date\"\nORDER BY shipments DESC\nLIMIT 5;"),
            ("Shipments by day of week",
             "SELECT\n    TO_CHAR(\"date\", 'Day')        AS weekday,\n    EXTRACT(DOW FROM \"date\")::int AS dow_num,\n    COUNT(*)                      AS shipments,\n    ROUND(AVG(total_charge)::numeric, 2) AS avg_charge\nFROM fact.fact_shipments\nWHERE \"date\" IS NOT NULL\nGROUP BY TO_CHAR(\"date\", 'Day'), EXTRACT(DOW FROM \"date\")\nORDER BY dow_num;"),
        ],
        "🌍 Geography": [
            ("Top 10 destination cities by revenue",
             "SELECT\n    receiver_city, receiver_state,\n    COUNT(*)                                AS shipments,\n    ROUND(SUM(total_charge)::numeric, 2)    AS total_charge,\n    ROUND(AVG(weight_billable)::numeric, 2) AS avg_weight_lbs\nFROM fact.fact_shipments\nWHERE receiver_city IS NOT NULL\nGROUP BY receiver_city, receiver_state\nORDER BY total_charge DESC\nLIMIT 10;"),
            ("Shipments by destination country",
             "SELECT\n    receiver_country,\n    COUNT(*)                               AS shipments,\n    ROUND(SUM(total_charge)::numeric, 2)   AS total_charge\nFROM fact.fact_shipments\nWHERE receiver_country IS NOT NULL\nGROUP BY receiver_country\nORDER BY shipments DESC\nLIMIT 30;"),
        ],
        "🔍 Data Quality": [
            ("Null coverage across key columns",
             "SELECT\n    COUNT(*)               AS total_rows,\n    COUNT(carrier)         AS has_carrier,\n    COUNT(total_charge)    AS has_charge,\n    COUNT(weight_billable) AS has_weight,\n    COUNT(\"date\")          AS has_date,\n    COUNT(receiver_city)   AS has_city,\n    COUNT(order_id)        AS has_order_id,\n    COUNT(order_name)      AS has_order_name,\n    COUNT(tracking_number) AS has_tracking\nFROM fact.fact_shipments;"),
            ("Order ID vs order name coverage",
             "SELECT\n    CASE\n        WHEN order_id IS NOT NULL AND order_name IS NOT NULL THEN 'both'\n        WHEN order_id IS NOT NULL  THEN 'order_id only'\n        WHEN order_name IS NOT NULL THEN 'order_name only'\n        ELSE 'neither'\n    END           AS coverage,\n    COUNT(*)      AS shipments,\n    source_file\nFROM fact.fact_shipments\nGROUP BY coverage, source_file\nORDER BY shipments DESC;"),
            ("Duplicate tracking numbers",
             "SELECT\n    tracking_number,\n    COUNT(*)              AS occurrences,\n    MIN(\"date\")::text     AS first_date,\n    MAX(\"date\")::text     AS last_date,\n    COUNT(DISTINCT carrier) AS carriers\nFROM fact.fact_shipments\nWHERE tracking_number IS NOT NULL\nGROUP BY tracking_number\nHAVING COUNT(*) > 1\nORDER BY occurrences DESC\nLIMIT 20;"),
        ],
    }

    with st.expander("💡 Query Suggestions", expanded=True):
        for category, queries in SUGGESTIONS.items():
            st.markdown(f"**{category}**")
            btn_cols = st.columns(len(queries))
            for col_btn, (label, sql) in zip(btn_cols, queries):
                if col_btn.button(label, key=f"sug_{label[:30]}", use_container_width=True):
                    st.session_state["sql_input"] = sql

    sql_input = st.text_area(
        "Query",
        value=st.session_state.get("sql_input", "SELECT *\nFROM fact.fact_shipments\nLIMIT 100;"),
        height=220,
        key="sql_input",
        label_visibility="collapsed",
    )

    run_col, limit_col = st.columns([1, 3])
    with run_col:
        run_btn = st.button("▶ Run", type="primary")
    with limit_col:
        row_limit = st.slider("Row cap", 10, 5_000, 500, key="sql_limit")

    SAFE_STARTS = ("select", "with", "explain")

    def _safe(sql: str) -> bool:
        first = sql.strip().lower().lstrip("(").split()[0] if sql.strip() else ""
        return first in SAFE_STARTS

    if run_btn:
        if not _safe(sql_input):
            st.error("Only SELECT / WITH / EXPLAIN queries allowed.")
        else:
            wrapped = f"SELECT * FROM (\n{sql_input.rstrip(';')}\n) AS _q LIMIT {row_limit}"
            try:
                t0 = time.time()
                with psycopg2.connect(DB_CONN) as conn:
                    df_sql = pd.read_sql(wrapped, conn)
                elapsed = time.time() - t0

                st.success(
                    f"{len(df_sql):,} rows · {df_sql.shape[1]} cols · {elapsed*1000:.0f} ms"
                )
                st.dataframe(df_sql, hide_index=True, use_container_width=True, height=400)
                dl_btn(df_sql, "query_result.csv", "dl_sql")

                with st.expander("Executed SQL"):
                    st.code(wrapped, language="sql")
            except Exception as exc:
                st.error(f"```\n{exc}\n```")
