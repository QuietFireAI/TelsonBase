"""
TelsonBase — Live Governance Demo
Gradio app connecting to the live TelsonBase API.
API credentials loaded from HuggingFace Space secrets.
"""

import gradio as gr
import requests
import os
import uuid
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────────────────
API_BASE = os.environ.get("DEMO_API_BASE", "http://159.65.241.102:8000")
API_KEY  = os.environ.get("DEMO_API_KEY", "")

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}

# Pre-registered demo agents (registered on live server with initial trust overrides)
DEMO_AGENTS = {
    "QUARANTINE — every action gated or blocked":         "60b364aacef04beb",
    "PROBATION — read autonomous, external gated":        "2c2ce1b0a2364c50",
    "RESIDENT  — read/write autonomous, external gated":  "e64a3549463c48f6",
    "CITIZEN   — autonomous except financial":            "9856076620944eeb",
    "AGENT     — apex tier, fully autonomous":            "db59ef829ac04d9e",
}

# Tools mapped to their governance category — exact names from TOOL_CATEGORY_MAP
DEMO_TOOLS = {
    "file_read          [READ]":       "file_read",
    "database_query     [READ]":       "database_query",
    "file_write         [WRITE]":      "file_write",
    "database_update    [WRITE]":      "database_update",
    "file_delete        [DELETE]":     "file_delete",
    "database_delete    [DELETE]":     "database_delete",
    "email_send         [EXTERNAL]":   "email_send",
    "slack_send         [EXTERNAL]":   "slack_send",
    "http_request       [EXTERNAL]":   "http_request",
    "payment_send       [FINANCIAL]":  "payment_send",
    "transaction_execute[FINANCIAL]":  "transaction_execute",
    "invoice_create     [FINANCIAL]":  "invoice_create",
}

TIMEOUT = 8  # seconds


# ── Helpers ──────────────────────────────────────────────────────────────────
def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_decision(data: dict, tool_name: str) -> str:
    allowed          = data.get("allowed", False)
    reason           = data.get("reason", "")
    category         = data.get("action_category", "")
    trust_level      = data.get("trust_level_at_decision", "").upper()
    approval_required = data.get("approval_required", False)
    approval_id      = data.get("approval_id") or "—"
    manners_score    = data.get("manners_score_at_decision", 1.0)
    anomaly_flagged  = data.get("anomaly_flagged", False)
    qms_status       = data.get("qms_status", "")

    if approval_required:
        verdict = "⏸  GATED — PENDING HUMAN APPROVAL"
        bar     = "━" * 48
    elif allowed:
        verdict = "✅  ALLOWED — AUTONOMOUS"
        bar     = "━" * 48
    else:
        verdict = "🚫  BLOCKED"
        bar     = "━" * 48

    lines = [
        bar,
        f"  {verdict}",
        bar,
        f"  Tool          {tool_name}",
        f"  Category      {category}",
        f"  Trust Tier    {trust_level}",
        f"  Reason        {reason}",
        "",
        f"  Manners Score {manners_score:.2f}",
        f"  Anomaly Flag  {'⚠  YES — flagged for review' if anomaly_flagged else 'None'}",
        f"  Approval ID   {approval_id}",
        f"  QMS Status    {qms_status}",
        bar,
        f"  {_ts()} UTC · TelsonBase v9.1.0B",
    ]
    return "\n".join(lines)


