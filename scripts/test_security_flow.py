#!/usr/bin/env python3
# TelsonBase/scripts/test_security_flow.py
# REM: =======================================================================================
# REM: INTEGRATION TEST - DEMONSTRATES COMPLETE SECURITY FLOW
# REM: =======================================================================================
# REM: Run this after `docker-compose up -d` to verify everything works.
# REM:
# REM: Usage:
# REM:   python scripts/test_security_flow.py
# REM:
# REM: Or from within the container:
# REM:   docker-compose exec mcp_server python scripts/test_security_flow.py
# REM: =======================================================================================

import os
import sys
import json
import time
import requests
from datetime import datetime

# Configuration
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
API_KEY = os.getenv("MCP_API_KEY", "test_api_key")

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log(msg, color=RESET):
    print(f"{color}{msg}{RESET}")


def log_test(name, passed, details=""):
    status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{status}] {name}")
    if details and not passed:
        print(f"         {YELLOW}{details}{RESET}")


def api_get(endpoint):
    """Make authenticated GET request."""
    headers = {"X-API-Key": API_KEY}
    return requests.get(f"{API_BASE}{endpoint}", headers=headers)


def api_post(endpoint, data):
    """Make authenticated POST request."""
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    return requests.post(f"{API_BASE}{endpoint}", headers=headers, json=data)


def test_health():
    """Test that the API is up."""
    log(f"\n{BOLD}1. HEALTH CHECK{RESET}")
    
    try:
        r = requests.get(f"{API_BASE}/health")
        passed = r.status_code == 200 and r.json().get("status") == "healthy"
        log_test("API responds to /health", passed)
        return passed
    except Exception as e:
        log_test("API responds to /health", False, str(e))
        return False


def test_authentication():
    """Test that authentication works."""
    log(f"\n{BOLD}2. AUTHENTICATION{RESET}")
    
    # Test without auth
    r = requests.get(f"{API_BASE}/v1/system/status")
    log_test("Protected endpoint rejects no auth", r.status_code == 401)
    
    # Test with bad auth
    r = requests.get(f"{API_BASE}/v1/system/status", headers={"X-API-Key": "wrong"})
    log_test("Protected endpoint rejects bad auth", r.status_code == 401)
    
    # Test with good auth
    r = api_get("/v1/system/status")
    passed = r.status_code == 200
    log_test("Protected endpoint accepts valid auth", passed)
    
    if passed:
        data = r.json()
        log_test("System status returns version", "version" in data)
        log_test("System status returns security_status", "security_status" in data)
    
    return passed


def test_agent_registration():
    """Test agent listing and registration."""
    log(f"\n{BOLD}3. AGENT REGISTRATION{RESET}")
    
    r = api_get("/v1/agents/")
    passed = r.status_code == 200
    log_test("Agent list endpoint works", passed)
    
    if passed:
        data = r.json()
        log_test("Returns agent list", "agents" in data)
        log_test("Returns count", "count" in data)
        log(f"    {CYAN}Found {data.get('count', 0)} registered agents{RESET}")
    
    return passed


def test_task_dispatch():
    """Test task dispatch (will fail if Celery not running, that's ok)."""
    log(f"\n{BOLD}4. TASK DISPATCH{RESET}")
    
    # This tests the API endpoint, not necessarily Celery execution
    r = api_post("/v1/tasks/dispatch", {
        "task_name": "demo_agent.health",
        "args": [],
        "kwargs": {}
    })
    
    if r.status_code == 200:
        log_test("Task dispatch accepted", True)
        data = r.json()
        log_test("Returns task_id", "task_id" in data)
        log(f"    {CYAN}Task ID: {data.get('task_id', 'N/A')}{RESET}")
        return True
    elif r.status_code == 503:
        log_test("Task dispatch (Celery not running)", False, "Expected - Celery workers not running")
        return True  # This is expected if just testing API
    else:
        log_test("Task dispatch", False, f"Status: {r.status_code}")
        return False


