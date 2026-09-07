# PDM-002 — Customer Twin (sales + churn as one object)

**Status:** Accepted (amends PDM-001, still pre-build)  
**Owner:** CEO  
**Depends on:** [PDM-001 — Keel](./PDM-001-keel.md)  
**Build:** still not started. This memo is explanation + intelligence lock.

PDM-001 said Keel is a revenue retention OS with pipeline, ledger, and a risk queue. That is necessary plumbing. It is **not** the product idea.

The product idea, from the meta brief: **Sales and Churn are not two graphs. They are two sides of one Customer Twin. The center is a decision.**

This is the honors-domain story: Factory + Product + **Customer**. Keel owns the Customer layer.

---

## 1. Decision

Every account in Keel is a **Customer Twin**: a living, versioned object with three lobes that share one identity.

```text
┌─────────────────────┐   ┌──────────────────────┐   ┌─────────────────────┐
│     SALES TWIN      │   │  COMBINED DECISION   │   │     CHURN TWIN      │
│  what they buy      │──▶│  next best action    │◀──│  will they leave    │
│  LTV + forecast     │   │  "Retain with X"     │   │  risk + drivers     │
└─────────────────────┘   └──────────────────────┘   └─────────────────────┘
            ▲                         │                          ▲
            └──────────── Customer identity (Account) ───────────┘
```

If a screen shows MRR on the left and a pie chart of churn on the right with no shared decision, it **fails this PDM**. That is the commodity everyone else ships.

---

## 2. Why this is the industry standard (and still rare)

Industry names for the same idea:

| Discipline | Name | What they get right | What they still split |
| --- | --- | --- | --- |
| CRM | Customer 360 | One identity | Sales tab vs Service tab |
| CS platforms | Health score | Risk | Expansion lives in Salesforce |
| Marketing clouds | Next Best Action | A decision | Weak on MRR physics |
| Digital twin | Digital Twin of the Customer | Living object | Usually web-behavior, not revenue |
| Finance | LTV vs churn | Math | Spreadsheet, not a workspace |

Keel’s standard: **one twin, two inference heads, one policy.** Value and risk are computed on the same as-of timestamp, then a decision engine emits a play. The play writes back onto the twin (closed loop). That is industry-ready. Two charts is a student dashboard.

---

## 3. The SaaS (what the company is)

Keel is a **multi-tenant B2B SaaS** for the customer layer of a software company.

A **workspace** is one customer of *ours* (e.g. a SaaS founder). Inside that workspace live *their* accounts. Each of those accounts is a Customer Twin.

**What the SaaS sells (later billing, not v1):** a place where Sales, CS, and Marketing share one object instead of three tools.

**What the user does in a session**

1. Open the twin board (portfolio of customers in value × risk space).
2. Click one twin. See Sales Twin | Decision | Churn Twin.
3. Accept, edit, or dismiss the recommended offer.
4. That action becomes activity on the twin and changes the next score.

**Roles on the same twin**

| Role | Reads | Writes |
| --- | --- | --- |
| Sales | LTV, forecast, open ops | Opportunity stage |
| CS | Risk, drivers | Playbook / save attempt |
| Marketing | Decision + offer class | Campaign tag (v1.1) |
| Exec | Portfolio map | Nothing operational |

---

## 4. Two pipelines (do not confuse them)

There are two pipelines. Both feed the twin. Neither *is* the twin.

### 4.1 Revenue / CRM pipeline (human process)

This is how money is supposed to enter.

```text
Lead → Qualified → Proposal → Won / Lost
                              │
                              ▼
                    Subscription + MRR movement
                              │
                              ▼
                    Sales Twin updates (LTV, mix, forecast)
```

Rules:

- **Won** creates or expands a subscription. That is not churn.
- **Lost** is a sales outcome on an opportunity. It does not mean the account churned.
- **Churn** is a subscription ending after they were already a customer. Different event.

This pipeline is the left lobe.

### 4.2 Intelligence pipeline (machine process)

This is how the twin stays alive. Same clock for both heads.

```text
Workspace events
  (purchases, plan changes, usage, tickets, payments, silence)
        │
        ▼
  Feature store as-of t
        │
        ├──────────────► Sales Twin head
        │                 LTV, expected 12m value, expansion forecast
        │
        └──────────────► Churn Twin head
                          P(churn), time-to-churn, drivers
        │
        ▼
  Decision policy  (value × risk → offer)
        │
        ▼
  Combined Decision written onto the twin
        │
        ▼
  Human accepts / edits / dismisses  →  activity  →  next run
```

Invariant: Sales Twin and Churn Twin are scored on the **same `as_of`**. You never pair last month’s LTV with today’s risk. That is how fake 360s lie.

---

## 5. The three lobes (intelligence contract)

### Sales Twin (left)

Computed, not typed in:

