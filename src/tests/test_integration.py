"""Integration tests for MCP Security Gateway."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.main import app
from src.database import get_db
from src.models import Base, User
from src.gateway.auth import get_password_hash


# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def client():
    """Create test client."""
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create test user
    db = TestingSessionLocal()
    test_user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpass"),
        is_active=True,
        is_admin=True
    )
    db.add(test_user)
    db.commit()
    db.close()

    # Create client
    client = TestClient(app)
    yield client

    # Cleanup
    Base.metadata.drop_all(bind=engine)


class TestAuthentication:
    """Test authentication endpoints."""

    def test_login_success(self, client):
        """Test successful login."""
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "testpass"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_password(self, client):
        """Test login with invalid password."""
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "wrongpass"}
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """Test login with nonexistent user."""
        response = client.post(
            "/auth/login",
            json={"username": "nonexistent", "password": "password"}
        )
        assert response.status_code == 401

    def test_get_current_user(self, client):
        """Test getting current user info."""
        # Login first
        login_response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "testpass"}
        )
        token = login_response.json()["access_token"]

        # Get user info
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"

    def test_unauthorized_access(self, client):
        """Test access without token."""
        response = client.get("/auth/me")
        assert response.status_code == 403  # No auth header


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_readiness_check(self, client):
        """Test readiness check endpoint."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "MCP Security Gateway"


class TestAdminEndpoints:
    """Test admin endpoints."""

    def test_list_servers_as_admin(self, client):
        """Test listing servers as admin."""
        # Login
        login_response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "testpass"}
        )
        token = login_response.json()["access_token"]

        # List servers
        response = client.get(
            "/admin/servers",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_metrics_as_admin(self, client):
        """Test getting metrics as admin."""
        # Login
        login_response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "testpass"}
        )
        token = login_response.json()["access_token"]

        # Get metrics
        response = client.get(
            "/admin/metrics",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "blocked_requests" in data
        assert "active_users" in data


class TestDashboard:
    """Test dashboard endpoint."""

    def test_dashboard_accessible(self, client):
        """Test that dashboard is accessible."""
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "MCP Security Gateway" in response.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
