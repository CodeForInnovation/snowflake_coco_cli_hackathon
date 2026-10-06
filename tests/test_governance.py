"""
Unit tests for SupplyChain Semantic Guardian governance logic.
Validates that the governance registry, mappings, and audit log
are consistent and that the governance gate works correctly.

Run: python -m pytest tests/test_governance.py -v
"""
import os
import pytest
import snowflake.connector
from cryptography.hazmat.primitives import serialization


@pytest.fixture(scope="module")
def conn():
    """Create a Snowflake connection using env vars or secrets."""
    account = os.environ.get("SNOWFLAKE_ACCOUNT", "NKUOKGO-UM83108")
    user = os.environ.get("SNOWFLAKE_USER", "ARUNACHALAM")
    warehouse = os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
    database = os.environ.get("SNOWFLAKE_DATABASE", "SUPPLY_CHAIN_GOV")
    role = os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN")
    password = os.environ.get("SNOWFLAKE_PASSWORD", "")

    params = dict(account=account, user=user, warehouse=warehouse, database=database, role=role)
    if password:
        params["password"] = password

    connection = snowflake.connector.connect(**params)
    yield connection
    connection.close()


def query(conn, sql):
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# -------------------------------------------------------
# Test 1: All schemas exist
# -------------------------------------------------------
class TestSchemaExists:
    def test_stg_schema(self, conn):
        rows = query(conn, "SHOW SCHEMAS LIKE 'STG' IN DATABASE SUPPLY_CHAIN_GOV")
        assert len(rows) == 1

    def test_analytics_schema(self, conn):
        rows = query(conn, "SHOW SCHEMAS LIKE 'ANALYTICS' IN DATABASE SUPPLY_CHAIN_GOV")
        assert len(rows) == 1

    def test_reporting_schema(self, conn):
        rows = query(conn, "SHOW SCHEMAS LIKE 'REPORTING' IN DATABASE SUPPLY_CHAIN_GOV")
        assert len(rows) == 1

    def test_governance_schema(self, conn):
        rows = query(conn, "SHOW SCHEMAS LIKE 'GOVERNANCE' IN DATABASE SUPPLY_CHAIN_GOV")
        assert len(rows) == 1


# -------------------------------------------------------
# Test 2: Core tables have data
# -------------------------------------------------------
class TestTablesHaveData:
    def test_suppliers(self, conn):
        rows = query(conn, "SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.STG.SUPPLIERS")
        assert rows[0]["N"] > 0

    def test_orders(self, conn):
        rows = query(conn, "SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.STG.ORDERS")
        assert rows[0]["N"] > 0

    def test_shipments(self, conn):
        rows = query(conn, "SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.STG.SHIPMENTS")
        assert rows[0]["N"] > 0

    def test_supplier_performance(self, conn):
        rows = query(conn, "SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.ANALYTICS.SUPPLIER_PERFORMANCE")
        assert rows[0]["N"] > 0

    def test_order_details(self, conn):
        rows = query(conn, "SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.ANALYTICS.ORDER_DETAILS")
        assert rows[0]["N"] > 0

    def test_semantic_registry(self, conn):
        rows = query(conn, "SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY")
        assert rows[0]["N"] >= 10


# -------------------------------------------------------
# Test 3: Governance registry has all three statuses
# -------------------------------------------------------
class TestGovernanceStatuses:
    def test_governed_exists(self, conn):
        rows = query(conn, "SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY WHERE STATUS='GOVERNED'")
        assert rows[0]["N"] >= 1

    def test_pending_exists(self, conn):
        rows = query(conn, "SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY WHERE STATUS='PENDING_REVIEW'")
        assert rows[0]["N"] >= 1

    def test_not_governed_exists(self, conn):
        rows = query(conn, "SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY WHERE STATUS='NOT_GOVERNED'")
        assert rows[0]["N"] >= 1


# -------------------------------------------------------
# Test 4: Every registry entry has required fields
# -------------------------------------------------------
class TestRegistryDataQuality:
    def test_no_null_concept_ids(self, conn):
        rows = query(conn, "SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY WHERE CONCEPT_ID IS NULL")
        assert rows[0]["N"] == 0

    def test_no_null_names(self, conn):
        rows = query(conn, "SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY WHERE CANONICAL_NAME IS NULL")
        assert rows[0]["N"] == 0

    def test_no_null_definitions(self, conn):
        rows = query(conn, "SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY WHERE DEFINITION IS NULL")
        assert rows[0]["N"] == 0

    def test_no_duplicate_concept_ids(self, conn):
        rows = query(conn, """
            SELECT CONCEPT_ID, COUNT(*) AS N
            FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
            GROUP BY CONCEPT_ID HAVING COUNT(*) > 1
        """)
        assert len(rows) == 0, f"Duplicate concept IDs: {rows}"


