# Skill: ontology-mapper

## Problem It Solves
When a new data source arrives (e.g., SHIPMENT_V2 from a different logistics vendor), its column names don't match the existing canonical names. VENDOR_NO means the same thing as SUP_ID, but without explicit mapping, the system treats them as unrelated. Teams end up with duplicate, conflicting definitions for the same real-world concept.

## Purpose
Map raw column names from new or ungoverned tables to existing canonical concepts in the ontology. This skill bridges the gap between "new data arrived" and "it's integrated into our governed semantic layer."

## When to Use
- A new table arrives with different naming conventions (e.g., SHIPMENT_V2 uses VENDOR_NO instead of SUP_ID)
- Merging data from an acquired company or new vendor
- Reconciling columns across STG tables that refer to the same business concept
- Before the governance-scanner proposes definitions, to check if existing concepts already cover the new columns

## Instructions

### Step 1: Get columns from the new/ungoverned table
```sql
SELECT COLUMN_NAME, DATA_TYPE, COMMENT
FROM SUPPLY_CHAIN_GOV.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'
ORDER BY ORDINAL_POSITION;
```

### Step 2: Get all existing canonical concepts
```sql
SELECT CONCEPT_ID, CANONICAL_NAME, DEFINITION, ENTITY_TYPE, STATUS
FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
WHERE STATUS IN ('GOVERNED', 'PENDING_REVIEW')
ORDER BY CANONICAL_NAME;
```

### Step 3: Get existing column mappings for comparison
```sql
SELECT SOURCE_TABLE, SOURCE_COLUMN, CANONICAL_NAME
FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS
WHERE STATUS = 'GOVERNED'
ORDER BY CANONICAL_NAME;
```

### Step 4: Apply mapping rules

#### Rule 1: Direct name match
If the new column name exactly matches an existing canonical name (case-insensitive), map directly.

#### Rule 2: Abbreviation expansion
Expand abbreviations using known patterns and compare:
| New Column | Expands To | Matches Canonical |
|---|---|---|
| VENDOR_NO | Vendor Number | Supplier ID (same entity, different name) |
| CONFIRMED_DT | Confirmed Date | Promised Date (semantic equivalent) |
| SHIP_QTY | Shipped Quantity | Ordered Quantity (related but different) |
| PERF_PCT | Performance Percentage | On-Time Delivery Percentage (if in shipment context) |

#### Rule 3: Data type + context matching
If names don't match but data types and table context align:
- DATE columns in a shipment table near a "promised" or "actual" concept -> likely delivery dates
- NUMERIC(5,2) columns ending in _PCT -> likely percentage metrics
- VARCHAR columns ending in _NO or _ID -> likely identifiers

#### Rule 4: Sample value comparison
```sql
-- Compare sample values between new and existing mapped columns
SELECT DISTINCT {new_column} FROM SUPPLY_CHAIN_GOV.{schema}.{table} LIMIT 20;
SELECT DISTINCT {existing_column} FROM SUPPLY_CHAIN_GOV.{existing_schema}.{existing_table} LIMIT 20;
```
If value patterns overlap significantly (e.g., same supplier IDs appear in both), they likely refer to the same entity.

### Step 5: Generate mapping report

```
ONTOLOGY MAPPING REPORT: {schema}.{table}
==========================================

DIRECT MATCHES (high confidence):
  {new_col} -> {canonical_name} (Concept: {concept_id}, Confidence: 0.95)

SEMANTIC EQUIVALENTS (medium confidence, needs review):
  {new_col} -> {canonical_name} (Reason: {explanation}, Confidence: 0.7)

NO MATCH (new concept needed):
  {new_col} -> No existing concept. Recommend: PROPOSE via semantic-definition-manager

CONFLICTS (same concept, different source):
  {new_col} maps to {canonical_name} but {existing_table}.{existing_col} already maps there.
  Resolution needed: Are these the same data or different measures?
```

### Step 6: Generate integration SQL
For confirmed mappings, generate the SQL to register them:

```sql
-- Map VENDOR_NO to existing Supplier ID concept
INSERT INTO SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS
(MAPPING_ID, CONCEPT_ID, SOURCE_DATABASE, SOURCE_SCHEMA, SOURCE_TABLE, SOURCE_COLUMN, 
 CANONICAL_NAME, TRANSFORMATION, STATUS)
VALUES ('{mapping_id}', '{existing_concept_id}', 'SUPPLY_CHAIN_GOV', '{schema}', '{table}', 
        '{new_column}', '{canonical_name}', 'Direct mapping from {new_column}', 'PENDING_REVIEW');
```

## Example: Mapping STG.SHIPMENT_V2

Input table SHIPMENT_V2 has: VENDOR_NO, CONFIRMED_DT, ACTUAL_DT, SHIP_QTY, PERF_PCT

Mapping results:
- VENDOR_NO -> Supplier ID (SC-004): Same entity, different naming convention from logistics vendor. Confidence: 0.85
- CONFIRMED_DT -> Promised Date (SC-007): Vendor uses "confirmed" instead of "promised". Confidence: 0.75
- ACTUAL_DT -> Actual Delivery Date (SC-006): Direct semantic match. Confidence: 0.95
- SHIP_QTY -> No exact match. Closest: Ordered Quantity, but this is shipped not ordered. Recommend: PROPOSE new concept "Shipped Quantity". Confidence: 0.6
- PERF_PCT -> On-Time Delivery Percentage (SC-001): Pre-calculated metric, same meaning. Confidence: 0.8

## Rules
1. Never auto-map with confidence below 0.7 without flagging for human review.
2. Always compare sample values when confidence is between 0.6 and 0.8.
3. If a new column could map to multiple existing concepts, list all candidates and ask for clarification.
4. Mappings are always PENDING_REVIEW — the data steward approves.
5. Document the mapping rationale in evidence so future auditors understand why.
6. If the new table has columns that don't map to ANY existing concept, hand off to governance-scanner for new definition proposals.
