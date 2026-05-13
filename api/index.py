from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import pandas as pd
import io
import os
import json
from typing import List, Optional
from .dedup_engine import run_dedup
from .privacy import apply_privacy_masking
# For Vercel serverless, sometimes absolute imports are needed:
# from api.dedup_engine import run_dedup

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Duplicate Detection API")
GEMINI_API_KEY = "AIzaSyAdjPoqr7nfsbGRxCkD-xnZVet6bAKNLc8"
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Max file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_details = traceback.format_exc()
    print(error_details)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": error_details}
    )

# In-memory storage is NOT used for Vercel deployment as it is stateless.
# Data is passed through the frontend.

@app.get("/api")
async def root():
    return {"status": "ok", "message": "Duplicate Detection API is running"}

@app.post("/api/upload")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    criteria: Optional[str] = Form(None),
    exclude_chains: Optional[str] = Form(None),
    privacy_mode: Optional[str] = Form(None)
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
    # Parse privacy_mode
    privacy_mode_bool = False
    if privacy_mode:
        privacy_mode_bool = privacy_mode.lower() == 'true'

    dfs = []
    for file in files:
        if not file.filename.endswith('.csv'):
            continue
            
        # File Size Validation
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large: {file.filename} exceeds 10MB limit")
            
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
    cleaned_df, duplicates_df, dedup_stats = run_dedup(
        filtered_df, 
        criteria=criteria_list,
        api_key=GEMINI_API_KEY
    )
    
    # Merge excluded_df into duplicates_df so they show up in the "重複排除分" tab and original tabs
    if not excluded_df.empty:
        excluded_df["_is_dup"] = True
        excluded_df["_dup_reason"] = excluded_df["_filter_reason"]
        
        # We need to compute 'municipality' and other missing columns to match dup_cols
        for col in ["_merged_to", "_dup_score", "brand", "is_chain"]:
            if col not in excluded_df.columns:
                excluded_df[col] = ""
                
        if "municipality" not in excluded_df.columns:
            from .normalizer import extract_municipality, normalize_address
            def _extract_muni(addr):
                if pd.isna(addr) or not addr: return "__unknown__"
                p, c = extract_municipality(addr)
                return p + c if p or c else "__unknown__"
            excluded_df["municipality"] = excluded_df.get("address", "").apply(_extract_muni)
            
        if "is_phone_invalid" not in excluded_df.columns:
            excluded_df["is_phone_invalid"] = False

        dup_cols = ["name", "brand", "is_chain", "address", "phone", "url", "source", "_merged_to", "_dup_reason", "_dup_score", "municipality", "is_phone_invalid"]
        
        # Add any missing columns from dup_cols just in case
        for col in dup_cols:
            if col not in excluded_df.columns:
                excluded_df[col] = ""
                
        # Map filter reason to dup reason for consistent export
        if "_filter_reason" in excluded_df.columns:
            excluded_df["_dup_reason"] = excluded_df["_filter_reason"]

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
    
    # Apply Privacy Masking if enabled
    if privacy_mode_bool:
        cleaned_df = apply_privacy_masking(cleaned_df)
        duplicates_df = apply_privacy_masking(duplicates_df)

    # Prepare samples for user review (Feedback Loop)
    review_samples = []
    if not duplicates_df.empty:
        # Take a few samples that were matched by ML or fuzzy logic (not phone exact)
        fuzzy_dups = duplicates_df[duplicates_df["_dup_reason"].isin(["ml_model", "name_addr_fuzzy", "name_addr_score", "name_area"])]
        sample_size = min(5, len(fuzzy_dups)) if not fuzzy_dups.empty else 0
        if sample_size > 0:
            samples = fuzzy_dups.sample(sample_size)
            for _, row in samples.iterrows():
                # Find the 'master' row in cleaned_df or filtered_df
                master_idx = row["_merged_to"]
                if master_idx and str(master_idx).isdigit():
                    try:
                        m_idx = int(master_idx)
                        if m_idx in filtered_df.index:
                            master_row = filtered_df.loc[m_idx]
                            # Clean NaN from dicts
                            row_a_dict = {k: (v if pd.notnull(v) else None) for k, v in master_row.to_dict().items()}
                            row_b_dict = {k: (v if pd.notnull(v) else None) for k, v in row.to_dict().items()}
                            
                            review_samples.append({
                                "row_a": row_a_dict,
                                "row_b": row_b_dict,
                                "reason": row["_dup_reason"]
                            })
                    except:
                        continue

    # Return everything to the frontend
    # Replace NaN with None to avoid JSON serialization errors
    cleaned_dict = cleaned_df.where(pd.notnull(cleaned_df), None).to_dict(orient="records")
    duplicates_dict = duplicates_df.where(pd.notnull(duplicates_df), None).to_dict(orient="records")
    
    return {
        "stats": stats,
        "results": {
            "cleaned": cleaned_dict,
            "duplicates": duplicates_dict,
            "review_samples": review_samples
        }
    }
    
