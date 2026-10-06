# Skill: semantic-definition-manager

## Problem It Solves
Raw data arrives with cryptic column names (SUP_ID, CNTRY, FREIGHT_AMT). Different teams invent their own names and definitions, creating conflicting metrics. There is no single source of truth for what a field means.

## Purpose
Create, update, and manage canonical business definitions for supply-chain data fields. This skill is the **governance brain** — it proposes standardized definitions, tracks approvals, and ensures no conflicting or duplicate definitions exist.

## When to Use
- A new table lands in STG with undefined columns
- A user wants to standardize a raw column name
- A pending definition needs approval or rejection
- An existing definition needs to be updated
- Before creating a Semantic View — all referenced fields must be governed first

## Prerequisites
ALWAYS use the **metadata-context** skill first to gather physical schema and existing governance data before performing any operation. Never propose blind.

## Operations

### PROPOSE — Suggest a new canonical definition
**When:** A raw column or metric has no governed definition.

1. Gather context via metadata-context skill
2. Analyze column name, data type, and usage in downstream objects
3. Propose canonical name + definition with evidence and confidence score
4. Write to SEMANTIC_REGISTRY with STATUS = 'PENDING_REVIEW'
5. Write to SEMANTIC_MAPPINGS linking physical column to concept
6. Log in GOVERNANCE_AUDIT_LOG

```sql
-- Step 1: Insert the proposed definition
INSERT INTO SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
(CONCEPT_ID, CANONICAL_NAME, DEFINITION, ENTITY_TYPE, STATUS, CONFIDENCE, EVIDENCE, VERSION, CREATED_BY)
VALUES ('{concept_id}', '{canonical_name}', '{definition}', '{entity_type}', 'PENDING_REVIEW', {confidence}, '{evidence}', 1, '{actor}');

-- Step 2: Link it to the physical source
INSERT INTO SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS
(MAPPING_ID, CONCEPT_ID, SOURCE_DATABASE, SOURCE_SCHEMA, SOURCE_TABLE, SOURCE_COLUMN, CANONICAL_NAME, TRANSFORMATION, STATUS)
VALUES ('{mapping_id}', '{concept_id}', 'SUPPLY_CHAIN_GOV', '{schema}', '{table}', '{column}', '{canonical_name}', '{transformation}', 'PENDING_REVIEW');

-- Step 3: Audit trail
INSERT INTO SUPPLY_CHAIN_GOV.GOVERNANCE.GOVERNANCE_AUDIT_LOG
(AUDIT_ID, CONCEPT_ID, ACTION, ACTOR, DETAILS)
VALUES ('{audit_id}', '{concept_id}', 'PROPOSED', '{actor}', '{details}');
```

### APPROVE — Mark a pending definition as governed
**When:** A data steward reviews and accepts a proposed definition.

```sql
UPDATE SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
SET STATUS = 'GOVERNED', APPROVED_BY = '{actor}', APPROVED_AT = CURRENT_TIMESTAMP(), UPDATED_AT = CURRENT_TIMESTAMP()
WHERE CONCEPT_ID = '{concept_id}' AND STATUS = 'PENDING_REVIEW';

UPDATE SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS
SET STATUS = 'GOVERNED', UPDATED_AT = CURRENT_TIMESTAMP()
WHERE CONCEPT_ID = '{concept_id}';

INSERT INTO SUPPLY_CHAIN_GOV.GOVERNANCE.GOVERNANCE_AUDIT_LOG
(AUDIT_ID, CONCEPT_ID, ACTION, ACTOR, DETAILS)
VALUES ('{audit_id}', '{concept_id}', 'APPROVED', '{actor}', '{details}');
```

### REJECT — Reject a pending definition
**When:** A proposed definition is inaccurate or unnecessary.

```sql
UPDATE SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
SET STATUS = 'NOT_GOVERNED', UPDATED_AT = CURRENT_TIMESTAMP()
WHERE CONCEPT_ID = '{concept_id}' AND STATUS = 'PENDING_REVIEW';

INSERT INTO SUPPLY_CHAIN_GOV.GOVERNANCE.GOVERNANCE_AUDIT_LOG
(AUDIT_ID, CONCEPT_ID, ACTION, ACTOR, DETAILS)
VALUES ('{audit_id}', '{concept_id}', 'REJECTED', '{actor}', '{details}');
```

### UPDATE — Modify an existing governed definition
**When:** Business logic changes (e.g., "on-time" now means within 2 days, not same day).

```sql
UPDATE SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
SET DEFINITION = '{new_definition}', VERSION = VERSION + 1, UPDATED_AT = CURRENT_TIMESTAMP()
WHERE CONCEPT_ID = '{concept_id}';

INSERT INTO SUPPLY_CHAIN_GOV.GOVERNANCE.GOVERNANCE_AUDIT_LOG
(AUDIT_ID, CONCEPT_ID, ACTION, ACTOR, DETAILS)
VALUES ('{audit_id}', '{concept_id}', 'UPDATED', '{actor}', 'Definition changed: {details}');
```

### VALIDATE — Check consistency of an existing definition
**When:** Periodic health check or before deploying a Semantic View.

Verify:
1. Source columns referenced in SEMANTIC_MAPPINGS still exist in INFORMATION_SCHEMA.COLUMNS
2. Transformation logic matches what REPORTING views actually compute
3. No conflicting definitions exist for the same physical column
4. No orphan mappings (mapping exists but concept was deleted)

## Output Format
For every operation, return:
- **Operation**: PROPOSE / APPROVE / REJECT / UPDATE / VALIDATE
- **Concept**: Canonical name
- **Definition**: Plain English definition
- **Evidence**: Why this was proposed or changed
- **Confidence**: 0.0 to 1.0
- **Status**: GOVERNED / PENDING_REVIEW / NOT_GOVERNED
- **Source**: Physical table.column

## Rules
1. **NEVER auto-approve.** New definitions always start as PENDING_REVIEW.
2. Always gather metadata-context BEFORE proposing.
3. Include evidence for every proposal — never propose without justification.
4. Use sequential IDs: SC-NNN for concepts, MAP-NNN for mappings, AUD-NNN for audit entries.
5. Check for existing definitions before creating duplicates.
6. Do NOT overwrite a GOVERNED definition without explicit user request.
