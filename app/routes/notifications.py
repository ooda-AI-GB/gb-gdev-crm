from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, cast, Date, or_
from app.database import get_db
from app.models import Notification, Activity, Deal, Contact
import app.routes as routes_module
from datetime import datetime, timedelta, date

router = APIRouter()

@router.get("/api/notifications")
async def get_notifications(
    request: Request,
    user=Depends(routes_module.get_current_user),
    db: Session = Depends(get_db)
):
    # --- Notification Generation Logic (Task Due) ---
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    # Find tasks due today or tomorrow that are not completed
    # Filter by user via Contact
    
    upcoming_tasks = db.query(Activity).join(Contact).filter(
        Contact.user_id == str(user.id),
        Activity.type == 'task',
        Activity.completed == False,
        cast(Activity.date, Date).in_([today, tomorrow])
    ).all()
    
    for task in upcoming_tasks:
        task_link = f"/contacts/{task.contact_id}"
        
        # Determine due message
        task_date_local = task.date.date() if isinstance(task.date, datetime) else task.date
        
        if task_date_local == today:
             msg = f"Task '{task.subject}' is due TODAY."
             title = "Task Due Today"
        else:
             msg = f"Task '{task.subject}' is due TOMORROW."
             title = "Task Due Tomorrow"
             
        # Check for existing notification (to avoid spam)
        # We check if we created a notification for this task recently
        existing = db.query(Notification).filter(
            Notification.user_id == str(user.id),
            Notification.type == "task_due",
            Notification.link == task_link,
            Notification.message == msg
        ).first()
        
        if not existing:
            notif = Notification(
                user_id=str(user.id),
                title=title,
                message=msg,
                type="task_due",
                link=task_link
            )
            db.add(notif)
            db.commit()

    # --- Fetch Notifications ---
    notifications = db.query(Notification).filter(
        Notification.user_id == str(user.id)
    ).order_by(desc(Notification.created_at)).limit(20).all()
    
    unread_count = db.query(Notification).filter(
        Notification.user_id == str(user.id),
        Notification.read == False
    ).count()

    return {
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "type": n.type,
                "read": n.read,
                "link": n.link,
                "created_at": n.created_at.isoformat() if n.created_at else None
            } for n in notifications
        ],
        "unread_count": unread_count
    }

@router.post("/api/notifications/{id}/read")
async def mark_notification_read(
    id: int,
    request: Request,
    user=Depends(routes_module.get_current_user),
    db: Session = Depends(get_db)
):
    notif = db.query(Notification).filter(
        Notification.id == id,
        Notification.user_id == str(user.id)
    ).first()
    
    if notif:
        notif.read = True
        db.commit()
        return {"status": "success"}
    
    raise HTTPException(status_code=404, detail="Notification not found")

@router.post("/api/notifications/mark-all-read")
async def mark_all_read(
    request: Request,
    user=Depends(routes_module.get_current_user),
    db: Session = Depends(get_db)
):
    db.query(Notification).filter(
        Notification.user_id == str(user.id),
        Notification.read == False
    ).update({Notification.read: True}, synchronize_session=False)
    db.commit()
    return {"status": "success"}
