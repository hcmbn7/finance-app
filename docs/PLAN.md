# 💰 Personal Finance App: Product & Technical Plan (Lean, Personal-Use Edition)

> **Status:** Draft v2 · **Owner:** Hicham · **Type:** Personal project, single user, local-first
**One-liner:** A private web app that shows net worth, spending, budgets, and Canadian registered-account room, fed by statement uploads, with AI categorization and an in-app finance assistant, built to cost almost nothing to run.
**Target running cost:** ~$1-3/month (≈$5-9/month if hosted on a small VPS)
> 

---

## 1. Goals & Non-Goals

### Goals

- See **net worth** at any point in time, with history.
- Understand **monthly spending** by category, merchant, and account.
- Set and track **budgets** per category, with rollover and alerts.
- Track **savings/investing accounts** with **Canadian contribution limits** (TFSA, RRSP, FHSA, RESP...).
- Get credit card spending in with **minimal manual work**: statement drop + AI classification (bank connection is a later, optional phase).
- Eventually ask an **AI assistant** questions about my own finances and get grounded advice.
- Keep it **as cheap as possible** to build and run.

### Non-Goals (v1)

- No trading, no moving money, no order placement.
- Not tax filing software (only tax-aware tracking of contribution room).
- No multi-user, sharing, or public SaaS.
- No native mobile app (responsive web is enough).
- No live market-data integration or holdings/ACB engine (manual balances first).
- No bank/credit-card connection in v1.

---

## 2. Key Scenarios

| # | Scenario | Success looks like |
| --- | --- | --- |
| 1 | Monthly close: drop new credit card/bank statements | Transactions parsed, ≥90% auto-categorized, ~5-10 min review |
| 2 | "What is my net worth today vs. 6 months ago?" | One dashboard number + trend chart |
| 3 | "Am I on track on groceries this month?" | Budget bar with pace indicator |
| 4 | "How much TFSA/RRSP/FHSA room do I have left?" | Per-account room, contribution ledger, warnings |
| 5 | "Why did spending jump in March?" | Month-over-month diff by category/merchant |
| 6 | Ask the assistant about a financial decision | Answer grounded in my real data, assumptions stated |

---

## 3. Build Principles (Cost & Simplicity)

- **Local-first:** run on my own computer or a home server; $0 hosting.
- **Boring tech:** one language (Python) for backend + UI, SQLite, no queue, no cache server.
- **AI only where it saves real time:** rules and memory first, LLM for what's left.
- **Cheapest model that works:** Haiku-class for classification and chat; upgrade only if answers are bad.
- **Data I can always leave with:** full CSV/JSON export from day one.
- **Phase gates:** each phase has a "done when" so scope can't creep.

### What's cut vs. a "full SaaS" version

| Full version | This plan | Saves |
| --- | --- | --- |
| Managed hosting | Run locally / home server | $10-25/mo |
| PostgreSQL | SQLite (WAL mode), money as **integer cents** | Ops + hosting |
| Celery + Redis | In-process background task (or Django-Q2 on the DB) | 2 services |
| S3 storage | Local encrypted folder | Bucket fees |
| Sentry / uptime monitors | Log files + weekly check | Subscriptions |
| Bank/card connection | Statement upload only | Aggregator fees |
| Market-data API | Manual monthly balances; FX from free Bank of Canada Valet API | API fees |
| Multi-user | Single user | Dev time |
| React SPA + separate API | Django + HTMX + Chart.js (React optional if I want it) | Dev time |
| Sonnet-class assistant | Haiku-class, upgrade if needed | AI cost |
| Holdings/ACB/returns engine | Account-level balances + contributions | Weeks |

---

## 4. Functional Requirements

### 4.1 Accounts & Net Worth