# -------------------------------------------------------
# Test 5: Mappings are consistent with registry
# -------------------------------------------------------
class TestMappingsConsistency:
    def test_all_mappings_have_registry_entry(self, conn):
        rows = query(conn, """
            SELECT m.CONCEPT_ID
            FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS m
            LEFT JOIN SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY r ON m.CONCEPT_ID = r.CONCEPT_ID
            WHERE r.CONCEPT_ID IS NULL
        """)
        assert len(rows) == 0, f"Orphan mappings: {rows}"

    def test_governed_mappings_match_governed_registry(self, conn):
        rows = query(conn, """
            SELECT m.CONCEPT_ID, m.STATUS AS MAP_STATUS, r.STATUS AS REG_STATUS
            FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS m
            JOIN SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY r ON m.CONCEPT_ID = r.CONCEPT_ID
            WHERE m.STATUS = 'GOVERNED' AND r.STATUS != 'GOVERNED'
        """)
        assert len(rows) == 0, f"Mapping governed but registry not: {rows}"


# -------------------------------------------------------
# Test 6: Governance gate — ungoverned data blocked
# -------------------------------------------------------
class TestGovernanceGate:
    def test_shipment_v2_is_ungoverned(self, conn):
        """SHIPMENT_V2 should NOT appear in governed mappings."""
        rows = query(conn, """
            SELECT * FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS
            WHERE SOURCE_TABLE = 'SHIPMENT_V2' AND STATUS = 'GOVERNED'
        """)
        assert len(rows) == 0, "SHIPMENT_V2 should not be governed"

    def test_on_time_delivery_is_governed(self, conn):
        rows = query(conn, """
            SELECT STATUS FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
            WHERE CANONICAL_NAME = 'Supplier On-Time Delivery'
        """)
        assert len(rows) == 1
        assert rows[0]["STATUS"] == "GOVERNED"


# -------------------------------------------------------
# Test 7: Persona consistency — same concept for all teams
# -------------------------------------------------------
class TestPersonaConsistency:
    def test_delivery_resolves_to_same_concept(self, conn):
        """All delivery-related keywords should resolve to the same concept."""
        rows = query(conn, """
            SELECT DISTINCT CONCEPT_ID FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
            WHERE (CANONICAL_NAME ILIKE '%delivery%' OR DEFINITION ILIKE '%delivery%')
            AND STATUS = 'GOVERNED' AND ENTITY_TYPE = 'METRIC'
        """)
        assert len(rows) == 1, f"Delivery should resolve to exactly one metric, got {len(rows)}"


# -------------------------------------------------------
# Test 8: Semantic View exists
# -------------------------------------------------------
class TestSemanticView:
    def test_semantic_view_exists(self, conn):
        rows = query(conn, "SHOW SEMANTIC VIEWS LIKE 'SUPPLY_CHAIN_SV' IN SCHEMA SUPPLY_CHAIN_GOV.ANALYTICS")
        assert len(rows) == 1


# -------------------------------------------------------
# Test 9: Cortex Agent exists
# -------------------------------------------------------
class TestCortexAgent:
    def test_agent_exists(self, conn):
        rows = query(conn, "SHOW AGENTS LIKE 'SUPPLY_CHAIN_SEMANTIC_AGENT' IN SCHEMA SUPPLY_CHAIN_GOV.ANALYTICS")
        assert len(rows) == 1


# -------------------------------------------------------
# Test 10: Audit log has entries
# -------------------------------------------------------
class TestAuditLog:
    def test_audit_log_not_empty(self, conn):
        rows = query(conn, "SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.GOVERNANCE.GOVERNANCE_AUDIT_LOG")
        assert rows[0]["N"] > 0

    def test_audit_log_has_required_fields(self, conn):
        rows = query(conn, """
            SELECT COUNT(*) AS N FROM SUPPLY_CHAIN_GOV.GOVERNANCE.GOVERNANCE_AUDIT_LOG
            WHERE AUDIT_ID IS NULL OR CONCEPT_ID IS NULL OR ACTION IS NULL
        """)
        assert rows[0]["N"] == 0