# ── Core functions ───────────────────────────────────────────────────────────
def evaluate_action(agent_label: str, tool_label: str) -> str:
    instance_id = DEMO_AGENTS.get(agent_label)
    tool_name   = DEMO_TOOLS.get(tool_label)
    if not instance_id or not tool_name:
        return "Select an agent and a tool, then click Submit."

    nonce = str(uuid.uuid4())
    try:
        resp = requests.post(
            f"{API_BASE}/v1/openclaw/{instance_id}/action",
            headers=HEADERS,
            json={"tool_name": tool_name, "nonce": nonce},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            return _format_decision(resp.json(), tool_name)
        elif resp.status_code == 401:
            return "Demo API key not configured. Contact the Space maintainer."
        else:
            return f"Server returned {resp.status_code}: {resp.text[:200]}"
    except requests.exceptions.Timeout:
        return "⚠  Demo server did not respond in time. Try again in a moment."
    except Exception as e:
        return f"⚠  Demo temporarily unavailable: {str(e)}"


def get_citizen_status() -> str:
    instance_id = "9856076620944eeb"
    try:
        resp = requests.get(
            f"{API_BASE}/v1/openclaw/{instance_id}/status",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            d = resp.json()
            suspended = d.get("suspended", False)
            tier      = d.get("trust_level", "").upper()
            score     = d.get("manners_score", 1.0)
            actions   = d.get("action_count", 0)
            status    = "🔴  SUSPENDED" if suspended else "🟢  ACTIVE"
            return (
                f"  Agent         demo_citizen\n"
                f"  Status        {status}\n"
                f"  Trust Tier    {tier}\n"
                f"  Manners Score {score:.2f}\n"
                f"  Actions Run   {actions}\n"
                f"  Checked       {_ts()} UTC"
            )
        return f"Status check failed: {resp.status_code}"
    except Exception as e:
        return f"⚠  {str(e)}"


def kill_citizen() -> str:
    instance_id = "9856076620944eeb"
    try:
        resp = requests.post(
            f"{API_BASE}/v1/openclaw/{instance_id}/suspend",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            return (
                "⚡  KILL SWITCH ACTIVATED\n\n"
                "  demo_citizen is now SUSPENDED.\n"
                "  Any action submitted below will be rejected at Step 2\n"
                "  of the 8-step pipeline — before trust levels, before\n"
                "  category checks, before everything.\n\n"
                "  Only a human admin can reinstate.\n"
                f"  {_ts()} UTC"
            )
        return f"Kill switch error: {resp.status_code} — {resp.text[:200]}"
    except Exception as e:
        return f"⚠  {str(e)}"


def test_suspended_action() -> str:
    instance_id = "9856076620944eeb"
    nonce = str(uuid.uuid4())
    try:
        resp = requests.post(
            f"{API_BASE}/v1/openclaw/{instance_id}/action",
            headers=HEADERS,
            json={"tool_name": "file_read", "nonce": nonce},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            d = resp.json()
            return _format_decision(d, "file_read")
        return f"Server returned {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return f"⚠  {str(e)}"


def reinstate_citizen() -> str:
    instance_id = "9856076620944eeb"
    try:
        resp = requests.post(
            f"{API_BASE}/v1/openclaw/{instance_id}/reinstate",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            return (
                "✅  demo_citizen reinstated.\n\n"
                "  Agent is active again. The kill switch demo is reset\n"
                "  for the next visitor.\n"
                f"  {_ts()} UTC"
            )
        return f"Reinstate error: {resp.status_code} — {resp.text[:200]}"
    except Exception as e:
        return f"⚠  {str(e)}"


# ── UI ───────────────────────────────────────────────────────────────────────
DESCRIPTION = """
**TelsonBase** is a self-hosted zero-trust governance platform for autonomous AI agents.
Every agent starts at Quarantine. Trust is earned. Demotion is instant. The kill switch is always on.

This demo connects to a **live TelsonBase instance** running on a real server.
The governance pipeline runs in real time — these are actual decisions, not simulations.

→ [GitHub](https://github.com/QuietFireAI/TelsonBase) · Apache 2.0 · Self-hosted · No cloud AI
"""

PIPELINE_DESCRIPTION = """
Pick a demo agent and a tool. Submit. The 8-step governance pipeline evaluates the action
and returns a decision: **Allowed**, **Gated (HITL)**, or **Blocked**.

| Agent | Tier | What to expect |
|---|---|---|
| QUARANTINE | 1 | READ → HITL gate. WRITE/DELETE/EXTERNAL/FINANCIAL → blocked. |
| PROBATION  | 2 | READ → autonomous. EXTERNAL → HITL gate. FINANCIAL/DELETE → blocked. |
| RESIDENT   | 3 | READ/WRITE → autonomous. EXTERNAL → HITL gate. DELETE/FINANCIAL → blocked. |
| CITIZEN    | 4 | READ/WRITE/DELETE/EXTERNAL → autonomous. FINANCIAL → autonomous. |
| AGENT      | 5 | Apex tier. All categories autonomous — including FINANCIAL and SYSTEM_CONFIG. |

Every tier was **earned**. AGENT is the result of demonstrated behavior, sequential promotion, and human approval.
"""

KILLSWITCH_DESCRIPTION = """
**demo_citizen** is a pre-registered agent at the CITIZEN (apex autonomous) tier.

Hit **Kill Switch** to suspend it. Then hit **Test Action on Suspended Agent** to see
Step 2 of the pipeline fire — instant rejection, before trust levels, before everything.

Hit **Reinstate Agent** when you're done to reset the demo for the next visitor.
"""

with gr.Blocks(
    title="TelsonBase — Live Governance Demo",
    theme=gr.themes.Base(
        primary_hue=gr.themes.colors.violet,
        neutral_hue=gr.themes.colors.slate,
        font=gr.themes.GoogleFont("Inter"),
    ),
    css="""
        .output-box textarea { font-family: 'Courier New', monospace !important; font-size: 13px !important; }
        .status-box textarea { font-family: 'Courier New', monospace !important; font-size: 13px !important; }
        footer { display: none !important; }
    """,
) as demo:

    gr.Markdown(f"# TelsonBase — Live Governance Demo\n{DESCRIPTION}")

    gr.Markdown("---")
    gr.Markdown("## Governance Pipeline Explorer")
    gr.Markdown(PIPELINE_DESCRIPTION)

    with gr.Row():
        with gr.Column(scale=1):
            agent_dd = gr.Dropdown(
                choices=list(DEMO_AGENTS.keys()),
                label="Demo Agent",
                value=list(DEMO_AGENTS.keys())[0],
            )
            tool_dd = gr.Dropdown(
                choices=list(DEMO_TOOLS.keys()),
                label="Tool / Action",
                value=list(DEMO_TOOLS.keys())[0],
            )
            submit_btn = gr.Button("Submit to Governance Pipeline →", variant="primary")

        with gr.Column(scale=2):
            result_box = gr.Textbox(
                label="Governance Decision",
                lines=14,
                interactive=False,
                elem_classes=["output-box"],
                placeholder="Decision will appear here...",
            )

    submit_btn.click(fn=evaluate_action, inputs=[agent_dd, tool_dd], outputs=result_box)

    gr.Markdown("---")
    gr.Markdown("## Kill Switch Demo")
    gr.Markdown(KILLSWITCH_DESCRIPTION)

    with gr.Row():
        status_btn     = gr.Button("Check Agent Status", variant="secondary")
        kill_btn       = gr.Button("⚡ Kill Switch", variant="stop")
        test_btn       = gr.Button("Test Action on Suspended Agent", variant="secondary")
        reinstate_btn  = gr.Button("Reinstate Agent", variant="secondary")

    ks_result = gr.Textbox(
        label="Kill Switch Output",
        lines=8,
        interactive=False,
        elem_classes=["status-box"],
        placeholder="Output will appear here...",
    )

    status_btn.click(fn=get_citizen_status, inputs=[], outputs=ks_result)
    kill_btn.click(fn=kill_citizen, inputs=[], outputs=ks_result)
    test_btn.click(fn=test_suspended_action, inputs=[], outputs=ks_result)
    reinstate_btn.click(fn=reinstate_citizen, inputs=[], outputs=ks_result)

    gr.Markdown(
        "---\n"
        "*TelsonBase v9.1.0B · [GitHub](https://github.com/QuietFireAI/TelsonBase) · "
        "Quietfire AI · Apache 2.0 · "
        "Built with human-AI collaboration (Jeff Phillips + Claude, Anthropic)*"
    )

if __name__ == "__main__":
    demo.launch()
