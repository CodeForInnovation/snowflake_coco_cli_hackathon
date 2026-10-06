# Skill: governed-query-engine

## Problem It Solves
Business users ask questions like "Which suppliers have poor delivery performance?" Different teams ask the same question in different words and get different numbers because they query different tables with different logic. Worse, some teams unknowingly query ungoverned data.

## Purpose
Gate every data question through the governance registry **before** answering it. This skill ensures:
1. The question maps to a **governed** canonical concept
2. The answer uses the **canonical definition** (not ad-hoc logic)
3. Ungoverned data is **flagged and refused**, not silently used
4. Different personas asking the same question get the **same answer**

## When to Use
- Any natural language question about supply chain data
- When the Cortex Agent receives a business question
- When the Streamlit "Ask Supply Chain" page receives input

## Instructions

### Step 1: Identify the concept being asked about
Parse the question for supply-chain terms and map to canonical concepts:

| Question Keywords | Canonical Concept | Concept ID |
|---|---|---|
| delivery, on-time, OTD, late, delay, risk, target, commitment | On-Time Delivery Percentage | SC-001 |
| fill rate, shipped, fulfilled, quantity | Fill Rate Percentage | SC-002 |
| supplier, vendor, provider | Supplier Name / Supplier ID | SC-003/SC-004 |
| country, region, origin | Country | SC-005 |
| freight, cost, shipping cost | Freight Cost | SC-008 |

### Step 2: Check governance status
```sql
SELECT CONCEPT_ID, CANONICAL_NAME, DEFINITION, STATUS, CONFIDENCE
FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
WHERE CANONICAL_NAME ILIKE '%{matched_concept}%'
   OR DEFINITION ILIKE '%{keyword}%';
```

### Step 3: Branch based on governance status

#### If STATUS = 'GOVERNED':
Proceed with the query. Always include governance metadata in the response.

```sql
-- Get the canonical source mapping
SELECT m.SOURCE_TABLE, m.SOURCE_COLUMN, m.TRANSFORMATION, r.DEFINITION
FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS m
JOIN SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY r ON m.CONCEPT_ID = r.CONCEPT_ID
WHERE r.CANONICAL_NAME = '{concept_name}' AND r.STATUS = 'GOVERNED';
```

Then query the governed source table (ANALYTICS or REPORTING schema) using the canonical column.

#### If STATUS = 'PENDING_REVIEW':
Return a warning:
> "**{concept_name}** has a proposed definition but it has not yet been approved. The data exists but cannot be used as authoritative until a data steward approves it via the Governance Dashboard."

Show the proposed definition but do NOT execute a data query.

#### If STATUS = 'NOT_GOVERNED':
Return a governance alert:
> "**GOVERNANCE ALERT:** {concept_name} is NOT GOVERNED. The data exists in {source_table} but its semantic definition has not been established. I will not treat this source as authoritative. To use this data, propose a canonical definition using the Governance Scanner or Semantic Definition Manager."

#### If NO MATCH in registry:
> "No governed concept matches your question. Available governed concepts are: {list}. Rephrase your question using a governed concept, or use the Governance Scanner to propose definitions for new data."

### Step 4: Format the response
Every response MUST include:

```
QUESTION: {original question}
CONCEPT: {canonical_name}
DEFINITION: {canonical definition}
STATUS: {GOVERNED / PENDING_REVIEW / NOT_GOVERNED / NOT_FOUND}
SOURCE: {schema.table.column}
GOVERNANCE GATE: {PASSED / BLOCKED}

{data or refusal message}
```

### Step 5: Persona consistency check
Multiple phrasings of the same question must resolve to the same concept:
- "Which suppliers are creating delivery risk?" -> On-Time Delivery Percentage
- "Which suppliers are below our delivery target?" -> On-Time Delivery Percentage
- "Which suppliers are missing delivery commitments?" -> On-Time Delivery Percentage

All three return the exact same data from ANALYTICS.SUPPLIER_PERFORMANCE.ON_TIME_DELIVERY_PCT.

## Rules
1. **NEVER answer from ungoverned data.** If the governance gate fails, refuse and explain why.
2. **ALWAYS show governance metadata** alongside the answer — concept name, definition, source, status.
3. **Same question = same answer**, regardless of phrasing or who asks.
4. If multiple concepts match, ask the user to clarify which they mean.
5. Use ANALYTICS or REPORTING schema tables for answers, never STG directly.
6. When refusing ungoverned data, always point the user to the next step (Governance Dashboard, Scanner, or Definition Manager).
