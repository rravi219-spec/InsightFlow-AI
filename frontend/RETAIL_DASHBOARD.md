# Retail Customer Analytics

Run the existing application from the repository root:

```powershell
.venv\Scripts\python.exe -m streamlit run frontend/adaptive_dashboard.py
```

Use the grouped sidebar: **OVERVIEW → Executive Pulse**; **CUSTOMER INTELLIGENCE → Customer Segments / Retention / Customer 360**; **PREDICTIVE AI → Churn Intelligence / AI Insights**; **ANALYTICS → Reports / Settings**. Churn Intelligence offers **Risk Dashboard** and **Observed Telco Analytics**, preserving both legacy Telco pages. Retail is an independent Online Retail II population; no customer identities are joined across domains. Prepare the local database with the [retail ETL](../etl/README.md) before opening retail views. Missing databases are reported without triggering ingestion or fabricating data.

## Pages and business questions

| View | Question and content |
|---|---|
| Executive Pulse | How large and active is the observed purchaser base? Six headline KPIs: eligible purchasers, purchase orders, repeat rate, gross purchase value, net transaction value, average order value. Purchaser counts by RFM segment, median historical customer net value, and top-decile purchaser value concentration. |
| Customer Segments | Which groups account for value and purchase frequency? Counts, percentages, net GBP value, orders per purchaser, AOV, value and frequency bar charts. |
| Retention | When do first-observed purchasers buy again? Cohort heatmap and table, month-zero 100%, future NULL cells blank, incomplete final activity month warning. Repeat/one-time counts, repeat rate, average frequency, median consecutive and first-to-second intervals, order-frequency distribution. |
| Customer 360 | What is observed for one customer? One exact-ID search field, global-population RFM scores and deterministic interpretation, first/latest purchases, recency, order count, gross/net value, AOV, signed adjustments, median interval, transaction countries, monthly purchase orders, paginated history. |

Segment selections affect only the segment page's table/charts; customer percentages keep the full purchaser denominator. Cohorts default to **All cohorts**, without selected chips. **Choose cohorts** reveals a multi-select affecting only the heatmap/table, not repeat metrics. The raw table is in the collapsed **View cohort data** expander. Customer selection affects Customer 360 only; a single exact-ID field selects the profile. History pages contain at most 50 lines, newest first; line counts are not order counts. A selected customer's activity is aggregated in SQL, without loading all transaction histories.

## Source of truth and methodology

```text
Retail SQLite → analytics/retail_customer_analytics.py → frontend/retail_dashboard.py
```

The frontend formats results and selects rows for display. SQL owns all business aggregates and RFM scoring. The read-only analytics layer opens and closes connections per call. Existing [analytics definitions](../analytics/RETAIL_CUSTOMER_ANALYTICS.md) govern purchaser eligibility, customer/invoice order grain, signed adjustments, tie-aware RFM scores and segment precedence, cohorts, and historical value. New APIs supply median net value, observation/reference dates, customer references, and scoped Customer 360 results.

Amounts are dataset-derived GBP transaction values, not audited accounting revenue or predicted lifetime value. Headline net value and median include return-only customers; segment and concentration values use purchasers only. Positive cancellations stay signed adjustments. Returns are not matched to original orders. Anonymous rows do not receive invented identities. Product descriptions are representative dimension descriptions; countries are transaction attributes, not residence. Purchase activity does not establish churn or causality. First observed purchase is not necessarily true acquisition. UI help and the **About this analysis** expander explain these limitations; dates come from the database, not today's date.

Missing/corrupt/unavailable databases show actionable messages. Empty databases, empty selections, unknown IDs, return-only customers and insufficient history have explicit states; undefined measures display **Not available**. No LLM or recommendation engine is used.

## Caching and local performance

Only data results are cached (`st.cache_data`, 300-second TTL, 128 entries). Keys include the resolved database path, database/WAL modification time and size, query name and parameters. No live database connection is cached. A normal ETL replacement invalidates cached results; metadata-preserving external rewrites may require cache clearing or TTL expiry. Run ETL outside active review sessions to avoid mixed snapshots during replacement.

