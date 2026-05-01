from contextlib import asynccontextmanager
from datetime import date
import time

import os
from fastapi import Depends, FastAPI, Request, Response
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from sqlalchemy import and_
from sqlalchemy.orm import Session

from auth import get_current_user, require_role, user_or_ip_identifier
from logger import configure_logging, get_logger
from redis_client import redis_client

from db import get_db
from models import (
    AdminProfileResponse,
    Admins,
    ClassSectionResponse,
    ClassSections,
    GenericUserRoleResponse,
    Staff,
    StaffSubjects,
    StudentEnrollments,
    StudentInfoResponse,
    StudentProfileResponse,
    Students,
    StudentSummaryResponse,
    TeacherProfileResponse,
    User,
)
from routes import announcements, attendance, health_check, admin
from routes.auth import token

configure_logging()
_log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _log.info(
        "Starting SSMD API",
        extra={"environment": os.getenv("ENVIRONMENT", "development")},
    )
    await FastAPILimiter.init(redis_client, identifier=user_or_ip_identifier)
    _log.info("Rate-limiter connected")
    yield

    await redis_client.close()
    _log.info("SSMD API shut down")


app = FastAPI(
    title="SSMD",
    description="Main API for SSMD school management software.",
    lifespan=lifespan,
    dependencies=[Depends(RateLimiter(times=100, seconds=60))],
)

app.include_router(attendance.router)
app.include_router(token.router)
app.include_router(health_check.router)
app.include_router(announcements.router)
app.include_router(admin.router)


@app.middleware("http")
async def _log_requests(request: Request, call_next) -> Response:
    """Log every HTTP request with method, path, status code, and duration."""
    start = time.perf_counter()
    identity = await user_or_ip_identifier(request)
    response: Response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1_000

    level = _log.warning if response.status_code >= 400 else _log.info
    level(
        "%s %s → %d  (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client": identity,
        },
    )
    return response


@app.get(
    "/students/{student_id}",
    response_model=StudentInfoResponse,
    dependencies=[Depends(require_role(["teacher"]))],
    tags=["students"],
    summary="Get a student's enrollment details",
)
def get_student_details(student_id: int, db: Session = Depends(get_db)):
    _log.debug("Fetching student details", extra={"student_id": student_id})
    data = (
        db.query(Students)
        .join(StudentEnrollments)
        .filter(
            and_(
                Students.id == StudentEnrollments.student_id, Students.id == student_id
            )
        )
        .join(ClassSections)
        .filter(StudentEnrollments.class_section_id == ClassSections.id)
        .one()
    )

    return StudentInfoResponse(
        roll_no=data.student_enrollments[0].roll_no,
        name=data.name,
        father_name=data.father_name,
        mother_name=data.mother_name,
        admission_date=data.admission_date,
        class_name=data.student_enrollments[0].class_section.class_name,
        section=data.student_enrollments[0].class_section.section,
        academic_year=data.student_enrollments[0].class_section.academic_year,
    )


@app.get(
    "/class-sections",
    response_model=list[ClassSectionResponse],
    dependencies=[Depends(require_role(["teacher", "student"]))],
    tags=["class-sections"],
    summary="List class sections for the current academic year",
)
def list_class_sections(db: Session = Depends(get_db)):
    classes = (
        db.query(ClassSections)
        .filter(ClassSections.academic_year == date.today().year)
        .all()
    )

    return [
        ClassSectionResponse(
            id=class_section.id,
            class_name=class_section.class_name,
            section=class_section.section,
            academic_year=class_section.academic_year,
        )
        for class_section in classes
    ]


@app.get(
    "/class-sections/{class_section_id}/students",
    response_model=list[StudentSummaryResponse],
    dependencies=[Depends(require_role(["teacher"]))],
    tags=["class-sections"],
    summary="List students in a class section",
)
def list_students_in_class_section(
    class_section_id: int, db: Session = Depends(get_db)
):
    data = (
        db.query(StudentEnrollments)
        .join(Students)
        .filter(StudentEnrollments.class_section_id == class_section_id)
        .order_by(StudentEnrollments.roll_no)
        .all()
    )

    return [
        StudentSummaryResponse(
            id=d.student.id,
            roll_no=d.roll_no,
            name=d.student.name,
        )
        for d in data
    ]


@app.get(
    "/users/me",
    response_model=(
        StudentProfileResponse
        | TeacherProfileResponse
        | AdminProfileResponse
        | GenericUserRoleResponse
    ),
    tags=["users"],
    summary="Get the current user's profile",
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    current_role = current_user.role
    if current_role == "student":
        return get_student_data(db=db, user_id=current_user.id)
    elif current_role == "teacher":
        return get_teacher_data(db, user_id=current_user.id)
    elif current_role == "admin":
        return get_admin_data(db, user_id=current_user.id)
    else:
        return GenericUserRoleResponse(role=current_role)


def get_student_data(db: Session, user_id):
    data = (
        db.query(Students)
        .join(StudentEnrollments)
        .join(ClassSections)
        .filter(ClassSections.id == StudentEnrollments.class_section_id)
        .filter(Students.user_id == user_id)
        .limit(1)
        .one()
    )

    return StudentProfileResponse(
        id=data.id,
        name=data.name,
        reg_no=data.reg_no,
        father_name=data.father_name,
        mother_name=data.mother_name,
        admission_date=data.admission_date,
        class_name=data.student_enrollments[0].class_section.class_name,
        section=data.student_enrollments[0].class_section.section,
        academic_year=data.student_enrollments[0].class_section.academic_year,
    )


def get_teacher_data(db: Session, user_id):
    staff = db.query(Staff).where(Staff.user_id == user_id).one()

    subject_ids = [
        row.subject_id
        for row in db.query(StaffSubjects)
        .where(StaffSubjects.staff_id == staff.id)
        .all()
    ]

    return TeacherProfileResponse(
        id=staff.id,
        name=staff.name,
        position=staff.position,
        subjects=subject_ids,
    )


def get_admin_data(db: Session, user_id):
    admin = db.query(Admins).where(Admins.user_id == user_id).one()
    return AdminProfileResponse(id=admin.id, name=admin.name)
