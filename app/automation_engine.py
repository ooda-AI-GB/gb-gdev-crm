from sqlalchemy.orm import Session
from app.models import AutomationRule, Notification, Activity
from datetime import datetime, timedelta

def evaluate_rules(db: Session, trigger_type: str, entity, user):
    """
    Evaluate and execute automation rules based on a trigger and context entity.
    entity: The SQLAlchemy model instance (Contact, Deal, etc.)
    """
    rules = db.query(AutomationRule).filter(
        AutomationRule.trigger_type == trigger_type,
        AutomationRule.enabled == True
    ).all()

    for rule in rules:
        if check_condition(rule.condition, entity):
            execute_action(db, rule.action_type, rule.action_config, entity, user)

def check_condition(condition: dict, entity) -> bool:
    for key, value in condition.items():
        # Handle probability_gte special case
        if key == "probability_gte":
             prob = getattr(entity, "probability", 0)
             if prob < value:
                 return False
        # Handle normal fields
        elif hasattr(entity, key):
             attr_val = getattr(entity, key)
             # Simple equality check
             if attr_val != value:
                 return False
    return True

def execute_action(db: Session, action_type: str, config: dict, entity, user):
    if action_type == "create_notification":
        message = config.get("message", "Automation Alert")
        # Simple template replacement could go here if needed
        # e.g. message = message.replace("{{title}}", entity.title)
        
        notif = Notification(
            user_id=str(user.id),
            title="Automation Rule",
            message=message,
            type="system",
            read=False
        )
        db.add(notif)
        db.commit()

    elif action_type == "create_activity":
        # Determine contact_id
        contact_id = None
        if hasattr(entity, "contact_id") and entity.contact_id:
            contact_id = entity.contact_id
        elif hasattr(entity, "__tablename__") and entity.__tablename__ == "contacts":
            contact_id = entity.id
            
        if not contact_id:
            return

        due_days = int(config.get("due_in_days", 0))
        due_date = datetime.now() + timedelta(days=due_days)
        
        deal_id = getattr(entity, "deal_id", None)
        if hasattr(entity, "__tablename__") and entity.__tablename__ == "deals":
            deal_id = entity.id

        activity = Activity(
            contact_id=contact_id,
            deal_id=deal_id,
            type=config.get("type", "task"),
            subject=config.get("subject", "Automated Task"),
            description=config.get("description", "Created by automation rule"),
            date=due_date,
            completed=False
        )
        db.add(activity)
        db.commit()
