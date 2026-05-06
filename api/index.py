from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import pandas as pd
import io
import os
import json
from typing import List, Optional
from .dedup_engine import run_dedup
# For Vercel serverless, sometimes absolute imports are needed:
# from api.dedup_engine import run_dedup

app = FastAPI(title="Duplicate Detection API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (Note: Vercel serverless is stateless, this may not persist between requests)
processed_data = {}

@app.get("/api")
async def root():
    return {"status": "ok", "message": "Duplicate Detection API is running"}

@app.post("/api/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    criteria: Optional[str] = Form(None)
):
    # Parse criteria if provided (it might come as a JSON string from the frontend)
    criteria_list = None
    if criteria:
        try:
            criteria_list = json.loads(criteria)
        except:
            # Fallback if it's just a comma-separated string
            criteria_list = criteria.split(",")

    dfs = []
    for file in files:
        if not file.filename.endswith('.csv'):
            continue
        content = await file.read()
        try:
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig", dtype=str)
            df.columns = df.columns.str.strip().str.lower()
            dfs.append(df)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading {file.filename}: {e}")

    if not dfs:
        raise HTTPException(status_code=400, detail="No valid CSV files uploaded")

    combined_df = pd.concat(dfs, ignore_index=True)
    
    cleaned, duplicates, summary = run_dedup(combined_df, criteria=criteria_list)
    
    # Store results (using a simple ID for now)
    session_id = "last_run" 
    processed_data[session_id] = {
        "cleaned": cleaned,
        "duplicates": duplicates,
        "summary": summary
    }

    return summary

@app.get("/api/download")
async def download_results():
    if "last_run" not in processed_data:
        raise HTTPException(status_code=404, detail="No data available")
    
    cleaned = processed_data["last_run"]["cleaned"]
    duplicates = processed_data["last_run"]["duplicates"]
    
    source_map = {
        "google": "Google Maps",
        "tabelog": "食べログ",
        "hotpepper": "ホットペッパー"
    }

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Split by source
        sources = cleaned["source"].unique()
        for src in sources:
            sheet_name = source_map.get(src.lower(), src.capitalize())
            # Sheet names must be <= 31 chars
            sheet_name = sheet_name[:31]
            src_df = cleaned[cleaned["source"] == src]
            src_df.to_excel(writer, index=False, sheet_name=sheet_name)
        
        # Also include a combined sheet for convenience
        cleaned.to_excel(writer, index=False, sheet_name='統合データ')
        
        # Include duplicates
        duplicates.to_excel(writer, index=False, sheet_name='重複データ')
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=dedup_results.xlsx"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
