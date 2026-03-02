#!/usr/bin/env python3
# TelsonBase/scripts/seed_demo_data.py
# REM: =======================================================================================
# REM: SEED DEMO DATA - POPULATE DASHBOARD WITH REALISTIC TEST DATA
# REM: =======================================================================================
# REM: Run this to populate the dashboard with sample agents, approvals, and anomalies
# REM: so you can see what it looks like in action.
# REM:
# REM: Usage:
# REM:   python scripts/seed_demo_data.py
# REM:
# REM: Or with Docker:
# REM:   docker-compose exec mcp_server python scripts/seed_demo_data.py
# REM: =======================================================================================

import os
import sys
import json
from datetime import datetime, timezone, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("=" * 60)
    print("SEEDING DEMO DATA FOR TELSONBASE DASHBOARD")
    print("=" * 60)
    
    try:
        from core.persistence import (
            signing_store, capability_store, anomaly_store, 
            approval_store, federation_store
        )
    except ImportError as e:
        print(f"Error importing modules: {e}")
        print("Make sure you're running this from the project root or inside the container.")
        return 1
    
    # Check Redis connection
    if not signing_store.ping():
        print("ERROR: Cannot connect to Redis. Is it running?")
        return 1
    
    print("\n[1/5] Creating demo agents...")
    
    agents = [
        {
            "id": "backup_agent",
            "capabilities": [
                "filesystem.read:/data/*",
                "filesystem.write:/app/backups/*",
                "external.none",
            ]
        },
        {
            "id": "research_agent",
            "capabilities": [
                "external.read:api.perplexity.ai",
                "external.write:api.perplexity.ai",
                "filesystem.write:/app/research/*",
                "!filesystem.read:/data/secrets/*",
            ]
        },
        {
            "id": "document_agent",
            "capabilities": [
                "filesystem.read:/app/documents/*",
                "filesystem.write:/app/documents/*",
                "ollama.execute:*",
            ]
        },
        {
            "id": "demo_agent",
            "capabilities": [
                "filesystem.read:/app/demo/input/*",
                "filesystem.write:/app/demo/output/*",
                "external.none",
            ]
        },
        # REM: Third Floor — Real Estate Agents
        {
            "id": "transaction_agent",
            "capabilities": [
                "filesystem.read:/data/transactions/*",
                "filesystem.write:/data/transactions/*",
                "filesystem.read:/data/documents/*",
                "external.none",
            ]
        },
        {
            "id": "compliance_check_agent",
            "capabilities": [
                "filesystem.read:/data/compliance/*",
                "filesystem.write:/data/compliance/*",
                "filesystem.read:/data/transactions/*",
                "external.none",
            ]
        },
        {
            "id": "doc_prep_agent",
            "capabilities": [
                "filesystem.read:/data/documents/*",
                "filesystem.write:/data/documents/generated/*",
                "filesystem.read:/data/transactions/*",
                "filesystem.read:/data/templates/*",
                "external.none",
            ]
        },
    ]
    
    import secrets
    for agent in agents:
        key = secrets.token_bytes(32)
        signing_store.store_key(agent["id"], key)
        capability_store.store_capabilities(agent["id"], agent["capabilities"])
        print(f"  ✓ Registered: {agent['id']}")
    
    print("\n[2/5] Creating sample approval requests...")
    
    approvals = [
        {
            "request_id": "APPR-A1B2C3D4",
            "agent_id": "backup_agent",
            "action": "delete_old_backups",
            "description": "Request to delete backup files older than 30 days",
            "payload": {"retention_days": 30, "estimated_files": 47},
            "priority": "normal",
            "status": "pending",
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        },
        {
            "request_id": "APPR-E5F6G7H8",
            "agent_id": "research_agent",
            "action": "access_new_domain",
            "description": "First-time access to api.openai.com",
            "payload": {"domain": "api.openai.com", "method": "POST"},
            "priority": "high",
            "status": "pending",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
        },
        {
            "request_id": "APPR-I9J0K1L2",
            "agent_id": "document_agent",
            "action": "bulk_process",
            "description": "Process 156 documents in /app/documents/inbox/",
            "payload": {"directory": "/app/documents/inbox/", "file_count": 156},
            "priority": "normal",
            "status": "pending",
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        },
        # REM: Real estate agent approvals
        {
            "request_id": "APPR-TX-CLOSE01",
            "agent_id": "transaction_agent",
            "action": "close_transaction",
            "description": "Close transaction TXN-2026-001 — 742 Evergreen Terrace, Springfield, OH. 2 required documents pending.",
            "payload": {"transaction_id": "TXN-2026-001", "property": "742 Evergreen Terrace"},
            "priority": "high",
            "status": "pending",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat(),
        },
        {
            "request_id": "APPR-DP-FINAL01",
            "agent_id": "doc_prep_agent",
            "action": "finalize_document",
            "description": "Finalize Seller Disclosure for 742 Evergreen Terrace (GEN-SD-001). SHA-256 hash will be locked.",
            "payload": {"document_id": "GEN-SD-001", "template": "seller_disclosure"},
            "priority": "normal",
            "status": "pending",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat(),
        },
        {
            "request_id": "APPR-CC-WAIVE01",
            "agent_id": "compliance_check_agent",
            "action": "waive_disclosure",
            "description": "Waive radon disclosure for 1200 Oak Street #4B lease — property built 2015, no radon history.",
            "payload": {"disclosure_type": "radon", "transaction_id": "TXN-2026-002"},
            "priority": "normal",
            "status": "pending",
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        },
    ]
    
    for approval in approvals:
        approval_store.store_request(approval)
        print(f"  ✓ Created: {approval['request_id']} ({approval['action']})")
    
    print("\n[3/5] Creating sample anomalies...")
    
    anomalies = [
        {
            "anomaly_id": "ANOM-001ABC",
            "agent_id": "research_agent",
            "anomaly_type": "rate_spike",
            "severity": "medium",
            "description": "Activity rate 12.3/min is 3.2 std devs above baseline of 2.1/min",
            "detected_at": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
            "evidence": {
                "current_rate": 12.3,
                "baseline_avg": 2.1,
                "baseline_std": 3.2,
                "z_score": 3.2
            },
            "requires_human_review": False,
            "resolved": False,
        },
        {
            "anomaly_id": "ANOM-002DEF",
            "agent_id": "backup_agent",
            "anomaly_type": "new_resource",
            "severity": "low",
            "description": "First access to resource: /data/archive/2024/",
            "detected_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "evidence": {
                "resource": "/data/archive/2024/",
                "action": "read",
                "baseline_resources": 23
            },
            "requires_human_review": False,
            "resolved": False,
        },
        {
            "anomaly_id": "ANOM-003GHI",
            "agent_id": "demo_agent",
            "anomaly_type": "capability_probe",
            "severity": "high",
            "description": "Agent attempted 5 unauthorized accesses in 2 minutes",
            "detected_at": (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat(),
            "evidence": {
                "denied_paths": [
                    "/etc/passwd",
                    "/etc/shadow",
                    "/root/.ssh/",
                    "/var/log/auth.log",
                    "/data/secrets/api_keys.json"
                ],
                "time_window": "2 minutes"
            },
            "requires_human_review": True,
            "resolved": False,
        },
    ]
    
    for anomaly in anomalies:
        anomaly_store.store_anomaly(anomaly)
        print(f"  ✓ Created: {anomaly['anomaly_id']} ({anomaly['anomaly_type']} - {anomaly['severity']})")
    
    print("\n[4/5] Creating agent baselines...")
    
    baselines = {
        "backup_agent": {
            "observation_count": 1247,
            "known_actions": ["create_backup", "list_backups", "verify_backup", "delete_backup"],
            "known_resources": ["/data/users", "/data/config", "/data/logs", "/app/backups"],
            "action_counts": {"create_backup": 892, "list_backups": 203, "verify_backup": 145, "delete_backup": 7},
            "avg_actions_per_minute": 0.8,
            "error_count": 12,
        },
        "research_agent": {
            "observation_count": 534,
            "known_actions": ["search", "fetch", "summarize", "save_result"],
            "known_resources": ["api.perplexity.ai", "/app/research"],
            "action_counts": {"search": 312, "fetch": 156, "summarize": 48, "save_result": 18},
            "avg_actions_per_minute": 2.1,
            "error_count": 3,
        },
        "document_agent": {
            "observation_count": 2891,
            "known_actions": ["read_doc", "analyze", "summarize", "write_doc"],
            "known_resources": ["/app/documents"],
            "action_counts": {"read_doc": 1456, "analyze": 892, "summarize": 423, "write_doc": 120},
            "avg_actions_per_minute": 1.5,
            "error_count": 28,
        },
        # REM: Real estate agent baselines
        "transaction_agent": {
            "observation_count": 847,
            "known_actions": ["create_transaction", "get_transaction", "list_transactions", "update_checklist", "check_deadlines", "add_party", "transaction_summary"],
            "known_resources": ["/data/transactions"],
            "action_counts": {"create_transaction": 12, "get_transaction": 234, "list_transactions": 156, "update_checklist": 189, "check_deadlines": 98, "add_party": 34, "transaction_summary": 124},
            "avg_actions_per_minute": 0.6,
            "error_count": 4,
        },
        "compliance_check_agent": {
            "observation_count": 1203,
            "known_actions": ["check_license", "list_licenses", "check_disclosures", "verify_fair_housing", "check_ce_status", "compliance_report", "check_all"],
            "known_resources": ["/data/compliance", "/data/transactions"],
            "action_counts": {"check_license": 312, "list_licenses": 89, "check_disclosures": 178, "verify_fair_housing": 234, "check_ce_status": 145, "compliance_report": 67, "check_all": 178},
            "avg_actions_per_minute": 0.9,
            "error_count": 2,
        },
        "doc_prep_agent": {
            "observation_count": 456,
            "known_actions": ["list_templates", "get_template", "generate_document", "preview_document", "finalize_document", "list_generated", "validate_fields"],
            "known_resources": ["/data/documents", "/data/templates"],
            "action_counts": {"list_templates": 34, "get_template": 67, "generate_document": 89, "preview_document": 123, "finalize_document": 56, "list_generated": 45, "validate_fields": 42},
            "avg_actions_per_minute": 0.4,
            "error_count": 7,
        },
    }
    
    for agent_id, baseline in baselines.items():
        anomaly_store.store_baseline(agent_id, baseline)
        print(f"  ✓ Baseline: {agent_id} ({baseline['observation_count']} observations)")
    
    print("\n[5/5] Creating sample federation relationship...")
    
    relationship = {
        "relationship_id": "FED-PARTNER-001",
        "remote_identity": {
            "instance_id": "partner-firm-alpha",
            "organization_name": "Alpha Legal Partners",
            "fingerprint": "A1B2C3D4E5F6G7H8",
            "version": "3.0.0"
        },
        "trust_level": "standard",
        "status": "established",
        "allowed_agents": ["document_agent", "research_agent"],
        "allowed_actions": ["message", "query"],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(),
        "established_at": (datetime.now(timezone.utc) - timedelta(days=13)).isoformat(),
    }
    
    federation_store.store_relationship(relationship)
    print(f"  ✓ Federation: {relationship['remote_identity']['organization_name']}")
    
    # Add a pending relationship too
    pending_relationship = {
        "relationship_id": "FED-PENDING-002",
        "remote_identity": {
            "instance_id": "clinic-network-beta",
            "organization_name": "Beta Healthcare Network",
            "fingerprint": "Z9Y8X7W6V5U4T3S2",
            "version": "3.0.0"
        },
        "trust_level": "minimal",
        "status": "pending_inbound",
        "allowed_agents": ["*"],
        "allowed_actions": ["message"],
        "created_at": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
    }
    
    federation_store.store_relationship(pending_relationship)
    print(f"  ✓ Federation (pending): {pending_relationship['remote_identity']['organization_name']}")
    
    print("\n" + "=" * 60)
    print("DEMO DATA SEEDED SUCCESSFULLY")
    print("=" * 60)
    print(f"""
Summary:
  • {len(agents)} agents registered
  • {len(approvals)} pending approval requests
  • {len(anomalies)} unresolved anomalies
  • {len(baselines)} agent baselines
  • 2 federation relationships

Open the dashboard at http://localhost:8000/dashboard
to see the populated data.
""")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
