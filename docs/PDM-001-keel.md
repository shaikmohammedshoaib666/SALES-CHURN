# PDM-001 — Keel

**Status:** Accepted (planning lock) — **amended by [PDM-002 — Customer Twin](./PDM-002-customer-twin.md)**  
**Owner:** CEO  
**Product:** Keel — Sales + Churn as one Customer Twin  
**Bar:** Forge v2 + PDM standards  
**Build:** not started until PDM-001 and PDM-002 are the source of truth

This is the product decision memo. Features, stack, and repo layout follow this file. If a later idea is not in here, it does not ship in v1.

---

## 1. Decision

We are building **Keel**, a B2B SaaS **revenue retention OS**.

Keel is not a Streamlit lab, not a college churn notebook, and not a dashboard over a CSV. It is a multi-tenant product that a sales lead and a customer-success lead can run a real week of work in:

1. See money (pipeline + MRR movement).
2. See risk (who is about to churn, and why).
3. Act (account 360 + playbook).

Python `.venv` and any model training kit are **supporting tools**, not the product. They can be created on a home machine later. They are never committed.

---

## 2. Why this, not a churn demo

Sales tools celebrate logos. Finance tools report churn after the invoice already died. Customer success lives in spreadsheets, Slack, and memory.

The gap: **nobody owns the account after close with a shared number.**

Keel’s job is that number: **at-risk MRR**, explained, assigned, and worked — **on the same object as LTV and forecast**, not on a second graph.

If Keel only predicts “this customer looks like churn,” it is a science fair. If it shows sales in one chart and churn in another, it is every other CRM. If a team opens **one Customer Twin** and gets a decision (`Retain with offer X`), it is a product. See PDM-002.

---

## 3. Forge v2 + PDM bar (non-negotiable)

These are the standards. Anything that fails them is out of v1.

| Standard | What it means on Keel |
| --- | --- |
| Spec before code | This PDM is merged before app code. |
| One domain language | Account, Customer Twin, Sales Twin, Churn Twin, Decision, subscription, opportunity, MRR movement. No synonym soup. |
| Multi-tenant from day one | Every row belongs to a workspace. Demo data is a workspace, not a global table. |
| Workflows over dashboards | A screen must end in an action (open account, assign owner, run playbook). Charts are supporting. |
| Explainable intelligence | A risk score must show drivers. No black-box “82% churn” with no cause. |
| Production-shaped slice | Auth boundary, tenancy, seed, empty/error states, audit of score runs. Not a happy-path prototype. |
| Thin vertical, not a platform | One ICP, one workflow, one repo. No billing-for-Keel, no Salesforce two-way, no mobile. |
| Data over decoration | Seeded SaaS economics that reconcile (NRR, GRR, logo vs revenue churn). |
| Secrets and machines stay local | `.venv`, `.env`, model binaries, and `secrets` never go to git. |
| Deploy the product, not the lab | Web app is the deployable surface. Streamlit is not v1. |

---

## 4. Who it is for

**ICP:** B2B SaaS, founder-led or small CS team, roughly $200k–$10M ARR. They sell subscriptions, feel expansion and churn monthly, and today stitch HubSpot/Sheets/Stripe by hand.

**Buyer:** Founder, Head of CS, or Head of Sales.

**Users in a workspace:**

| Role | Job in Keel |
| --- | --- |
| Owner | Workspace, seed, settings |
| Sales | Pipeline, expansion, win/loss |
| CS | Risk queue, playbooks, account health |
| Exec | NRR, at-risk MRR, logo vs revenue churn |

**Jobs to be done**

1. “Tell me which accounts will take money with them this quarter.”
2. “Show me whether we are selling into a leaky bucket.”
3. “Give CS a queue that is not a graveyard of unused dashboards.”

**Out of ICP for v1:** marketplace consumer apps, pure services firms with no recurring revenue, enterprise procurement / SSO-first buyers.

---

## 5. Category and positioning

Keel sits between **sales CRM** and **customer success**, with a finance-grade revenue spine.

| Product | What they own | What we refuse to copy |
| --- | --- | --- |
| HubSpot / Pipedrive | Pipeline | Full CRM, marketing, email |
| ChartMogul / Baremetrics | SaaS metrics | Billing ingestion as the whole product |
| Gainsight / ChurnZero / Vitally | CS health + playbooks | Enterprise complexity, 50 integrations |
| Commodity dashboards | Two graphs (sales vs churn) | That split — Keel’s unit is the Customer Twin |
| **Keel** | Sales Twin + Churn Twin + Decision on one identity | Everything else |

