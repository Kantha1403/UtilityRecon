import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="UtilityRecon Dashboard", layout="wide")

st.title("UtilityRecon: Multi-Vendor Bill Validation & Reconciliation")
st.caption("Simulated revenue-ops pipeline — utility invoice ingestion, reconciliation, and anomaly detection")


@st.cache_data
def load_data():
    invoices = pd.read_csv(r"C:\Users\KL\OneDrive\Desktop\UtilityRecon\all_invoices_clean.csv")
    with open(r"C:\Users\KL\OneDrive\Desktop\UtilityRecon\kpi_summary.json", "r") as f:
        kpis = json.load(f)
    return invoices, kpis


def load_reconciliation_data():
    vendor_summary = pd.read_csv(r"C:\Users\KL\OneDrive\Desktop\UtilityRecon\vendor_summary.csv")
    return vendor_summary


invoices, kpis = load_data()
vendor_summary = load_reconciliation_data()

st.divider()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Invoices", f"{kpis['total_invoices']:,}")
col2.metric("Avg Daily Throughput", f"{kpis['avg_daily_throughput']:.0f}")
col3.metric("Exception Rate", f"{kpis['error_rate_pct']}%")
col4.metric("SLA On-Time Rate", f"{kpis['sla_on_time_pct']}%")

st.divider()
st.subheader("Reconciliation Summary")

rcol1, rcol2, rcol3 = st.columns(3)
rcol1.metric("Total Billed", f"₹{kpis['total_billed_inr']:,.0f}")
rcol2.metric("Missing Invoices", f"{kpis['missing_invoices']:,}")
rcol3.metric("Amount Mismatches", f"{kpis['amount_mismatches']:,}")

st.write("**Billed vs. Paid, by Vendor**")
display_summary = vendor_summary.copy()
display_summary["gap_pct"] = display_summary["gap_pct"].astype(str) + "%"
display_summary.columns = ["Vendor", "Total Invoices", "Total Billed (₹)", "Total Paid (₹)", "Gap (₹)", "Gap %"]

st.dataframe(
    display_summary.style.format({
        "Total Billed (₹)": "{:,.2f}",
        "Total Paid (₹)": "{:,.2f}",
        "Gap (₹)": "{:,.2f}"
    }),
    use_container_width=True
)

st.write("**Vendor Health Ranking**")

exception_rate_by_vendor = (
    invoices.groupby("vendor")["needs_review"]
    .mean()
    .reset_index()
)
exception_rate_by_vendor.columns = ["vendor", "exception_rate"]
exception_rate_by_vendor["exception_rate"] = (exception_rate_by_vendor["exception_rate"] * 100).round(2)

vendor_health = vendor_summary.merge(exception_rate_by_vendor, on="vendor")
vendor_health["health_score"] = round(100 - (vendor_health["gap_pct"] + vendor_health["exception_rate"]) / 2, 2)
vendor_health = vendor_health.sort_values("health_score", ascending=False)

health_display = vendor_health[["vendor", "gap_pct", "exception_rate", "health_score"]].copy()
health_display.columns = ["Vendor", "Reconciliation Gap %", "Exception Rate %", "Health Score"]

st.dataframe(health_display, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Billed Amount by Vendor")

vendor_totals = invoices.groupby("vendor")["amount_inr"].sum().reset_index()
vendor_totals.columns = ["Vendor", "Total Billed (INR)"]

st.bar_chart(vendor_totals.set_index("Vendor"))

st.divider()
st.subheader("Exception Queue — Invoices Needing Review")

invoices["bill_date"] = pd.to_datetime(invoices["bill_date"])

fcol1, fcol2 = st.columns(2)
with fcol1:
    vendor_options = ["All Vendors"] + sorted(invoices["vendor"].unique().tolist())
    selected_vendor = st.selectbox("Filter by vendor", vendor_options)
with fcol2:
    date_range = st.date_input(
        "Filter by bill date range",
        value=(invoices["bill_date"].min(), invoices["bill_date"].max()),
        min_value=invoices["bill_date"].min(),
        max_value=invoices["bill_date"].max()
    )

flagged = invoices[invoices["needs_review"] == True]

if selected_vendor != "All Vendors":
    flagged = flagged[flagged["vendor"] == selected_vendor]

if len(date_range) == 2:
    start_date, end_date = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    flagged = flagged[(flagged["bill_date"] >= start_date) & (flagged["bill_date"] <= end_date)]

st.write(f"{len(flagged):,} invoices flagged")

display_columns = ["invoice_id", "vendor", "account_id", "amount_inr", "bill_date"]
st.dataframe(flagged[display_columns].head(100), use_container_width=True)

st.download_button(
    label="Download flagged invoices (CSV)",
    data=flagged[display_columns].to_csv(index=False).encode("utf-8"),
    file_name="flagged_invoices.csv",
    mime="text/csv"
)

st.divider()
st.subheader("Why Invoices Get Flagged")

flag_columns = {
    "consumption_flag": "Negative Consumption",
    "missing_due_date_flag": "Missing Due Date",
    "consumption_missing_flag": "Missing Consumption Reading",
    "consumption_spike_flag": "Consumption Spike (built-in)",
    "consumption_anomaly_flag": "Consumption Statistical Anomaly",
    "amount_inr_anomaly_flag": "Amount Statistical Anomaly",
}

flag_counts = {}
for col, label in flag_columns.items():
    flag_counts[label] = invoices[col].fillna(False).astype(bool).sum()

flag_breakdown = pd.DataFrame(
    list(flag_counts.items()), columns=["Reason", "Count"]
).sort_values("Count", ascending=False)

st.bar_chart(flag_breakdown.set_index("Reason"))
st.dataframe(flag_breakdown, use_container_width=True, hide_index=True)