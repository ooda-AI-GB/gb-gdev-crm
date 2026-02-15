import os
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Note
from typing import Any
from app.routes import get_current_user, get_active_subscription

try:
    from google import genai
except ImportError:
    genai = None

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/ai/summary", response_class=HTMLResponse)
async def summary_page(request: Request, user: Any = Depends(get_current_user), sub: Any = Depends(get_active_subscription)):
    # sub is just verified, we don't necessarily need it, but it ensures subscription
    return templates.TemplateResponse("ai/summary.html", {"request": request, "user": user})

@router.post("/api/notes/summarize")
async def summarize_notes(request: Request, user: Any = Depends(get_current_user), sub: Any = Depends(get_active_subscription), db: Session = Depends(get_db)):
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return JSONResponse({"error": "AI not configured"}, status_code=503)
    
    if not genai:
        return JSONResponse({"error": "Google GenAI library not installed"}, status_code=500)

    notes = db.query(Note).filter(Note.user_id == user.id).all()
    if not notes:
        return JSONResponse({"error": "No notes to summarize"}, status_code=400)
    
    text_content = ""
    for note in notes:
        text_content += f"Title: {note.title}\nContent: {note.content}\n\n"
        
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=f"Summarize the following personal notes. Identify key themes, action items, and important ideas.\n\n{text_content}"
        )
        return JSONResponse({"summary": response.text})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