**Pitch:** *One twin per customer. Left is what they buy. Right is whether they leave. Center is the play.*

---

## 6. North-star and product metrics

**North-star:** Twin decisions accepted this week (retain / expand), weighted by risk-adjusted LTV.  
Operational proxy: at-risk MRR on twins where the Combined Decision was accepted.

**Board metrics (must reconcile on the Overview):**

- MRR / ARR
- New, expansion, contraction, churn, reactivation
- Gross revenue retention (GRR) and net revenue retention (NRR)
- Logo churn vs revenue churn
- Pipeline coverage vs at-risk MRR
- Quick ratio: (new + expansion) / (contraction + churn)

If a chart cannot tie back to these, it does not go on Overview.

---

## 7. v1 scope — one complete slice

A CS or sales user can log into a **demo workspace**, see live economics, open the risk queue, inspect an account, and record an action.

### In

- Workspace + roles (demo login is acceptable; structure is real)
- Accounts, contacts, plans, subscriptions
- Opportunities / pipeline (stages: qualified → proposal → won/lost)
- MRR ledger (movements, not just a current total)
- Health snapshots (usage, tickets, payment failures, recency)
- Explainable risk engine (rules + score 0–100 + drivers)
- Risk queue (filter, sort, assign)
- Customer Twin snapshot (sales lobe + churn lobe + decision, same `as_of`)
- Twin page: Sales Twin \| Combined Decision \| Churn Twin
- Twin board (value × risk), not two unrelated charts
- Overview cockpit (the board metrics above)
- Seed dataset that looks like a real SaaS book of business
- Empty, loading, and error states
- GitHub-ready repo: README, env example, no `.venv`

### Out (explicit)

- Streamlit as the product
- Committing `.venv` or trained pickle files
- Keel’s own Stripe billing / pricing page checkout
- SSO, SCIM, audit exports
- Native email / in-app inbox
- Salesforce / HubSpot two-way sync
- Product analytics SDK inside customer apps
- Generative “AI chatbot over your customers”
- Mobile apps
- Multi-region, custom domains, white-label

Those are later PDMs. Not this one.

---

## 8. Domain model (canonical language)

```text
Workspace
  └── UserMembership (role)
  └── ProductPlan
  └── PipelineStage
  └── Account
        ├── Contact
        ├── Opportunity
        ├── Subscription
        ├── MrrMovement          // new | expansion | contraction | churn | reactivation
        ├── HealthSnapshot       // as-of date, usage, tickets, payments
        ├── RiskScore            // 0-100, drivers[], model_version
        ├── CustomerTwinSnapshot // sales + churn + decision, same as_of
        ├── TwinDecision         // accepted | edited | dismissed
        └── Activity             // note | owner_change | playbook
  └── Playbook                   // offer catalog behind the decision policy
```

**Invariants**

1. Current MRR of an account = sum of active subscription MRR in that workspace.
2. Every subscription change writes an `MrrMovement`. Totals are derived, never typed in by hand on Overview.
3. A `RiskScore` is immutable once written. Recalc creates a new row (`model_version`).
4. No query is valid without `workspace_id`.
5. A twin snapshot always contains both lobes or it is invalid (PDM-002).
6. `predicted_ltv` uses `p_churn` from the same snapshot.

**Churn engine (v1) — explainable, not theatrical ML**

Score is a weighted blend, each driver visible on the account:

| Driver | Signal | Direction |
| --- | --- | --- |
| Usage drop | 30d usage vs 90d baseline | higher risk |
| Payment failure | open failed charges | higher risk |
| Support load | tickets / 30d, reopen rate | higher risk |
| Silence | days since last activity | higher risk |
| Contract | month-to-month vs annual | higher risk |
| Contraction | recent negative MRR movement | higher risk |
| Champion risk | missing exec contact | higher risk |
| Tenure | very new or late-life without expansion | context |

Output: `score`, `band` (healthy / watch / risk / critical), `drivers[]`, `recommended_playbook`.

A later Python training kit can *fit weights* from labeled history. v1 ships with transparent weights and seeded labels so the UI is honest without a `.venv`.

---

## 9. Product surface (v1 screens)

| Route | User | Must do |
| --- | --- | --- |
| `/` | Exec | Twin board (LTV × risk) + NRR |
| `/pipeline` | Sales | CRM pipeline that feeds the Sales Twin |
| `/accounts` | All | Twins, sorted by expected value of action |
| `/accounts/[id]` | CS / Sales | **Sales Twin \| Decision \| Churn Twin** |
| `/risk` | CS | Twins whose decision is Retain or Let go |
| `/playbooks` | CS | Offer catalog behind the decision policy |
| `/settings` | Owner | Workspace, seed reset, roles |

