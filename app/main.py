import os
from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from app.database import engine, Base, get_db, SessionLocal
import app.routes as routes_module
from app.routes import dashboard, contacts, pipeline, activities, intel, billing, notifications, automations, reports, api
from app.seed import seed_crm_data
from viv_auth import init_auth
from viv_pay import init_pay

app = FastAPI(title="CRM Pro")
templates = Jinja2Templates(directory="app/templates")

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    return templates.TemplateResponse("404.html", {"request": request})

# Health check (must be first)
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/health")
def api_health_check():
    return {"status": "ok"}

# Initialize Auth
User, require_auth = init_auth(app, engine, Base, get_db, app_name="CRM Pro")

# Initialize Pay
create_checkout, get_customer, require_subscription = init_pay(app, engine, Base, get_db, app_name="CRM Pro")

# Wrapper: chain auth -> subscription check so require_subscription gets user_id
# viv-auth uses encrypted session cookie (viv_session), not a user_id cookie,
# so require_subscription can't find user_id on its own.
async def require_active_subscription(request: Request, user=Depends(require_auth)):
    return await require_subscription(request, user_id=user.id)

# Inject dependencies into routes module
routes_module.User = User
routes_module.require_auth = require_auth
routes_module.require_subscription = require_subscription
routes_module.create_checkout = create_checkout
routes_module.get_customer = get_customer

# Auth bypass for dev/testing -- set DEV_AUTH_BYPASS=true to skip login
if os.environ.get("DEV_AUTH_BYPASS", "").lower() == "true":
    from types import SimpleNamespace
    print("[AUTH] DEV_AUTH_BYPASS=true -- all routes accessible without login")
    _fake_user = SimpleNamespace(id=1, email="dev@bypass.local")
    async def _bypass_auth(): return _fake_user
    async def _bypass_subscription(request: Request): return True
    app.dependency_overrides[routes_module.get_current_user] = _bypass_auth
    app.dependency_overrides[routes_module.get_active_subscription] = _bypass_subscription
else:
    app.dependency_overrides[routes_module.get_current_user] = require_auth
    app.dependency_overrides[routes_module.get_active_subscription] = require_active_subscription

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(dashboard.router)
app.include_router(contacts.router)
app.include_router(pipeline.router)
app.include_router(activities.router)
app.include_router(intel.router)
app.include_router(billing.router)
app.include_router(notifications.router)
app.include_router(automations.router)
app.include_router(reports.router)
app.include_router(api.router, prefix="/api/v1", tags=["api"])

# Startup event
@app.on_event("startup")
def startup_event():
    # Ensure all tables are created
    import app.models
    Base.metadata.create_all(bind=engine)
    
    # Seed data
    db = SessionLocal()
    try:
        seed_crm_data(db)
    finally:
        db.close()
