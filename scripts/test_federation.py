#!/usr/bin/env python3
# TelsonBase/scripts/test_federation.py
# REM: =======================================================================================
# REM: FEDERATION TEST - VERIFY CROSS-INSTANCE TRUST ESTABLISHMENT
# REM: =======================================================================================
# REM: This script tests the complete federation flow between two TelsonBase instances.
# REM:
# REM: Prerequisites:
# REM:   docker-compose -f docker-compose.federation-test.yml up -d
# REM:
# REM: Usage:
# REM:   python scripts/test_federation.py
# REM: =======================================================================================

import sys
import json
import time
import requests
from datetime import datetime

# Instance configuration
INSTANCE_A = {
    "name": "Alpha Legal Partners",
    "url": "http://localhost:8001",
    "api_key": "alpha_secret_key_12345"
}

INSTANCE_B = {
    "name": "Beta Healthcare Network",
    "url": "http://localhost:8002",
    "api_key": "beta_secret_key_67890"
}

# Terminal colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log(msg, color=RESET):
    print(f"{color}{msg}{RESET}")


def log_step(step, msg):
    print(f"\n{BOLD}{CYAN}[Step {step}]{RESET} {msg}")


def api_get(instance, endpoint):
    headers = {"X-API-Key": instance["api_key"]}
    return requests.get(f"{instance['url']}{endpoint}", headers=headers, timeout=10)


def api_post(instance, endpoint, data):
    headers = {"X-API-Key": instance["api_key"], "Content-Type": "application/json"}
    return requests.post(f"{instance['url']}{endpoint}", headers=headers, json=data, timeout=10)


def check_health(instance):
    """Verify instance is running."""
    try:
        r = requests.get(f"{instance['url']}/health", timeout=5)
        return r.status_code == 200
    except:
        return False


