from sqlalchemy.orm import Session
from app.models import Contact, Deal, Activity, CompanyIntel, Tag
from datetime import datetime, date

def seed_crm_data(db: Session):
    # Seed Tags
    tags_data = [
        {"name": "VIP", "color": "gold"},
        {"name": "Follow-up", "color": "blue"},
        {"name": "At Risk", "color": "red"},
        {"name": "New Lead", "color": "green"},
        {"name": "Enterprise", "color": "purple"}
    ]

    for t_data in tags_data:
        existing = db.query(Tag).filter(Tag.name == t_data["name"]).first()
        if not existing:
            db.add(Tag(**t_data))
    
    db.commit()

    # Check if data exists
    if db.query(Contact).count() > 0:
        return

    contacts_data = [
        {"name": "Alice Johnson", "email": "alice@techcorp.com", "phone": "+1-555-0101", "company": "TechCorp", "title": "VP Engineering", "status": "lead", "source": "linkedin", "assigned_to": "Sales Team", "user_id": "system"},
        {"name": "Bob Smith", "email": "bob@startups.inc", "phone": "+1-555-0102", "company": "Startups Inc", "title": "CEO", "status": "contacted", "source": "referral", "assigned_to": "Sales Team", "user_id": "system"},
        {"name": "Charlie Brown", "email": "charlie@enterprise.global", "phone": "+1-555-0103", "company": "Enterprise Global", "title": "CTO", "status": "proposal", "source": "website", "assigned_to": "Sales Team", "user_id": "system"},
        {"name": "Diana Prince", "email": "diana@amazonia.net", "phone": "+1-555-0104", "company": "Amazonia", "title": "Head of Procurement", "status": "negotiation", "source": "cold_call", "assigned_to": "Sales Team", "user_id": "system"},
        {"name": "Evan Wright", "email": "evan@logistics.co", "phone": "+1-555-0105", "company": "Logistics Co", "title": "Operations Director", "status": "lead", "source": "website", "assigned_to": "Sales Team", "user_id": "system"},
        {"name": "Fiona Green", "email": "fiona@ecofriendly.org", "phone": "+1-555-0106", "company": "EcoFriendly", "title": "Sustainability Lead", "status": "contacted", "source": "referral", "assigned_to": "Sales Team", "user_id": "system"},
        {"name": "George King", "email": "george@royal.ltd", "phone": "+1-555-0107", "company": "Royal Ltd", "title": "Managing Director", "status": "proposal", "source": "linkedin", "assigned_to": "Sales Team", "user_id": "system"},
        {"name": "Hannah White", "email": "hannah@medical.care", "phone": "+1-555-0108", "company": "Medical Care", "title": "Administrator", "status": "closed_won", "source": "referral", "assigned_to": "Sales Team", "user_id": "system"},
        {"name": "Ian Black", "email": "ian@construction.works", "phone": "+1-555-0109", "company": "Construction Works", "title": "Project Manager", "status": "lead", "source": "cold_call", "assigned_to": "Sales Team", "user_id": "system"},
        {"name": "Jane Doe", "email": "jane@unknown.net", "phone": "+1-555-0110", "company": "Unknown Net", "title": "Founder", "status": "closed_lost", "source": "website", "assigned_to": "Sales Team", "user_id": "system"}
    ]
    
    # Create contacts
    contacts = []
    for data in contacts_data:
        contact = Contact(**data)
        db.add(contact)
        contacts.append(contact)
    db.commit()
    
    # Refresh to get IDs
    for c in contacts:
        db.refresh(c)
        
    # Map by index (0-based) to IDs
    # contacts[0] is Alice (id usually 1 but depends)
    # The spec uses 1-based IDs in deals/activities, assuming sequential insert.
    # To be safe, I should look up by name or index.
    # Let's assume sequential insert order matches the list.
    
    c_map = {i+1: contacts[i].id for i in range(len(contacts))}

    deals_data = [
        {"contact_id": 1, "title": "TechCorp Platform License", "value": 45000.00, "stage": "qualified", "probability": 30, "expected_close": "2026-04-15"},
        {"contact_id": 2, "title": "Startups Inc Annual Plan", "value": 12000.00, "stage": "proposal", "probability": 60, "expected_close": "2026-03-20"},
        {"contact_id": 3, "title": "Enterprise Global Migration", "value": 150000.00, "stage": "negotiation", "probability": 75, "expected_close": "2026-03-01"},
        {"contact_id": 4, "title": "Amazonia Procurement Suite", "value": 85000.00, "stage": "negotiation", "probability": 80, "expected_close": "2026-02-28"},
        {"contact_id": 7, "title": "Royal Ltd Consulting", "value": 35000.00, "stage": "proposal", "probability": 50, "expected_close": "2026-04-01"},
        {"contact_id": 8, "title": "Medical Care Integration", "value": 28000.00, "stage": "closed_won", "probability": 100, "expected_close": "2026-01-15"},
        {"contact_id": 5, "title": "Logistics Fleet Tracker", "value": 52000.00, "stage": "qualified", "probability": 25, "expected_close": "2026-05-01"},
        {"contact_id": 10, "title": "Unknown Net Pilot", "value": 8000.00, "stage": "closed_lost", "probability": 0, "expected_close": "2026-01-10"}
    ]

    deals = []
    for data in deals_data:
        # Resolve contact_id
        cid = c_map.get(data["contact_id"])
        if cid:
            data["contact_id"] = cid
            data["expected_close"] = date.fromisoformat(data["expected_close"])
            deal = Deal(**data)
            db.add(deal)
            deals.append(deal)
    db.commit()
    
    # Refresh deals
    for d in deals:
        db.refresh(d)
        
    # We don't have explicit deal IDs in spec, but activities reference deal_id.
    # Activities use deal_id 1..N based on the order above.
    d_map = {i+1: deals[i].id for i in range(len(deals))}

    activities_data = [
        {"contact_id": 1, "deal_id": 1, "type": "call", "subject": "Discovery call", "description": "Discussed platform needs. Evaluating 3 vendors.", "date": "2026-02-10 10:00:00", "completed": True},
        {"contact_id": 2, "deal_id": 2, "type": "email", "subject": "Proposal sent", "description": "Sent annual plan proposal with pricing.", "date": "2026-02-11 14:30:00", "completed": True},
        {"contact_id": 3, "deal_id": 3, "type": "meeting", "subject": "Technical review", "description": "CTO reviewed architecture. Positive on scalability.", "date": "2026-02-12 09:00:00", "completed": True},
        {"contact_id": 4, "deal_id": 4, "type": "call", "subject": "Procurement check-in", "description": "Budget approved. Waiting on legal.", "date": "2026-02-13 11:00:00", "completed": True},
        {"contact_id": 1, "type": "task", "subject": "Follow up with Alice", "description": "Send case studies.", "date": "2026-02-15 09:00:00", "completed": False},
        {"contact_id": 5, "deal_id": 7, "type": "email", "subject": "Introduction email", "description": "Initial outreach about fleet tracking.", "date": "2026-02-08 16:00:00", "completed": True},
        {"contact_id": 6, "type": "note", "subject": "Research note", "description": "EcoFriendly got Series B. Good time to re-engage.", "date": "2026-02-13 08:00:00", "completed": True},
        {"contact_id": 8, "deal_id": 6, "type": "meeting", "subject": "Onboarding kickoff", "description": "Kicked off implementation. 6-week timeline.", "date": "2026-01-20 10:00:00", "completed": True}
    ]

    for data in activities_data:
        cid = c_map.get(data["contact_id"])
        did = d_map.get(data.get("deal_id")) if "deal_id" in data else None
        
        if cid:
            data["contact_id"] = cid
            if did:
                data["deal_id"] = did
            elif "deal_id" in data:
                del data["deal_id"] # Remove if not found/mapped
                
            data["date"] = datetime.strptime(data["date"], "%Y-%m-%d %H:%M:%S")
            activity = Activity(**data)
            db.add(activity)
            
    # Company Intel
    intel_data = [
        {"company_name": "TechCorp", "analysis_type": "swot", "content": "STRENGTHS: Strong engineering team, growing market share. WEAKNESSES: High burn rate. OPPORTUNITIES: Expanding to Europe. THREATS: Competitor X offering 20% discount.", "model_used": "seed_data", "requested_by": "system"},
        {"company_name": "Enterprise Global", "analysis_type": "competitor", "content": "Evaluating three vendors including us. Primary concern: migration risk. Our advantage: better post-migration support and 99.9% uptime SLA.", "model_used": "seed_data", "requested_by": "system"}
    ]
    
    for data in intel_data:
        intel = CompanyIntel(**data)
        db.add(intel)
        
    db.commit()
