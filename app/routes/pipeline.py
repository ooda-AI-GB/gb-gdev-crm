from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from app.database import get_db
from app.models import Deal, Contact, Notification
from app.automation_engine import evaluate_rules
import app.routes as routes_module
from datetime import date, datetime
import csv
import io

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/pipeline", response_class=HTMLResponse)
async def pipeline_board(
    request: Request,
    q: str = Query(None),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    query = db.query(Deal).join(Contact)
    
    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                Deal.title.ilike(search),
                Contact.name.ilike(search)
            )
        )
    
    deals = query.all()
    # Group deals by stage
    stages = ["qualified", "proposal", "negotiation", "closed_won", "closed_lost"]
    deals_by_stage = {stage: [] for stage in stages}
    for deal in deals:
        if deal.stage in deals_by_stage:
            deals_by_stage[deal.stage].append(deal)
        else:
            # Fallback for unknown stages
            deals_by_stage.setdefault("qualified", []).append(deal)
            
    return templates.TemplateResponse("pipeline/board.html", {
        "request": request,
        "deals_by_stage": deals_by_stage,
        "user": user,
        "stages": stages,
        "q": q
    })

@router.post("/pipeline/deals")
async def create_deal(
    request: Request,
    title: str = Form(...),
    value: float = Form(...),
    contact_id: int = Form(...),
    stage: str = Form("qualified"),
    probability: int = Form(0),
    expected_close: str = Form(None), # Date string
    notes: str = Form(None),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    # Parse date if provided
    close_date = None
    if expected_close:
        try:
            close_date = date.fromisoformat(expected_close)
        except ValueError:
            pass # Handle error or default to None

    deal = Deal(
        title=title,
        value=value,
        contact_id=contact_id,
        stage=stage,
        probability=probability,
        expected_close=close_date,
        notes=notes
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    evaluate_rules(db, "deal_stage_change", deal, user)
    evaluate_rules(db, "deal_probability_threshold", deal, user)
    return RedirectResponse(url="/pipeline", status_code=303)

@router.post("/pipeline/deals/{id}/move")
async def move_deal(
    request: Request,
    id: int,
    stage: str = Form(...),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    deal = db.query(Deal).filter(Deal.id == id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    deal.stage = stage

    evaluate_rules(db, "deal_stage_change", deal, user)

    if stage == "closed_won":
        contact = db.query(Contact).filter(Contact.id == deal.contact_id).first()
        if contact:
            # Check if notification already exists for this milestone
            existing = db.query(Notification).filter(
                Notification.user_id == str(contact.user_id),
                Notification.type == "deal_milestone",
                Notification.link == f"/contacts/{contact.id}",
                Notification.message.like(f"%{deal.title}%")
            ).first()
            
            if not existing:
                notif = Notification(
                    user_id=str(contact.user_id),
                    title="Deal Won!",
                    message=f"Deal '{deal.title}' has been won!",
                    type="deal_milestone",
                    link=f"/contacts/{contact.id}"
                )
                db.add(notif)
    
    db.commit()
    # If it's an AJAX request, we might want to return JSON, but for now redirect is safer for simple implementation
    # However, for drag-and-drop usually we want JSON. 
    # But the spec says "POST /pipeline/deals/{id}/move -> update stage" without specifying response type explicitly.
    # Given typical "board" interactions, I'll return JSON if it looks like an API call, or redirect if form submit.
    # Actually, let's just return a simple JSON response as it's likely consumed by JS.
    return JSONResponse({"status": "success", "new_stage": stage})

@router.post("/pipeline/deals/{id}/update")
async def update_deal(
    request: Request,
    id: int,
    probability: int = Form(None),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    deal = db.query(Deal).filter(Deal.id == id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    if probability is not None:
        deal.probability = probability
        evaluate_rules(db, "deal_probability_threshold", deal, user)
        
    db.commit()
    return RedirectResponse(url="/pipeline", status_code=303)

@router.get("/pipeline/export")
async def export_deals(
    request: Request,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    deals = db.query(Deal).join(Contact).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["ID", "Title", "Contact Name", "Value", "Currency", "Stage", "Probability", "Expected Close", "Notes", "Created At"])
    
    for deal in deals:
        writer.writerow([
            deal.id,
            deal.title,
            deal.contact.name,
            deal.value,
            deal.currency,
            deal.stage,
            deal.probability,
            deal.expected_close,
            deal.notes,
            deal.created_at
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=deals_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"}
    )

