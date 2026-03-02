# TelsonBase/gateway/egress_proxy.py
# REM: =======================================================================================
# REM: EGRESS GATEWAY - EXTERNAL COMMUNICATION FIREWALL
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: This service is the ONLY path to the outside world for agents.
# REM: All external API calls MUST go through this gateway. It enforces the domain
# REM: whitelist, logs all external communications, and prevents agent infection vectors
# REM: from unauthorized external sources.
# REM:
# REM: Security Model: Zero-trust for external communication. If a domain isn't on the
# REM: whitelist, the request is blocked. Period. No exceptions.
# REM: =======================================================================================

import os
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel

# REM: Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("egress_gateway")

# REM: Load whitelist from environment (comma-separated or JSON array format)
_raw_domains = os.getenv("ALLOWED_EXTERNAL_DOMAINS", "api.anthropic.com,api.perplexity.ai,api.venice.ai")
# REM: Strip JSON array brackets/quotes if present (e.g. '["a.com","b.com"]' → 'a.com,b.com')
_raw_domains = _raw_domains.strip().strip("[]")
ALLOWED_DOMAINS = [d.strip().strip('"').strip("'").lower() for d in _raw_domains.split(",") if d.strip().strip('"').strip("'")]

logger.info(f"REM: Egress Gateway initialized with allowed domains: ::{ALLOWED_DOMAINS}::")

app = FastAPI(
    title="TelsonBase Egress Gateway",
    description="Secure proxy for external API calls. Only whitelisted domains allowed.",
    version="1.0.0"
)

# REM: HTTP client for making outbound requests
http_client = httpx.AsyncClient(timeout=30.0)


class ProxyRequest(BaseModel):
    """REM: Structure for explicit proxy requests."""
    target_url: str
    method: str = "GET"
    headers: dict = {}
    body: Optional[str] = None


def is_domain_allowed(url: str) -> tuple[bool, str]:
    """
    REM: Check if the target URL's domain is in the whitelist.
    
    Returns:
        Tuple of (is_allowed, domain_name)
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # REM: Handle port numbers in domain
        if ":" in domain:
            domain = domain.split(":")[0]
        
        # REM: Check against whitelist
        for allowed in ALLOWED_DOMAINS:
            # REM: Allow exact match or subdomain match
            if domain == allowed or domain.endswith(f".{allowed}"):
                return True, domain
        
        return False, domain
        
    except Exception as e:
        logger.error(f"REM: Failed to parse URL ::{url}:: - Error: ::{e}::")
        return False, "invalid"


@app.get("/health")
async def health_check():
    """REM: Health check endpoint for Docker."""
    return {"status": "healthy", "service": "egress_gateway"}


@app.get("/whitelist")
async def get_whitelist():
    """REM: Return the current domain whitelist (for debugging/admin)."""
    return {
        "allowed_domains": ALLOWED_DOMAINS,
        "count": len(ALLOWED_DOMAINS)
    }


@app.api_route("/proxy", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_request(request: Request, target_url: str):
    """
    REM: Main proxy endpoint. Forwards requests to external APIs if domain is whitelisted.
    
    Query Parameters:
        target_url: The external URL to call
    
    Headers:
        X-Agent-Name: Name of the requesting agent (for audit logging)
        All other headers are forwarded to the target
    """
    agent_name = request.headers.get("X-Agent-Name", "unknown")
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # REM: Validate domain
    is_allowed, domain = is_domain_allowed(target_url)
    
    if not is_allowed:
        logger.warning(
            f"REM: BLOCKED - Agent ::{agent_name}:: attempted to reach "
            f"non-whitelisted domain ::{domain}:: - URL: ::{target_url}:: - "
            f"Timestamp: ::{timestamp}::_Thank_You_But_No"
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Domain not in whitelist",
                "domain": domain,
                "allowed_domains": ALLOWED_DOMAINS,
                "qms_status": "Thank_You_But_No"
            }
        )
    
    logger.info(
        f"REM: ALLOWED - Agent ::{agent_name}:: requesting ::{target_url}:: - "
        f"Domain ::{domain}:: - Method ::{request.method}::_Please"
    )
    
    try:
        # REM: Build headers to forward (exclude internal headers)
        forward_headers = {}
        for key, value in request.headers.items():
            key_lower = key.lower()
            # REM: Don't forward hop-by-hop or internal headers
            if key_lower not in ["host", "x-agent-name", "content-length", "transfer-encoding"]:
                forward_headers[key] = value
        
        # REM: Get request body if present
        body = await request.body()
        
        # REM: Make the external request
        response = await http_client.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            content=body if body else None
        )
        
        logger.info(
            f"REM: Response from ::{domain}:: - Status ::{response.status_code}:: - "
            f"Agent ::{agent_name}::_Thank_You"
        )
        
        # REM: Return the response to the agent
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type")
        )
        
    except httpx.TimeoutException:
        logger.error(f"REM: Timeout calling ::{target_url}::_Thank_You_But_No")
        raise HTTPException(
            status_code=504,
            detail={
                "error": "Gateway timeout",
                "target_url": target_url,
                "qms_status": "Thank_You_But_No"
            }
        )
    except httpx.RequestError as e:
        logger.error(f"REM: Request error calling ::{target_url}:: - Error: ::{e}::_Thank_You_But_No")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "Bad gateway",
                "target_url": target_url,
                "message": str(e),
                "qms_status": "Thank_You_But_No"
            }
        )


@app.on_event("shutdown")
async def shutdown():
    """REM: Cleanup on shutdown."""
    await http_client.aclose()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