- Account types: chequing, savings, credit card, line of credit, loan, mortgage, TFSA, RRSP, FHSA, RESP, LIRA/LIF, non-registered brokerage, crypto, cash, plus **manual assets** (home, vehicle, other) and **manual liabilities**.
- Each account: institution, type, currency (CAD/USD), opening balance, status (open/closed), tax wrapper (registered / non-registered).
- Net worth = Σ assets − Σ liabilities, **in CAD**, with USD converted at the daily rate.
- **Snapshots:** one balance per account per month (or day) so history is stable and never recomputed from scratch.
- Views: current net worth, history chart (1M/6M/1Y/All), breakdown by account type, by institution, liquid vs. illiquid, registered vs. non-registered.
- Manual balance entry/adjustment for accounts without imports.

### 4.2 Transactions & Spending

- Fields: date, posted date, amount (cents), currency, raw description, normalized merchant, category, subcategory, account, tags, notes, source (upload/manual), import batch ID, confidence, status (pending/confirmed), classified_by.
- Views: monthly summary, category breakdown, merchant leaderboard, recurring/subscription detector, month-over-month and year-over-year comparison, search + filters.
- **Transfers and card payments excluded from spending:** detect paired legs across accounts (e.g., chequing → credit card payment) to avoid double counting.
- Refunds/reversals net against the original category.
- Split transactions (one purchase → several categories).
- Bulk edit and "create rule from this edit."

### 4.3 Budgets

- Monthly budget per category (plus optional overall cap).
- Modes: fixed amount, percent of income, rollover of unspent/overspent amounts.
- Sinking funds for irregular expenses (insurance, car maintenance, gifts).
- Pace indicator (spent vs. expected by day of month); in-app alerts at 80% and 100%.
- Income tracking to compute savings rate.
- Budget-vs-actual report per month, plus trailing 3/6/12-month averages to help set realistic budgets.

### 4.4 Savings & Canadian Registered Accounts

- **Contribution room tracking** per account type:
    - **TFSA:** annual limit by year; withdrawals restore room **the following January**; warn when a planned contribution risks over-contribution.
    - **RRSP:** deduction limit (from Notice of Assessment), contributions, carry-forward, $2,000 over-contribution buffer, penalty warning.
    - **FHSA:** annual limit, carry-forward (capped), lifetime limit, participation start year.
    - **RESP / RDSP / others:** lifetime limits and grants (later).
- Limits live in an **editable `limit_rule` table by year** (never hardcoded). Room is entered manually from CRA My Account / NOA, then the app tracks changes from that starting point.
- Distinguish **contributions vs. transfers**: direct institution-to-institution transfers are not new contributions.
- **Savings goals** (emergency fund, down payment, travel): target, deadline, linked accounts, projected completion date.
- Interest/dividends recorded as income-type transactions.
- **Later (optional):** holdings (ticker, quantity, ACB, market value), allocation vs. target, simple and money-weighted returns, price refresh.

### 4.5 Data Ingestion

**Priority order:**

1. **Statement upload (primary):** drag-and-drop PDF/CSV/OFX/QFX per account or in bulk.
2. **Manual entry** for one-offs and manual assets.
3. **Bank/card connection (later, optional):** aggregator or official consumer-driven banking once live; read-only.

**Upload pipeline:**

1. Upload → store file (encrypted) + file hash (reject exact duplicates).
2. Detect institution/format (saved CSV column-mapping template, or PDF).
3. Extract transactions:
    - CSV/OFX/QFX: deterministic parser with per-institution mapping saved for reuse.
    - PDF: text extraction first; if layout is messy or scanned, AI document/vision input with a strict JSON schema.
4. Normalize (dates, signs, currency, merchant cleanup).
5. **Reconcile:** opening balance + Σ transactions = closing balance. If mismatch → flag the batch, don't silently import.
6. **De-duplicate** (fingerprint: account + date + amount + normalized description + occurrence index).
7. Detect transfers / card payments / refunds.
8. **Classify** (see 4.6).
9. Review queue: low-confidence rows first; approve in bulk.
10. Commit; ability to **undo an entire import batch**.

### 4.6 AI Classification

- **Layered (cheap → expensive):**
    1. **User rules** (merchant contains X → category Y), always wins.
    2. **Merchant memory** (previous confirmed categorizations of the same normalized merchant).
    3. **LLM** for what's left, given the category taxonomy, merchant text, amount, account type, and a few of my own past corrections as few-shot examples.
