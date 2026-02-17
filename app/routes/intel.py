from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models import CompanyIntel
import app.routes as routes_module
import os
import json
from pydantic import BaseModel
from google import genai
from datetime import datetime, timezone

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

class IntelRequest(BaseModel):
    company_name: str
    analysis_type: str

@router.get("/intel", response_class=HTMLResponse)
async def intel_dashboard(
    request: Request,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    analyses = db.query(CompanyIntel).order_by(desc(CompanyIntel.generated_at)).all()
    return templates.TemplateResponse("intel/dashboard.html", {
        "request": request,
        "analyses": analyses,
        "user": user
    })

@router.get("/intel/{id}", response_class=HTMLResponse)
async def view_analysis(
    request: Request,
    id: int,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    analysis = db.query(CompanyIntel).filter(CompanyIntel.id == id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    structured_data = None
    if getattr(analysis, 'analysis_version', None) == "2.0":
        try:
            # Clean up potential markdown formatting before parsing
            content = analysis.content
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            structured_data = json.loads(content.strip())
        except:
            # Fallback to raw content if parsing fails
            pass
            
    return templates.TemplateResponse("intel/analysis.html", {
        "request": request, 
        "analysis": analysis,
        "structured_data": structured_data,
        "user": user
    })

@router.post("/api/intel/analyze")
async def analyze_company(
    request: Request,
    data: IntelRequest,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    return await _perform_analysis(data.company_name, data.analysis_type, user, db)

@router.post("/api/intel/{id}/refresh")
async def refresh_analysis(
    id: int,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    analysis = db.query(CompanyIntel).filter(CompanyIntel.id == id).first()
    if not analysis:
        return JSONResponse(status_code=404, content={"error": "Analysis not found"})
        
    return await _perform_analysis(analysis.company_name, analysis.analysis_type, user, db, existing_id=id)

async def _perform_analysis(company_name: str, analysis_type: str, user, db: Session, existing_id: int | None = None):
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return JSONResponse(status_code=500, content={"error": "Google API Key not set"})
        
    client = genai.Client(api_key=api_key)
    
    # Fetch known competitors
    competitors = db.query(CompanyIntel.company_name).distinct().all()
    competitors_list = [c[0] for c in competitors if c[0] != company_name]
    competitors_str = ", ".join(competitors_list) if competitors_list else "None found in database"
    
    prompt = f"""Analyze the company '{company_name}' using a {analysis_type.upper()} analysis. 
    Provide a structured JSON output with the following keys:
    - executive_summary: A concise 3-sentence summary.
    - strengths: A list of bullet points.
    - weaknesses: A list of bullet points.
    - opportunities: A list of bullet points.
    - threats: A list of bullet points.
    - recommended_actions: A list of 3 specific actionable items.
    - competitor_comparison: Compare with known competitors: {competitors_str}. If none relevant, compare with general market leaders. Format as a markdown table.
    
    Ensure the output is valid JSON. Do not include markdown formatting for the JSON block itself."""
    
    try:
        response = client.models.generate_content(model="gemini-3-pro-preview", contents=prompt)
        content = response.text or ""
        
        # Clean up JSON if wrapped in markdown
        clean_content = content.strip()
        if clean_content.startswith("```json"):
            clean_content = clean_content[7:]
        if clean_content.endswith("```"):
            clean_content = clean_content[:-3]
        clean_content = clean_content.strip()
        
        if existing_id:
            intel = db.query(CompanyIntel).filter(CompanyIntel.id == existing_id).first()
            if not intel:
                 return JSONResponse(status_code=404, content={"error": "Analysis not found"})
            intel.content = clean_content
            intel.model_used = "gemini-3-pro-preview"
            intel.analysis_version = "2.0"
            intel.generated_at = datetime.now(timezone.utc)
        else:
            intel = CompanyIntel(
                company_name=company_name,
                analysis_type=analysis_type,
                content=clean_content,
                model_used="gemini-3-pro-preview",
                requested_by=str(user.email),
                analysis_version="2.0"
            )
            db.add(intel)
            
        db.commit()
        db.refresh(intel)
        
        return JSONResponse({"id": intel.id, "status": "success"})
    except Exception as e:
        # db.rollback() # db session rollback is safer if implicit in Depends(get_db) context manager?
        # Typically session rollback is needed on error.
        db.rollback()
        return JSONResponse(status_code=500, content={"error": str(e)})
