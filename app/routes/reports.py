from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date, desc, or_, and_
from app.database import get_db
from app.models import Deal, Activity, Contact
import app.routes as routes_module
from datetime import datetime, timedelta, date
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def get_week_start(d):
    return d - timedelta(days=d.weekday())

@router.get("/reports", response_class=HTMLResponse)
async def reports_index(
    request: Request,
    start: str = Query(None),
    end: str = Query(None),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    # Date handling
    if end:
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
    else:
        end_date = datetime.utcnow().date()
        
    if start:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
    else:
        start_date = end_date - timedelta(days=90)

    # --- Pipeline Report ---
    pipeline_data = db.query(
        Deal.stage,
        func.count(Deal.id).label("count"),
        func.sum(Deal.value).label("value")
    ).group_by(Deal.stage).all()
    
    stages = ["qualified", "proposal", "negotiation", "closed_won", "closed_lost"]
    pipeline_stats = {s: {"count": 0, "value": 0, "avg_size": 0, "avg_time": 0} for s in stages}
    
    for stage, count, value in pipeline_data:
        if stage in pipeline_stats:
            pipeline_stats[stage]["count"] = count
            pipeline_stats[stage]["value"] = value or 0
            if count > 0:
                pipeline_stats[stage]["avg_size"] = (value or 0) / count

    # Avg time (approx: now - updated_at for current deals)
    now = datetime.utcnow()
    current_deals = db.query(Deal).filter(Deal.stage.notin_(["closed_won", "closed_lost"])).all()
    stage_durations = {s: [] for s in stages}
    for deal in current_deals:
        if deal.stage in stage_durations:
            # Handle timezone naive/aware
            updated = deal.updated_at
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=None) # ensure naive if mixed
                delta = now - updated
            else:
                delta = now.replace(tzinfo=updated.tzinfo) - updated
            stage_durations[deal.stage].append(delta.days)
            
    for s in stage_durations:
        if stage_durations[s]:
            pipeline_stats[s]["avg_time"] = sum(stage_durations[s]) / len(stage_durations[s])

    # Projected Revenue
    projected_revenue = 0
    open_deals = db.query(Deal).filter(Deal.stage.notin_(["closed_won", "closed_lost"])).all()
    for d in open_deals:
        projected_revenue += (d.value * (d.probability or 0) / 100.0)

    # --- Activity Report ---
    # Last 8 weeks logic (independent of date selector for chart, but table might use selector? Prompt says "last 8 weeks as table and chart")
    # Prompt: "Activity Report showing activity count by type per week for the last 8 weeks as a table and Chart.js bar chart"
    # So strictly last 8 weeks from NOW or from end_date? Let's assume from end_date.
    
    activity_end = end_date
    activity_start = activity_end - timedelta(weeks=8)
    
    activities = db.query(Activity).filter(
        cast(Activity.date, Date) >= activity_start, 
        cast(Activity.date, Date) <= activity_end
    ).all()
    
    # Bucket by week
    weeks = {}
    curr = get_week_start(activity_end)
    # Generate keys for last 8 weeks
    week_keys = []
    for i in range(8):
        # Go backwards 8 weeks? Or forwards from start?
        # Let's go backwards from end
        w_start = get_week_start(activity_end - timedelta(weeks=i))
        key = w_start.strftime("%Y-%m-%d")
        week_keys.append(key)
        weeks[key] = {t: 0 for t in ["call", "email", "meeting", "note", "task"]}
    
    week_keys.sort()
    
    for act in activities:
        d = act.date.date() if isinstance(act.date, datetime) else act.date
        w_start = get_week_start(d)
        key = w_start.strftime("%Y-%m-%d")
        if key in weeks:
            if act.type in weeks[key]:
                weeks[key][act.type] += 1

    activity_chart = {
        "labels": week_keys,
        "datasets": []
    }
    colors_map = {"call": "#4f8ef7", "email": "#34c759", "meeting": "#f5a623", "note": "#5bc0de", "task": "#7f8c9b"}
    
    for t in ["call", "email", "meeting", "note", "task"]:
        data = [weeks[k][t] for k in week_keys]
        activity_chart["datasets"].append({
            "label": t.capitalize(),
            "data": data,
            "backgroundColor": colors_map[t]
        })

    # Top 5 Contacts (within date range)
    top_contacts_res = db.query(
        Contact.name,
        func.count(Activity.id).label("cnt")
    ).join(Activity).filter(
        cast(Activity.date, Date) >= start_date,
        cast(Activity.date, Date) <= end_date
    ).group_by(Contact.id).order_by(desc("cnt")).limit(5).all()
    
    top_contacts = [{"name": r[0], "count": r[1]} for r in top_contacts_res]

    # --- Win/Loss Report ---
    # Counts and Values by month (within date range)
    win_loss_deals = db.query(Deal).filter(
        Deal.stage.in_(["closed_won", "closed_lost"]),
        cast(Deal.updated_at, Date) >= start_date,
        cast(Deal.updated_at, Date) <= end_date
    ).all()
    
    monthly_stats = {}
    # Generate months
    curr_m = start_date.replace(day=1)
    while curr_m <= end_date:
        key = curr_m.strftime("%Y-%m")
        monthly_stats[key] = {"won": 0, "lost": 0, "won_val": 0, "lost_val": 0}
        # next month
        if curr_m.month == 12:
            curr_m = curr_m.replace(year=curr_m.year + 1, month=1)
        else:
            curr_m = curr_m.replace(month=curr_m.month + 1)
            
    total_won_val = 0
    total_lost_val = 0
    won_count = 0
    lost_count = 0
    
    for d in win_loss_deals:
        ud = d.updated_at.date() if isinstance(d.updated_at, datetime) else d.updated_at
        key = ud.strftime("%Y-%m")
        if key in monthly_stats:
            if d.stage == "closed_won":
                monthly_stats[key]["won"] += 1
                monthly_stats[key]["won_val"] += d.value
                total_won_val += d.value
                won_count += 1
            else:
                monthly_stats[key]["lost"] += 1
                monthly_stats[key]["lost_val"] += d.value
                total_lost_val += d.value
                lost_count += 1

    win_loss_labels = sorted(monthly_stats.keys())
    
    win_rate_trend = []
    for m in win_loss_labels:
        w = monthly_stats[m]["won"]
        l = monthly_stats[m]["lost"]
        rate = (w / (w + l) * 100) if (w + l) > 0 else 0
        win_rate_trend.append(rate)

    avg_won = total_won_val / won_count if won_count else 0
    avg_lost = total_lost_val / lost_count if lost_count else 0

    return templates.TemplateResponse("reports/index.html", {
        "request": request,
        "user": user,
        "start_date": start_date,
        "end_date": end_date,
        "pipeline_stats": pipeline_stats,
        "projected_revenue": projected_revenue,
        "activity_chart": activity_chart,
        "activity_weeks": weeks,
        "week_keys": week_keys,
        "top_contacts": top_contacts,
        "win_loss_labels": win_loss_labels,
        "monthly_stats": monthly_stats,
        "win_rate_trend": win_rate_trend,
        "avg_won": avg_won,
        "avg_lost": avg_lost
    })

