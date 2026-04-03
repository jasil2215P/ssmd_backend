from datetime import date
from operator import and_
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from auth import get_current_user, require_role
from db import get_db
from models import AnnouncementCreate, AnnouncementPosts, AnnouncementRoles, User, Users

router = APIRouter()
ALLOWED_ANNOUNCEMENT_ROLES = {"teacher", "student"}


@router.get("/announcements/all")
def get_announcements(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    data = (
        db.query(AnnouncementPosts)
        .join(AnnouncementRoles)
        .filter(
            and_(
                AnnouncementRoles.announcement_post_id == AnnouncementPosts.id,
                AnnouncementRoles.for_role == current_user.role,
            )
        )
        .join(Users)
        .filter(AnnouncementPosts.issuer == Users.id)
        .all()
    )

    return [
        {
            "id": d.id,
            "subject": d.subject,
            "details": d.details,
            "username": d.user.username,
            "date": d.date,
        }
        for d in data
    ]


@router.get("/announcements/me")
def get_ones_announcements(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    data = (
        db.query(AnnouncementPosts)
        .join(AnnouncementRoles)
        .filter(
            AnnouncementRoles.announcement_post_id == AnnouncementPosts.id,
        )
        .join(Users)
        .filter(AnnouncementPosts.issuer == Users.id)
        .where(AnnouncementPosts.issuer == current_user.id)
    ).all()
    return [
        {
            "id": d.id,
            "subject": d.subject,
            "details": d.details,
            "username": d.user.username,
            "date": d.date,
        }
        for d in data
    ]


@router.delete("/announcement", dependencies=[Depends(require_role(["teacher"]))])
def delete_announcements(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(AnnouncementPosts).filter(AnnouncementPosts.id == id).first()
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found",
        )
    if post.issuer != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to delete this announcement",
        )

    try:
        db.query(AnnouncementRoles).filter(
            AnnouncementRoles.announcement_post_id == id
        ).delete()
        db.delete(post)

        db.commit()
        return {"done": True}
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not delete announcement",
        )


@router.post("/announcements", dependencies=[Depends(require_role(["teacher"]))])
def post_announcements(
    data: AnnouncementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invalid_roles = sorted(set(data.roles) - ALLOWED_ANNOUNCEMENT_ROLES)
    if not data.roles or invalid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Announcement roles must be a non-empty subset of allowed roles",
        )

    try:
        post = AnnouncementPosts(
            subject=data.subject,
            details=data.details,
            issuer=current_user.id,
            date=date.today(),
        )

        db.add(post)
        db.commit()

        db.refresh(post)

        for role in sorted(set(data.roles)):
            role_entry = AnnouncementRoles(announcement_post_id=post.id, for_role=role)
            db.add(role_entry)
        db.commit()

        return {"id": post.id}
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create announcement",
        )
