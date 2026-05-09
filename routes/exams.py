from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from db import get_db
from models import (
    ExamCreate,
    ExamResponse,
    Exams,
    ExamSubjects,
    Marks,
    MarkStudent,
    OperationStatusResponse,
    StudentExamMarksResponse,
    SubjectMarkResponse,
)

router = APIRouter(tags=["exams"])


@router.post(
    "/exams",
    response_model=OperationStatusResponse,
    dependencies=[Depends(require_role(["teacher", "admin"]))],
    summary="Create an class tests with multiple subjects for teachers.",
)
def create_exam(
    data: ExamCreate, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    try:
        exam = Exams(
            name=data.name,
            class_section_id=data.class_section_id,
            date=data.date,
            exam_type="class_tests",
            created_by=user.id,
        )
        db.add(exam)
        db.flush()

        for sub in data.subjects:
            exam_subject = ExamSubjects(
                exam_id=exam.id,
                class_subject_id=sub.class_subject_id,
                max_marks=sub.max_marks,
            )
            db.add(exam_subject)

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return OperationStatusResponse(status="success")


@router.get(
    "/exams",
    response_model=List[ExamResponse],
    dependencies=[Depends(require_role(["admin", "teacher"]))],
    summary="Returns the registered exams",
)
def get_exams(
    completed: bool | None = None,
    official: bool | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    exams = db.query(Exams)
    if completed is not None:
        if completed:
            exams = exams.filter(Exams.status == "completed")
        else:
            exams = exams.filter(Exams.status == "pending")

    if official is not None:
        if official:
            exams = exams.filter(Exams.exam_type == "official")
        else:
            exams = exams.filter(Exams.exam_type != "official")

    result = exams.offset(skip).limit(limit).all()

    return [
        ExamResponse(
            id=e.id,
            name=e.name,
            class_name=e.class_section.class_name,
            class_section=e.class_section.section,
            date=e.date,
            exam_type=e.exam_type,
            status=e.status,
        )
        for e in result
    ]


@router.post(
    "/mark",
    response_model=OperationStatusResponse,
    dependencies=[Depends(require_role(["teacher", "admin"]))],
    summary="Mark a student for an examination",
)
def mark_student(data: MarkStudent, db: Session = Depends(get_db)):
    mark = Marks(
        student_id=data.student_id,
        exam_subject_id=data.exam_subject_id,
        marks_obtained=data.marks_obtained,
    )
    db.add(mark)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return OperationStatusResponse(status="success")


@router.get(
    "/mark",
    response_model=StudentExamMarksResponse,
    dependencies=[Depends(require_role(["teacher", "admin"]))],
    summary="returns the mark of a student for given examination",
)
def get_marks(student_id: int, exam_id: int, db: Session = Depends(get_db)):
    marks = (
        db.query(Marks)
        .join(ExamSubjects)
        .filter(Marks.student_id == student_id, ExamSubjects.exam_id == exam_id)
        .all()
    )
    if not marks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No marks record found."
        )

    exam = marks[0].exam_subject.exam
    subjects = [
        SubjectMarkResponse(
            subject=m.exam_subject.class_subject.subject.name,
            marks_obtained=m.marks_obtained,
            max_marks=m.exam_subject.max_marks,
        )
        for m in marks
    ]

    return StudentExamMarksResponse(
        student_id=student_id,
        exam=exam.name,
        total_marks=sum(s.marks_obtained for s in subjects),
        max_marks=sum(s.max_marks for s in subjects),
        subjects=subjects,
    )
