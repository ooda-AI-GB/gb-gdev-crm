from fastapi import APIRouter, Depends, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import app.routes as routes_module
from app.routes import get_current_user
from typing import Any

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    return templates.TemplateResponse("billing/pricing.html", {"request": request, "user": None})

@router.post("/subscribe")
async def subscribe(request: Request, user: Any = Depends(get_current_user)):
    if not routes_module.create_checkout:
        raise HTTPException(status_code=500, detail="Billing not configured")

    try:
        url = routes_module.create_checkout(user_id=user.id, email=user.email, price_id="premium")
        return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Checkout failed: {str(e)[:200]}")
