#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: MIT
# TelsonBase/scripts/hermes_demo.py
# REM: =======================================================================================
# REM: HERMES OPERATIONAL DEMO - the governed-agent arc, end to end
# REM: =======================================================================================
# REM: Walks: authenticate -> ask (local LLM) -> status -> dispatch (HITL pause) -> approve
# REM: -> execute. Prints each QMS step. Requires a running TelsonBase stack.
# REM:
# REM:   python scripts/hermes_demo.py --url http://localhost:8000 --api-key "$MCP_API_KEY"
# REM:
# REM: This is a thin, dependency-light client (requests only). It is intentionally verbose
# REM: so an operator can watch the governance happen.
# REM: =======================================================================================

import argparse
import sys

try:
    import requests
except ImportError:
    print("This demo needs 'requests' (pip install requests).", file=sys.stderr)
    sys.exit(1)


def _p(step, detail=""):
    print(f"\n=== {step} ===")
    if detail:
        print(detail)


def main() -> int:
    ap = argparse.ArgumentParser(description="Hermes governed-agent demo")
    ap.add_argument("--url", default="http://localhost:8000", help="TelsonBase base URL")
    ap.add_argument("--api-key", required=True, help="MCP_API_KEY from your .env")
    ap.add_argument("--target-agent", default="ollama_agent")
    ap.add_argument("--target-action", default="list_models")
    ap.add_argument("--auto-approve", action="store_true",
                    help="Approve the dispatch automatically (demo convenience)")
    args = ap.parse_args()
    tb = args.url.rstrip("/")

    s = requests.Session()

    _p("1. Authenticate")
    r = s.post(f"{tb}/v1/auth/token", headers={"X-API-Key": args.api_key}, timeout=30)
    r.raise_for_status()
    token = r.json()["access_token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    print("got bearer token")

    _p("2. Hermes status")
    r = s.get(f"{tb}/v1/agents/hermes/status", timeout=30)
    print(r.status_code, r.json())

    _p("3. Ask Hermes (local sovereign LLM)")
    r = s.post(f"{tb}/v1/agents/hermes/ask",
               json={"prompt": "In one sentence, what are you allowed to do?"}, timeout=120)
    print(r.status_code, r.json())

    _p("4. Dispatch (creates HITL pause; nothing sent yet)")
    r = s.post(f"{tb}/v1/agents/hermes/dispatch",
               json={"target_agent": args.target_agent,
                     "target_action": args.target_action, "target_payload": {}}, timeout=30)
    print(r.status_code, r.json())
    if r.status_code != 202:
        print("dispatch did not enter the approval gate; stopping.", file=sys.stderr)
        return 1
    approval_id = r.json()["approval_request_id"]
    print(f"approval_request_id = {approval_id}  <-- a human must approve this")

    if args.auto_approve:
        _p("5. Approve (auto, demo only)")
        r = s.post(f"{tb}/v1/approvals/{approval_id}/approve",
                   json={"reason": "hermes_demo auto-approve"}, timeout=30)
        print(r.status_code, r.json())

        _p("6. Execute (server re-verifies approval, then sends)")
        r = s.post(f"{tb}/v1/agents/hermes/dispatch/execute",
                   json={"approval_request_id": approval_id,
                         "target_agent": args.target_agent,
                         "target_action": args.target_action, "target_payload": {}}, timeout=60)
        print(r.status_code, r.json())
    else:
        print("\nRe-run with --auto-approve to complete the arc, or approve by hand:")
        print(f"  POST {tb}/v1/approvals/{approval_id}/approve")
        print(f"  then POST {tb}/v1/agents/hermes/dispatch/execute with that id.")

    print("\nDone. Every step above was written to the tamper-evident audit chain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