- LLM returns structured JSON: `category`, `subcategory`, `merchant_clean`, `confidence`, `is_transfer`, `is_recurring`, `reason`.
- Confidence below threshold (e.g., <0.75) → review queue.
- Every correction becomes a rule or memory entry, so accuracy improves over time.
- Store `model_version` and `classified_by` (rule / memory / llm / manual) on every transaction.
- **Privacy:** redact account numbers and names before any LLM call; send only needed fields.
- Default taxonomy (editable): Housing, Groceries, Dining, Transport, Utilities & Telecom, Insurance, Health, Subscriptions, Shopping, Entertainment, Travel, Education, Gifts & Donations, Fees & Interest, Taxes, Income, Transfers, Investments, Uncategorized.

### 4.7 AI Assistant (optional, late)

- Chat panel with conversation history.
- **Grounded via tool calls** over the same service layer the dashboard uses:
    - `get_net_worth(date)`, `get_net_worth_history(range)`
    - `get_spending(category, start, end, group_by)`
    - `compare_periods(a, b)`
    - `get_budget_status(month)`
    - `get_registered_room(account_type)`
    - `search_transactions(filters)`
    - `run_projection(inputs)` (math in code, not in the model)
- Rules: numbers must come from tools; state assumptions; show which data was used; never claim certainty about markets or taxes.
- Read-only by default; any write (e.g., recategorize) needs explicit confirmation.
- Educational, not licensed advice; visible disclaimer and a "data used" expander.
- Example prompts: "Where did I overspend vs. my 6-month average?", "Given my room, should I prioritize TFSA or FHSA this year?", "Project my net worth in 10 years at 5%/7%."
- **Eval set:** 30-50 golden questions with known answers for regression testing.

### 4.8 Dashboard & UX

- Home: net worth + trend, this month's spending vs. budget, savings rate, upcoming recurring charges, registered room summary, "needs review" count.
- Fast filtering, keyboard-friendly review queue, full CSV export, dark mode, responsive.
- Optional EN/FR UI via i18n from the start, even if only EN ships first.

---

## 5. Non-Functional Requirements

| Area | Requirement |
| --- | --- |
| **Security** | Local-only by default. If reachable remotely: private tunnel (e.g., Tailscale) or 2FA + HTTPS; encrypted backups and uploads folder; audit log of imports/edits/exports |
| **Privacy** | Redact before LLM calls; option to delete source files after parsing; no financial data in logs; never commit statements or DB to git |
| **Accuracy** | Money as **integer cents**, never floats; reconcile every import |
| **Performance** | Dashboard < 1s on 5+ years of data; import of a 300-line statement < 60s |
| **Reliability** | Nightly backup (`sqlite3 .backup` + encrypted archive), tested restore, versioned migrations |
| **Portability** | Full data export (CSV/JSON); no lock-in |
| **Observability** | Log files; token/cost logging per AI call |

---

## 6. Tech Stack

| Layer | Choice | Why |
| --- | --- | --- |
| Backend + UI | **Django** + **HTMX** + **Chart.js** (alt: Django + React) | One codebase; admin, ORM, auth, migrations included; Python is best for PDF parsing and AI |
| DB | **SQLite** (WAL), integer cents | Zero ops, single-file backup, plenty for one user |
| Jobs | In-process background task (or Django-Q2 with DB broker) | No Redis/Celery |
| File storage | Local encrypted folder | No bucket fees |
| Parsing | `pdfplumber` / `PyMuPDF`, `pandas`, `ofxparse`; AI document input as PDF fallback | Deterministic first, AI second |
| AI | Anthropic API: **Haiku 4.5** for classification + chat, **Batch API** for monthly imports, **prompt caching** for the static prompt | Cheapest workable setup |
| FX | Bank of Canada Valet API (free) | USD/CAD |
| Market prices | Manual for now; optional free-tier API later | Avoid fees |
| Auth | Password (local) / private tunnel or 2FA if remote | Single user |
| Testing | pytest, golden-file tests for parsers, small Playwright smoke test | Parsers are the fragile part |
| CI | Optional GitHub Actions: lint + tests | Free tier |

