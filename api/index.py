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
    criteria: Optional[str] = Form(None),
    exclude_chains: Optional[str] = Form(None)
):
    # Parse criteria
    criteria_list = None
    if criteria:
        try:
            criteria_list = json.loads(criteria)
        except:
            criteria_list = criteria.split(",")

    # Parse exclude_chains
    exclude_chains_bool = False
    if exclude_chains:
        exclude_chains_bool = exclude_chains.lower() == 'true'

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
    
    # Pre-filter using external masters
    from .filters import filter_out_unwanted
    filtered_df, excluded_df, filter_stats = filter_out_unwanted(
        combined_df,
        exclude_chains=exclude_chains_bool
    )
    
    # Process Deduplication
    # We no longer pass exclude_chains to run_dedup as it is handled by filters
    cleaned_df, duplicates_df, dedup_stats = run_dedup(filtered_df, criteria=criteria_list)
    
    # Merge excluded_df into duplicates_df so they show up in the "重複排除分" tab and original tabs
    if not excluded_df.empty:
        excluded_df["_is_dup"] = True
        excluded_df["_dup_reason"] = excluded_df["_filter_reason"]
        
        # We need to compute 'municipality' and other missing columns to match dup_cols
        for col in ["_merged_to", "_dup_score", "brand", "is_chain"]:
            if col not in excluded_df.columns:
                excluded_df[col] = ""
                
        if "municipality" not in excluded_df.columns:
            from .dedup_engine import extract_municipality, normalize_address
            excluded_df["municipality"] = excluded_df.get("address", "").apply(lambda x: extract_municipality(normalize_address(x)) if pd.notna(x) else "__unknown__")
            
        if "is_phone_invalid" not in excluded_df.columns:
            excluded_df["is_phone_invalid"] = False

        dup_cols = ["name", "brand", "is_chain", "address", "phone", "url", "source", "_merged_to", "_dup_reason", "_dup_score", "municipality", "is_phone_invalid"]
        
        # Add any missing columns from dup_cols just in case
        for col in dup_cols:
            if col not in excluded_df.columns:
                excluded_df[col] = ""
                
        excluded_df = excluded_df[dup_cols].copy()
        duplicates_df = pd.concat([duplicates_df, excluded_df], ignore_index=True)

    # Compile final stats
    stats = {
        "original": len(combined_df),
        "after_filter": filter_stats["after_filter"],
        "duplicates_removed": len(duplicates_df) - len(excluded_df),
        "final": len(cleaned_df),
        "mall_excluded": filter_stats["mall_excluded"],
        "chain_excluded": filter_stats["chain_excluded"],
        # Keep original stats for backward compatibility in the frontend
        "input_count": len(combined_df),
        "dup_count": len(duplicates_df),
        "output_count": len(cleaned_df),
        "excluded_chains_count": filter_stats["chain_excluded"],
        "dup_rate": round(len(duplicates_df) / len(combined_df) * 100, 1) if len(combined_df) else 0,
        "invalid_phone_count": dedup_stats.get("invalid_phone_count", 0),
        "municipality_counts": dedup_stats.get("municipality_counts", {}),
        "reasons": {
            **dedup_stats.get("reasons", {}),
            "mall_excluded": filter_stats["mall_excluded"],
            "chain_excluded": filter_stats["chain_excluded"]
        }
    }
    
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
    
    export_format = payload.get("format", "excel")
    results = payload["results"]
    
    try:
        cleaned = pd.read_json(io.StringIO(results["cleaned"]))
    except:
        cleaned = pd.DataFrame()
        
    try:
        duplicates = pd.read_json(io.StringIO(results["duplicates"]))
    except:
        duplicates = pd.DataFrame()
    
    source_val_map = {"google": "googlemaps", "tabelog": "tabelog", "hotpepper": "hotpepper"}
    source_tab_map = {"google": "Google Maps", "tabelog": "食べログ", "hotpepper": "ホットペッパー"}
    
    # Prepare Cleaned List
    display_df = cleaned.copy()
    if not display_df.empty and "source" in display_df.columns:
        display_df["source"] = display_df["source"].apply(lambda s: source_val_map.get(str(s).lower(), s))
    
    template_cols = ["name", "genre", "address", "phone", "url", "source"]
    for col in template_cols:
        if col not in display_df.columns:
            display_df[col] = ""
    
    final_cleaned_df = display_df[template_cols] if not display_df.empty else pd.DataFrame(columns=template_cols)

    if export_format == "csv":
        import zipfile
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            # 1. 統合リスト
            csv_buffer = io.StringIO()
            final_cleaned_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
            zip_file.writestr("統合リスト.csv", csv_buffer.getvalue().encode('utf-8-sig'))
            
            # 2. 各媒体の元データ
            if not cleaned.empty or not duplicates.empty:
                full_original = pd.concat([cleaned, duplicates], ignore_index=True)
                if not full_original.empty and "source" in full_original.columns:
                    for src in full_original["source"].unique():
                        tab_name = source_tab_map.get(str(src).lower(), str(src).capitalize())
                        src_df = full_original[full_original["source"] == src]
                        csv_buffer = io.StringIO()
                        src_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                        zip_file.writestr(f"{tab_name[:31]}.csv", csv_buffer.getvalue().encode('utf-8-sig'))
            
            # 3. 重複排除分
            if not duplicates.empty:
                csv_buffer = io.StringIO()
                duplicates.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                zip_file.writestr("重複排除分.csv", csv_buffer.getvalue().encode('utf-8-sig'))
        
        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=restaurant_list_csv.zip"}
        )

    # Excel Generation (default)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_cleaned_df.to_excel(writer, index=False, sheet_name='統合リスト')
        if not cleaned.empty or not duplicates.empty:
            full_original = pd.concat([cleaned, duplicates], ignore_index=True)
            if not full_original.empty and "source" in full_original.columns:
                for src in full_original["source"].unique():
                    tab_name = source_tab_map.get(str(src).lower(), str(src).capitalize())
                    src_df = full_original[full_original["source"] == src]
                    src_df.to_excel(writer, index=False, sheet_name=tab_name[:31])
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