@app.post("/api/download")
async def download_results(payload: dict):
    if "results" not in payload:
        raise HTTPException(status_code=400, detail="No data provided")
    
    export_format = payload.get("format", "excel")
    results = payload["results"]
    
    try:
        cleaned = pd.DataFrame(results["cleaned"])
    except:
        cleaned = pd.DataFrame()
        
    try:
        duplicates = pd.DataFrame(results["duplicates"])
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
            # 1. 統合済みリスト
            zip_file.writestr("統合済みリスト.csv", final_cleaned_df.to_csv(index=False, encoding='utf-8-sig'))
            
            # 2. 重複排除分 (ロジックによる重複)
            dups_real = duplicates[~duplicates["_dup_reason"].isin(["chain_excluded", "mall_excluded"])]
            if not dups_real.empty:
                zip_file.writestr("重複排除分.csv", dups_real[template_cols].to_csv(index=False, encoding='utf-8-sig'))
            
            # 3. 排除チェーン店
            chains = duplicates[duplicates["_dup_reason"] == "chain_excluded"]
            if not chains.empty:
                zip_file.writestr("排除チェーン店.csv", chains[template_cols].to_csv(index=False, encoding='utf-8-sig'))
            
            # 4. 商業施設除外
            malls = duplicates[duplicates["_dup_reason"] == "mall_excluded"]
            if not malls.empty:
                zip_file.writestr("商業施設除外.csv", malls[template_cols].to_csv(index=False, encoding='utf-8-sig'))
            
            # 5. 各媒体の元データ
            if not cleaned.empty or not duplicates.empty:
                full_original = pd.concat([cleaned, duplicates], ignore_index=True)
                if not full_original.empty and "source" in full_original.columns:
                    for src in full_original["source"].unique():
                        tab_name = source_tab_map.get(str(src).lower(), str(src).capitalize())
                        src_df = full_original[full_original["source"] == src]
                        zip_file.writestr(f"{tab_name[:31]}.csv", src_df.to_csv(index=False, encoding='utf-8-sig'))
        
        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=results.zip"}
        )

    # Excel Generation (default)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # 1. 統合済みリスト
        final_cleaned_df.to_excel(writer, index=False, sheet_name="統合済みリスト")
        
        # 2. 重複排除分
        dups_real = duplicates[~duplicates["_dup_reason"].isin(["chain_excluded", "mall_excluded"])]
        if not dups_real.empty:
            dups_real[template_cols].to_excel(writer, index=False, sheet_name="重複排除分")
        
        # 3. 排除チェーン店
        chains = duplicates[duplicates["_dup_reason"] == "chain_excluded"]
        if not chains.empty:
            chains[template_cols].to_excel(writer, index=False, sheet_name="排除チェーン店")
            
        # 4. 商業施設除外
        malls = duplicates[duplicates["_dup_reason"] == "mall_excluded"]
        if not malls.empty:
            malls[template_cols].to_excel(writer, index=False, sheet_name="商業施設除外")
            
        # 5. 各媒体の元データ
        if not cleaned.empty or not duplicates.empty:
            full_original = pd.concat([cleaned, duplicates], ignore_index=True)
            if not full_original.empty and "source" in full_original.columns:
                for src in full_original["source"].unique():
                    tab_name = source_tab_map.get(str(src).lower(), str(src).capitalize())
                    src_df = full_original[full_original["source"] == src]
                    src_df.to_excel(writer, index=False, sheet_name=tab_name[:31])
    
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=results.xlsx"}
    )

@app.post("/api/feedback")
async def save_feedback(payload: dict):
    """
    Accepts feedback on a pair of records.
    Payload: { "row_a": {}, "row_b": {}, "is_duplicate": bool }
    """
    if "row_a" not in payload or "row_b" not in payload:
        raise HTTPException(status_code=400, detail="Incomplete feedback data")
        
    feedback_item = {
        "row_a": payload["row_a"],
        "row_b": payload["row_b"],
        "is_duplicate": 1 if payload["is_duplicate"] else 0,
        "timestamp": os.getenv("VERCEL_REGION", "local") # Optional metadata
    }
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    feedback_path = os.path.join(base_dir, "data", "feedback.jsonl")
    
    try:
        os.makedirs(os.path.dirname(feedback_path), exist_ok=True)
        with open(feedback_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_item, ensure_ascii=False) + "\n")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save feedback: {e}")

@app.post("/api/train")
async def train_model():
    """
    Triggers re-training of the ML model using feedback.jsonl.
    """
    from .model import DedupModel
    base_dir = os.path.dirname(os.path.abspath(__file__))
    feedback_path = os.path.join(base_dir, "data", "feedback.jsonl")
    
    if not os.path.exists(feedback_path):
        raise HTTPException(status_code=404, detail="No feedback data available for training.")
        
    labeled_pairs = []
    try:
        with open(feedback_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    labeled_pairs.append(json.loads(line))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading feedback: {e}")
        
    if not labeled_pairs:
        raise HTTPException(status_code=400, detail="Feedback file is empty.")
        
    model = DedupModel()
    result = model.train(labeled_pairs)
    return result

@app.get("/api/config")
async def get_config():
    """Returns system configuration status."""
    return {
        "gemini_active": bool(GEMINI_API_KEY),
        "feedback_count": sum(1 for line in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "feedback.jsonl"), "r")) if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "feedback.jsonl")) else 0
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
