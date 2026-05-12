from fastapi.testclient import TestClient
from ..index import app
import io
import pandas as pd
import json

client = TestClient(app)

def test_api_root():
    response = client.get("/api")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_upload_and_process():
    # Create sample CSV content
    csv_data1 = "name,address,phone,url,source\n焼鳥 鳥一郎,東京都新宿区1-2-3,03-1234-5678,http://a,google"
    csv_data2 = "name,address,phone,url,source\n鳥一郎 新宿店,新宿区1-2-3,0312345678,http://b,tabelog"
    
    files = [
        ("files", ("file1.csv", io.BytesIO(csv_data1.encode("utf-8-sig")), "text/csv")),
        ("files", ("file2.csv", io.BytesIO(csv_data2.encode("utf-8-sig")), "text/csv"))
    ]
    
    response = client.post(
        "/api/upload",
        files=files,
        data={"criteria": json.dumps(["phone", "name"]), "exclude_chains": "false"}
    )
    
    assert response.status_code == 200
    res_data = response.json()
    assert "stats" in res_data
    assert res_data["stats"]["original"] == 2
    assert res_data["stats"]["final"] == 1
    assert res_data["stats"]["dup_count"] == 1

def test_download_excel():
    # Setup some dummy data in session (index.py uses stateless payload for download)
    cleaned_data = [{"name": "A", "address": "B", "phone": "C", "source": "google"}]
    duplicates_data = []
    
    payload = {
        "results": {
            "cleaned": json.dumps(cleaned_data),
            "duplicates": json.dumps(duplicates_data)
        },
        "format": "excel"
    }
    
    response = client.post("/api/download", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

def test_download_zip_csv():
    cleaned_data = [{"name": "A", "address": "B", "phone": "C", "source": "google"}]
    duplicates_data = []
    
    payload = {
        "results": {
            "cleaned": json.dumps(cleaned_data),
            "duplicates": json.dumps(duplicates_data)
        },
        "format": "csv"
    }
    
    response = client.post("/api/download", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