@router.get("/reports/{report_type}/pdf")
async def export_pdf(
    report_type: str,
    start: str = Query(None),
    end: str = Query(None),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    title = report_type.replace('_', ' ').title() + " Report"
    elements.append(Paragraph(title, styles['Title']))
    elements.append(Paragraph(f"Period: {start or 'N/A'} to {end or 'N/A'}", styles['Normal']))
    elements.append(Spacer(1, 12))

    if report_type == "pipeline":
        # Simplified query re-run for PDF
        data = [["Stage", "Count", "Total Value", "Avg Size", "Avg Days"]]
        
        deals = db.query(Deal).all() # Fetch all to calc stats
        stages = ["qualified", "proposal", "negotiation", "closed_won", "closed_lost"]
        stats = {s: {"count": 0, "value": 0, "avg_size": 0, "avg_time": 0} for s in stages}
        
        # Recalculate stats (copy logic from above ideally, but keeping it simple)
        now = datetime.utcnow()
        for d in deals:
            if d.stage in stats:
                stats[d.stage]["count"] += 1
                stats[d.stage]["value"] += d.value
                
                # Time in stage for open deals
                if d.stage not in ["closed_won", "closed_lost"]:
                     updated = d.updated_at
                     if updated.tzinfo is None: updated = updated.replace(tzinfo=None)
                     else: updated = updated.replace(tzinfo=None) # naive comparison
                     stats[d.stage]["avg_time"] += (datetime.utcnow() - updated).days

        for s in stages:
            c = stats[s]["count"]
            v = stats[s]["value"]
            avg_s = v/c if c else 0
            avg_t = stats[s]["avg_time"]/c if c else 0 # this is averaging total days by count, simplified
            
            data.append([
                s.replace('_',' ').title(),
                str(c),
                f"${v:,.2f}",
                f"${avg_s:,.2f}",
                f"{avg_t:.1f}"
            ])
            
        t = Table(data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        elements.append(t)

    elif report_type == "activity":
        # Just top 5 contacts for PDF as example
        elements.append(Paragraph("Top 5 Active Contacts", styles['Heading2']))
        data = [["Contact", "Activity Count"]]
        
        # Parse dates
        if end: e_date = datetime.strptime(end, "%Y-%m-%d").date()
        else: e_date = datetime.utcnow().date()
        if start: s_date = datetime.strptime(start, "%Y-%m-%d").date()
        else: s_date = e_date - timedelta(days=90)
            
        res = db.query(Contact.name, func.count(Activity.id)).join(Activity).filter(
            cast(Activity.date, Date) >= s_date,
            cast(Activity.date, Date) <= e_date
        ).group_by(Contact.id).order_by(desc(func.count(Activity.id))).limit(5).all()
        
        for r in res:
            data.append([r[0], str(r[1])])
            
        t = Table(data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        elements.append(t)
        
    elif report_type == "win_loss":
        # Win stats
        elements.append(Paragraph("Win/Loss Summary", styles['Heading2']))
        
        # Parse dates
        if end: e_date = datetime.strptime(end, "%Y-%m-%d").date()
        else: e_date = datetime.utcnow().date()
        if start: s_date = datetime.strptime(start, "%Y-%m-%d").date()
        else: s_date = e_date - timedelta(days=90)
        
        won = db.query(func.count(Deal.id), func.sum(Deal.value)).filter(
            Deal.stage == "closed_won",
            cast(Deal.updated_at, Date) >= s_date,
            cast(Deal.updated_at, Date) <= e_date
        ).first()
        
        lost = db.query(func.count(Deal.id), func.sum(Deal.value)).filter(
            Deal.stage == "closed_lost",
            cast(Deal.updated_at, Date) >= s_date,
            cast(Deal.updated_at, Date) <= e_date
        ).first()
        
        data = [
            ["Type", "Count", "Total Value"],
            ["Won", str(won[0] or 0), f"${(won[1] or 0):,.2f}"],
            ["Lost", str(lost[0] or 0), f"${(lost[1] or 0):,.2f}"]
        ]
        
        t = Table(data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        elements.append(t)

    doc.build(elements)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={report_type}.pdf"})