**Upgrade path if it ever grows:** Postgres, Celery/Redis, S3, React SPA, Sonnet-class assistant, aggregator-based connections, multi-user.

---

## 7. Architecture Overview

- **Django app** serves pages (HTMX partials) and a small JSON API for charts.
- **SQLite** stores everything; uploads live in a local encrypted folder.
- **Background task** runs: parse → reconcile → dedupe → classify → snapshot.
- **AI service module** (single place for all LLM calls): redaction, prompts, JSON validation, retries, caching, cost logging.
- **Assistant** = chat endpoint + tool layer calling the same read-only service functions as the dashboard (one source of truth for numbers).
- **Connector interface** (`BankConnector`) reserved for a future aggregator/open-banking source, unused in v1.

---

## 8. Data Model (core tables, single user)

| Table | Key fields |
| --- | --- |
| `institution` | id, name, type |
| `account` | id, institution_id, name, type, tax_wrapper, currency, opened_at, closed_at, is_liability |
| `balance_snapshot` | id, account_id, date, balance_cents, source |
| `transaction` | id, account_id, date, posted_date, amount_cents, currency, raw_desc, merchant_id, category_id, status, confidence, classified_by, model_version, import_batch_id, transfer_group_id, fingerprint, notes |
| `merchant` | id, normalized_name, default_category_id |
| `category` | id, parent_id, name, kind (expense/income/transfer) |
| `rule` | id, match_type, pattern, category_id, priority |
| `import_batch` | id, account_id, file_id, status, reconciliation_ok, counts, created_at |
| `file` | id, hash, storage_path, mime, uploaded_at, delete_after |
| `budget` | id, category_id, month, amount_cents, rollover_mode |
| `goal` | id, name, target_cents, deadline, linked_account_ids |
| `fx_rate` | pair, date, rate |
| `limit_rule` | account_type, year, annual_limit_cents, lifetime_limit_cents, notes |
| `room_entry` | id, account_type, year, kind (opening_room / contribution / withdrawal / adjustment), amount_cents, source |
| `chat_thread` / `chat_message` | id, thread_id, role, content, tool_calls, created_at |
| `ai_call_log` | id, purpose, model, tokens_in, tokens_out, cost, latency_ms |
| *(later)* `holding`, `price` | ticker, quantity, acb_cents, asset_class, currency / ticker, date, close |

---

## 9. Key Routes & Services

- **Imports:** upload, view batch, commit, undo
- **Transactions:** list/filter, edit, bulk update, split, review queue
- **Accounts:** CRUD, snapshots
- **Reports:** net worth history, spending summary (by month/category/merchant), budget status
- **Registered:** room summary, add contribution/withdrawal/adjustment, edit yearly limits
- **Rules:** list/create/edit
- **Chat:** send message (streamed), list threads
- **Export:** full CSV/JSON

---

## 10. Hosting & Running Costs

| Option | Cost | Trade-off |
| --- | --- | --- |
| **Run locally** on laptop/desktop | $0 | Only available when the machine is on |
| **Home server / old laptop / Raspberry Pi** + private tunnel | ~$0 (electricity) | I maintain it |
| **Small VPS** (Canadian region if possible) | ~$4-6/mo | Internet-exposed; needs hardening + 2FA |

**Recommendation:** start local. Move to a VPS only if I want phone access away from home; prefer a private tunnel over opening it to the internet.

### Estimated monthly cost

| Item | Estimate |
| --- | --- |
| Hosting (local) | $0 |
| Categorization (~300 tx/mo, Haiku, batch) | < $0.25 |
| PDF fallback parsing (a few statements) | < $0.25 |
| Assistant (light use, Haiku) | ~$0.50-$3 |
| Domain/SSL (only if public) | $0 |
| **Total** | **~$1-3/mo** (≈$5-9/mo on a small VPS) |

