from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query, Body, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from app.database import get_db
from app.models import Contact, Deal, Activity, Tag, ContactNote
import app.routes as routes_module
import os
import resend
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
import csv
import io
import json
import uuid

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/contacts", response_class=HTMLResponse)
async def list_contacts(
    request: Request,
    q: str = Query(None),
    status: str = Query(None),
    tag_id: List[int] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    message: str = Query(None),
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

    if tag_id:
        query = query.join(Contact.tags).filter(Tag.id.in_(tag_id)).distinct()
        
    # Validation for sort column to prevent injection or errors
    valid_sort_columns = ["name", "company", "status", "created_at"]
    if sort not in valid_sort_columns:
        sort = "created_at"

    if order == "asc":
        query = query.order_by(getattr(Contact, sort))
    else:
        query = query.order_by(desc(getattr(Contact, sort)))

    contacts = query.all()
    all_tags = db.query(Tag).all()

    return templates.TemplateResponse("contacts/list.html", {
        "request": request, 
        "contacts": contacts, 
        "user": user,
        "q": q,
        "status": status,
        "tag_id": tag_id,
        "all_tags": all_tags,
        "sort": sort,
        "order": order,
        "message": message
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
    
    all_tags = db.query(Tag).all()
    notes = db.query(ContactNote).filter(ContactNote.contact_id == id).order_by(desc(ContactNote.created_at)).all()

    return templates.TemplateResponse("contacts/detail.html", {
        "request": request, 
        "contact": contact, 
        "user": user,
        "deals": contact.deals,
        "activities": contact.activities,
        "contact_notes": notes,
        "all_tags": all_tags,
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


class BulkStatusRequest(BaseModel):
    ids: List[int]
    status: str

class BulkDeleteRequest(BaseModel):
    ids: List[int]

@router.post("/contacts/bulk-status")
async def bulk_status(
    request: Request,
    payload: BulkStatusRequest,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    valid_statuses = ["lead", "contacted", "proposal", "negotiation", "closed_won", "closed_lost"]
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    contacts = db.query(Contact).filter(Contact.id.in_(payload.ids)).all()
    count = 0
    for contact in contacts:
        contact.status = payload.status
        count += 1
    
    db.commit()
    return {"message": f"Updated {count} contacts"}

@router.post("/contacts/bulk-delete")
async def bulk_delete(
    request: Request,
    payload: BulkDeleteRequest,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    contacts = db.query(Contact).filter(Contact.id.in_(payload.ids)).all()
    count = 0
    for contact in contacts:
        db.delete(contact)
        count += 1
    
    db.commit()
    return {"message": f"Deleted {count} contacts"}

@router.get("/contacts/export")
async def export_contacts(
    request: Request,
    ids: str = Query(None),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    if ids:
        try:
            id_list = [int(id) for id in ids.split(',')]
            contacts = db.query(Contact).filter(Contact.id.in_(id_list)).all()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid IDs provided")
    else:
        contacts = db.query(Contact).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(["ID", "Name", "Email", "Phone", "Company", "Title", "Status", "Source", "Notes", "Assigned To", "Created At"])
    
    # Write data
    for contact in contacts:
        writer.writerow([
            contact.id,
            contact.name,
            contact.email,
            contact.phone,
            contact.company,
            contact.title,
            contact.status,
            contact.source,
            contact.notes,
            contact.assigned_to,
            contact.created_at
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=contacts_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"}
    )

@router.post("/contacts/import")
async def import_contacts_step1(
    request: Request,
    file: UploadFile = File(...),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription)
):
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
        # Save to temp file
        file_id = str(uuid.uuid4())
        # Use /tmp for temporary storage
        file_path = f"/tmp/import_{file_id}.csv"
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            f.write(text_content)
        
        # Parse first few rows for preview
        csv_reader = csv.reader(io.StringIO(text_content))
        header = next(csv_reader, None)
        if not header:
            raise HTTPException(status_code=400, detail="Empty CSV file")
        
        preview_rows = []
        for i in range(5):
            try:
                row = next(csv_reader)
                preview_rows.append(row)
            except StopIteration:
                break
                
        # Auto-detect columns
        column_mapping = {}
        for i, col in enumerate(header):
            col_lower = col.lower()
            if "name" in col_lower:
                column_mapping["name"] = i
            elif "email" in col_lower:
                column_mapping["email"] = i
            elif "company" in col_lower:
                column_mapping["company"] = i
            elif "phone" in col_lower:
                column_mapping["phone"] = i
            elif "status" in col_lower:
                column_mapping["status"] = i
                
        return templates.TemplateResponse("contacts/import_preview.html", {
            "request": request,
            "user": user,
            "header": header,
            "preview_rows": preview_rows,
            "column_mapping": column_mapping,
            "file_id": file_id
        })
        
    except UnicodeDecodeError:
         raise HTTPException(status_code=400, detail="Invalid CSV file encoding. Please use UTF-8.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing CSV: {str(e)}")

@router.post("/contacts/import/confirm")
async def import_contacts_confirm(
    request: Request,
    file_id: str = Form(...),
    col_name: int = Form(...),
    col_email: int = Form(...),
    col_company: int = Form(-1),
    col_phone: int = Form(-1),
    col_status: int = Form(-1),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    file_path = f"/tmp/import_{file_id}.csv"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="Import session expired. Please upload again.")
    
    added_count = 0
    skipped_count = 0
    
    try:
        with open(file_path, "r", newline="", encoding="utf-8") as f:
            csv_reader = csv.reader(f)
            header = next(csv_reader, None) # Skip header
            
            for row in csv_reader:
                # Safety check for index out of bounds
                if len(row) <= max(col_name, col_email):
                    continue
                    
                name = row[col_name].strip()
                email = row[col_email].strip()
                
                if not email or not name:
                    continue
                    
                # Check duplicate
                existing = db.query(Contact).filter(Contact.email == email).first()
                if existing:
                    skipped_count += 1
                    continue
                
                company = row[col_company].strip() if col_company >= 0 and len(row) > col_company else None
                phone = row[col_phone].strip() if col_phone >= 0 and len(row) > col_phone else None
                status_val = row[col_status].strip().lower().replace(" ", "_") if col_status >= 0 and len(row) > col_status else "lead"
                
                # Normalize status
                valid_statuses = ["lead", "contacted", "proposal", "negotiation", "closed_won", "closed_lost"]
                if status_val not in valid_statuses:
                    status_val = "lead"
                
                contact = Contact(
                    user_id=str(user.id),
                    name=name,
                    email=email,
                    company=company,
                    phone=phone,
                    status=status_val,
                    source="import"
                )
                db.add(contact)
                added_count += 1
            
            db.commit()
            
    except Exception as e:
        # cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
    
    # cleanup
    if os.path.exists(file_path):
        os.remove(file_path)
        
@router.post("/contacts/{id}/tags")
async def add_contact_tag(
    request: Request,
    id: int,
    tag_id: Optional[int] = Form(None),
    new_tag_name: Optional[str] = Form(None),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(Contact.id == id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    tag = None
    if tag_id:
        tag = db.query(Tag).filter(Tag.id == tag_id).first()
    elif new_tag_name:
        # Check if tag already exists
        new_tag_name = new_tag_name.strip()
        tag = db.query(Tag).filter(Tag.name.ilike(new_tag_name)).first()
        if not tag:
            # Create new tag with a random color
            import random
            colors = ["blue", "red", "green", "purple", "gold", "indigo", "pink", "yellow"]
            tag = Tag(name=new_tag_name, color=random.choice(colors))
            db.add(tag)
            db.commit()
            db.refresh(tag)
    
    if tag:
        if tag not in contact.tags:
            contact.tags.append(tag)
            db.commit()
    
    return RedirectResponse(url=f"/contacts/{id}", status_code=303)

@router.post("/contacts/{id}/tags/{tag_id}/delete")
async def remove_contact_tag(
    request: Request,
    id: int,
    tag_id: int,
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(Contact.id == id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if tag and tag in contact.tags:
        contact.tags.remove(tag)
        db.commit()
        
    return RedirectResponse(url=f"/contacts/{id}", status_code=303)

@router.post("/contacts/{id}/notes")
async def add_contact_note(
    request: Request,
    id: int,
    content: str = Form(...),
    user=Depends(routes_module.get_current_user),
    subscription=Depends(routes_module.get_active_subscription),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(Contact.id == id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    note = ContactNote(contact_id=contact.id, content=content)
    db.add(note)
    db.commit()
    
    return RedirectResponse(url=f"/contacts/{id}", status_code=303)
