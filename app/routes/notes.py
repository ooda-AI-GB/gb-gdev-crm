from fastapi import APIRouter, Depends, HTTPException, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models import Note
from app.seed import seed_notes
from app.routes import get_current_user
# We cannot type hint User directly because it's not defined at module level
# So we use Any or object
from typing import Any

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/notes", response_class=HTMLResponse)
async def list_notes(request: Request, db: Session = Depends(get_db), user: Any = Depends(get_current_user)):
    # Seed data check
    count = db.query(Note).filter(Note.user_id == user.id).count()
    if count == 0:
        seed_notes(db, user.id)
        # Re-query
    
    notes = db.query(Note).filter(Note.user_id == user.id).order_by(desc(Note.updated_at)).all()
    return templates.TemplateResponse("notes/list.html", {"request": request, "user": user, "notes": notes})

@router.get("/notes/new", response_class=HTMLResponse)
async def new_note_form(request: Request, user: Any = Depends(get_current_user)):
    return templates.TemplateResponse("notes/form.html", {"request": request, "user": user})

@router.post("/notes/new")
async def create_note(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user)
):
    new_note = Note(user_id=user.id, title=title, content=content)
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    return RedirectResponse(url=f"/notes/{new_note.id}", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/notes/{id}", response_class=HTMLResponse)
async def note_detail(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user)
):
    note = db.query(Note).filter(Note.id == id, Note.user_id == user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return templates.TemplateResponse("notes/detail.html", {"request": request, "user": user, "note": note})

@router.get("/notes/{id}/edit", response_class=HTMLResponse)
async def edit_note_form(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user)
):
    note = db.query(Note).filter(Note.id == id, Note.user_id == user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return templates.TemplateResponse("notes/form.html", {"request": request, "user": user, "note": note})

@router.post("/notes/{id}/edit")
async def update_note(
    request: Request,
    id: int,
    title: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user)
):
    note = db.query(Note).filter(Note.id == id, Note.user_id == user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    note.title = title
    note.content = content
    db.commit()
    return RedirectResponse(url=f"/notes/{id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/notes/{id}/delete")
async def delete_note(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user)
):
    note = db.query(Note).filter(Note.id == id, Note.user_id == user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    db.delete(note)
    db.commit()
    return RedirectResponse(url="/notes", status_code=status.HTTP_303_SEE_OTHER)
