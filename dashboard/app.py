"""
Steam review dashboard.
Run from the repo root:   streamlit run dashboard/app.py
Data comes from dashboard/data/ (built by src/build_dashboard_data.py).
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DATA = Path(__file__).parent / "data"
PINK, CYAN, LIME, GREY = "#ff4fd8", "#35e0ff", "#b6ff3b", "#8a8fb8"

st.set_page_config(page_title="Steam Review Explorer", page_icon="🎮", layout="wide")


@st.cache_data
def load(name, **kw):
    return pd.read_csv(DATA / name, **kw)


monthly = load("monthly.csv", parse_dates=["month"])
playtime = load("playtime.csv")
summary = load("summary.csv", parse_dates=["first_month", "last_month"])
examples = load("examples.csv", parse_dates=["month"])
themes_game = load("complaint_themes_by_game.csv").set_index("game")
themes_half = load("complaint_themes_by_half_year.csv")
topics = load("bertopic_topics.csv")
impact = load("event_impact.csv", parse_dates=["date"])
events = load("events.csv", parse_dates=["date"])

games = sorted(summary["game"])

# ---------- sidebar ----------
st.sidebar.title("🎮 Steam Review Explorer")
game = st.sidebar.selectbox("Game", games)
st.sidebar.caption(
    "About 300,000 English Steam reviews for five games, cleaned and analysed in Python. "
    "Thumbs-up share = reviews that recommend the game.")

row = summary[summary["game"] == game].iloc[0]
st.title(game)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Reviews analysed", f"{int(row['reviews']):,}")
c2.metric("Thumbs-up share", f"{row['pct_positive']:.1f}%")
c3.metric("Median hours played", f"{row['median_hours']:.1f}")
c4.metric("Covers", f"{row['first_month']:%Y} to {row['last_month']:%Y}")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Sentiment over time", "What players complain about", "Playtime",
     "Example reviews", "Method and limits"])

# ---------- tab 1: timeline ----------
with tab1:
    m = monthly[monthly["game"] == game].sort_values("month").copy()
    min_n = st.slider("Hide months with fewer reviews than", 0, 300, 30, step=10,
                      help="Months with few reviews swing a lot and are hard to trust.")
    m = m[m["n"] >= min_n]
    m["rolling"] = m["pct_positive"].rolling(3, min_periods=1).mean()

    fig = go.Figure()
    fig.add_bar(x=m["month"], y=m["n"], name="Reviews in sample", yaxis="y2",
                marker_color=GREY, opacity=0.25)
    fig.add_scatter(x=m["month"], y=m["pct_positive"], mode="lines", name="Thumbs-up % (month)",
                    line=dict(color=CYAN, width=1.5))
    fig.add_scatter(x=m["month"], y=m["rolling"], mode="lines", name="3-month average",
                    line=dict(color=PINK, width=3))

    ev = events[events["game"] == game]
    rel = impact[(impact["game"] == game)]
    reliable_dates = set(rel.loc[rel["reliable"], "date"])
    show_all = st.checkbox("Show events that the data cannot test reliably", value=False)
    for _, e in ev.iterrows():
        ok = e["date"] in reliable_dates
        if not (ok or show_all):
            continue
        fig.add_shape(type="line", x0=e["date"], x1=e["date"], y0=0, y1=100, yref="y",
                      line=dict(color=LIME if ok else GREY, width=2 if ok else 1,
                                dash="solid" if ok else "dot"))
        fig.add_annotation(x=e["date"], y=100, text=e["label"].split(":")[0][:28], showarrow=False,
                           textangle=-90, yanchor="top", xanchor="right",
                           font=dict(size=11, color=LIME if ok else GREY))
    fig.update_layout(height=480, yaxis=dict(title="% thumbs up", range=[0, 100]),
                      yaxis2=dict(overlaying="y", side="right", showgrid=False, title="reviews"),
                      legend=dict(orientation="h", y=1.08), margin=dict(t=30))
    st.plotly_chart(fig, width="stretch")
    st.caption("Green lines are events with enough reviews on both sides to measure. "
               "Grey dotted lines (optional) are events where the sample covers too few days.")

    tested = rel[rel["reliable"]].copy()
    if len(tested):
        tested["event"] = tested["event"].str[:60]
        st.subheader("Measured event effects")
        st.dataframe(tested[["date", "event", "pct_before", "pct_after", "change_pp", "+-95%"]]
                     .rename(columns={"pct_before": "% up before", "pct_after": "% up after",
                                      "change_pp": "change (points)", "+-95%": "± (95%)"}),
                     hide_index=True, width="stretch")

# ---------- tab 2: themes ----------
with tab2:
    st.write("Share of **thumbs-down** reviews that mention each theme (a review can mention several).")
    t = themes_game.loc[game].sort_values()
    f = px.bar(t, orientation="h", labels={"value": "% of thumbs-down reviews", "index": ""})
    f.update_traces(marker_color=PINK)
    f.update_layout(showlegend=False, height=380, margin=dict(t=10))
    st.plotly_chart(f, width="stretch")

    th = themes_half[themes_half["game"] == game]
    theme_cols = [c for c in themes_game.columns]
    pick = st.multiselect("Themes over time (half-years)", theme_cols,
                          default=[t.index[-1]] if len(t) else [])
    if pick and len(th):
        f2 = px.line(th, x="half", y=pick, markers=True,
                     labels={"value": "% of thumbs-down reviews", "half": "", "variable": ""})
        f2.update_layout(height=360, legend=dict(orientation="h", y=1.15))
        st.plotly_chart(f2, width="stretch")
        st.caption("Early half-years can rest on few thumbs-down reviews; check the counts in the notebook.")

    st.subheader("Topics found by BERTopic (clusters of similar reviews)")
    tp = topics[topics["game"] == game]
    grp = st.radio("Reviews", ["complaints", "praise"], horizontal=True)
    st.dataframe(tp[tp["group"] == grp][["topic", "reviews", "top words"]]
                 .sort_values("reviews", ascending=False),
                 hide_index=True, width="stretch")

# ---------- tab 3: playtime ----------
with tab3:
    p = playtime[playtime["game"] == game]
    order = ["<2h", "2-10h", "10-50h", "50-200h", "200h+"]
    p = p.set_index("playtime_bucket").reindex(order).dropna(how="all").reset_index()
    f = px.bar(p, x="playtime_bucket", y="pct_positive", text="pct_positive",
               labels={"playtime_bucket": "Hours played when reviewing", "pct_positive": "% thumbs up"})
    f.update_traces(marker_color=CYAN, texttemplate="%{text:.0f}%")
    f.update_layout(yaxis_range=[0, 100], height=400, margin=dict(t=10))
    st.plotly_chart(f, width="stretch")
    st.caption("Thumbs-up share by hours played at the time of the review. Compare games: "
               "some are harshest in the first two hours (refunds), others among long-time players.")

# ---------- tab 4: examples ----------
with tab4:
    side = st.radio("Show", ["thumbs down", "thumbs up"], horizontal=True)
    ex = examples[(examples["game"] == game) & (examples["sentiment"] == side)]
    if st.button("Shuffle"):
        ex = ex.sample(frac=1)
    for _, r in ex.head(6).iterrows():
        st.markdown(f"**{r['month']:%b %Y}** · {r['playtime_hours']:.0f} h played")
        st.write(r["review"][:700] + ("..." if len(r["review"]) > 700 else ""))
        st.divider()

# ---------- tab 5: method ----------
with tab5:
    st.markdown("""
**Data.** English reviews from Steam's public review API for No Man's Sky, Cyberpunk 2077,
Helldivers 2, Battlefield 2042 and Stardew Valley. No usernames or Steam IDs are stored.

**Cleaning.** Removed duplicates, empty reviews, copy-paste and joke-template reviews, ASCII art,
non-English text and hateful language. Very short reviews ("10/10") are kept for vote charts but left
out of text analysis.

**Sentiment.** The thumbs-up or thumbs-down vote is the label. VADER (a word-list scorer) barely beats
always guessing "positive" (AUC 0.80), while a model trained on the review text reaches AUC 0.96.

**Themes.** Keyword rules tag each thumbs-down review; BERTopic clusters similar reviews as a second view.

**Known limits.**
- The scrape kept at most 800 reviews per game per month, newest first. In busy months the sample
  covers only the last days of the month, so exact event timing is unreliable. Only events with enough
  data on both sides are marked as measured.
- Steam reviews are not a random sample of players.
- Theme percentages come from keyword rules and miss reviews that describe a problem in other words.
""")