### AI cost controls

1. Rules + merchant memory first; after 2-3 months most rows never hit the LLM.
2. Haiku-class model, `max_tokens` capped, JSON-only output.
3. **Batch API** for monthly imports (50% off; not urgent).
4. **Prompt caching** for the static prompt (taxonomy + few-shot).
5. Send only merchant text, amount, date, account type, redacted.
6. Monthly **spend limit** in the Anthropic Console; log tokens per call in `ai_call_log`.
7. Zero-AI fallback: rules-only + manual categorization of leftovers.

---

## 11. Roadmap (ordered by value per hour)

### Phase 0: Foundations (≈3-5 days)

- [ ]  Repo, Django project, SQLite, base layout, password auth
- [ ]  Core schema + migrations, seed categories
- **Done when:** I can log in and create an account.

### Phase 1: Ledger + Import (MVP, ≈2-3 weeks) ⭐

- [ ]  Accounts, transactions, categories (integer cents)
- [ ]  CSV/OFX import with saved column mappings, dedupe, undo batch
- [ ]  Reconciliation check against statement balance
- [ ]  Rules + merchant memory (no AI yet)
- [ ]  Transfer/card-payment detection
- **Done when:** a real month imports and reviews cleanly.

### Phase 2: Spending & Budgets (≈1-2 weeks)

- [ ]  Monthly category/merchant views, drill-down
- [ ]  Budgets, rollover, pace bar, in-app alerts
- [ ]  Recurring charge detection
- **Done when:** my monthly review happens entirely in the app.

### Phase 3: Net Worth & Registered Room (≈1-2 weeks)

- [ ]  Monthly balance snapshots + net worth chart
- [ ]  TFSA/RRSP/FHSA room ledger, editable yearly limits table, over-contribution warnings
- [ ]  Savings goals with projections
- **Done when:** net worth is within 0.5% of my manual spreadsheet and room numbers match CRA My Account after initial entry.

### Phase 4: AI Classification + PDF Fallback (≈1-2 weeks)

- [ ]  Haiku classification for unmatched rows, review queue, learn-from-corrections
- [ ]  PDF parsing fallback with reconciliation
- [ ]  Batch API + prompt caching, cost logging
- **Done when:** ≥90% correct categories on a real month, AI cost under cap.

### Phase 5: Assistant (optional, ≈2 weeks)

- [ ]  Read-only tool layer over existing services
- [ ]  Streaming chat UI, history, "data used" panel
- [ ]  Guardrails, disclaimer, eval set (30-50 Qs), spend cap
- **Done when:** ≥90% of the eval set is correct and every number traces to tool output.

### Phase 6: Only if ever needed

- [ ]  Holdings, ACB, returns, price API
- [ ]  Bank/card connection (re-check open-banking status and aggregator pricing first)
- [ ]  VPS hosting, 2FA, backup-restore drill
- [ ]  Email alerts, PWA, EN/FR UI

---

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| PDF formats vary/change | Bad or missing transactions | Prefer CSV; reconciliation check; golden-file tests; AI fallback |
| LLM misclassification | Wrong budgets | Confidence threshold, review queue, rules override, audit fields |
| Sensitive data sent to an LLM | Privacy | Redaction, minimal fields, review provider data-retention terms, rules-only mode available |
| Double counting (transfers/card payments) | Wrong spending totals | Pair detection, exclude Transfers from reports |
| Registered-limit rules change or misapplied | Penalties from bad data | Editable limit table; CRA/NOA entry as source of truth; "verify with CRA" note in UI |
| Local machine failure | Data loss | Nightly encrypted backups to a second location; tested restore |
| Scope creep | Never finishing | Phase gates with "done when" criteria |
| Overconfident assistant advice | Bad decisions | Tool-grounded numbers, stated assumptions, disclaimer |

---

## 13. Open Questions

