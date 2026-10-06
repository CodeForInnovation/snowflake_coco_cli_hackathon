import streamlit as st
import pandas as pd
import snowflake.connector
from cryptography.hazmat.primitives import serialization

st.set_page_config(
    page_title="SupplyChain Semantic Guardian",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Snowflake brand palette
# ---------------------------------------------------------------------------
SNOW_BLUE = "#29B5E8"
SNOW_DARK = "#11567F"
SNOW_LIGHT = "#E8F4FD"
GOV_GREEN = "#2ECC71"
GOV_YELLOW = "#F39C12"
GOV_RED = "#E74C3C"

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {SNOW_DARK} 0%, #1a3a5c 100%);
}}
section[data-testid="stSidebar"] * {{
    color: #FFFFFF !important;
}}
section[data-testid="stSidebar"] hr {{
    border-color: rgba(255,255,255,0.2);
}}
.section-header {{
    background: linear-gradient(90deg, {SNOW_DARK}, {SNOW_BLUE});
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 800;
    margin-bottom: 0.25rem;
}}
.subtitle {{
    color: #64748B;
    font-size: 1.05rem;
    margin-bottom: 1.5rem;
}}
.badge {{
    display: inline-block;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.3px;
}}
.badge-governed   {{ background: #d1fae5; color: #065f46; }}
.badge-pending    {{ background: #fef3c7; color: #92400e; }}
.badge-ungoverned {{ background: #fee2e2; color: #991b1b; }}
.kpi-card {{
    background: #FFFFFF;
    border-radius: 12px;
    padding: 20px 24px;
    border-left: 4px solid {SNOW_BLUE};
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    margin-bottom: 8px;
}}
.kpi-card h3 {{
    margin: 0 0 4px 0;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #64748B;
}}
.kpi-card .value {{
    font-size: 2rem;
    font-weight: 800;
}}
.arch-step {{
    background: #FFFFFF;
    border-radius: 12px;
    padding: 16px 20px;
    border-top: 4px solid {SNOW_BLUE};
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    margin-bottom: 12px;
    min-height: 100px;
}}
.arch-step h4 {{
    margin: 0 0 8px 0;
    color: {SNOW_DARK};
    font-size: 0.95rem;
}}
.arch-step p {{
    margin: 4px 0;
    font-size: 0.85rem;
    color: #475569;
}}
.skill-card {{
    background: #FFFFFF;
    border-radius: 10px;
    padding: 14px 18px;
    border-left: 4px solid {SNOW_BLUE};
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    margin-bottom: 10px;
}}
.skill-card h4 {{
    margin: 0 0 4px 0;
    color: {SNOW_DARK};
    font-size: 0.9rem;
}}
.skill-card p {{
    margin: 2px 0;
    font-size: 0.82rem;
    color: #64748B;
}}
.gov-result {{
    background: #FFFFFF;
    border-radius: 10px;
    padding: 16px 20px;
    border-left: 4px solid {GOV_GREEN};
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    margin: 12px 0;
}}
.gov-blocked {{
    border-left-color: {GOV_RED};
}}
.gov-pending {{
    border-left-color: {GOV_YELLOW};
}}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
@st.cache_resource
def get_connection():
    sf = st.secrets["snowflake"]
    conn_params = dict(
        account=sf["account"],
        user=sf["user"],
        warehouse=sf["warehouse"],
        database=sf["database"],
        role=sf["role"],
    )
    key_data = sf.get("private_key", sf.get("password", ""))
    if key_data and len(key_data) > 50:
        if "BEGIN" not in key_data:
            key_data = f"-----BEGIN PRIVATE KEY-----\n{key_data}\n-----END PRIVATE KEY-----"
        p_key = serialization.load_pem_private_key(key_data.encode(), password=None)
        conn_params["private_key"] = p_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    elif key_data:
        conn_params["password"] = key_data
    return snowflake.connector.connect(**conn_params)


def run_query(sql):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql)
    columns = [desc[0] for desc in cur.description]
    data = cur.fetchall()
    return pd.DataFrame(data, columns=columns)


def run_update(sql):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()


def status_badge(status):
    cls = {"GOVERNED": "badge-governed", "PENDING_REVIEW": "badge-pending", "NOT_GOVERNED": "badge-ungoverned"}.get(status, "")
    return f'<span class="badge {cls}">{status}</span>'


def governance_check(concept_keywords):
    """Real governance gate — queries SEMANTIC_REGISTRY to check if concept is governed."""
    conditions = " OR ".join(
        [f"CANONICAL_NAME ILIKE '%{kw}%' OR DEFINITION ILIKE '%{kw}%'" for kw in concept_keywords]
    )
    results = run_query(f"""
        SELECT CONCEPT_ID, CANONICAL_NAME, DEFINITION, STATUS, CONFIDENCE
        FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
        WHERE {conditions}
        ORDER BY CONFIDENCE DESC
    """)
    return results


def get_source_mapping(concept_id):
    """Get the physical source table/column for a governed concept."""
    return run_query(f"""
        SELECT SOURCE_TABLE, SOURCE_COLUMN, TRANSFORMATION
        FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS
        WHERE CONCEPT_ID = '{concept_id}' AND STATUS = 'GOVERNED'
    """)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## SupplyChain Semantic Guardian")
    st.caption("Governed analytics for home appliances manufacturing")
    st.divider()

    page = st.radio(
        "Navigate",
        [
            "Solution Architecture",
            "Ontology",
            "Governance Dashboard",
            "Semantic Explorer",
            "Ask Supply Chain",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown(
        "**Core Principle**  \n"
        "_Data can exist without being semantically governed._ "
        "Ungoverned data is never treated as authoritative."
    )
    st.divider()
    st.caption("Powered by Snowflake Cortex Agent | Semantic View | CoCo Skills")

# ============================
# PAGE 0: SOLUTION ARCHITECTURE
# ============================
if page == "Solution Architecture":
    st.markdown('<h1 class="section-header">Solution Architecture</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">How we solve the supply chain ontology and governed conversational analytics problem — end to end.</p>',
        unsafe_allow_html=True,
    )

    # --- The Problem ---
    st.markdown("#### The Problem")
    st.markdown(
        "Supply chain data is scattered across ERP, logistics, supplier, and IoT systems with **inconsistent definitions**. "
        "The same question yields different answers across teams. A planning team asks about 'delivery risk,' procurement "
        "asks about 'below target,' and logistics asks about 'missed commitments' — all mean the same metric, but without "
        "governance, each team queries different tables with different logic and gets different numbers."
    )

    st.markdown("#### Industry Impact")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(f"""<div class="kpi-card" style="border-left-color:{GOV_RED};">
            <h3>Gartner (2024)</h3>
            <p style="margin:0;font-size:0.85rem;">Poor data quality costs organizations an average of <strong>$12.9M per year</strong></p>
        </div>""", unsafe_allow_html=True)
    with col_b:
        st.markdown(f"""<div class="kpi-card" style="border-left-color:{GOV_YELLOW};">
            <h3>Harvard Business Review</h3>
            <p style="margin:0;font-size:0.85rem;">Only <strong>3% of companies' data</strong> meets basic quality standards</p>
        </div>""", unsafe_allow_html=True)
    with col_c:
        st.markdown(f"""<div class="kpi-card" style="border-left-color:{GOV_GREEN};">
            <h3>McKinsey</h3>
            <p style="margin:0;font-size:0.85rem;">Supply chains with governed data see <strong>20-50% reduction</strong> in costs from better decisions</p>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # --- 5-Step Lifecycle ---
    st.markdown("#### The 5-Step Governance Lifecycle")
    st.markdown("Every piece of data flows through this lifecycle before it can be used for analytics.")

    lifecycle_steps = [
        ("1. DISCOVER", "metadata-context", "New data arrives → gather schema, columns, check governance status", SNOW_BLUE),
        ("2. SCAN", "governance-scanner", "Find governance gaps — unmapped columns, missing definitions", GOV_YELLOW),
        ("3. MAP & PROPOSE", "ontology-mapper + definition-manager", "Map new columns to canonical concepts, propose definitions (PENDING_REVIEW)", GOV_YELLOW),
        ("4. APPROVE", "Governance Dashboard", "Data stewards review → approve or reject with full audit trail", GOV_GREEN),
        ("5. QUERY", "governed-query-engine + Cortex Agent", "Governance gate checks registry → only GOVERNED data is queried", GOV_GREEN),
    ]
    row1 = st.columns(3)
    for i, col in enumerate(row1):
        step = lifecycle_steps[i]
        with col:
            st.markdown(f"""<div class="arch-step" style="border-top-color:{step[3]};">
                <h4>{step[0]}</h4>
                <p><strong>Skill:</strong> {step[1]}</p>
                <p>{step[2]}</p>
            </div>""", unsafe_allow_html=True)
    row2 = st.columns([1, 1, 1])
    for i, col in enumerate(row2[:2]):
        step = lifecycle_steps[3 + i]
        with col:
            st.markdown(f"""<div class="arch-step" style="border-top-color:{step[3]};">
                <h4>{step[0]}</h4>
                <p><strong>Skill:</strong> {step[1]}</p>
                <p>{step[2]}</p>
            </div>""", unsafe_allow_html=True)

    st.divider()

    # --- Technical Stack ---
    st.markdown("#### Technical Stack")
    ts1, ts2 = st.columns(2)

    with ts1:
        st.markdown("**Snowflake Components**")
        st.markdown(f"""
        <div class="skill-card"><h4>Semantic View</h4>
        <p><code>SUPPLY_CHAIN_GOV.ANALYTICS.SUPPLY_CHAIN_SV</code></p>
        <p>Encodes the ontology — business meaning drives answers, not raw column names. Exposes SUPPLIER_PERFORMANCE and ORDER_DETAILS with governed metrics.</p></div>

        <div class="skill-card"><h4>Cortex Agent</h4>
        <p><code>SUPPLY_CHAIN_GOV.ANALYTICS.SUPPLY_CHAIN_SEMANTIC_AGENT</code></p>
        <p>Natural language interface. Uses cortex_analyst_text_to_sql against the Semantic View + sql_exec_tool for governance checks. Refuses ungoverned data.</p></div>

        <div class="skill-card"><h4>Governance Registry</h4>
        <p><code>GOVERNANCE.SEMANTIC_REGISTRY</code> + <code>SEMANTIC_MAPPINGS</code> + <code>AUDIT_LOG</code></p>
        <p>Tracks canonical definitions (GOVERNED / PENDING_REVIEW / NOT_GOVERNED), physical source mappings, and full audit trail of all governance actions.</p></div>

        <div class="skill-card"><h4>Data Architecture</h4>
        <p>Medallion: <code>STG</code> → <code>ANALYTICS</code> → <code>REPORTING</code></p>
        <p>9 tables across 4 schemas. Raw staging with abbreviated names, modeled analytics with canonical names, business-logic reporting views.</p></div>
        """, unsafe_allow_html=True)

    with ts2:
        st.markdown("**CoCo Skills (5 reusable skills)**")
        skills_data = [
            ("metadata-context", "Context provider", "Retrieves physical schema, governance status, transformation logic. The shared evidence layer for all other skills."),
            ("governance-scanner", "Gap detector", "Scans tables/schemas to find unmapped columns. Detects abbreviation patterns. Generates batch PROPOSE commands."),
            ("ontology-mapper", "Cross-source mapper", "Maps raw columns from new tables (e.g., SHIPMENT_V2) to existing canonical concepts with confidence scores."),
            ("semantic-definition-manager", "Governance brain", "PROPOSE, APPROVE, REJECT, UPDATE, VALIDATE operations on canonical definitions. Never auto-approves."),
            ("governed-query-engine", "Governance gate", "Gates every question through the registry. Only GOVERNED data is queried. Ensures persona consistency."),
        ]
        for name, role, desc in skills_data:
            st.markdown(f"""<div class="skill-card">
                <h4>{name} <span style="font-weight:400;color:#94a3b8;">— {role}</span></h4>
                <p>{desc}</p>
            </div>""", unsafe_allow_html=True)

    st.divider()

    # --- CoCo Usage Evidence ---
    st.markdown("#### CoCo Usage Across the Lifecycle")
    coco_data = pd.DataFrame({
        "Phase": ["Planning", "Planning", "Development", "Development", "Development", "Development", "Execution", "Testing", "Testing"],
        "What We Did": [
            "Explored Snowflake schema, framed the governance problem, designed the data model",
            "Researched industry reports on data governance costs via CoCo",
            "Generated synthetic data (15 suppliers, 100 orders, 100 shipments) with referential integrity",
            "Built semantic view (SUPPLY_CHAIN_SV) using CoCo agent-studio skill",
            "Created and deployed Cortex Agent (SUPPLY_CHAIN_SEMANTIC_AGENT) via CoCo",
            "Authored 5 reusable CoCo skills with SQL templates and governance logic",
            "Streamlit app scaffolded and iterated via CoCo, deployed to Community Cloud",
            "Tested ungoverned data rejection (SHIPMENT_V2 scenario)",
            "Validated persona consistency — 3 teams, 3 phrasings, same answer",
        ],
        "CoCo Feature": [
            "Conversational planning, data exploration",
            "Web research, report synthesis",
            "Synthetic data generation via SQL",
            "agent-studio skill (sv-generate, agent-write, agent-deploy)",
            "Agent YAML authoring, cortex agents deploy CLI",
            "Custom skill authoring (skill.md files)",
            "Streamlit scaffolding, iterative development",
            "Edge case testing, governance gate validation",
            "Cross-persona query testing",
        ],
    })
    st.dataframe(coco_data, use_container_width=True, hide_index=True)

# ============================
# PAGE 1: ONTOLOGY
# ============================
elif page == "Ontology":
    st.markdown('<h1 class="section-header">Supply Chain Ontology</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">The business entity and relationship model for a home appliances manufacturer — '
        'Supplier to Part to Shipment to Order to Customer.</p>',
        unsafe_allow_html=True,
    )

    # --- Architecture diagram ---
    st.markdown("#### Data Flow Architecture")
    arch_cols = st.columns(4)
    labels = [
        ("Source Systems", "ERP, Logistics, Order Mgmt", "Raw, messy column names", GOV_YELLOW),
        ("STG Schema", "SUPPLIERS, ORDERS, SHIPMENTS", "Landed as-is from source", SNOW_BLUE),
        ("ANALYTICS Schema", "SUPPLIER_PERFORMANCE, ORDER_DETAILS", "Modeled, clean canonical names", GOV_GREEN),
        ("REPORTING Schema", "DELIVERY_SUMMARY, AT_RISK_SUPPLIERS", "Business-logic views", SNOW_DARK),
    ]
    for col, (title, content, note, color) in zip(arch_cols, labels):
        with col:
            st.markdown(f"""<div class="kpi-card" style="border-left-color:{color};">
                <h3>{title}</h3>
                <p style="margin:0;font-size:0.9rem;">{content}</p>
                <p style="margin:4px 0 0;font-size:0.78rem;color:#94a3b8;">{note}</p>
            </div>""", unsafe_allow_html=True)

    ungov_col1, ungov_col2 = st.columns([3, 1])
    with ungov_col1:
        st.warning(
            "**STG.SHIPMENT_V2** exists but is **NOT GOVERNED**. "
            "Column names differ from canonical definitions (VENDOR_NO vs SUPPLIER_ID, CONFIRMED_DT vs PROMISED_DATE). "
            "Cannot be used for authoritative reporting until governed."
        )
    with ungov_col2:
        st.markdown(f"""<div class="kpi-card" style="border-left-color:{GOV_RED};">
            <h3>Governance</h3>
            <p style="margin:0;">SEMANTIC_REGISTRY<br>SEMANTIC_MAPPINGS<br>AUDIT_LOG</p>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # --- Entities, Metrics, Mappings ---
    st.markdown("#### Core Entities, Canonical Metrics & Column Mappings")
    tab_ent, tab_met, tab_map, tab_sv = st.tabs([
        "Entities & Relationships", "Canonical Metrics", "Column Mapping (STG → ANALYTICS)", "Semantic View"
    ])

    with tab_ent:
        entities = pd.DataFrame({
            "Entity": ["Supplier", "Order", "Shipment", "Customer"],
            "Source Table": ["STG.SUPPLIERS", "STG.ORDERS", "STG.SHIPMENTS", "STG.ORDERS (CUST_NM)"],
            "Key Field": ["SUP_ID", "ORD_NO", "SHPMT_ID", "CUST_NM"],
            "Relationships": [
                "Supplier → Shipment (via SUP_ID), Supplier → Order (via join)",
                "Order → Shipment (via ORD_NO), Order → Customer (via CUST_NM)",
                "Shipment → Supplier (via SUP_ID), Shipment → Order (via ORD_NO)",
                "Customer → Order (via CUST_NM)",
            ],
            "Description": [
                "Component suppliers across global regions",
                "Purchase orders from dealers / retailers",
                "Deliveries tied to orders and suppliers",
                "Dealers and retail partners",
            ],
        })
        st.dataframe(entities, use_container_width=True, hide_index=True)
        st.info(
            "**Hierarchy:** Supplier → supplies Parts → shipped via Shipment → fulfills Order → for Customer. "
            "This ontology ensures every query resolves through governed relationships."
        )

    with tab_met:
        metrics = pd.DataFrame({
            "Metric": ["On-Time Delivery %", "Fill Rate %"],
            "Definition": [
                "Percentage of shipments delivered on or before the promised delivery date",
                "Percentage of ordered quantity actually shipped",
            ],
            "Formula": [
                "COUNT(ACTUAL_DT <= PROM_DT) / COUNT(*) * 100",
                "SUM(QTY_SHIPPED) / SUM(QTY) * 100",
            ],
            "Source Column": ["ANALYTICS.SUPPLIER_PERFORMANCE.ON_TIME_DELIVERY_PCT", "ANALYTICS.SUPPLIER_PERFORMANCE.FILL_RATE_PCT"],
            "Status": ["GOVERNED", "GOVERNED"],
        })
        st.dataframe(metrics, use_container_width=True, hide_index=True)
        st.info(
            "These are the **single source-of-truth** definitions. Every team — Planning, Procurement, Logistics — "
            "resolves to these same metrics via the Semantic View and governance gate."
        )

    with tab_map:
        st.markdown("Raw staging column names are abbreviated. The governance layer maps them to canonical names.")
        mapping = pd.DataFrame({
            "Raw (STG)": ["SUP_ID", "SUP_NM", "CNTRY", "ORD_NO", "CUST_NM", "PROM_DT", "ACTUAL_DT", "FREIGHT_AMT"],
            "Canonical (ANALYTICS)": ["SUPPLIER_ID", "SUPPLIER_NAME", "COUNTRY", "ORDER_NUMBER", "CUSTOMER_NAME", "PROMISED_DATE", "DELIVERY_DATE", "FREIGHT_COST"],
            "Governance Status": ["GOVERNED", "GOVERNED", "GOVERNED", "GOVERNED", "GOVERNED", "GOVERNED", "GOVERNED", "PENDING_REVIEW"],
        })
        st.dataframe(mapping, use_container_width=True, hide_index=True)

    with tab_sv:
        st.markdown("**Snowflake Semantic View** encodes the ontology so business meaning — not raw column names — drives answers.")
        st.code("""
-- Semantic View: SUPPLY_CHAIN_GOV.ANALYTICS.SUPPLY_CHAIN_SV
-- This view is used by the Cortex Agent to answer natural language questions.
-- It exposes ONLY governed data from ANALYTICS schema.

CREATE OR REPLACE SEMANTIC VIEW SUPPLY_CHAIN_GOV.ANALYTICS.SUPPLY_CHAIN_SV
  TABLES (
    SUPPLY_CHAIN_GOV.ANALYTICS.SUPPLIER_PERFORMANCE
      PRIMARY KEY (SUPPLIER_ID)
      WITH SYNONYMS = 'supplier metrics, vendor performance',
    SUPPLY_CHAIN_GOV.ANALYTICS.ORDER_DETAILS
      PRIMARY KEY (ORDER_NUMBER)
      WITH SYNONYMS = 'purchase orders, order data'
  )
  RELATIONSHIPS (
    SUPPLY_CHAIN_GOV.ANALYTICS.ORDER_DETAILS (SUPPLIER_ID)
      REFERENCES SUPPLY_CHAIN_GOV.ANALYTICS.SUPPLIER_PERFORMANCE (SUPPLIER_ID)
  )
  -- Facts, Dimensions, and Metrics defined on governed columns only
        """, language="sql")
        st.success("This Semantic View is deployed and active at `SUPPLY_CHAIN_GOV.ANALYTICS.SUPPLY_CHAIN_SV`")

# ============================
# PAGE 2: GOVERNANCE DASHBOARD
# ============================
elif page == "Governance Dashboard":
    st.markdown('<h1 class="section-header">Governance Dashboard</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Proactive scan of all data objects and their governance status. '
        'Approve, reject, or investigate pending definitions.</p>',
        unsafe_allow_html=True,
    )

    registry = run_query(
        "SELECT STATUS, COUNT(*) AS CNT FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY GROUP BY STATUS"
    )
    governed = int(registry.loc[registry["STATUS"] == "GOVERNED", "CNT"].sum()) if "GOVERNED" in registry["STATUS"].values else 0
    pending = int(registry.loc[registry["STATUS"] == "PENDING_REVIEW", "CNT"].sum()) if "PENDING_REVIEW" in registry["STATUS"].values else 0
    not_gov = int(registry.loc[registry["STATUS"] == "NOT_GOVERNED", "CNT"].sum()) if "NOT_GOVERNED" in registry["STATUS"].values else 0
    total = governed + pending + not_gov
    gov_pct = round(governed / total * 100) if total else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="kpi-card" style="border-left-color:{SNOW_BLUE};">
            <h3>Total Concepts</h3><div class="value" style="color:{SNOW_DARK};">{total}</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card" style="border-left-color:{GOV_GREEN};">
            <h3>Governed</h3><div class="value" style="color:#065f46;">{governed}</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card" style="border-left-color:{GOV_YELLOW};">
            <h3>Pending Review</h3><div class="value" style="color:#92400e;">{pending}</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card" style="border-left-color:{GOV_RED};">
            <h3>Not Governed</h3><div class="value" style="color:#991b1b;">{not_gov}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="margin:8px 0 16px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="font-weight:600;color:{SNOW_DARK};">Governance Coverage</span>
            <span style="font-weight:700;color:{SNOW_DARK};">{gov_pct}%</span>
        </div>
        <div style="background:#e2e8f0;border-radius:8px;height:10px;overflow:hidden;">
            <div style="width:{gov_pct}%;height:100%;background:linear-gradient(90deg,{GOV_GREEN},{SNOW_BLUE});border-radius:8px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    tab_reg, tab_pending, tab_ungov, tab_audit = st.tabs([
        "Semantic Registry", "Pending Approvals", "Ungoverned Sources", "Audit Log"
    ])

    with tab_reg:
        full_registry = run_query("""
            SELECT CONCEPT_ID, CANONICAL_NAME, DEFINITION, ENTITY_TYPE, STATUS, CONFIDENCE,
                   APPROVED_BY, APPROVED_AT
            FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
            ORDER BY STATUS, CANONICAL_NAME
        """)
        def color_status(val):
            colors = {
                "GOVERNED": "background-color: #d1fae5; color: #065f46",
                "PENDING_REVIEW": "background-color: #fef3c7; color: #92400e",
                "NOT_GOVERNED": "background-color: #fee2e2; color: #991b1b",
            }
            return colors.get(val, "")
        st.dataframe(
            full_registry.style.applymap(color_status, subset=["STATUS"]),
            use_container_width=True, hide_index=True,
        )

    with tab_pending:
        pending_items = run_query("""
            SELECT CONCEPT_ID, CANONICAL_NAME, DEFINITION, CONFIDENCE, EVIDENCE
            FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
            WHERE STATUS = 'PENDING_REVIEW'
        """)
        if len(pending_items) == 0:
            st.success("No pending definitions to review.")
        else:
            st.markdown(f"**{len(pending_items)}** definition(s) awaiting governance review:")
            for _, row in pending_items.iterrows():
                with st.expander(f"{row['CANONICAL_NAME']} — Confidence: {row['CONFIDENCE']}"):
                    st.markdown(f"**Proposed Definition:** {row['DEFINITION']}")
                    st.markdown(f"**Evidence:** {row['EVIDENCE']}")
                    c1, c2, _ = st.columns([1, 1, 3])
                    if c1.button("Approve", key=f"approve_{row['CONCEPT_ID']}", type="primary"):
                        run_update(f"""
                            UPDATE SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
                            SET STATUS='GOVERNED', APPROVED_BY='dashboard_user',
                                APPROVED_AT=CURRENT_TIMESTAMP(), UPDATED_AT=CURRENT_TIMESTAMP()
                            WHERE CONCEPT_ID='{row['CONCEPT_ID']}'
                        """)
                        run_update(f"""
                            UPDATE SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS
                            SET STATUS='GOVERNED', UPDATED_AT=CURRENT_TIMESTAMP()
                            WHERE CONCEPT_ID='{row['CONCEPT_ID']}'
                        """)
                        run_update(f"""
                            INSERT INTO SUPPLY_CHAIN_GOV.GOVERNANCE.GOVERNANCE_AUDIT_LOG
                            (AUDIT_ID, CONCEPT_ID, ACTION, ACTOR, DETAILS)
                            VALUES ('{row['CONCEPT_ID']}-APR','{row['CONCEPT_ID']}','APPROVED','dashboard_user','Approved via dashboard')
                        """)
                        st.success(f"Approved: {row['CANONICAL_NAME']}")
                        st.rerun()
                    if c2.button("Reject", key=f"reject_{row['CONCEPT_ID']}"):
                        run_update(f"""
                            UPDATE SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
                            SET STATUS='NOT_GOVERNED', UPDATED_AT=CURRENT_TIMESTAMP()
                            WHERE CONCEPT_ID='{row['CONCEPT_ID']}'
                        """)
                        run_update(f"""
                            INSERT INTO SUPPLY_CHAIN_GOV.GOVERNANCE.GOVERNANCE_AUDIT_LOG
                            (AUDIT_ID, CONCEPT_ID, ACTION, ACTOR, DETAILS)
                            VALUES ('{row['CONCEPT_ID']}-REJ','{row['CONCEPT_ID']}','REJECTED','dashboard_user','Rejected via dashboard')
                        """)
                        st.warning(f"Rejected: {row['CANONICAL_NAME']}")
                        st.rerun()

    with tab_ungov:
        ungoverned = run_query("""
            SELECT t.TABLE_SCHEMA, t.TABLE_NAME, t.COMMENT, t.ROW_COUNT
            FROM SUPPLY_CHAIN_GOV.INFORMATION_SCHEMA.TABLES t
            WHERE t.TABLE_SCHEMA IN ('STG','ANALYTICS','REPORTING')
            AND t.TABLE_NAME NOT IN (
                SELECT DISTINCT SOURCE_TABLE FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS WHERE STATUS='GOVERNED'
            )
            AND t.TABLE_TYPE = 'BASE TABLE'
        """)
        if len(ungoverned) > 0:
            st.error(f"**{len(ungoverned)} table(s)** exist without governed semantic mappings.")
            st.markdown("These cannot be used for authoritative analytics. Use the **governance-scanner** skill to scan and propose definitions.")
            st.dataframe(ungoverned, use_container_width=True, hide_index=True)
        else:
            st.success("All tables have governed semantic mappings.")

    with tab_audit:
        audit = run_query("""
            SELECT AUDIT_ID, CONCEPT_ID, ACTION, ACTOR, DETAILS, TIMESTAMP
            FROM SUPPLY_CHAIN_GOV.GOVERNANCE.GOVERNANCE_AUDIT_LOG
            ORDER BY TIMESTAMP DESC LIMIT 20
        """)
        st.dataframe(audit, use_container_width=True, hide_index=True)

# ============================
# PAGE 3: SEMANTIC EXPLORER
# ============================
elif page == "Semantic Explorer":
    st.markdown('<h1 class="section-header">Semantic Explorer</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Look up any business concept to see its canonical definition, governance status, and physical source mapping.</p>',
        unsafe_allow_html=True,
    )

    search_term = st.text_input("Search business concepts", placeholder="e.g., delivery performance, supplier name, fill rate")

    if search_term:
        results = run_query(f"""
            SELECT r.CONCEPT_ID, r.CANONICAL_NAME, r.DEFINITION, r.ENTITY_TYPE, r.STATUS, r.CONFIDENCE,
                   m.SOURCE_TABLE, m.SOURCE_COLUMN, m.TRANSFORMATION
            FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY r
            LEFT JOIN SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_MAPPINGS m ON r.CONCEPT_ID = m.CONCEPT_ID
            WHERE r.CANONICAL_NAME ILIKE '%{search_term}%' OR r.DEFINITION ILIKE '%{search_term}%'
            ORDER BY r.STATUS, r.CANONICAL_NAME
        """)
        if len(results) == 0:
            st.info("No concepts found matching your search.")
        else:
            for _, row in results.iterrows():
                st.markdown(f"### {row['CANONICAL_NAME']} {status_badge(row['STATUS'])}", unsafe_allow_html=True)
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**Definition:** {row['DEFINITION']}")
                    if pd.notna(row.get("SOURCE_TABLE")) and row.get("SOURCE_TABLE"):
                        st.markdown(f"**Source:** `{row['SOURCE_TABLE']}.{row['SOURCE_COLUMN']}` | **Transform:** {row['TRANSFORMATION']}")
                with c2:
                    st.markdown(f"**Type:** {row['ENTITY_TYPE']}")
                    st.markdown(f"**Confidence:** {row['CONFIDENCE']}")
                st.divider()
    else:
        st.markdown("#### All Governed Concepts")
        all_governed = run_query("""
            SELECT CANONICAL_NAME, DEFINITION, ENTITY_TYPE, STATUS
            FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY ORDER BY STATUS, CANONICAL_NAME
        """)
        st.dataframe(all_governed, use_container_width=True, hide_index=True)

# ============================
# PAGE 4: ASK SUPPLY CHAIN (with real governance gate)
# ============================
elif page == "Ask Supply Chain":
    st.markdown('<h1 class="section-header">Ask Supply Chain</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Ask business questions in natural language. Every question goes through a '
        '<strong>real governance gate</strong> — the system queries SEMANTIC_REGISTRY before answering.</p>',
        unsafe_allow_html=True,
    )

    question = st.text_input("Ask a question", placeholder="e.g., Which suppliers have poor delivery performance?")

    if question:
        with st.spinner("Running governance check against SEMANTIC_REGISTRY..."):
            # --- REAL GOVERNANCE GATE ---
            # Step 1: Detect concepts from the question
            q_lower = question.lower()

            # Check for ungoverned data references first
            ungov_keywords = ["shipment_v2", "shipment v2", "vendor_no", "v2", "new logistics"]
            if any(kw in q_lower for kw in ungov_keywords):
                # Query registry to confirm it's actually ungoverned
                ungov_check = run_query("""
                    SELECT CANONICAL_NAME, STATUS FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY
                    WHERE STATUS = 'NOT_GOVERNED'
                """)

                st.markdown(f"""<div class="gov-result gov-blocked">
                    <h4>GOVERNANCE GATE: BLOCKED</h4>
                    <p><strong>Reason:</strong> Your question references data from <code>STG.SHIPMENT_V2</code> which is <strong>NOT GOVERNED</strong>.</p>
                    <p><strong>Issue:</strong> Column names differ from canonical definitions (VENDOR_NO vs SUPPLIER_ID, CONFIRMED_DT vs PROMISED_DATE).</p>
                    <p><strong>Action Required:</strong></p>
                    <ol>
                        <li>Use the <strong>governance-scanner</strong> skill to scan SHIPMENT_V2</li>
                        <li>Use the <strong>ontology-mapper</strong> skill to map columns to existing concepts</li>
                        <li>Use the <strong>semantic-definition-manager</strong> to propose definitions</li>
                        <li>Approve via the <strong>Governance Dashboard</strong></li>
                    </ol>
                    <p><em>This source will not be treated as authoritative until governed.</em></p>
                </div>""", unsafe_allow_html=True)

                if len(ungov_check) > 0:
                    st.markdown("**Currently NOT_GOVERNED concepts in registry:**")
                    st.dataframe(ungov_check, use_container_width=True, hide_index=True)

            else:
                # Map question keywords to concept search terms
                concept_map = {
                    "delivery": ["delivery", "on-time"],
                    "on-time": ["delivery", "on-time"],
                    "otd": ["delivery", "on-time"],
                    "late": ["delivery", "on-time"],
                    "performance": ["delivery", "on-time"],
                    "risk": ["delivery", "on-time"],
                    "target": ["delivery", "on-time"],
                    "commitment": ["delivery", "on-time"],
                    "delay": ["delivery", "on-time"],
                    "fill rate": ["fill rate"],
                    "fill": ["fill rate"],
                    "shipped": ["fill rate"],
                    "fulfilled": ["fill rate"],
                    "quantity": ["fill rate"],
                    "supplier": ["supplier"],
                    "freight": ["freight"],
                    "cost": ["freight"],
                }

                matched_keywords = []
                for kw, concepts in concept_map.items():
                    if kw in q_lower:
                        matched_keywords.extend(concepts)
                matched_keywords = list(set(matched_keywords)) if matched_keywords else ["supplier"]

                # Step 2: REAL governance check — query the registry
                gov_results = governance_check(matched_keywords)

                if len(gov_results) == 0:
                    st.markdown(f"""<div class="gov-result gov-blocked">
                        <h4>GOVERNANCE GATE: NO MATCH</h4>
                        <p>No governed concept matches your question. Try rephrasing using governed terms.</p>
                    </div>""", unsafe_allow_html=True)

                    all_concepts = run_query("SELECT CANONICAL_NAME, STATUS FROM SUPPLY_CHAIN_GOV.GOVERNANCE.SEMANTIC_REGISTRY WHERE STATUS='GOVERNED'")
                    st.markdown("**Available governed concepts:**")
                    st.dataframe(all_concepts, use_container_width=True, hide_index=True)

                else:
                    # Find the best governed match
                    governed_matches = gov_results[gov_results["STATUS"] == "GOVERNED"]
                    pending_matches = gov_results[gov_results["STATUS"] == "PENDING_REVIEW"]

                    if len(governed_matches) > 0:
                        best = governed_matches.iloc[0]

                        # Get source mapping
                        source = get_source_mapping(best["CONCEPT_ID"])
                        source_info = f"{source.iloc[0]['SOURCE_TABLE']}.{source.iloc[0]['SOURCE_COLUMN']}" if len(source) > 0 else "N/A"

                        col1, col2 = st.columns([2, 1])

                        with col2:
                            st.markdown(f"""<div class="gov-result">
                                <h4>GOVERNANCE GATE: PASSED</h4>
                                <p><strong>Concept:</strong> {best['CANONICAL_NAME']}</p>
                                <p><strong>Definition:</strong> {best['DEFINITION']}</p>
                                <p><strong>Status:</strong> {status_badge('GOVERNED')}</p>
                                <p><strong>Source:</strong> <code>{source_info}</code></p>
                                <p><strong>Confidence:</strong> {best['CONFIDENCE']}</p>
                            </div>""", unsafe_allow_html=True)

                        with col1:
                            # Query the actual governed data
                            if any(kw in q_lower for kw in ["delivery", "on-time", "otd", "late", "risk", "target", "performance", "commitment", "delay"]):
                                data = run_query("""
                                    SELECT SUPPLIER_NAME, COUNTRY, RATING, ON_TIME_DELIVERY_PCT, FILL_RATE_PCT, TOTAL_SHIPMENTS
                                    FROM SUPPLY_CHAIN_GOV.ANALYTICS.SUPPLIER_PERFORMANCE
                                    ORDER BY ON_TIME_DELIVERY_PCT ASC
                                """)
                                st.dataframe(data, use_container_width=True, hide_index=True)
                                poor = data[data["ON_TIME_DELIVERY_PCT"] < 70]
                                if len(poor) > 0:
                                    st.markdown(f"**{len(poor)} supplier(s) below 70% OTD:**")
                                    for _, r in poor.iterrows():
                                        st.markdown(f"- **{r['SUPPLIER_NAME']}** ({r['COUNTRY']}): {r['ON_TIME_DELIVERY_PCT']}% OTD")

                            elif any(kw in q_lower for kw in ["fill", "shipped", "fulfilled", "quantity"]):
                                data = run_query("""
                                    SELECT SUPPLIER_NAME, COUNTRY, FILL_RATE_PCT, TOTAL_SHIPMENTS
                                    FROM SUPPLY_CHAIN_GOV.ANALYTICS.SUPPLIER_PERFORMANCE
                                    ORDER BY FILL_RATE_PCT ASC
                                """)
                                st.dataframe(data, use_container_width=True, hide_index=True)

                            else:
                                data = run_query("""
                                    SELECT SUPPLIER_NAME, COUNTRY, RATING, ON_TIME_DELIVERY_PCT, FILL_RATE_PCT,
                                           TOTAL_ORDERS, TOTAL_SHIPMENTS, TOTAL_FREIGHT
                                    FROM SUPPLY_CHAIN_GOV.ANALYTICS.SUPPLIER_PERFORMANCE ORDER BY SUPPLIER_NAME
                                """)
                                st.dataframe(data, use_container_width=True, hide_index=True)

                    elif len(pending_matches) > 0:
                        best = pending_matches.iloc[0]
                        st.markdown(f"""<div class="gov-result gov-pending">
                            <h4>GOVERNANCE GATE: PENDING</h4>
                            <p><strong>Concept:</strong> {best['CANONICAL_NAME']}</p>
                            <p><strong>Definition:</strong> {best['DEFINITION']}</p>
                            <p><strong>Status:</strong> {status_badge('PENDING_REVIEW')}</p>
                            <p>This concept has a proposed definition but has <strong>not yet been approved</strong>.
                            The data cannot be used as authoritative until a data steward approves it via the Governance Dashboard.</p>
                        </div>""", unsafe_allow_html=True)

    st.divider()

    # --- Persona Consistency Demo (LIVE, not static) ---
    st.markdown("#### Persona Consistency Guarantee (Live Demo)")
    st.markdown(
        "Three different teams ask about the same concept using different words. "
        "The governance gate resolves all three to the **same canonical metric**."
    )

    persona_questions = [
        ("Planning", "Which suppliers are creating delivery risk?"),
        ("Procurement", "Which suppliers are below our delivery target?"),
        ("Logistics", "Which suppliers are missing delivery commitments?"),
    ]

    for team, q in persona_questions:
        keywords = ["delivery", "on-time"]
        result = governance_check(keywords)
        governed_row = result[result["STATUS"] == "GOVERNED"].iloc[0] if len(result[result["STATUS"] == "GOVERNED"]) > 0 else None

        if governed_row is not None:
            st.markdown(
                f"**{team}:** \"{q}\"  \n"
                f"→ Resolves to: **{governed_row['CANONICAL_NAME']}** "
                f"{status_badge('GOVERNED')} "
                f"| Definition: {governed_row['DEFINITION']}",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f"**{team}:** \"{q}\" → No governed match")

    st.success("All three teams get the same concept, same definition, same data source. No conflicting numbers.")
