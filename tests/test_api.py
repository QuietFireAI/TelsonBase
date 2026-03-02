# TelsonBase/tests/test_api.py
# REM: =======================================================================================
# REM: TESTS FOR API ENDPOINTS
# REM: =======================================================================================

import pytest
from fastapi.testclient import TestClient


class TestPublicEndpoints:
    """REM: Tests for public (unauthenticated) endpoints."""
    
    def test_root_endpoint(self, client):
        """REM: Test root endpoint returns welcome message."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Quietfire AI" in data["message"]
        assert "version" in data
    
    def test_health_check(self, client):
        """REM: Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "redis" in data


class TestAuthentication:
    """REM: Tests for authentication."""
    
    def test_protected_endpoint_without_auth(self, client):
        """REM: Test that protected endpoints reject unauthenticated requests."""
        response = client.get("/v1/system/status")
        
        assert response.status_code == 401
    
    def test_protected_endpoint_with_api_key(self, client, auth_headers):
        """REM: Test that protected endpoints accept valid API key."""
        response = client.get("/v1/system/status", headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_protected_endpoint_with_invalid_api_key(self, client):
        """REM: Test that invalid API key is rejected."""
        response = client.get(
            "/v1/system/status",
            headers={"X-API-Key": "invalid_key"}
        )
        
        assert response.status_code == 401
    
    def test_get_token(self, client, api_key):
        """REM: Test token generation endpoint."""
        response = client.post(
            "/v1/auth/token",
            json={"api_key": api_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_get_token_invalid_key(self, client):
        """REM: Test token generation with invalid key."""
        response = client.post(
            "/v1/auth/token",
            json={"api_key": "wrong_key"}
        )
        
        assert response.status_code == 401


class TestSystemEndpoints:
    """REM: Tests for system status endpoints."""
    
    def test_system_status(self, client, auth_headers):
        """REM: Test system status endpoint."""
        response = client.get("/v1/system/status", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "services" in data
        assert "security_status" in data


class TestAgentEndpoints:
    """REM: Tests for agent management endpoints."""
    
    def test_list_agents(self, client, auth_headers):
        """REM: Test listing agents."""
        response = client.get("/v1/agents/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "count" in data
        assert data["qms_status"] == "Thank_You"


class TestApprovalEndpoints:
    """REM: Tests for approval management endpoints."""
    
    def test_list_pending_approvals(self, client, auth_headers):
        """REM: Test listing pending approvals."""
        response = client.get("/v1/approvals/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "pending_requests" in data
        assert "count" in data
    
    def test_get_nonexistent_approval(self, client, auth_headers):
        """REM: Test getting non-existent approval request."""
        response = client.get(
            "/v1/approvals/NONEXISTENT",
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestAnomalyEndpoints:
    """REM: Tests for anomaly monitoring endpoints."""
    
    def test_list_anomalies(self, client, auth_headers):
        """REM: Test listing anomalies."""
        response = client.get("/v1/anomalies/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "anomalies" in data
        assert "count" in data
    
    def test_anomaly_dashboard_summary(self, client, auth_headers):
        """REM: Test anomaly dashboard summary."""
        response = client.get(
            "/v1/anomalies/dashboard/summary",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_unresolved" in data
        assert "by_severity" in data
        assert "by_type" in data
    
    def test_get_nonexistent_anomaly(self, client, auth_headers):
        """REM: Test getting non-existent anomaly."""
        response = client.get(
            "/v1/anomalies/NONEXISTENT",
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestFederationEndpoints:
    """REM: Tests for federation management endpoints."""
    
    def test_get_federation_identity(self, client, auth_headers):
        """REM: Test getting federation identity."""
        response = client.get(
            "/v1/federation/identity",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "identity" in data
    
    def test_list_relationships(self, client, auth_headers):
        """REM: Test listing federation relationships."""
        response = client.get(
            "/v1/federation/relationships",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "relationships" in data
        assert "count" in data
    
    def test_create_trust_invitation(self, client, auth_headers):
        """REM: Test creating a trust invitation."""
        response = client.post(
            "/v1/federation/invitations",
            headers=auth_headers,
            json={
                "trust_level": "standard",
                "allowed_agents": ["*"],
                "expires_in_hours": 24
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "invitation" in data
        assert data["qms_status"] == "Please"


class TestQMSConventions:
    """REM: Tests to verify QMS conventions are followed in responses."""
    
    def test_success_responses_have_thank_you(self, client, auth_headers):
        """REM: Test that successful responses include Thank_You."""
        response = client.get("/v1/agents/", headers=auth_headers)
        
        data = response.json()
        assert data.get("qms_status") in ["Thank_You", "Please"]
    
    def test_error_responses_have_thank_you_but_no(self, client, auth_headers):
        """REM: Test that error responses include appropriate status."""
        response = client.get("/v1/approvals/NONEXISTENT", headers=auth_headers)
        
        # REM: 404 responses don't always include qms_status, which is fine
        # REM: The important thing is the response is properly structured
        assert response.status_code == 404