- [ ]  Which institutions/cards/brokerages do I need on day one, and do they offer CSV export?
- [ ]  Which registered accounts do I hold, and what are my current room numbers (CRA My Account)?
- [ ]  Local only, or do I want phone access away from home (→ tunnel or VPS)?
- [ ]  HTMX UI or React?
- [ ]  How far back do I want to import history?
- [ ]  Monthly AI spend cap?

---

## 14. Success Metrics

- Monthly import + review time < 15 min
- ≥90% auto-categorization accuracy (measured on reviewed rows)
- Net worth within 0.5% of manual spreadsheet at month-end
- 0 unreconciled imports committed
- Assistant eval pass rate ≥90% (if built)
- Total running cost ≤ ~$3/month (local)

---

## 15. Immediate Next Steps

- [ ]  Collect 2-3 real statements (CSV + PDF) per institution as parser test fixtures (redacted).
- [ ]  Lock category taxonomy and my first 20 rules.
- [ ]  Decide HTMX vs. React and local vs. VPS.
- [ ]  Create repo + Phase 0 tickets in a Notion board.

---

## Appendix A: Reference Facts (verify before relying on them)

**Open banking in Canada (as of Sept 2026):** not live. Proposed Consumer-Driven Banking Regulations were published June 27, 2026; Phase 1 is read-only; coming into force is expected roughly a year after final publication. → Statement upload is the primary path; revisit connections in Phase 6.

