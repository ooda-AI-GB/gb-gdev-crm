from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app.database import engine, Base, get_db
import app.routes
from app.routes import notes, ai, billing
# Start imports for viv-auth and viv-pay
from viv_auth import init_auth
from viv_pay import init_pay

app = FastAPI()

# Health check (must be first)
@app.get("/health")
def health_check():
    return {"status": "ok"}

# Root redirect
@app.get("/")
def root():
    return RedirectResponse(url="/notes", status_code=303)

# Initialize Auth
User, require_auth = init_auth(app, engine, Base, get_db, app_name="AI Notes")

# Initialize Pay
create_checkout, get_customer, require_subscription = init_pay(app, engine, Base, get_db, app_name="AI Notes")

# Inject dependencies into routes module
app.routes.User = User
app.routes.require_auth = require_auth
app.routes.require_subscription = require_subscription
app.routes.create_checkout = create_checkout
app.routes.get_customer = get_customer

# Override dependency getters
app.dependency_overrides[app.routes.get_current_user] = require_auth
app.dependency_overrides[app.routes.get_active_subscription] = require_subscription

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(notes.router)
app.include_router(ai.router)
app.include_router(billing.router)

# Startup event
@app.on_event("startup")
def startup_event():
    # Ensure all tables are created
    # This includes User (from viv-auth), Billing tables (from viv-pay), and Note (from app.models)
    # We must import app.models so Note is registered in Base
    import app.models
    Base.metadata.create_all(bind=engine)
