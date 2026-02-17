from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from app.database import get_db
from app.models import Contact, Deal, Activity
import app.routes as routes_module
import os
import resend
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/contacts", response_class=HTMLResponse)
async def list_contacts(
    request: Request,
    q: str = Query(None),
    status: str = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    query = db.query(Contact)

    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                Contact.name.ilike(search),
                Contact.email.ilike(search),
                Contact.company.ilike(search)
            )
        )
    
    if status:
        query = query.filter(Contact.status == status)
        
    # Validation for sort column to prevent injection or errors
    valid_sort_columns = ["name", "company", "status", "created_at"]
    if sort not in valid_sort_columns:
        sort = "created_at"

    if order == "asc":
        query = query.order_by(getattr(Contact, sort))
    else:
        query = query.order_by(desc(getattr(Contact, sort)))

    contacts = query.all()
    return templates.TemplateResponse("contacts/list.html", {
        "request": request, 
        "contacts": contacts, 
        "user": user,
        "q": q,
        "status": status,
        "sort": sort,
        "order": order
    })

@router.get("/contacts/new", response_class=HTMLResponse)
async def new_contact(
    request: Request,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription)
):
    return templates.TemplateResponse("contacts/form.html", {"request": request, "user": user, "contact": None})

@router.post("/contacts/new")
async def create_contact(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    company: str = Form(None),
    title: str = Form(None),
    status: str = Form(...),
    source: str = Form(None),
    notes: str = Form(None),
    assigned_to: str = Form(None),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    contact = Contact(
        user_id=str(user.id),
        name=name,
        email=email,
        phone=phone,
        company=company,
        title=title,
        status=status,
        source=source,
        notes=notes,
        assigned_to=assigned_to
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return RedirectResponse(url=f"/contacts/{contact.id}", status_code=303)

@router.get("/contacts/{id}", response_class=HTMLResponse)
async def view_contact(
    request: Request,
    id: int,
    message: str = Query(None),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(Contact.id == id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return templates.TemplateResponse("contacts/detail.html", {
        "request": request, 
        "contact": contact, 
        "user": user,
        "deals": contact.deals,
        "activities": contact.activities,
        "message": message
    })

@router.get("/contacts/{id}/edit", response_class=HTMLResponse)
async def edit_contact(
    request: Request,
    id: int,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(Contact.id == id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return templates.TemplateResponse("contacts/form.html", {"request": request, "user": user, "contact": contact})

@router.post("/contacts/{id}/edit")
async def update_contact(
    request: Request,
    id: int,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    company: str = Form(None),
    title: str = Form(None),
    status: str = Form(...),
    source: str = Form(None),
    notes: str = Form(None),
    assigned_to: str = Form(None),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(Contact.id == id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    contact.name = name
    contact.email = email
    contact.phone = phone
    contact.company = company
    contact.title = title
    contact.status = status
    contact.source = source
    contact.notes = notes
    contact.assigned_to = assigned_to
    
    db.commit()
    return RedirectResponse(url=f"/contacts/{id}", status_code=303)

@router.post("/contacts/{id}/delete")
async def delete_contact(
    request: Request,
    id: int,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(Contact.id == id).first()
    if contact:
        db.delete(contact)
        db.commit()
    return RedirectResponse(url="/contacts", status_code=303)

@router.post("/contacts/{id}/email")
async def send_email_contact(
    request: Request,
    id: int,
    subject: str = Form(...),
    body: str = Form(...),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(Contact.id == id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Create activity first
    activity = Activity(
        contact_id=contact.id,
        type="email",
        subject=subject,
        description=body,
        date=datetime.now(),
        completed=True
    )
    db.add(activity)
    db.commit()

    # Send email
    resend_api_key = os.environ.get("RESEND_API_KEY")
    if resend_api_key:
        try:
            resend.api_key = resend_api_key
            resend.Emails.send({
                "from": os.environ.get("FROM_EMAIL", "noreply@send.gigabox.ai"),
                "to": contact.email,
                "subject": subject,
                "html": f"<p>{body}</p>"
            })
        except Exception as e:
            print(f"[EMAIL-ERROR] Failed to send email: {e}")
    else:
        print(f"[EMAIL-DEV] To: {contact.email}, Subject: {subject}, Body: {body}")

    return RedirectResponse(url=f"/contacts/{id}?message=Email+sent+successfully", status_code=303)
