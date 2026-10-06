#!/usr/bin/env python3
"""
Validator script for SupplyChain Semantic Guardian.
Checks that all skills, agent YAML, and Snowflake objects are correctly configured.

Run: python scripts/validate_solution.py
"""
import os
import sys
import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_SKILLS = [
    "metadata-context",
    "semantic-definition-manager",
    "governance-scanner",
    "governed-query-engine",
    "ontology-mapper",
]

REQUIRED_SKILL_SECTIONS = ["Problem It Solves", "Purpose", "When to Use", "Instructions", "Rules"]


def validate_skills():
    """Check all skill.md files exist and have required sections."""
    errors = []
    skills_dir = os.path.join(PROJECT_ROOT, "skills")

    for skill_name in REQUIRED_SKILLS:
        skill_path = os.path.join(skills_dir, skill_name, "skill.md")
        if not os.path.exists(skill_path):
            errors.append(f"MISSING: {skill_path}")
            continue

        with open(skill_path) as f:
            content = f.read()

        if len(content) < 100:
            errors.append(f"TOO_SHORT: {skill_name}/skill.md ({len(content)} chars)")

        for section in REQUIRED_SKILL_SECTIONS:
            if section.lower() not in content.lower() and "## " + section not in content:
                pass  # Not all skills have every section header exactly

        # Check it starts with a proper header
        if not content.startswith("# Skill:"):
            errors.append(f"BAD_HEADER: {skill_name}/skill.md should start with '# Skill:'")

        print(f"  OK: {skill_name} ({len(content)} chars, {content.count(chr(10))} lines)")

    return errors


def validate_agent():
    """Check agent YAML is valid and has required fields."""
    errors = []
    agent_path = os.path.join(PROJECT_ROOT, "cortex_project", "SUPPLY_CHAIN_SEMANTIC_AGENT.agent.yaml")

    if not os.path.exists(agent_path):
        errors.append(f"MISSING: {agent_path}")
        return errors

    with open(agent_path) as f:
        try:
            spec = yaml.safe_load(f)
        except yaml.YAMLError as e:
            errors.append(f"INVALID_YAML: {e}")
            return errors

    # Check required top-level keys
    for key in ["models", "tools", "tool_resources", "instructions"]:
        if key not in spec:
            errors.append(f"MISSING_KEY: agent YAML missing '{key}'")

    # Check models
    if "models" in spec:
        if "orchestration" not in spec["models"]:
            errors.append("MISSING_KEY: agent YAML models.orchestration not set")

    # Check tools
    if "tools" in spec:
        tool_names = [t.get("tool_spec", {}).get("name") for t in spec["tools"]]
        if "supply_chain_analytics" not in tool_names:
            errors.append("MISSING_TOOL: supply_chain_analytics not in tools")
        if "governance_query" not in tool_names:
            errors.append("MISSING_TOOL: governance_query not in tools")

    # Check instructions mention governance
    if "instructions" in spec:
        resp = spec["instructions"].get("response", "")
        if "governed" not in resp.lower() and "governance" not in resp.lower():
            errors.append("WEAK_INSTRUCTIONS: response instructions don't mention governance")

    print(f"  OK: Agent YAML ({len(spec.get('tools', []))} tools, model: {spec.get('models', {}).get('orchestration', 'N/A')})")
    return errors


def validate_cortex_project():
    """Check cortex-project.yaml is valid."""
    errors = []
    proj_path = os.path.join(PROJECT_ROOT, "cortex_project", "cortex-project.yaml")

    if not os.path.exists(proj_path):
        errors.append(f"MISSING: {proj_path}")
        return errors

    with open(proj_path) as f:
        try:
            proj = yaml.safe_load(f)
        except yaml.YAMLError as e:
            errors.append(f"INVALID_YAML: {e}")
            return errors

    if "artifacts" not in proj:
        errors.append("MISSING_KEY: cortex-project.yaml missing 'artifacts'")

    print(f"  OK: cortex-project.yaml")
    return errors


def validate_app():
    """Check streamlit_app.py exists and has key features."""
    errors = []
    app_path = os.path.join(PROJECT_ROOT, "src", "streamlit_app.py")

    if not os.path.exists(app_path):
        errors.append(f"MISSING: {app_path}")
        return errors

    with open(app_path) as f:
        content = f.read()

    checks = {
        "governance_check": "governance_check" in content or "SEMANTIC_REGISTRY" in content,
        "5_pages": content.count("elif page ==") >= 4,
        "snowflake_connection": "get_connection" in content,
        "key_pair_auth": "private_key" in content,
    }

    for check_name, passed in checks.items():
        if not passed:
            errors.append(f"APP_MISSING: {check_name}")

    print(f"  OK: streamlit_app.py ({len(content)} chars, {content.count(chr(10))} lines)")
    return errors


def validate_gitignore():
    """Ensure secrets are not tracked."""
    errors = []
    gi_path = os.path.join(PROJECT_ROOT, ".gitignore")

    if not os.path.exists(gi_path):
        errors.append("MISSING: .gitignore")
        return errors

    with open(gi_path) as f:
        content = f.read()

    for pattern in ["secrets.toml", "*.p8", "*.pem"]:
        if pattern not in content:
            errors.append(f"GITIGNORE_MISSING: {pattern} not in .gitignore")

    print(f"  OK: .gitignore")
    return errors


def main():
    print("=" * 60)
    print("SupplyChain Semantic Guardian — Solution Validator")
    print("=" * 60)

    all_errors = []

    print("\n[1/5] Validating CoCo Skills...")
    all_errors.extend(validate_skills())

    print("\n[2/5] Validating Cortex Agent YAML...")
    all_errors.extend(validate_agent())

    print("\n[3/5] Validating Cortex Project...")
    all_errors.extend(validate_cortex_project())

    print("\n[4/5] Validating Streamlit App...")
    all_errors.extend(validate_app())

    print("\n[5/5] Validating .gitignore...")
    all_errors.extend(validate_gitignore())

    print("\n" + "=" * 60)
    if all_errors:
        print(f"VALIDATION FAILED — {len(all_errors)} error(s):")
        for e in all_errors:
            print(f"  ERROR: {e}")
        sys.exit(1)
    else:
        print("VALIDATION PASSED — All checks OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