def test_approval_flow():
    """Test approval endpoints."""
    log(f"\n{BOLD}5. APPROVAL FLOW{RESET}")
    
    # List approvals
    r = api_get("/v1/approvals/")
    passed = r.status_code == 200
    log_test("List approvals endpoint works", passed)
    
    if passed:
        data = r.json()
        count = data.get("count", 0)
        log(f"    {CYAN}Found {count} pending approvals{RESET}")
        
        # If there are approvals, test getting one
        if count > 0 and data.get("pending_requests"):
            req = data["pending_requests"][0]
            req_id = req.get("request_id")
            
            r2 = api_get(f"/v1/approvals/{req_id}")
            log_test("Get specific approval works", r2.status_code == 200)
    
    # Test non-existent approval
    r = api_get("/v1/approvals/NONEXISTENT-123")
    log_test("Non-existent approval returns 404", r.status_code == 404)
    
    return passed


def test_anomaly_monitoring():
    """Test anomaly endpoints."""
    log(f"\n{BOLD}6. ANOMALY MONITORING{RESET}")
    
    # List anomalies
    r = api_get("/v1/anomalies/")
    passed = r.status_code == 200
    log_test("List anomalies endpoint works", passed)
    
    if passed:
        data = r.json()
        count = data.get("count", 0)
        log(f"    {CYAN}Found {count} unresolved anomalies{RESET}")
    
    # Dashboard summary
    r = api_get("/v1/anomalies/dashboard/summary")
    passed2 = r.status_code == 200
    log_test("Dashboard summary endpoint works", passed2)
    
    if passed2:
        data = r.json()
        log_test("Summary has severity breakdown", "by_severity" in data)
        log_test("Summary has type breakdown", "by_type" in data)
    
    return passed and passed2


def test_federation():
    """Test federation endpoints."""
    log(f"\n{BOLD}7. FEDERATION{RESET}")
    
    # Get identity
    r = api_get("/v1/federation/identity")
    passed = r.status_code == 200
    log_test("Get federation identity works", passed)
    
    if passed:
        data = r.json()
        log_test("Identity has instance info", "identity" in data)
    
    # List relationships
    r = api_get("/v1/federation/relationships")
    passed2 = r.status_code == 200
    log_test("List relationships works", passed2)
    
    if passed2:
        data = r.json()
        count = data.get("count", 0)
        log(f"    {CYAN}Found {count} federation relationships{RESET}")
    
    # Create invitation (just test the endpoint accepts the request)
    r = api_post("/v1/federation/invitations", {
        "trust_level": "minimal",
        "allowed_agents": ["demo_agent"],
        "expires_in_hours": 1
    })
    log_test("Create invitation endpoint works", r.status_code == 200)
    
    return passed and passed2


def test_dashboard():
    """Test that dashboard is served."""
    log(f"\n{BOLD}8. DASHBOARD{RESET}")
    
    r = requests.get(f"{API_BASE}/dashboard")
    passed = r.status_code == 200
    log_test("Dashboard endpoint responds", passed)
    
    if passed:
        content = r.text
        log_test("Dashboard contains HTML", "<html" in content.lower())
        log_test("Dashboard contains TelsonBase/TelsonBase reference", 
                 "telsonbase" in content.lower() or "telsonbase" in content.lower())
    
    return passed


def main():
    log(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════╗{RESET}")
    log(f"{BOLD}{CYAN}║         TELSONBASE SECURITY FLOW INTEGRATION TEST            ║{RESET}")
    log(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════╝{RESET}")
    log(f"\n{YELLOW}API Base: {API_BASE}{RESET}")
    log(f"{YELLOW}Timestamp: {datetime.now().isoformat()}{RESET}")
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    results.append(("Authentication", test_authentication()))
    results.append(("Agent Registration", test_agent_registration()))
    results.append(("Task Dispatch", test_task_dispatch()))
    results.append(("Approval Flow", test_approval_flow()))
    results.append(("Anomaly Monitoring", test_anomaly_monitoring()))
    results.append(("Federation", test_federation()))
    results.append(("Dashboard", test_dashboard()))
    
    # Summary
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    log(f"\n{BOLD}═══════════════════════════════════════════════════════════════{RESET}")
    log(f"{BOLD}SUMMARY: {passed}/{total} test groups passed{RESET}")
    
    if passed == total:
        log(f"\n{GREEN}{BOLD}✓ All tests passed. TelsonBase is operational.{RESET}\n")
        return 0
    else:
        failed = [name for name, p in results if not p]
        log(f"\n{RED}{BOLD}✗ Some tests failed: {', '.join(failed)}{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
