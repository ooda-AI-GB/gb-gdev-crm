from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AutomationRule
import app.routes as routes_module
import json

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/settings/automations", response_class=HTMLResponse)
async def list_automations(
    request: Request,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    rules = db.query(AutomationRule).order_by(AutomationRule.created_at.desc()).all()
    return templates.TemplateResponse("settings/automations.html", {
        "request": request,
        "user": user,
        "rules": rules
    })

@router.post("/settings/automations/new")
async def create_automation(
    request: Request,
    name: str = Form(...),
    trigger_type: str = Form(...),
    condition_key: str = Form(...),
    condition_value: str = Form(...),
    action_type: str = Form(...),
    action_config_key: str = Form(...),
    action_config_value: str = Form(...),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    # Simple construction of JSON fields from form data
    # In a real app, this would be more complex or use JS to build the JSON
    condition = {condition_key: condition_value}
    
    # Try to parse value as number if possible for probability
    if condition_key == "probability_gte":
        try:
            condition[condition_key] = int(condition_value)
        except ValueError:
            pass

    action_config = {action_config_key: action_config_value}
    
    # Handle specific action configs based on type if needed
    if action_type == "create_activity":
        # Add default fields for activity if not present
        if "type" not in action_config:
            action_config["type"] = "task"
        if "due_in_days" not in action_config:
            action_config["due_in_days"] = 3
        if "description" not in action_config:
            action_config["description"] = "Auto-generated via automation rule"

    rule = AutomationRule(
        name=name,
        trigger_type=trigger_type,
        condition=condition,
        action_type=action_type,
        action_config=action_config,
        enabled=True
    )
    db.add(rule)
    db.commit()
    return RedirectResponse(url="/settings/automations", status_code=303)

@router.post("/settings/automations/{id}/toggle")
async def toggle_automation(
    request: Request,
    id: int,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    rule = db.query(AutomationRule).filter(AutomationRule.id == id).first()
    if rule:
        rule.enabled = not rule.enabled
        db.commit()
    return RedirectResponse(url="/settings/automations", status_code=303)

@router.post("/settings/automations/{id}/delete")
async def delete_automation(
    request: Request,
    id: int,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    rule = db.query(AutomationRule).filter(AutomationRule.id == id).first()
    if rule:
        db.delete(rule)
        db.commit()
    return RedirectResponse(url="/settings/automations", status_code=303)
