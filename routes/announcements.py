from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from auth import get_current_user
from db import get_db
from models import AnnouncementCreate, User

router = APIRouter()


@router.get("/announcements/all")
def get_announcements(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    current_role = current_user.role
    query = text("""
        select anp.id, anp.subject, anp.details, use.username, anp.date 
        FROM announcement_posts anp JOIN announcement_roles anr
        ON (anr.announcement_post_id = anp.id) 
        AND (anr.for_role = :role) JOIN users use 
        ON (anp.issuer = use.id)
                 """)
    results = db.execute(query, {"role": current_role}).fetchall()
    return [dict(row._mapping) for row in results]


@router.get("/announcements/me")
def get_ones_announcements(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    current_role = current_user.role
    query = text("""
        select anp.id, anp.subject, anp.details, use.username, anp.date 
        FROM announcement_posts anp JOIN announcement_roles anr
        ON (anr.announcement_post_id = anp.id) 
        AND (anr.for_role = :role) JOIN users use 
        ON (anp.issuer = use.id)
        WHERE anp.issuer = :user_id
                 """)
    results = db.execute(
        query, {"role": current_role, "user_id": current_user.id}
    ).fetchall()
    return [dict(row._mapping) for row in results]


@router.delete("/announcement")
def delete_announcements(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query1 = text("""
    DELETE FROM announcement_roles ar WHERE ar.announcement_post_id = :id
    """)

    db.execute(query1, {"id": id})

    db.execute(
        text("""
    DELETE FROM announcement_posts ap WHERE ap.id = :id
    """),
        {"id": id},
    )

    db.commit()

    return {"done"}


@router.post("/announcements")
def post_announcements(
    data: AnnouncementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = db.execute(
        text("""
        INSERT INTO announcement_posts (subject, details, issuer, date)
        VALUES (:subject, :details, :issuer, :date)
        RETURNING id
    """),
        {
            "subject": data.subject,
            "details": data.details,
            "issuer": current_user.id,
            "date": date.today(),
        },
    )

    post_id = result.scalar()

    for role in data.roles:
        db.execute(
            text("""
            INSERT INTO announcement_roles (announcement_post_id, for_role)
            VALUES (:post_id, :role)
        """),
            {"post_id": post_id, "role": role},
        )

    db.commit()

    return {"id": post_id}
