from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, cast, Date
from app.database import get_db
from app.models import Contact, Deal, Activity
import app.routes as routes_module
from datetime import datetime, timedelta
import json

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    # Quick stats
    total_contacts = db.query(Contact).count()
    open_deals_count = db.query(Deal).filter(Deal.stage.notin_(["closed_won", "closed_lost"])).count()
    total_pipeline_value = db.query(func.sum(Deal.value)).filter(Deal.stage.notin_(["closed_won", "closed_lost"])).scalar() or 0.0
    
    won_deals = db.query(Deal).filter(Deal.stage == "closed_won").count()
    lost_deals = db.query(Deal).filter(Deal.stage == "closed_lost").count()
    total_closed = won_deals + lost_deals
    win_rate = int((won_deals / total_closed) * 100) if total_closed > 0 else 0

    # Pipeline summary
    pipeline_summary = db.query(
        Deal.stage, 
        func.count(Deal.id).label("count"), 
        func.sum(Deal.value).label("value")
    ).group_by(Deal.stage).all()
    
    # Format summary for template
    summary_dict = {stage: {"count": 0, "value": 0} for stage in ["qualified", "proposal", "negotiation", "closed_won", "closed_lost"]}
    for stage, count, value in pipeline_summary:
        if stage in summary_dict:
            summary_dict[stage] = {"count": count, "value": value or 0}

    # Chart Data Preparation
    chart_stages = ["qualified", "proposal", "negotiation", "closed_won", "closed_lost"]
    chart_data = {
        "labels": [s.replace("_", " ").title() for s in chart_stages],
        "deal_values": [summary_dict[s]["value"] for s in chart_stages],
        "deal_counts": [summary_dict[s]["count"] for s in chart_stages],
        "activity_labels": [],
        "activity_datasets": []
    }

    # Activity Trends (Last 30 Days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    activity_trends = db.query(
        cast(Activity.date, Date),
        Activity.type,
        func.count(Activity.id)
    ).filter(Activity.date >= thirty_days_ago)\
     .group_by(cast(Activity.date, Date), Activity.type)\
     .order_by(cast(Activity.date, Date)).all()

    activity_map = {}
    activity_types = set()

    # Populate dates
    curr = thirty_days_ago.date()
    end = datetime.utcnow().date()
    dates = []
    while curr <= end:
        d_str = curr.strftime("%Y-%m-%d")
        dates.append(d_str)
        activity_map[d_str] = {}
        curr += timedelta(days=1)
    
    chart_data["activity_labels"] = dates

    for day, type_, count in activity_trends:
        if day:
            d_str = str(day)
            # Handle potential date string format differences if any, strictly matching YYYY-MM-DD
            if len(d_str) > 10: d_str = d_str[:10]
            if d_str in activity_map:
                activity_map[d_str][type_] = count
                activity_types.add(type_)

    # Colors for activity types
    type_colors = {
        "call": "#4f8ef7", "email": "#34c759", "meeting": "#f5a623", 
        "note": "#5bc0de", "task": "#7f8c9b"
    }

    for t in sorted(list(activity_types)):
        dataset = {
            "label": t.capitalize(),
            "data": [activity_map[d].get(t, 0) for d in dates],
            "borderColor": type_colors.get(t, "#2c3e50"),
            "backgroundColor": type_colors.get(t, "#2c3e50"),
            "fill": False,
            "tension": 0.1
        }
        chart_data["activity_datasets"].append(dataset)

    # Recent activities (last 10)
    recent_activities = db.query(Activity).order_by(desc(Activity.created_at)).limit(10).all()

    # Upcoming tasks (completed=False)
    upcoming_tasks = db.query(Activity).filter(Activity.completed == False).order_by(Activity.date).limit(10).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "total_contacts": total_contacts,
        "open_deals_count": open_deals_count,
        "total_pipeline_value": total_pipeline_value,
        "win_rate": win_rate,
        "pipeline_summary": summary_dict,
        "recent_activities": recent_activities,
        "upcoming_tasks": upcoming_tasks,
        "chart_data": chart_data
    })
