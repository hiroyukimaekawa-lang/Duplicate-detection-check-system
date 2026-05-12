from fastapi.testclient import TestClient
from ..index import app
import os
import json

client = TestClient(app)

def test_feedback_loop():
    payload = {
        "row_a": {"name": "Test A", "address": "Address A", "phone": "000"},
        "row_b": {"name": "Test B", "address": "Address B", "phone": "111"},
        "is_duplicate": False
    }
    
    response = client.post("/api/feedback", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Check if file exists and contains data
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    feedback_path = os.path.join(base_dir, "data", "feedback.jsonl")
    assert os.path.exists(feedback_path)
    
    with open(feedback_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        last_line = json.loads(lines[-1])
        assert last_line["row_a"]["name"] == "Test A"
        assert last_line["is_duplicate"] == 0
