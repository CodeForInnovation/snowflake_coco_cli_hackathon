# Skill: metadata-context

## Problem It Solves
Teams don't know what data exists, where it lives, or whether it's trustworthy. Without context, people build reports on wrong tables or use ungoverned fields.

## Purpose
Retrieve the current technical and business context for any data object in the SUPPLY_CHAIN_GOV database. This skill is the **shared context provider** — it gathers evidence that other skills and the agent use to reason about data.

## When to Use
- Before proposing or validating any semantic definition
- Before answering any business question about supply-chain data
- When checking governance status of a table, column, or metric
- When a user asks "what data do we have about X?"

## Database Context
SUPPLY_CHAIN_GOV is the data lake for a **home appliances manufacturing company**. It has 4 schemas:
- **STG**: Raw staging data from source systems (ERP, logistics, order management). Column names are abbreviated (SUP_ID, ORD_NO, CUST_NM).
- **ANALYTICS**: Modeled tables with clean canonical names, built by joining and transforming STG data.
- **REPORTING**: Business-logic views consumed by dashboards and reports.
- **GOVERNANCE**: Semantic registry, field mappings, and audit log tracking what is governed.

## Instructions

### Step 1: Retrieve Physical Schema
```sql
-- All tables and views in the data lake
SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE, COMMENT, ROW_COUNT
FROM SUPPLY_CHAIN_GOV.INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA IN ('STG', 'ANALYTICS', 'REPORTING', 'GOVERNANCE')
ORDER BY TABLE_SCHEMA, TABLE_NAME;

-- Columns for a specific table
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COMMENT
FROM SUPPLY_CHAIN_GOV.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'
ORDER BY ORDINAL_POSITION;

-- View SQL (transformation logic for REPORTING views)
SELECT TABLE_NAME, VIEW_DEFINITION
FROM SUPPLY_CHAIN_GOV.INFORMATION_SCHEMA.VIEWS
WHERE TABLE_SCHEMA = '{schema}';
```

### Step 2: Retrieve Governance Status
```sql
-- All canonical definitions and their status
SELECT CONCEPT_ID, CANONICAL_NAME, DEFINITION, ENTITY_TYPE, STATUS, CONFIDENCE, EVIDENCE
FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
ORDER BY STATUS, CANONICAL_NAME;

-- Field-level mappings for a specific table
SELECT m.SOURCE_COLUMN, m.CANONICAL_NAME, m.TRANSFORMATION, m.STATUS,
       r.DEFINITION, r.STATUS AS GOVERNANCE_STATUS
FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS m
LEFT JOIN SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY r ON m.CONCEPT_ID = r.CONCEPT_ID
WHERE m.SOURCE_TABLE = '{table}';

-- Search for a concept by name or description
SELECT CONCEPT_ID, CANONICAL_NAME, STATUS, CONFIDENCE
FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
WHERE CANONICAL_NAME ILIKE '%{search_term}%' OR DEFINITION ILIKE '%{search_term}%';
```

### Step 3: Sample Data (when needed for evidence)
```sql
SELECT * FROM SUPPLY_CHAIN_GOV.{schema}.{table} LIMIT 5;
```

## Output Format
Structure every response into these sections:

**PHYSICAL SCHEMA** — tables, columns, types, comments that exist
**GOVERNANCE STATUS** — which concepts are GOVERNED, PENDING_REVIEW, NOT_GOVERNED
**TRANSFORMATION LOGIC** — how downstream objects are derived (view SQL, table comments)
**GAPS DETECTED** — what has no comments, no definitions, no governance entry

## Rules
1. NEVER fabricate metadata. If a column has no comment, say "no comment defined."
2. NEVER infer business meaning from column names alone. Report what exists; let other skills interpret.
3. Always check GOVERNANCE.SEMANTIC_REGISTRY before reporting on any object.
4. If a table has NO entry in SEMANTIC_MAPPINGS, flag it as "NO GOVERNANCE METADATA."
5. Clearly label each section so the output is machine-readable by downstream skills.