Measured locally using AppTest with the full database (1,061,163 fact rows), clearing the application result cache before each view. These are application-cache-cold runs; the operating-system disk cache was not flushed. Cached runs reuse the same view/results. They exclude browser rendering and are not production benchmarks.

| View | Cold seconds | Cached seconds |
|---|---:|---:|
| Executive Pulse | 5.514 | 0.050 |
| Customer Segments | 1.877 | 0.153 |
| Retention | 7.960 | 0.085 |
| Customer 360, customer 12346 | 1.259 | 0.046 |

Before the redesign, Retention measured 7.785s cold / 0.048s cached. The redesigned view measured 7.960s / 0.085s; no query optimization or performance improvement is claimed. The validated cache architecture is preserved.

Retention's constituent query measurements: matrix 3.197s, repeat summary 1.898s, KPIs 1.551s, frequency distribution 0.908s, metadata 0.103s. Query plans show existing `fact_customer_date` usage plus grouping/sorting for full-population order and cohort aggregates. Customer history uses indexed customer lookup. No new index or persistent summary was introduced: cached reruns already avoid these scans, and a persistent summary would add refresh/versioning work beyond this presentation milestone. Cold latency remains a limitation.

## Validation and limits

Fixture AppTests cover actual KPI values, segment filtering, future cohort NULLs, partial months, known/unknown IDs, return-only/minimal histories, missing/corrupt/empty databases, cache reuse/invalidation and routing through the existing application. API checks cover bounded pagination and injection-shaped customer input. Existing Telco tests remain part of the full suite. Full-data AppTests exercise all four views; the retail validator independently reconciles streamed facts to orders, RFM, retention, intervals and values.

Local validation on 2026-10-01: **74 tests passed** (all 69 previous checks retained/adapted, 5 added for the redesign); compileall, pip check and diff whitespace checks passed. Retail analytics reconciled 824,293 known lines, 36,969 orders, 5,878 purchasers, 325 cohort cells and 31,091 intervals. Existing database ETL reconciliation passed for 1,067,371 staged and 1,061,163 fact rows, with no row mismatches or foreign-key violations; the workbook was not rebuilt for this presentation-only change. Telco ingestion validated 7,043 customers and the actual Telco Analytics page passed AppTest. Local Streamlit startup succeeded and its health endpoint returned HTTP 200 / `ok`. Generated timing and validation reports stay under ignored `data/processed/`.

Charts have question-oriented titles, labeled axes, percentage/GBP units, and responsive widths; tables retain NULLs and use readable precision. No browser was connected in this environment, so actual rendered contrast, narrow-screen layout and screenshot QA remain unverified. No screenshots are fabricated. This is local Streamlit presentation, not a deployed service or a concurrent-write snapshot guarantee.


## Executive AI visual system

`frontend/design_system.py` supplies the shared deep-navy theme, elevated cards, capability hero, semantic segment colors/badges, accessible five-point RFM indicators, chart containers and **✦ Intelligence Brief**. `.streamlit/config.toml` sets the native widget theme. Branding is **InsightFlow AI — Customer Intelligence & Analytics Platform**. `frontend/navigation.py` owns the four goal-oriented navigation groups.

Executive Pulse presents both retail analytics and the separate Telco predictive capability; its metrics remain explicitly retail. Brief observations select the largest/highest-net-value segment and format validated repeat-rate/concentration outputs, with alphabetical tie-breaking. No LLM, causal inference or prescriptive advice is used. Segment and cohort briefs describe only the displayed population. Customer 360 shows no activity trend for fewer than two observed purchase months; a single period receives an explanatory state. Dates use readable day/month labels. Cached query results, SQL, ETL, KPI definitions, RFM rules and model artifacts are unchanged by this redesign. The later Knowledge group adds the separately documented constrained Ask InsightFlow page, bringing navigation to five groups.
