# Placeholders for dependency injection from main.py
# This avoids circular imports and allows flexible configuration

User = None
require_auth = None
require_subscription = None
create_checkout = None
get_customer = None

# We can define a getter for user dependency to avoid "NoneType is not callable" during import time
# if we use Depends(get_current_user)
def get_current_user():
    pass

def get_active_subscription():
    pass