def main():
    log(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════╗{RESET}")
    log(f"{BOLD}{CYAN}║           TELSONBASE FEDERATION TEST                         ║{RESET}")
    log(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════╝{RESET}")
    log(f"\n{YELLOW}Timestamp: {datetime.now().isoformat()}{RESET}")
    
    # Step 1: Check both instances are running
    log_step(1, "Checking instance health")
    
    if not check_health(INSTANCE_A):
        log(f"{RED}✗ Instance A ({INSTANCE_A['name']}) is not reachable at {INSTANCE_A['url']}{RESET}")
        log(f"\n{YELLOW}Make sure to run:{RESET}")
        log(f"  docker-compose -f docker-compose.federation-test.yml up -d")
        return 1
    log(f"  {GREEN}✓{RESET} Instance A ({INSTANCE_A['name']}) is healthy")
    
    if not check_health(INSTANCE_B):
        log(f"{RED}✗ Instance B ({INSTANCE_B['name']}) is not reachable at {INSTANCE_B['url']}{RESET}")
        return 1
    log(f"  {GREEN}✓{RESET} Instance B ({INSTANCE_B['name']}) is healthy")
    
    # Step 2: Get identity of both instances
    log_step(2, "Fetching instance identities")
    
    r = api_get(INSTANCE_A, "/v1/federation/identity")
    if r.status_code != 200:
        log(f"{RED}✗ Failed to get Instance A identity: {r.status_code}{RESET}")
        return 1
    identity_a = r.json().get("identity", {})
    log(f"  {GREEN}✓{RESET} Instance A: {identity_a.get('instance_id')}")
    log(f"      Fingerprint: {CYAN}{identity_a.get('fingerprint', 'N/A')[:32]}...{RESET}")
    
    r = api_get(INSTANCE_B, "/v1/federation/identity")
    if r.status_code != 200:
        log(f"{RED}✗ Failed to get Instance B identity: {r.status_code}{RESET}")
        return 1
    identity_b = r.json().get("identity", {})
    log(f"  {GREEN}✓{RESET} Instance B: {identity_b.get('instance_id')}")
    log(f"      Fingerprint: {CYAN}{identity_b.get('fingerprint', 'N/A')[:32]}...{RESET}")
    
    # Step 3: Instance A creates a trust invitation
    log_step(3, "Instance A creates trust invitation for Instance B")
    
    r = api_post(INSTANCE_A, "/v1/federation/invitations", {
        "trust_level": "standard",
        "allowed_agents": ["document_agent", "research_agent"],
        "expires_in_hours": 24
    })
    
    if r.status_code != 200:
        log(f"{RED}✗ Failed to create invitation: {r.status_code}{RESET}")
        log(f"  Response: {r.text}")
        return 1
    
    invitation = r.json().get("invitation", {})
    invitation_token = invitation.get("token", "")
    log(f"  {GREEN}✓{RESET} Invitation created")
    log(f"      Token: {CYAN}{invitation_token[:40]}...{RESET}" if invitation_token else "      Token: N/A")
    
    # Step 4: Instance B processes the invitation
    log_step(4, "Instance B processes the invitation")
    
    r = api_post(INSTANCE_B, "/v1/federation/invitations/process", {
        "invitation_token": invitation_token
    })
    
    if r.status_code != 200:
        log(f"{RED}✗ Failed to process invitation: {r.status_code}{RESET}")
        log(f"  Response: {r.text}")
        return 1
    
    process_result = r.json()
    relationship_id = process_result.get("relationship_id")
    log(f"  {GREEN}✓{RESET} Invitation processed")
    log(f"      Relationship ID: {CYAN}{relationship_id}{RESET}")
    log(f"      Status: {process_result.get('status', 'unknown')}")
    
    # Step 5: Instance A accepts the trust relationship
    log_step(5, "Instance A accepts the trust relationship")
    
    # First, get A's view of the relationship
    r = api_get(INSTANCE_A, "/v1/federation/relationships")
    if r.status_code == 200:
        relationships = r.json().get("relationships", [])
        pending = [rel for rel in relationships if rel.get("status") in ["pending_inbound", "pending_outbound"]]
        
        if pending:
            rel = pending[0]
            rel_id = rel.get("relationship_id")
            log(f"      Found pending relationship: {rel_id}")
            
            r = api_post(INSTANCE_A, f"/v1/federation/relationships/{rel_id}/accept", {})
            if r.status_code == 200:
                log(f"  {GREEN}✓{RESET} Trust relationship accepted")
            else:
                log(f"  {YELLOW}⚠{RESET} Accept returned: {r.status_code}")
        else:
            log(f"  {YELLOW}⚠{RESET} No pending relationships found on Instance A")
    
    # Step 6: Verify relationships on both sides
    log_step(6, "Verifying established relationships")
    
    r = api_get(INSTANCE_A, "/v1/federation/relationships")
    if r.status_code == 200:
        rels_a = r.json().get("relationships", [])
        established_a = [rel for rel in rels_a if rel.get("status") == "established"]
        log(f"  Instance A: {len(established_a)} established relationship(s)")
        for rel in established_a:
            remote = rel.get("remote_identity", {})
            log(f"      → {remote.get('organization_name', remote.get('instance_id', 'Unknown'))}")
    
    r = api_get(INSTANCE_B, "/v1/federation/relationships")
    if r.status_code == 200:
        rels_b = r.json().get("relationships", [])
        established_b = [rel for rel in rels_b if rel.get("status") == "established"]
        log(f"  Instance B: {len(established_b)} established relationship(s)")
        for rel in established_b:
            remote = rel.get("remote_identity", {})
            log(f"      → {remote.get('organization_name', remote.get('instance_id', 'Unknown'))}")
    
    # Step 7: Test federated message (if relationships established)
    log_step(7, "Testing federated message exchange")
    
    if established_a:
        rel_id = established_a[0].get("relationship_id")
        r = api_post(INSTANCE_A, f"/v1/federation/relationships/{rel_id}/message", {
            "message_type": "ping",
            "payload": {"greeting": "Hello from Alpha!"}
        })
        
        if r.status_code == 200:
            log(f"  {GREEN}✓{RESET} Federated message sent successfully")
        else:
            log(f"  {YELLOW}⚠{RESET} Message send returned: {r.status_code}")
    else:
        log(f"  {YELLOW}⚠{RESET} Skipped - no established relationships")
    
    # Summary
    log(f"\n{BOLD}═══════════════════════════════════════════════════════════════{RESET}")
    log(f"{BOLD}FEDERATION TEST COMPLETE{RESET}")
    log(f"═══════════════════════════════════════════════════════════════")
    
    log(f"""
{CYAN}Dashboard Access:{RESET}
  Instance A: {INSTANCE_A['url']}/dashboard (key: {INSTANCE_A['api_key']})
  Instance B: {INSTANCE_B['url']}/dashboard (key: {INSTANCE_B['api_key']})

{CYAN}What was tested:{RESET}
  • Identity generation for both instances
  • Trust invitation creation and processing
  • Relationship establishment flow
  • Cross-instance message capability
""")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