**2026 registered-account limits (store in `limit_rule`, don't hardcode):**

| Account | 2026 figure |
| --- | --- |
| TFSA annual limit | $7,000 (cumulative $109,000 for someone eligible since 2009 who never contributed) |
| RRSP annual max | $33,810 (18% of prior-year earned income up to the max, plus carry-forward) |
| FHSA | $8,000/yr; carry-forward max $8,000; lifetime $40,000 |

**AI pricing (Haiku 4.5):** $1 input / $5 output per million tokens; Batch API = 50% off; cached input reads ≈ 10% of standard input price.

## 🧮 Month-End Close & True P&L

> **Goal:** At the end of each month, every account and statement balances, every dollar of change in net worth is explained, and the app produces a trustworthy P&L. If it doesn't balance, the month can't be closed.
> 

### A. Definitions

| Term | Definition |
| --- | --- |
| **Net worth change** | Net worth at month-end − net worth at month-start (all accounts, in CAD) |
| **Operating P&L** | Income − Spending. Only *external* money in/out; **transfers, card payments, registered contributions, and loan principal repayments are excluded** |
| **Investment P&L** (per investment account) | Closing value − Opening value − Net contributions (contributions − withdrawals). Dividends and interest earned inside the account count here |
| **Revaluation P&L** | Manual changes in value of assets like home or vehicle (shown separately) |
| **Unexplained difference** | Net worth change − (Operating + Investment + Revaluation). Target: **$0** (tolerance e.g. ±$1) |
| **True P&L** | Operating + Investment + Revaluation (also show a version *excluding* revaluations) |

### B. Worked example (fake numbers)

| Item | Amount |
| --- | --- |
| Net worth start / end | $100,000 → $102,300 (change **+$2,300**) |
| Paychecks | +$5,000 |
| Spending (excl. transfers) | −$3,600 |
| **Operating P&L** | **+$1,400** |
| TFSA: start $20,000, end $20,950, contributed $500 | **+$450** investment P&L |
| Home revaluation | +$450 |
| Sum of explained | 1,400 + 450 + 450 = **+$2,300** |
| **Unexplained** | **$0** ✅ |

### C. Three layers of reconciliation

**1. Account-level (every account, every month)**

- Opening balance + Σ transactions (+ market change for investment accounts) = Closing balance.
- Closing balance comes from a statement or a manually entered balance; flag how it was derived (`statement` / `manual` / `derived`).
- Difference ≠ 0 → account marked **Unreconciled** with the gap shown.

**2. Cross-account (transfers)**

- Every transfer has two legs that **net to zero** (e.g., chequing −$500 / credit card +$500; chequing −$500 / TFSA contribution +$500).
- Unmatched legs go to a "Needs matching" list (date window ±3 days, same amount, opposite sign).
- Loan/mortgage payments are **split**: interest = expense, principal = transfer to the liability.

**3. Net worth level**

- Compare net worth change vs. the sum of P&L components.
- Unexplained ≠ 0 → close blocked until resolved or an explicit **adjustment** is booked.

### D. Hard parts to design for

- **Statement cycles ≠ calendar months.** A card statement may end on the 14th. Compute the **month-end balance from transactions** (last statement balance ± transactions after/before the cut-off) and mark it `derived`; upgrade to `statement` when a real balance for that date exists.
- **Credit cards are liabilities.** Spending is recognized on the purchase date; the card payment is a transfer, never spending.
- **Pending vs. posted:** use one date rule consistently (recommend *transaction date* for spending, posted date for balances).
- **Fees, interest, FX:** booked as expenses or income with their own categories; FX differences on USD accounts shown as FX P&L, not as unexplained.
- **Adjustments:** if a gap can't be found, book an explicit **"Reconciliation adjustment"** transaction with a note. It is visible in reports and never hidden.
- **Locking:** a closed month is locked; later edits reopen it with an audit log entry and recalculate.

### E. Month-close wizard (UI)

1. **Account checklist:** each account shows ✅ reconciled / ⚠️ gap / ⬜ no statement yet.
2. **Fix gaps:** missing statement, missing transactions, duplicates, wrong sign, wrong date.
3. **Match transfers:** review unmatched legs.
4. **Enter balances** for accounts without statements (investments, home, vehicle).
5. **Review P&L breakdown:** operating, investment, revaluation, unexplained.
6. **Close month:** locks the month and freezes snapshots.
7. **Report:** one-page monthly summary (net worth, true P&L, top categories, savings rate, registered room).

### F. Data model additions

| Table | Key fields |
| --- | --- |
| `month_close` | month, status (open / reconciled / locked), net_worth_start_cents, net_worth_end_cents, operating_pnl_cents, investment_pnl_cents, revaluation_pnl_cents, unexplained_cents, locked_at |
| `account_month_recon` | account_id, month, opening_cents, closing_cents, sum_transactions_cents, market_change_cents, diff_cents, closing_source (statement / manual / derived), status |
| `transfer_group` | id, matched_legs, net_cents (must be 0), matched_by (auto / manual) |
| `transaction.kind` (new field) | income / expense / transfer / contribution / withdrawal / dividend / interest / fee / fx / adjustment |
| `adjustment` (as transaction kind) | account_id, month, amount_cents, reason, created_at |

### G. Automated checks (run on every import and at close)

- Every `import_batch` reconciles to its statement balance.
- No account has `diff_cents ≠ 0` at close.
- All transfer groups net to 0; zero unmatched legs.
- No duplicate fingerprints.
- Contribution entries on registered accounts match room ledger entries.
- Unexplained difference within tolerance.
- Snapshots exist for every account for the month-end date.

### H. Roadmap placement

- **Phase 1:** account-level reconciliation per import (already planned), `transaction.kind`, transfer detection.
- **Phase 3:** `month_close`, cross-account matching, investment P&L from balances + contributions, close wizard, locked months.
- **Phase 5 (assistant):** add `get_monthly_pnl(month)` and `get_unexplained(month)` tools so answers always trace to the closed month.

### I. Acceptance criteria

- [ ]  For one real month, all accounts reconcile to statement balances (or flagged `derived` with the reason).
- [ ]  Unexplained difference ≤ $1 after matching transfers.
- [ ]  True P&L agrees with my manual spreadsheet for that month.
- [ ]  Closing the month locks it; editing reopens it with an audit entry.
- [ ]  Monthly report exports to PDF/CSV.

### J. Open questions

- [ ]  Include home/vehicle revaluations in headline "True P&L," or show them separately only?
- [ ]  Tolerance for unexplained: $0, $1, or $5?
- [ ]  Month-end cut-off rule for spending: transaction date (recommended) or posted date?
- [ ]  Do any accounts have no statements at all (cash, crypto) that need manual balances monthly?