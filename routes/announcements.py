from datetime import date
from operator import and_
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from auth import get_current_user, require_role
from db import get_db
from models import (
    AnnouncementCreate,
    AnnouncementCreateResponse,
    AnnouncementPosts,
    AnnouncementResponse,
    AnnouncementRoles,
    DeleteResponse,
    User,
    UserRole,
    Users,
)

router = APIRouter(tags=["announcements"])
ALLOWED_ANNOUNCEMENT_ROLES = {UserRole.TEACHER, UserRole.STUDENT}


@router.get(
    "/announcements",
    response_model=list[AnnouncementResponse],
    summary="List announcements for the current user",
)
@router.get(
    "/announcements/all",
    include_in_schema=False,
    response_model=list[AnnouncementResponse],
)
def list_announcements(
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
        AnnouncementResponse(
            id=d.id,
            subject=d.subject,
            details=d.details,
            username=d.user.username,
            date=d.date,
        )
        for d in data
    ]


@router.get(
    "/announcements/mine",
    response_model=list[AnnouncementResponse],
    summary="List announcements created by the current user",
)
@router.get(
    "/announcements/me",
    include_in_schema=False,
    response_model=list[AnnouncementResponse],
)
def list_my_announcements(
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
        AnnouncementResponse(
            id=d.id,
            subject=d.subject,
            details=d.details,
            username=d.user.username,
            date=d.date,
        )
        for d in data
    ]


@router.delete(
    "/announcements/{announcement_id}",
    response_model=DeleteResponse,
    dependencies=[Depends(require_role(["teacher"]))],
    summary="Delete an announcement created by the current user",
)
def delete_announcement(
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = (
        db.query(AnnouncementPosts)
        .filter(AnnouncementPosts.id == announcement_id)
        .first()
    )
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
            AnnouncementRoles.announcement_post_id == announcement_id
        ).delete()
        db.delete(post)

        db.commit()
        return DeleteResponse(done=True)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not delete announcement",
        )


@router.post(
    "/announcements",
    response_model=AnnouncementCreateResponse,
    dependencies=[Depends(require_role(["teacher"]))],
    summary="Create an announcement",
)
def create_announcement(
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

        for role in sorted(set(data.roles), key=str):
            role_entry = AnnouncementRoles(announcement_post_id=post.id, for_role=role)
            db.add(role_entry)
        db.commit()

        return AnnouncementCreateResponse(id=post.id)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create announcement",
        )
