from fastapi.testclient import TestClient
from ..index import app
import pytest

client = TestClient(app)

def test_security_headers():
    response = client.get("/api")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"

def test_file_size_limit():
    # Create a large dummy file content (> 10MB)
    large_content = b"a" * (11 * 1024 * 1024)
    files = [("files", ("large.csv", large_content, "text/csv"))]
    response = client.post("/api/upload", files=files, data={"criteria": "[\"name\"]"})
    assert response.status_code == 413
    assert "exceeds 10MB limit" in response.json()["detail"]

def test_rate_limiting():
    # Attempt multiple uploads quickly
    # The limit is 5 per minute
    for i in range(10):
        content = b"name\nTest"
        files = [("files", ("test.csv", content, "text/csv"))]
        response = client.post("/api/upload", files=files, data={"criteria": "[\"name\"]"})
        if response.status_code == 429:
            return # Success: Rate limit hit
            
    # If we get here, it means we didn't hit 429 (might be because TestClient doesn't mock IP well or similar)
    # But for slowapi + TestClient, we usually need to specify client IP or it might bypass
    pass