Desktop is the primary surface. Mobile is readable, not a redesign.

Copy is operational English. No “Welcome to your app.” Empty states say what is missing and the next action (seed demo data / create account).

---

## 10. Architecture (v1)

One repo. One web app. No second product.

```text
Browser
  └── Next.js (App Router, TypeScript, Tailwind, shadcn/ui)
        ├── Server actions / route handlers
        ├── Domain (ledger, sales twin, churn twin, decision policy) — pure functions, tested
        └── SQLite locally / Postgres when DATABASE_URL is set
```

**Why this stack**

- Matches Forge-style product SaaS (typed UI, tenancy, deployable web).
- Risk math is testable TypeScript in v1 (no pickle version hell).
- Vercel-class deploy for the product; home machine only needs Node.
- Python `.venv` is an optional `/ml` kit *after* v1, for weight fitting and college-style model cards — not required to run Keel.

**Rejected for v1**

| Option | Why not |
| --- | --- |
| Streamlit app as Keel | Single-user lab, no tenancy, not a SaaS surface |
| Notebook + CSV | Cannot hold Account 360 or playbooks |
| Microservices | One team, one slice |
| Real Stripe ingestion | Needs customer credentials; seed ledger is enough to prove the model |

**Home machine later**

```text
# product (required)
node + npm install + npm run dev

# optional ML kit (never committed)
python -m venv .venv
source .venv/bin/activate
pip install -r ml/requirements.txt
```

`.venv` is gitignored. We push application code, lockfiles, and seed generators — not environments.

---

## 11. Seed book of business (so the product feels real)

Demo workspace **Northwind Cloud** (fictional B2B SaaS):

- ~80–120 accounts across Starter / Growth / Enterprise
- Mix of monthly and annual
- ~12 months of MRR movements (so NRR is computable)
- Pipeline with open + closed opportunities
- ~15–25 accounts in watch/risk/critical for a meaningful queue
- Names, regions, and plans that look like an Indian + US book, INR and USD labeled as workspace currency **USD** for metric conventions (SaaS reporting standard). Currency is a workspace field; v1 does not multi-currency convert.

Seed must be deterministic (`SEED=keel-demo-1`) so screenshots and tests match.

---

## 12. Risks

| Risk | Mitigation |
| --- | --- |
| Building a dashboard farm | Every page maps to a workflow in §9 |
| Fake ML | v1 scores are rule-based and displayed as such |
| Scope creep (CRM + CS + BI) | Out-list in §7 is binding |
| Empty-looking SaaS | Deterministic seed, not lorem |
| Deploy confusion | Product = web app. Streamlit is not a deploy target for v1 |

---

## 13. Build sequence (no calendar)

Execute in this order. Do not start 2 before 1 is true.

1. **Lock** — this PDM in git (this step).
2. **Skeleton** — Next.js app, tenancy types, gitignore, README, env example.
3. **Ledger + CRM pipeline** — opportunities → subscriptions → MRR.
4. **Both twin heads** on the same `as_of` (pure functions, tests).
5. **Decision policy + offer catalog** (value × risk matrix).
6. **Customer Twin page** (left / center / right) + twin board.
7. **Hardening** — empty/error, seed reset, README runbook, deploy config.

Do not build a sales dashboard and a churn dashboard and combine later (PDM-002).

GitHub: application code is pushed on the working branch. User connects a real GitHub repo from the New Project flow when ready. `.venv` stays on the home machine.

---

## 14. What “done” means for v1

A stranger can clone, run, open the demo workspace, and:

1. On one account, read Sales Twin, Churn Twin, and the center decision without switching tabs.
2. See why LTV is risk-adjusted (left uses right’s P(churn)).
3. Accept or dismiss the offer; it writes back onto the twin.
4. On Overview, see a value × risk board — not two unrelated graphs.

Until those four are true, we shipped the old world.

---

## 15. Open items the CEO already closed

| Question | Decision |
| --- | --- |
| Streamlit first because college / easy deploy? | No. Lab later. Product is the web app. |
| Commit `.venv`? | Never. |
| Auth in v1? | Demo user + workspace membership. Real SSO is a later PDM. |
| Python model in v1? | No. Explainable engine in-process. Optional `/ml` after. |
| Real customer data? | Seed only. CSV import is v1.1 if needed. |
| Product name? | **Keel**. |
| Two graphs (sales vs churn)? | Forbidden. Customer Twin is the unit (PDM-002). |

New scope requires **PDM-003**, not a drive-by feature.
