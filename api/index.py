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

# In-memory storage is NOT used for Vercel deployment as it is stateless.
# Data is passed through the frontend.

@app.get("/api")
async def root():
    return {"status": "ok", "message": "Duplicate Detection API is running"}

@app.post("/api/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    criteria: Optional[str] = Form(None)
):
    # Parse criteria
    criteria_list = None
    if criteria:
        try:
            criteria_list = json.loads(criteria)
        except:
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

    # Combine all DataFrames into one before dedup
    combined_df = pd.concat(dfs, ignore_index=True)
    
    # Process
    cleaned_df, duplicates_df, stats = run_dedup(combined_df, criteria=criteria_list)
    
    # Return everything to the frontend
    return {
        "stats": stats,
        "results": {
            "cleaned": cleaned_df.to_json(orient="records"),
            "duplicates": duplicates_df.to_json(orient="records")
        }
    }
    
@app.post("/api/download")
async def download_results(payload: dict):
    if "results" not in payload:
        raise HTTPException(status_code=400, detail="No data provided")
    
    results = payload["results"]
    # Handle potentially empty data
    try:
        cleaned = pd.read_json(io.StringIO(results["cleaned"]))
    except:
        cleaned = pd.DataFrame()
        
    try:
        duplicates = pd.read_json(io.StringIO(results["duplicates"]))
    except:
        duplicates = pd.DataFrame()
    
    # Map source values for the data inside the sheet
    source_val_map = {
        "google": "googlemaps",
        "tabelog": "tabelog",
        "hotpepper": "hotpepper"
    }
    
    # Mapping for Tab Names
    source_tab_map = {
        "google": "Google Maps",
        "tabelog": "食べログ",
        "hotpepper": "ホットペッパー"
    }
    
    # 1. Prepare Standardized "統合リスト"
    display_df = cleaned.copy()
    if not display_df.empty and "source" in display_df.columns:
        display_df["source"] = display_df["source"].apply(lambda s: source_val_map.get(str(s).lower(), s))
    
    template_cols = ["name", "genre", "address", "phone", "url", "source"]
    for col in template_cols:
        if col not in display_df.columns:
            display_df[col] = ""
    
    if not display_df.empty:
        final_cleaned_df = display_df[template_cols]
    else:
        final_cleaned_df = pd.DataFrame(columns=template_cols)

    # 2. Generate Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Standardized Cleaned List
        final_cleaned_df.to_excel(writer, index=False, sheet_name='統合リスト')
        
        # Original Media Sheets
        if not cleaned.empty or not duplicates.empty:
            full_original = pd.concat([cleaned, duplicates], ignore_index=True)
            
            if not full_original.empty and "source" in full_original.columns:
                sources = full_original["source"].unique()
                for src in sources:
                    tab_name = source_tab_map.get(str(src).lower(), str(src).capitalize())
                    src_df = full_original[full_original["source"] == src]
                    src_df.to_excel(writer, index=False, sheet_name=tab_name[:31])
            
        # Sheet "重複データ"
        duplicates.to_excel(writer, index=False, sheet_name='重複排除分')
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=restaurant_list.xlsx"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
