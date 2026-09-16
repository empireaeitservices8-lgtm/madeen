"""
Safety Knowledge Test Routes
"""
import random
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from auth import get_current_user, ensure_site_access, scoped_site_id
from db import get_db, Question, TestAttempt, Worker, User

router = APIRouter()

class AnswerItem(BaseModel):
    question_id: int
    answer: str  # "A", "B", "C", "D"

class SubmitTestRequest(BaseModel):
    worker_id: int
    site_id: int
    answers: List[AnswerItem]

@router.get("/api/test/start/{worker_id}")
def start_test(worker_id: int, category: str = "general", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch 50 random questions for a worker."""
    worker = db.get(Worker, worker_id)
    if not worker:
        raise HTTPException(404, "Worker not found")
    ensure_site_access(user, worker.site_id)
    
    # Get total count of questions
    # Note: For SQLite, order_by(func.random()).limit(50) is fine for 1000 rows.
    from sqlalchemy.sql.expression import func
    questions = db.scalars(select(Question).where(Question.category == category).order_by(func.random()).limit(50)).all()
    
    if len(questions) < 50:
        # Fallback if fewer than 50 questions exist
        if not questions:
            raise HTTPException(500, f"No questions found in database for category: {category}")
    
    # Do not send correct_answer to the frontend!
    return [
        {
            "id": q.id,
            "text": q.text,
            "options": {
                "A": q.option_a,
                "B": q.option_b,
                "C": q.option_c,
                "D": q.option_d
            }
        }
        for q in questions
    ]


@router.post("/api/test/submit")
def submit_test(req: SubmitTestRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Calculate score and save the attempt."""
    ensure_site_access(user, req.site_id)
    worker = db.get(Worker, req.worker_id)
    if not worker or worker.site_id != req.site_id:
        raise HTTPException(400, "Invalid worker or site")

    if not req.answers:
        raise HTTPException(400, "No answers provided")

    # Fetch the actual questions to grade
    q_ids = [a.question_id for a in req.answers]
    questions = {q.id: q for q in db.scalars(select(Question).where(Question.id.in_(q_ids))).all()}
    
    score = 0
    details = []
    
    for ans in req.answers:
        q = questions.get(ans.question_id)
        if not q:
            continue
        is_correct = (ans.answer.upper() == q.correct_answer.upper())
        if is_correct:
            score += 1
            
        details.append({
            "question_id": q.id,
            "question_text": q.text,
            "chosen_answer": ans.answer,
            "correct_answer": q.correct_answer,
            "is_correct": is_correct
        })
        
    total = len(req.answers)
    # Passed if score >= 33% (17/50)
    # The requirement is 33% correct. So score / total >= 0.33
    passed = (score / total) >= 0.33 if total > 0 else False
    
    attempt = TestAttempt(
        worker_id=req.worker_id,
        site_id=req.site_id,
        user_id=user.id,
        score=score,
        total=total,
        passed=passed,
        details={"results": details}
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    
    return {
        "id": attempt.id,
        "score": score,
        "total": total,
        "passed": passed
    }

@router.get("/api/test/history")
def test_history(user: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = 50, offset: int = 0):
    scope = scoped_site_id(user)
    q = select(TestAttempt)
    if scope is not None:
        q = q.where(TestAttempt.site_id == scope)
    
    q = q.options(selectinload(TestAttempt.worker), selectinload(TestAttempt.user)).order_by(TestAttempt.created_at.desc()).limit(limit).offset(offset)
    rows = db.scalars(q).all()
    
    return {
        "items": [
            {
                "id": a.id,
                "score": a.score,
                "total": a.total,
                "passed": a.passed,
                "created_at": a.created_at.isoformat(),
                "worker": {"id": a.worker.id, "name": a.worker.full_name},
                "user": {"id": a.user.id, "name": a.user.username}
            }
            for a in rows
        ]
    }
