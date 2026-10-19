"""
app.py
------
Streamlit front end for the HLL Lifecare candidate screening tool.
All screening rules live in screening_engine.py; this file only handles
upload, display, filtering and download.

Run with:  streamlit run app.py
"""

import pandas as pd
import streamlit as st

from screening_engine import (
    MANUAL_REVIEW,
    NOT_QUALIFIED,
    QUALIFIED,
    STATUS_LABELS,
    ScreeningInputError,
    evaluate_dataframe,
    load_candidates,
    summarise,
)

st.set_page_config(page_title="HLL Candidate Screening", page_icon="📋", layout="wide")

st.title("Candidate Preliminary Screening")
st.caption(
    "Decision-support tool. Labels are suggestions only - every final "
    "recruitment decision must be made by a human."
)

# ---- Sidebar: show the rules being applied (transparency) ----------------
with st.sidebar:
    st.header("Eligibility rules")
    st.markdown(
        "- **Qualification:** BE/B.Tech in Computer Science, IT or Software Engineering\n"
        "- **Experience:** at least 3 years\n"
        "- **Mandatory skills:** Python **and** SQL\n"
        "- **Desirable (not mandatory):** AI, ML, NLP, GenAI, cloud, APIs, BI tools"
    )
    st.header("How labels are decided")
    st.markdown(
        "1. A mandatory requirement is **definitely unmet** → *Not Qualified*\n"
        "2. Otherwise, something is **missing / unclear / needs verification** → *Manual Review*\n"
        "3. Otherwise, everything is clearly met → *Qualified*\n\n"
        "A definite failure always beats ambiguity."
    )

# ---- Step 1: upload ------------------------------------------------------
uploaded = st.file_uploader("Upload the candidate CSV file", type=["csv"])
if uploaded is None:
    st.info("Upload HLL_AI_Screening_200_Candidates.csv (or a file with the same columns) to begin.")
    st.stop()

try:
    candidates, warnings = load_candidates(uploaded)
except ScreeningInputError as err:
    st.error(str(err))
    st.stop()

st.success(f"File read successfully: **{len(candidates)} rows**, {len(candidates.columns)} columns.")
for message in warnings:
    st.warning(message)

# ---- Step 2: evaluate every candidate ------------------------------------
results = evaluate_dataframe(candidates)
summary = summarise(results)

# ---- Step 3: dashboard ---------------------------------------------------
st.subheader("Summary")
c_total, c_q, c_nq, c_mr = st.columns(4)
c_total.metric("Total candidates", summary["total"])
c_q.metric(QUALIFIED, summary[QUALIFIED])
c_nq.metric(NOT_QUALIFIED, summary[NOT_QUALIFIED])
c_mr.metric(MANUAL_REVIEW, summary[MANUAL_REVIEW])

if summary["reconciles"]:
    st.caption(
        f"Reconciliation: {summary[QUALIFIED]} + {summary[NOT_QUALIFIED]} + "
        f"{summary[MANUAL_REVIEW]} = {summary['total']} ✔"
    )
else:  # should never happen, but we check rather than assume
    st.error("Totals do not reconcile - please check the input data.")

chart_data = pd.Series({label: summary[label] for label in STATUS_LABELS}, name="Candidates")
st.bar_chart(chart_data)

# ---- Step 4: filterable results table ------------------------------------
st.subheader("Candidate results")
f_status, f_search = st.columns([2, 3])
selected = f_status.multiselect("Filter by status", STATUS_LABELS, default=STATUS_LABELS)
query = f_search.text_input("Search by ID, name or reason (optional)").strip().lower()
show_all = st.checkbox("Show all original columns")

view = results[results["Expected_Status"].isin(selected)]
if query:
    haystack = (
        view["Candidate_ID"].astype(str) + " " + view["Candidate_Name"].astype(str)
        + " " + view["Reason"]
    ).str.lower()
    view = view[haystack.str.contains(query, regex=False)]

columns = list(results.columns) if show_all else ["Candidate_ID", "Candidate_Name", "Expected_Status", "Reason"]
st.caption(f"Showing {len(view)} of {len(results)} candidates")
st.dataframe(
    view[columns].rename(columns={"Expected_Status": "Status"}),
    hide_index=True,
)

# ---- Step 5: export (always the full set, not the filtered view) ---------
st.download_button(
    label=f"Download full report ({len(results)} rows, CSV)",
    data=results.to_csv(index=False).encode("utf-8"),
    file_name="HLL_Screening_Results.csv",
    mime="text/csv",
)
