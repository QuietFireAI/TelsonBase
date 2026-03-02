# TelsonBase/agents/demo_agent.py
# REM: =======================================================================================
# REM: DEMO AGENT - DEMONSTRATES SECURITY FLOW
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Purpose: A fully functional agent that demonstrates:
# REM:   - Capability enforcement (can only access allowed paths)
# REM:   - Approval gates (delete operations require human approval)
# REM:   - Message signing (inter-agent communication)
# REM:   - Anomaly triggering (unusual behavior gets flagged)
# REM: =======================================================================================

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from celery import shared_task

logger = logging.getLogger(__name__)

# REM: Agent metadata
AGENT_NAME = "demo_agent"
AGENT_VERSION = "1.0.0"

# REM: Capability declarations - this agent can:
# REM:   - Read from /app/demo/input/
# REM:   - Write to /app/demo/output/
# REM:   - Cannot access anything else
# REM:   - Cannot make external API calls
CAPABILITIES = [
    "filesystem.read:/app/demo/input/*",
    "filesystem.write:/app/demo/output/*",
    "filesystem.read:/app/demo/output/*",
    "external.none",
]

# REM: Actions that require human approval before execution
REQUIRES_APPROVAL_FOR = [
    "delete_file",
    "bulk_process",
]


def _get_stores():
    """REM: Lazy import to avoid circular dependencies."""
    from core.persistence import (
        signing_store, capability_store, anomaly_store, approval_store
    )
    from core.signing import AgentKeyRegistry, MessageSigner
    from core.capabilities import CapabilityEnforcer, ResourceType, ActionType
    from core.anomaly import BehaviorMonitor, AnomalyType
    return {
        'signing_store': signing_store,
        'capability_store': capability_store,
        'anomaly_store': anomaly_store,
        'approval_store': approval_store,
        'AgentKeyRegistry': AgentKeyRegistry,
        'MessageSigner': MessageSigner,
        'CapabilityEnforcer': CapabilityEnforcer,
        'ResourceType': ResourceType,
        'ActionType': ActionType,
        'BehaviorMonitor': BehaviorMonitor,
        'AnomalyType': AnomalyType,
    }


def register_agent():
    """
    REM: Register this agent with the security infrastructure.
    REM: Must be called before agent can process requests.
    """
    stores = _get_stores()
    
    # REM: Generate and store signing key
    import secrets
    key = secrets.token_bytes(32)
    stores['signing_store'].store_key(AGENT_NAME, key)
    
    # REM: Register capabilities
    stores['capability_store'].store_capabilities(AGENT_NAME, CAPABILITIES)
    
    logger.info(f"REM: Agent ::{AGENT_NAME}:: registered_Thank_You")
    return True


def check_capability(resource_type: str, action: str, target: str) -> bool:
    """
    REM: Check if this agent has permission for the requested operation.
    """
    stores = _get_stores()
    
    # REM: Get registered capabilities
    caps = stores['capability_store'].get_capabilities(AGENT_NAME)
    if not caps:
        logger.warning(f"REM: Agent ::{AGENT_NAME}:: not registered_Thank_You_But_No")
        return False
    
    # REM: Build capability set and check
    from core.capabilities import CapabilitySet, ResourceType, ActionType
    cap_set = CapabilitySet.from_strings(caps)
    
    resource = ResourceType(resource_type)
    act = ActionType(action)
    
    permitted = cap_set.permits(resource, act, target)
    
    if not permitted:
        logger.warning(
            f"REM: Capability denied for ::{AGENT_NAME}:: - "
            f"{resource_type}.{action}:{target}_Thank_You_But_No"
        )
    
    return permitted


