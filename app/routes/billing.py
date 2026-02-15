from fastapi import APIRouter, Depends, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import app.routes
from app.routes import get_current_user
from typing import Any

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    # Public page
    # If user is logged in, we ideally show "Current Plan". 
    # But since we can't easily get optional user without viv-auth internals, we skip for now.
    return templates.TemplateResponse("billing/pricing.html", {"request": request, "user": None})

@router.post("/subscribe")
async def subscribe(request: Request, user: Any = Depends(get_current_user)):
    # Calls create_checkout(user.id, user.email, price_id="premium")
    if not app.routes.create_checkout:
        raise HTTPException(status_code=500, detail="Billing not configured")
        
    url = app.routes.create_checkout(user_id=user.id, email=user.email, price_id="premium")
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)