| Field | Meaning |
| --- | --- |
| `current_mrr` | Active subscription MRR |
| `historical_ltv` | Sum of recognized revenue to date |
| `predicted_ltv` | Historical + expected remaining × (1 − P(churn)) — *risk-adjusted* |
| `expansion_forecast` | Expected added MRR if we sell the next plan |
| `buy_mix` | Plans / add-ons owned |
| `open_pipeline` | Open opportunities on this account |
| `next_likely_product` | Ranked next SKU |

The important industry move: **LTV is risk-adjusted.** Naive LTV ignores churn. A Sales Twin that forecasts $40k on a customer who is 80% gone is a lie. The left lobe must see the right lobe’s P(churn). That is fusion, not two widgets.

### Churn Twin (right)

| Field | Meaning |
| --- | --- |
| `p_churn` | Probability they cancel in the horizon (v1: 90 days) |
| `band` | healthy / watch / risk / critical |
| `hazard_drivers[]` | Why, with direction and weight |
| `time_to_churn` | Expected days to cancel if untreated |
| `trigger` | Last shock (failed payment, usage drop, contraction) |

Explainable. No black box percentage.

### Combined Decision (center)

A **policy**, not a slogan. Input is `(predicted_ltv, p_churn, drivers, open_pipeline, contract)`. Output is one `NextBestAction`.

v1 decision matrix (closed, testable):

| | Low risk | High risk |
| --- | --- | --- |
| **High LTV** | **Expand** — sell forecasted SKU / annual prepay | **Retain** — offer X matched to the top driver |
| **Low LTV** | **Nurture** — no discount, light touch | **Let go** — do not burn margin to save a bad-fit logo |

Offer X is matched to the **top churn driver**, not a generic coupon:

| Top driver | Offer / play |
| --- | --- |
| Failed payment | Billing rescue + dunning, not a discount |
| Usage drop | Onboarding / QBR / feature enablement |
| Support load | Named CS intervention |
| Month-to-month + price | Term lock: 2 months credit for annual |
| Champion missing | Stakeholder mapping (sales + CS) |
| Contraction | Save package on the remaining product, not a new logo hunt |

The center copy is operational, e.g.  
`Retain Helios Analytics — 2 months credit if they move to annual. Driver: month-to-month + usage drop. Risk-adjusted LTV $18.4k.`

If the user cannot read that sentence and act, the twin failed.

---

## 6. Domain additions (on top of PDM-001)

```text
Account  (identity)
  └── CustomerTwinSnapshot     // immutable, as_of, model_version
        ├── sales:  { mrr, historical_ltv, predicted_ltv, forecast, mix, next_sku }
        ├── churn:  { p_churn, band, drivers, time_to_churn, trigger }
        └── decision: { action, offer, reason, expected_value }
  └── TwinDecision             // human: accepted | edited | dismissed
```

Invariants (add to PDM-001):

5. A twin snapshot always contains both lobes or it is invalid.
6. `predicted_ltv` must use `p_churn` from the same snapshot.
7. Overview portfolio is plotted as **value × risk** (the twin board), not two unrelated charts.
8. Recording a decision is the primary write on `/accounts/[id]`. Notes are secondary.

---

## 7. Product surface change

PDM-001 `/accounts/[id]` as a 360 dump is replaced.

| Route | Now |
| --- | --- |
| `/` | Twin board: customers in LTV × risk space + NRR |
| `/pipeline` | Revenue pipeline (feeds Sales Twin) |
| `/twins` or `/accounts` | List of twins, sorted by decision priority |
| `/accounts/[id]` | **Hero: Sales Twin \| Decision \| Churn Twin** |
| `/risk` | Filter of twins whose decision is Retain or Let go |
| `/playbooks` | Offer catalog behind the decision policy |
| `/settings` | Unchanged |

Priority sort for the list: `expected_value_of_action = predicted_ltv × lift_if_we_act`. High-value save beats a cheap logo in critical.

---

## 8. What v1 still does not do

Unchanged from PDM-001 out-list, plus:

- No generative copy for offers (catalog is coded)
- No real-time web-behavior twin (usage is seeded snapshots)
- No marketing automation send (we *recommend*; we do not blast email)

---

## 9. Build sequence (replaces PDM-001 §13 from step 3)

1. Lock PDM-001 + PDM-002 (this step).
2. Skeleton (tenancy, app shell).
3. Ledger + CRM pipeline (opportunities → subscriptions → MRR).
4. Both twin heads on the same `as_of` (pure functions, tests).
5. Decision policy + offer catalog (matrix tests).
6. Customer Twin page (left / center / right) + twin board.
7. Hardening.

Do not build a sales dashboard and a churn dashboard and “combine later.” The first customer screen *is* the twin.

---

## 10. Done when

A stranger opens one account and, without switching tabs, can answer:

1. What do they buy, and what is risk-adjusted LTV?
2. Will they leave, and why?
3. What do we do now — retain with which offer, expand, nurture, or let go?

If those three require two graphs and a human to glue them, we shipped the old world.
