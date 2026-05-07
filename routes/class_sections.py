from datetime import date

from fastapi import Depends
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from auth import require_role
from db import get_db
from models import (
    ClassSectionResponse,
    ClassSections,
    StudentEnrollments,
    Students,
    StudentSummaryResponse,
)

router = APIRouter(prefix="/class-sections")


@router.get(
    "",
    response_model=list[ClassSectionResponse],
    dependencies=[Depends(require_role(["teacher", "student", "admin"]))],
    tags=["class-sections"],
    summary="List class sections for the current academic year",
)
def list_class_sections(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    classes = (
        db.query(ClassSections)
        .filter(ClassSections.academic_year == date.today().year)
        .offset(skip)
        .limit(limit)
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


@router.get(
    "/{class_section_id}/students",
    response_model=list[StudentSummaryResponse],
    dependencies=[Depends(require_role(["teacher", "admin"]))],
    tags=["class-sections"],
    summary="List students in a class section",
)
def list_students_in_class_section(
    class_section_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    data = (
        db.query(StudentEnrollments)
        .join(Students)
        .filter(StudentEnrollments.class_section_id == class_section_id)
        .order_by(StudentEnrollments.roll_no)
        .offset(skip)
        .limit(limit)
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
