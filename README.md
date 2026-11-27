x# Steam Review Explorer: what players praise and complain about

Text and sentiment analysis of about 300,000 English Steam reviews for five games, plus an interactive dashboard.

**Games:** No Man's Sky, Cyberpunk 2077, Helldivers 2, Battlefield 2042, Stardew Valley
**Tools:** Python (pandas, scikit-learn, VADER, BERTopic), Streamlit, Plotly
**Live dashboard:** `Not Deployed yet`

## Questions

1. What do players of each game praise, and what do they complain about?
2. How do reviews change over a game's life, and can specific events (patches, controversies) be seen in the data?
3. Do new players and veteran players feel differently?
4. Can simple sentiment tools (VADER) recover the thumbs-up/thumbs-down vote from the text?

## Key findings

**1. Complaints differ a lot by game.** Share of thumbs-down reviews that mention each theme (a review can mention several; keyword rules):

| Game | Top complaint themes |
|---|---|
| Helldivers 2 | Developers and updates 48.6%, bugs 34.1% |
| Cyberpunk 2077 | Bugs 41.1%, story and characters 32.5% |
| No Man's Sky | Content and repetition 28.2%, price 28.0%, bugs 25.7% |
| Battlefield 2042 | Price and value 22.9%, bugs 16.9% |
| Stardew Valley | Content and repetition 25.0%, price 13.6% (only a small number of thumbs-down reviews) |

**2. Patch 8.8 hurt Battlefield 2042 badly.** After the patch that required Secure Boot (27 May 2025), the thumbs-up share fell from 63.6% to 31.6% (-31.9 points, 95% margin ±3.7). It is the clearest event in the data, and sentiment recovered to around 60% by early 2026.

**3. Two other events can be measured.** No Man's Sky *Atlas Rises* (Aug 2017) lifted positive reviews from 70.2% to 87.3% (+17.1 points, ±3.9). The *NEXT* update (Jul 2018) shows no clear change (+2.7, ±4.9).

**4. Playtime tells a different story per game.**

| Hours played | Battlefield 2042 | Helldivers 2 |
|---|---|---|
| under 2h | 18% | 39% |
| 2-10h | 52% | 88% |
| 10-50h | 56% | 88% |
| 50-200h | 53% | 77% |
| 200h+ | 55% | 53% |

Battlefield 2042's negativity is concentrated in the first two hours (first impressions, price, refunds). Helldivers 2 is harshest at the two ends: new players and veterans with 200+ hours.

**5. Helldivers 2 backlash events are visible but not cleanly measurable.** Positive share dropped from about 80% to 46% after the end-of-April 2026 Reddit AMA, and from about 84% to 31% after Update 7.2.0 (Easy Anti-Cheat) in October 2026. Both are *consistent with* those events, but the sample covers only a small part of the days around them (see limitations), so they are not reported as measured effects.

**6. Simple sentiment tools are weak on game reviews.** VADER (a word-list scorer) reaches AUC 0.80 and accuracy 86.1%, barely above always guessing "positive" (85.5%). A logistic regression trained on the vote reaches AUC 0.96. Gaming slang ("sweaty", "grind", "refund") and sarcasm break general-purpose sentiment lexicons.

## Data

- **Source:** Steam's public review API (no key needed), English reviews only.
- **Collected:** 312,135 reviews, about 9-10 hours of scraping. Cleaned to **298,001** reviews, **237,811** of which have 3+ words and are used for text analysis.
- **Privacy:** usernames and Steam IDs are not collected, only review text and metadata.
- **Not included in the repo:** the raw and processed data are large and regenerate from the scraper. `dashboard/data/` holds the small aggregates the dashboard needs.

## Cleaning

Notebook `01_cleaning_and_eda.ipynb` removes: duplicates, empty reviews, the same long text posted 3+ times, ASCII art and symbol-only text, non-English text (non-Latin scripts, and Latin-script languages found with a stop-word heuristic), joke-template reviews (same opening posted 4+ times) and reviews containing hateful language. Very short reviews ("10/10") are kept for vote charts and flagged, but left out of text analysis. The incomplete last month is dropped.

## Method

| Step | Notebook | What it does |
|---|---|---|
| Collect | `src/review_scraper.py` | Pages through reviews newest first, caps reviews per month, saves a checkpoint after every page |
| Clean and explore | `01_cleaning_and_eda.ipynb` | Cleaning log, review volume and length, thumbs-up share by month and playtime |
| Sentiment | `02_sentiment.ipynb` | VADER vs a TF-IDF logistic regression, judged on AUC because positives are about 85% of reviews |
| Themes and topics | `03_topics.ipynb` | Keyword theme tagging, plus BERTopic clusters (MiniLM embeddings, UMAP, HDBSCAN) for complaints and praise |
| Events | `04_events.ipynb` | A sourced events list, before and after comparison with confidence intervals, and a dip finder |

## Limitations (read before quoting any number)

- **The sample is not uniform in time.** The scraper keeps at most 800 reviews per game per month, newest first. For busy months this means the sample covers only the last days of the month (a median of about 5-7 days for Helldivers 2 and Cyberpunk 2077). Only events with 100+ reviews on each side and 60%+ of days covered are reported as measured: **3 of 29**.
- **A known review-bomb is invisible.** Helldivers 2's PSN account controversy (May 2024) shows 82.1% vs 82.0% in this data, which reflects the sampling and says nothing about the event itself.
- **Event dates:** some dates come from memory or are month-level (marked `memory` or `approx` in `data/events.csv`); only `yes` rows were checked against a source.
- **Steam reviews are not a random sample of players.** People who write reviews skew toward strong opinions.
- **Theme percentages come from keyword rules.** They miss reviews that describe a problem in other words, and a review can fall under several themes.
- **The Helldivers 2 and Battlefield 2042 dips could come from other events** not listed in the events file. Notebook 04 flags unexplained dips (for example Battlefield 2042 in February 2022).

A re-scrape in weekly windows would remove the sampling issue; it would take much longer than the first run, so it was left out of this version.

## Run it yourself

```bash
pip install -r requirements.txt

python src/review_scraper.py --games nms --max-pages 5     # quick test
python src/review_scraper.py                                # all games (hours)

# run notebooks 01, 02, 03, 04 in order, then:
python src/build_dashboard_data.py
python -m streamlit run dashboard/app.py
```

## Project structure

```
data/
  events.csv                  sourced list of events (launches, patches, controversies)
  raw/                        scraper output (not committed)
  processed/                  cleaned and scored data (not committed)
notebooks/                    01 to 04
src/
  review_scraper.py
  build_dashboard_data.py
dashboard/
  app.py
  data/                       small CSVs for the dashboard
images/                       charts saved by the notebooks
.streamlit/config.toml        dashboard theme
requirements.txt
```

## What I learned

- A per-month cap with newest-first paging quietly biases a time series; checking day coverage per month exposed it.
- Accuracy is a poor yardstick when one class is 85% of the data; AUC showed that VADER adds little.
- Cleaning decisions change results: dropping 3-word reviews removed about 20% of the data, so those reviews are now kept and flagged instead.
