from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
import os
from typing import List
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
async def upload_files(files: List[UploadFile] = File(...)):
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
    
    cleaned, duplicates, summary = run_dedup(combined_df)
    
    # Store results (using a simple ID for now)
    session_id = "last_run" 
    processed_data[session_id] = {
        "cleaned": cleaned,
        "duplicates": duplicates,
        "summary": summary
    }

    return summary

@app.get("/api/download/cleaned")
async def download_cleaned():
    if "last_run" not in processed_data:
        raise HTTPException(status_code=404, detail="No data available")
    
    df = processed_data["last_run"]["cleaned"]
    output = io.StringIO()
    df.to_csv(output, index=False, encoding="utf-8-sig")
    return {
        "content": output.getvalue(),
        "filename": "cleaned.csv"
    }

@app.get("/api/download/duplicates")
async def download_duplicates():
    if "last_run" not in processed_data:
        raise HTTPException(status_code=404, detail="No data available")
    
    df = processed_data["last_run"]["duplicates"]
    output = io.StringIO()
    df.to_csv(output, index=False, encoding="utf-8-sig")
    return {
        "content": output.getvalue(),
        "filename": "duplicates.csv"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
