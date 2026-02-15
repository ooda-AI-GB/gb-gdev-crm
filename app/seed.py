from sqlalchemy.orm import Session
from app.models import Note

def seed_notes(db: Session, user_id: int):
    notes_data = [
        {"title": "Welcome to AI Notes", "content": "This is your personal notes app with AI-powered features. You can create, edit, and delete notes. Try the AI Summary feature to get insights from all your notes at once.\n\nFree tier: Create, edit, and delete unlimited notes.\nPremium tier: AI Summarization, AI Chat, and more."},
        {"title": "Meeting Notes - Q2 Planning", "content": "Discussed Q2 roadmap with the team. Key decisions:\n- Launch new dashboard by March\n- Hire two more engineers\n- Migrate to new cloud provider\n- Set up automated testing pipeline"},
        {"title": "Ideas", "content": "1. Build a habit tracker app\n2. Learn Rust for systems programming\n3. Write a blog post about AI summarization\n4. Create a weekly review template\n5. Set up a personal knowledge base"}
    ]
    
    for data in notes_data:
        note = Note(user_id=user_id, **data)
        db.add(note)
    
    db.commit()
