# SupplyChain Semantic Guardian

**Snowflake CoCo CLI Hackathon — Problem 5: Supply Chain Ontology and Governed Conversational Analytics**

A governed semantic layer for a home appliances manufacturing company that ensures every business question is answered through canonically defined, auditable data — or not answered at all.

> **Core principle:** Data can exist without being semantically governed. Ungoverned data must never be treated as authoritative.

---

## Live Demo

**Streamlit App:** [https://appcococlihackathon-37rfvd3ue4wds44ikahxeq.streamlit.app/](https://appcococlihackathon-37rfvd3ue4wds44ikahxeq.streamlit.app/)

---

## The Problem

Supply chain data is scattered across ERP, logistics, supplier, and IoT systems with inconsistent definitions. The same question yields different answers across teams:
- **Planning** asks about "delivery risk"
- **Procurement** asks about "below target"
- **Logistics** asks about "missed commitments"

All three mean the same metric, but without governance, each team queries different tables with different logic and gets different numbers.

---

## Solution Architecture

### 5-Step Governance Lifecycle

```
DISCOVER → SCAN → MAP/PROPOSE → APPROVE → QUERY
```

1. **DISCOVER** — Metadata Context skill retrieves physical schema, governance status, and transformation logic
2. **SCAN** — Governance Scanner skill detects ungoverned tables and abbreviation patterns
3. **MAP/PROPOSE** — Ontology Mapper skill maps raw columns to canonical concepts with confidence scores; Semantic Definition Manager proposes new definitions
4. **APPROVE** — Human approvers review pending definitions in the Governance Dashboard (never auto-approved)
5. **QUERY** — Governed Query Engine gates every question through the Semantic Registry before answering

### Snowflake Objects

| Layer | Schema | Objects |
|-------|--------|---------|
| Staging | `STG` | SUPPLIERS, ORDERS, SHIPMENTS, SHIPMENT_V2 (ungoverned) |
| Analytics | `ANALYTICS` | SUPPLIER_PERFORMANCE, ORDER_DETAILS, Semantic View, Cortex Agent |
| Reporting | `REPORTING` | DELIVERY_SUMMARY, AT_RISK_SUPPLIERS |
| Governance | `GOVERNANCE` | SEMANTIC_REGISTRY, SEMANTIC_MAPPINGS, GOVERNANCE_AUDIT_LOG |

### Cortex Agent

The **Supply Chain Semantic Agent** (`SUPPLY_CHAIN_GOV.ANALYTICS.SUPPLY_CHAIN_SEMANTIC_AGENT`) uses:
- **cortex_analyst_text_to_sql_tool** — Queries the Semantic View for governed analytics
- **sql_exec_tool** — Checks SEMANTIC_REGISTRY for governance status before answering
- **Model:** claude-sonnet-4-6 for orchestration

---

## 5 CoCo Skills

| Skill | Problem It Solves | Key Action |
|-------|-------------------|------------|
| **metadata-context** | Teams don't know what data exists | Retrieves schema, governance status, transformations |
| **semantic-definition-manager** | No single source of truth for field meanings | PROPOSE/APPROVE/REJECT canonical definitions |
| **governance-scanner** | Ungoverned tables silently accumulate | Scans for gaps, detects abbreviations, generates proposals |
| **governed-query-engine** | Different teams get different numbers | Gates every question through the registry |
| **ontology-mapper** | New sources arrive with incompatible naming | Maps raw columns to canonical concepts with confidence scores |

---

## Project Structure

```
snowflake_coco_cli_hackathon/
├── src/
│   └── streamlit_app.py          # Main app (5 pages, governance gate, persona consistency)
├── skills/
│   ├── metadata-context/          # CoCo skill: context provider
│   ├── semantic-definition-manager/ # CoCo skill: governance brain
│   ├── governance-scanner/        # CoCo skill: gap detector
│   ├── governed-query-engine/     # CoCo skill: governance gate
│   └── ontology-mapper/          # CoCo skill: cross-source mapper
├── cortex_project/
│   ├── cortex-project.yaml       # Cortex project manifest
│   └── SUPPLY_CHAIN_SEMANTIC_AGENT.agent.yaml  # Agent spec
├── tests/
│   └── test_governance.py        # 10 test classes validating Snowflake objects
├── scripts/
│   └── validate_solution.py      # Offline validator for skills + agent + app
├── requirements.txt
└── .gitignore
```

---

## How to Run

### Streamlit App (Local)

```bash
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml` with your Snowflake credentials:
```toml
account = "YOUR_ACCOUNT"
user = "YOUR_USER"
private_key = """-----BEGIN PRIVATE KEY-----
...your RSA private key...
-----END PRIVATE KEY-----"""
```

```bash
streamlit run src/streamlit_app.py
```

### Validate Solution

```bash
python scripts/validate_solution.py
```

### Run Tests (requires Snowflake connection)

```bash
export SNOWFLAKE_PASSWORD="your_password"
python -m pytest tests/test_governance.py -v
```

### Deploy Agent (via Cortex CLI)

```bash
cd cortex_project
snow cortex deploy
```

---

## App Pages

1. **Solution Architecture** — End-to-end overview of the problem, the 5-step lifecycle, skills, and agent
2. **Ontology** — Entity model showing Supplier, Part, Shipment, Order, Customer and their relationships
3. **Governance Dashboard** — Live KPIs, coverage metrics, full registry with approve/reject workflow
4. **Semantic Explorer** — Look up any concept to see its definition, source mapping, and plain-English calculation logic
5. **Ask Supply Chain** — Natural language Q&A with a real governance gate (queries SEMANTIC_REGISTRY before answering)

---

## Governance Gate in Action

**Governed question:** "Which suppliers have poor delivery performance?"
- System finds `Supplier On-Time Delivery` (SC-001, GOVERNED, 0.95 confidence)
- Returns data from `ANALYTICS.SUPPLIER_PERFORMANCE`

**Ungoverned question:** "What is the VENDOR_NO trend from SHIPMENT_V2?"
- System finds no governed mapping for SHIPMENT_V2
- **Refuses to answer** — shows warning that the data is not governed

---

## Sample Scenarios (Try These)

### Scenario 1: New ERP Source Arrives

A logistics partner sends a new `SHIPMENT_V2` table with columns like `VENDOR_NO`, `SHIP_DT`, `QTY_SENT`. Nobody knows if these map to existing concepts.

**What happens:**
1. The **Governance Scanner** skill detects `SHIPMENT_V2` as ungoverned
2. The **Ontology Mapper** skill maps its columns to canonical concepts:
   - `VENDOR_NO` → Supplier ID (confidence: 0.85)
   - `SHIP_DT` → Shipment Date (confidence: 0.90)
   - `QTY_SENT` → Quantity Shipped (confidence: 0.80)
3. The **Semantic Definition Manager** proposes these as `PENDING_REVIEW`
4. A data steward reviews and approves/rejects in the **Governance Dashboard**
5. Until approved, any question referencing SHIPMENT_V2 is **blocked** by the governance gate

**Try in the app:** Go to "Ask Supply Chain" and ask *"What is the VENDOR_NO trend?"* — the system will refuse because SHIPMENT_V2 is not governed.

### Scenario 2: Cross-Team Persona Consistency

Three teams ask the same question differently:
- **Planning:** "What is the delivery risk for our suppliers?"
- **Procurement:** "Which suppliers are below target?"
- **Logistics:** "Show me missed commitments"

**What happens:**
All three resolve to the same governed concept: `Supplier On-Time Delivery` (SC-001), using the same formula (`COUNT(on-time) / COUNT(total) * 100`), from the same source table (`ANALYTICS.SUPPLIER_PERFORMANCE`).

**Try in the app:** Go to "Ask Supply Chain" and try each phrasing — all return the same metric.

### Scenario 3: Governance Gap Detection

A data engineer creates a new analytics table but forgets to register its columns in the semantic registry.

**What happens:**
1. The **Governance Scanner** skill runs a scheduled scan and flags the new table
2. It detects abbreviation patterns (e.g., `SUP_` = Supplier, `_DT` = Date)
3. It generates batch PROPOSE commands for the **Semantic Definition Manager**
4. The gap appears on the **Governance Dashboard** as a drop in coverage percentage

---

## Reusability Guide

### Adapting Skills for Your Domain

Each of the 5 CoCo skills is **domain-agnostic by design**. To reuse them for a different industry (healthcare, finance, retail, etc.):

1. **Fork the skill folder** — Copy any `skills/<skill-name>/skill.md` file
2. **Change the governance tables** — Replace `SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY` with your own registry table
3. **Update abbreviation patterns** — In `governance-scanner`, change the domain-specific abbreviations (e.g., `SUP_` → `PAT_` for patient data)
4. **Adjust entity types** — The ontology mapper uses entity types like `METRIC`, `DIMENSION`, `ATTRIBUTE` — these are universal; only the canonical names change

**Example: Adapting for Healthcare**
```
SEMANTIC_REGISTRY entries:
  HC-001 | Patient Readmission Rate | METRIC | GOVERNED
  HC-002 | Average Length of Stay   | METRIC | GOVERNED
  HC-003 | Diagnosis Code           | DIMENSION | GOVERNED

Abbreviation patterns:
  PAT_ = Patient, DX_ = Diagnosis, ADM_ = Admission, _DT = Date
```

No code changes are needed in the skills — only the data in the governance tables.

### Reusing the Cortex Agent

The agent YAML (`cortex_project/SUPPLY_CHAIN_SEMANTIC_AGENT.agent.yaml`) can be adapted:

1. **Change the Semantic View** — Point `tool_resources.supply_chain_analytics` to your own semantic view
2. **Update instructions** — Replace supply chain domain terms with your domain
3. **Deploy** — Run `snow cortex deploy` to create the new agent

### Reusing the Streamlit App

The app (`src/streamlit_app.py`) connects to any Snowflake account with the same governance table structure:

1. **Create the 3 governance tables** — `SEMANTIC_REGISTRY`, `SEMANTIC_MAPPINGS`, `GOVERNANCE_AUDIT_LOG` (DDL in `scripts/` or replicate from the demo)
2. **Update `.streamlit/secrets.toml`** with your credentials
3. **Deploy** — Push to Streamlit Community Cloud or run locally

### Governance Table DDL (Quick Start)

```sql
CREATE TABLE GOVERNANCE.SEMANTIC_REGISTRY (
    CONCEPT_ID VARCHAR(20) PRIMARY KEY,
    CANONICAL_NAME VARCHAR(200),
    DEFINITION TEXT,
    ENTITY_TYPE VARCHAR(50),   -- METRIC, DIMENSION, ATTRIBUTE
    STATUS VARCHAR(50),        -- GOVERNED, PENDING_REVIEW, NOT_GOVERNED
    CONFIDENCE FLOAT,
    OWNER VARCHAR(100),
    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE GOVERNANCE.SEMANTIC_MAPPINGS (
    MAPPING_ID VARCHAR(20) PRIMARY KEY,
    CONCEPT_ID VARCHAR(20) REFERENCES SEMANTIC_REGISTRY(CONCEPT_ID),
    SOURCE_TABLE VARCHAR(200),
    SOURCE_COLUMN VARCHAR(200),
    TRANSFORMATION TEXT,
    STATUS VARCHAR(50),
    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE GOVERNANCE.GOVERNANCE_AUDIT_LOG (
    AUDIT_ID VARCHAR(20) PRIMARY KEY,
    CONCEPT_ID VARCHAR(20),
    ACTION VARCHAR(50),        -- PROPOSED, APPROVED, REJECTED, UPDATED
    PERFORMED_BY VARCHAR(100),
    DETAILS TEXT,
    PERFORMED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
```

---

## Tech Stack

- **Snowflake** — Database, Semantic View, Cortex Agent, warehouse compute
- **Snowflake CoCo CLI** — 5 reusable skills for governance automation
- **Streamlit** — Interactive dashboard deployed on Community Cloud
- **RSA Key Pair Auth** — Secure connection without password exposure

---

## Judging Criteria Alignment

| Criteria | How We Address It |
|----------|-------------------|
| **Ontology Design** | 5-entity model (Supplier → Part → Shipment → Order → Customer) with governed canonical definitions |
| **Semantic Governance** | 3-status registry (GOVERNED/PENDING/NOT_GOVERNED) with audit trail; never auto-approves |
| **CoCo Skills** | 5 reusable skills covering the full governance lifecycle |
| **Cortex Agent** | Semantic View + Agent with governance-first orchestration |
| **Conversational Analytics** | Natural language Q&A with real governance gate |
| **Persona Consistency** | Same concept resolves identically regardless of team or phrasing |
| **Reusability** | Domain-agnostic skills, portable governance tables, documented DDL |
| **Data Quality** | Ungoverned data is blocked, not just flagged; confidence scores on mappings |