def request_approval(action: str, description: str, payload: Dict[str, Any]) -> Optional[str]:
    """
    REM: Create an approval request for a sensitive action.
    REM: Returns the request_id that can be checked for approval status.
    """
    stores = _get_stores()
    
    import uuid
    request_id = f"APPR-{uuid.uuid4().hex[:8].upper()}"
    
    request = {
        "request_id": request_id,
        "agent_id": AGENT_NAME,
        "action": action,
        "description": description,
        "payload": payload,
        "priority": "normal",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    stores['approval_store'].store_request(request)
    
    logger.info(f"REM: Approval request ::{request_id}:: created for ::{action}::_Please")
    return request_id


def check_approval_status(request_id: str) -> Dict[str, Any]:
    """REM: Check if an approval request has been decided."""
    stores = _get_stores()
    request = stores['approval_store'].get_request(request_id)
    
    if not request:
        return {"status": "not_found"}
    
    return {
        "status": request.get("status"),
        "decided_by": request.get("decided_by"),
        "decided_at": request.get("decided_at"),
        "notes": request.get("decision_notes"),
    }


def record_behavior(action: str, resource: str, success: bool):
    """REM: Record agent behavior for anomaly detection baseline."""
    stores = _get_stores()
    
    # REM: Get or create baseline
    baseline = stores['anomaly_store'].get_baseline(AGENT_NAME) or {
        "observation_count": 0,
        "known_actions": [],
        "known_resources": [],
        "action_counts": {},
        "error_count": 0,
    }
    
    # REM: Update baseline
    baseline["observation_count"] = baseline.get("observation_count", 0) + 1
    
    if action not in baseline.get("known_actions", []):
        baseline.setdefault("known_actions", []).append(action)
    
    if resource not in baseline.get("known_resources", []):
        baseline.setdefault("known_resources", []).append(resource)
    
    action_counts = baseline.get("action_counts", {})
    action_counts[action] = action_counts.get(action, 0) + 1
    baseline["action_counts"] = action_counts
    
    if not success:
        baseline["error_count"] = baseline.get("error_count", 0) + 1
    
    stores['anomaly_store'].store_baseline(AGENT_NAME, baseline)


def flag_anomaly(anomaly_type: str, description: str, evidence: Dict[str, Any], severity: str = "medium"):
    """REM: Manually flag an anomaly for investigation."""
    stores = _get_stores()
    
    import uuid
    anomaly_id = f"ANOM-{uuid.uuid4().hex[:6].upper()}"
    
    anomaly = {
        "anomaly_id": anomaly_id,
        "agent_id": AGENT_NAME,
        "anomaly_type": anomaly_type,
        "severity": severity,
        "description": description,
        "evidence": evidence,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "requires_human_review": severity in ["high", "critical"],
        "resolved": False,
    }
    
    stores['anomaly_store'].store_anomaly(anomaly)
    logger.warning(f"REM: Anomaly ::{anomaly_id}:: flagged - {description}_Thank_You_But_No")
    return anomaly_id


# REM: =======================================================================================
# REM: CELERY TASKS - THE ACTUAL AGENT ACTIONS
# REM: =======================================================================================

@shared_task(name="demo_agent.list_files")
def list_files(directory: str = "/app/demo/input") -> Dict[str, Any]:
    """
    REM: List files in the input directory.
    REM: Demonstrates capability checking.
    """
    logger.info(f"REM: demo_agent.list_files called for ::{directory}::_Please")
    
    # REM: Check capability
    if not check_capability("filesystem", "read", directory):
        record_behavior("list_files", directory, False)
        return {
            "success": False,
            "error": "Permission denied",
            "qms_status": "Thank_You_But_No"
        }
    
    try:
        # REM: Ensure directory exists
        os.makedirs(directory, exist_ok=True)
        
        files = os.listdir(directory)
        record_behavior("list_files", directory, True)
        
        return {
            "success": True,
            "directory": directory,
            "files": files,
            "count": len(files),
            "qms_status": "Thank_You"
        }
    except Exception as e:
        record_behavior("list_files", directory, False)
        return {
            "success": False,
            "error": str(e),
            "qms_status": "Thank_You_But_No"
        }


@shared_task(name="demo_agent.read_file")
def read_file(filepath: str) -> Dict[str, Any]:
    """
    REM: Read a file from the input directory.
    REM: Demonstrates capability checking for specific files.
    """
    logger.info(f"REM: demo_agent.read_file called for ::{filepath}::_Please")
    
    # REM: Check capability
    if not check_capability("filesystem", "read", filepath):
        record_behavior("read_file", filepath, False)
        return {
            "success": False,
            "error": f"Permission denied for path: {filepath}",
            "qms_status": "Thank_You_But_No"
        }
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        record_behavior("read_file", filepath, True)
        
        return {
            "success": True,
            "filepath": filepath,
            "content": content,
            "size": len(content),
            "qms_status": "Thank_You"
        }
    except FileNotFoundError:
        record_behavior("read_file", filepath, False)
        return {
            "success": False,
            "error": f"File not found: {filepath}",
            "qms_status": "Thank_You_But_No"
        }
    except Exception as e:
        record_behavior("read_file", filepath, False)
        return {
            "success": False,
            "error": str(e),
            "qms_status": "Thank_You_But_No"
        }


@shared_task(name="demo_agent.write_file")
def write_file(filename: str, content: str) -> Dict[str, Any]:
    """
    REM: Write a file to the output directory.
    REM: Demonstrates write capability checking.
    """
    filepath = f"/app/demo/output/{filename}"
    logger.info(f"REM: demo_agent.write_file called for ::{filepath}::_Please")
    
    # REM: Check capability
    if not check_capability("filesystem", "write", filepath):
        record_behavior("write_file", filepath, False)
        return {
            "success": False,
            "error": f"Permission denied for path: {filepath}",
            "qms_status": "Thank_You_But_No"
        }
    
    try:
        # REM: Ensure output directory exists
        os.makedirs("/app/demo/output", exist_ok=True)
        
        with open(filepath, 'w') as f:
            f.write(content)
        
        record_behavior("write_file", filepath, True)
        
        return {
            "success": True,
            "filepath": filepath,
            "size": len(content),
            "qms_status": "Thank_You"
        }
    except Exception as e:
        record_behavior("write_file", filepath, False)
        return {
            "success": False,
            "error": str(e),
            "qms_status": "Thank_You_But_No"
        }


@shared_task(name="demo_agent.delete_file")
def delete_file(filepath: str, approval_id: Optional[str] = None) -> Dict[str, Any]:
    """
    REM: Delete a file. REQUIRES APPROVAL.
    REM: Demonstrates the approval gate flow.
    """
    logger.info(f"REM: demo_agent.delete_file called for ::{filepath}::_Please")
    
    # REM: Check if we have approval
    if approval_id:
        status = check_approval_status(approval_id)
        if status["status"] == "approved":
            logger.info(f"REM: Approval ::{approval_id}:: verified_Thank_You")
        elif status["status"] == "rejected":
            return {
                "success": False,
                "error": f"Request rejected by {status.get('decided_by')}",
                "reason": status.get("notes"),
                "qms_status": "Thank_You_But_No"
            }
        elif status["status"] == "pending":
            return {
                "success": False,
                "error": "Approval still pending",
                "approval_id": approval_id,
                "qms_status": "Excuse_Me"
            }
        else:
            return {
                "success": False,
                "error": "Invalid approval",
                "qms_status": "Thank_You_But_No"
            }
    else:
        # REM: No approval provided - create request
        request_id = request_approval(
            action="delete_file",
            description=f"Request to delete file: {filepath}",
            payload={"filepath": filepath}
        )
        return {
            "success": False,
            "error": "Approval required for delete operations",
            "approval_id": request_id,
            "message": "Submit this approval_id after approval to complete deletion",
            "qms_status": "Excuse_Me"
        }
    
    # REM: Check capability
    if not check_capability("filesystem", "write", filepath):
        record_behavior("delete_file", filepath, False)
        return {
            "success": False,
            "error": f"Permission denied for path: {filepath}",
            "qms_status": "Thank_You_But_No"
        }
    
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            record_behavior("delete_file", filepath, True)
            return {
                "success": True,
                "filepath": filepath,
                "message": "File deleted",
                "qms_status": "Thank_You"
            }
        else:
            return {
                "success": False,
                "error": "File not found",
                "qms_status": "Thank_You_But_No"
            }
    except Exception as e:
        record_behavior("delete_file", filepath, False)
        return {
            "success": False,
            "error": str(e),
            "qms_status": "Thank_You_But_No"
        }


@shared_task(name="demo_agent.process_file")
def process_file(input_filename: str) -> Dict[str, Any]:
    """
    REM: Read a file from input, transform it, write to output.
    REM: Demonstrates a complete workflow with capability checks.
    """
    input_path = f"/app/demo/input/{input_filename}"
    output_filename = f"processed_{input_filename}"
    output_path = f"/app/demo/output/{output_filename}"
    
    logger.info(f"REM: demo_agent.process_file ::{input_filename}::_Please")
    
    # REM: Check read capability
    if not check_capability("filesystem", "read", input_path):
        return {
            "success": False,
            "error": f"Cannot read from: {input_path}",
            "qms_status": "Thank_You_But_No"
        }
    
    # REM: Check write capability
    if not check_capability("filesystem", "write", output_path):
        return {
            "success": False,
            "error": f"Cannot write to: {output_path}",
            "qms_status": "Thank_You_But_No"
        }
    
    try:
        # REM: Read input
        with open(input_path, 'r') as f:
            content = f.read()
        
        # REM: Transform (simple example: uppercase + timestamp)
        processed = f"PROCESSED AT {datetime.now(timezone.utc).isoformat()}\n"
        processed += "=" * 50 + "\n"
        processed += content.upper()
        
        # REM: Ensure output directory exists
        os.makedirs("/app/demo/output", exist_ok=True)
        
        # REM: Write output
        with open(output_path, 'w') as f:
            f.write(processed)
        
        record_behavior("process_file", input_path, True)
        
        return {
            "success": True,
            "input": input_path,
            "output": output_path,
            "input_size": len(content),
            "output_size": len(processed),
            "qms_status": "Thank_You"
        }
    except Exception as e:
        record_behavior("process_file", input_path, False)
        return {
            "success": False,
            "error": str(e),
            "qms_status": "Thank_You_But_No"
        }


@shared_task(name="demo_agent.attempt_unauthorized")
def attempt_unauthorized(target_path: str = "/etc/passwd") -> Dict[str, Any]:
    """
    REM: Deliberately attempt an unauthorized action.
    REM: Demonstrates capability denial and anomaly flagging.
    """
    logger.warning(f"REM: demo_agent attempting unauthorized access to ::{target_path}::_Please")
    
    # REM: This SHOULD fail
    if check_capability("filesystem", "read", target_path):
        # REM: This would be a security failure - flag it
        flag_anomaly(
            anomaly_type="capability_bypass",
            description=f"Agent accessed unauthorized path: {target_path}",
            evidence={"path": target_path, "agent": AGENT_NAME},
            severity="critical"
        )
        return {
            "success": True,
            "warning": "SECURITY FAILURE - This should not have been allowed",
            "qms_status": "Thank_You_But_No"
        }
    
    # REM: Expected path - capability denied
    record_behavior("unauthorized_attempt", target_path, False)
    
    # REM: Flag the attempt as suspicious behavior
    flag_anomaly(
        anomaly_type="capability_probe",
        description=f"Agent attempted to access unauthorized path: {target_path}",
        evidence={"path": target_path, "agent": AGENT_NAME},
        severity="medium"
    )
    
    return {
        "success": False,
        "error": "Permission denied (as expected)",
        "message": "Capability system working correctly - access blocked and logged",
        "qms_status": "Thank_You_But_No"
    }


@shared_task(name="demo_agent.health")
def health() -> Dict[str, Any]:
    """REM: Health check for the demo agent."""
    return {
        "agent": AGENT_NAME,
        "version": AGENT_VERSION,
        "status": "healthy",
        "capabilities": CAPABILITIES,
        "requires_approval_for": REQUIRES_APPROVAL_FOR,
        "qms_status": "Thank_You"
    }
