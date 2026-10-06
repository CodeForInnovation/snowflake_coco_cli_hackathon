# Skill: governance-scanner

## Problem It Solves
New tables arrive in the data lake constantly. Without proactive scanning, ungoverned tables silently accumulate and get used in reports without anyone knowing their fields have no canonical definitions. This creates inconsistent metrics across teams.

## Purpose
Proactively scan a table or entire schema to detect governance gaps — columns without definitions, tables without mappings, abbreviations that need standardization. Then generate PROPOSE actions for the semantic-definition-manager skill to execute.

## When to Use
- A new table lands in STG (e.g., SHIPMENT_V2 arrives from a new logistics system)
- Periodic governance audit across a schema
- Before building a new Semantic View or dashboard
- When governance coverage is below target

## Instructions

### Step 1: Identify all columns in the target
```sql
SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.COMMENT
FROM SUPPLY_CHAIN_GOV.INFORMATION_SCHEMA.COLUMNS c
WHERE c.TABLE_SCHEMA = '{schema}' AND c.TABLE_NAME = '{table}'
ORDER BY c.ORDINAL_POSITION;
```

### Step 2: Check which columns already have governance mappings
```sql
SELECT SOURCE_COLUMN, CANONICAL_NAME, STATUS
FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS
WHERE SOURCE_TABLE = '{table}';
```

### Step 3: For each unmapped column, detect abbreviation patterns
Apply these known supply-chain abbreviation rules:
| Pattern | Expansion | Example |
|---------|-----------|---------|
| SUP_ | Supplier | SUP_ID -> SUPPLIER_ID |
| CUST_ | Customer | CUST_NM -> CUSTOMER_NAME |
| ORD_ | Order | ORD_NO -> ORDER_NUMBER |
| SHPMT_ | Shipment | SHPMT_ID -> SHIPMENT_ID |
| _NM | Name | SUP_NM -> SUPPLIER_NAME |
| _DT | Date | PROM_DT -> PROMISED_DATE |
| _AMT | Amount/Cost | FREIGHT_AMT -> FREIGHT_COST |
| _PCT | Percentage | PERF_PCT -> PERFORMANCE_PERCENTAGE |
| _QTY | Quantity | SHIP_QTY -> SHIPPED_QUANTITY |
| _ID | Identifier | SUP_ID -> SUPPLIER_ID |
| _NO | Number | ORD_NO -> ORDER_NUMBER |
| CNTRY | Country | CNTRY -> COUNTRY |

### Step 4: Check for conflicting definitions
```sql
-- Find if the proposed canonical name already exists with a different source
SELECT CONCEPT_ID, CANONICAL_NAME, STATUS
FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
WHERE CANONICAL_NAME = '{proposed_canonical_name}';
```

### Step 5: Generate a scan report
For each column, output:
- **Column**: Physical column name
- **Status**: GOVERNED / PENDING_REVIEW / NOT_GOVERNED / NO_MAPPING
- **Proposed Name**: Canonical name suggestion (if unmapped)
- **Proposed Definition**: Business definition (if unmapped)
- **Confidence**: How confident the suggestion is
- **Conflict**: Whether a conflicting definition exists

### Step 6: Generate batch PROPOSE commands
For all unmapped columns, generate the SQL INSERT statements that the semantic-definition-manager would execute, ready for review:

```sql
-- Batch proposal for {table}
INSERT INTO SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
(CONCEPT_ID, CANONICAL_NAME, DEFINITION, ENTITY_TYPE, STATUS, CONFIDENCE, EVIDENCE, VERSION, CREATED_BY)
VALUES
  ('{id1}', '{name1}', '{def1}', '{type1}', 'PENDING_REVIEW', {conf1}, 'Auto-scanned from {table}', 1, 'governance-scanner'),
  ('{id2}', '{name2}', '{def2}', '{type2}', 'PENDING_REVIEW', {conf2}, 'Auto-scanned from {table}', 1, 'governance-scanner');
```

## Output Format
```
GOVERNANCE SCAN REPORT: {schema}.{table}
=========================================
Total Columns:     {n}
Already Governed:  {g}
Pending Review:    {p}
Not Governed:      {ng}
No Mapping:        {nm}
Coverage:          {pct}%

GAPS FOUND:
- {column1}: NO_MAPPING -> Proposed: {canonical1} ({confidence})
- {column2}: NO_MAPPING -> Proposed: {canonical2} ({confidence})

CONFLICTS:
- {column}: Proposed name "{name}" already exists as {concept_id} ({status})

READY TO PROPOSE: {count} new definitions (run semantic-definition-manager PROPOSE)
```

## Rules
1. Never auto-approve. All proposals from scanning start as PENDING_REVIEW.
2. Flag conflicts but do not resolve them — escalate to a data steward.
3. If a column name matches no known abbreviation pattern, set confidence to 0.5 and flag for human review.
4. Always compare against existing SEMANTIC_REGISTRY to avoid duplicates.
5. Include the source table in evidence so proposals are traceable.
