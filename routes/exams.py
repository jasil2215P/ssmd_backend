from operator import and_
from os.path import join
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Select, label, select
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from db import get_db
from models import (
    ClassSections,
    ClassSubjects,
    ExamCreate,
    ExamResponse,
    Exams,
    ExamSubjects,
    Marks,
    MarkStudent,
    OperationStatusResponse,
    StudentEnrollments,
    StudentExamMarksResponse,
    Students,
    SubjectMarkResponse,
    Subjects,
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
    "/exams/{exam_subject_id}/grading_data",
    summary="Returns grading data for an exam with exam_subject_id.",
    dependencies=[Depends(require_role(["admin", "teacher"]))],
)
def get_grading_data(exam_subject_id: int, db: Session = Depends(get_db)):

    data_query = (
        select(
            Students.id.label("student_id"),
            Students.name.label("student_name"),
            StudentEnrollments.roll_no,
            ExamSubjects.id.label("exam_subject_id"),
            ExamSubjects.max_marks,
            Marks.marks_obtained,
        )
        .select_from(ExamSubjects)
        .join(ExamSubjects.class_subject)
        .join(ClassSubjects.class_section)
        .join(ClassSections.student_enrollments)
        .join(StudentEnrollments.student)
        .outerjoin(
            Marks,
            and_(
                Marks.student_id == Students.id,
                Marks.exam_subject_id == exam_subject_id,
            ),
        )
        .where(ExamSubjects.id == exam_subject_id)
        .order_by(StudentEnrollments.roll_no)
    )

    data = db.execute(data_query).mappings().all()

    return [
        {
            "student_id": d["student_id"],
            "student_name": d["student_name"],
            "roll_no": d["roll_no"],
            "exam_subject_id": d["exam_subject_id"],
            "max_marks": d["max_marks"],
            "marks": d["marks_obtained"],
        }
        for d in data
    ]


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
    exams = (
        select(
            Exams.id,
            ExamSubjects.id.label("exam_subject_id"),
            Exams.name,
            Exams.date,
            Exams.exam_type,
            Exams.status,
            ClassSections.class_name,
            ClassSections.section,
            Subjects.name.label("subject_name"),
        )
        .join(Exams.class_section)
        .join(Exams.exam_subjects)
        .join(ExamSubjects.class_subject)
        .join(ClassSubjects.subject)
    )

    if completed is not None:
        exams = exams.where(Exams.status == ("completed" if completed else "pending"))

    if official is not None:
        exams = exams.where(
            (Exams.exam_type == "official")
            if official
            else (Exams.exam_type != "official")
        )

    exams = exams.offset(skip).limit(limit)

    result = db.execute(exams).mappings().all()
    return [
        ExamResponse(
            id=r["id"],
            name=r["name"],
            exam_subject_id=r["exam_subject_id"],
            class_name=r["class_name"],
            exam_subjects=r["subject_name"],
            class_section=r["section"],
            date=r["date"],
            exam_type=r["exam_type"],
            status=r["status"],
        )
        for r in result
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


@router.post(
    "/mark/bulk",
    response_model=OperationStatusResponse,
    dependencies=[Depends(require_role(["teacher", "admin"]))],
    summary="Mark students for an examination",
)
def bulk_mark_student(data: List[MarkStudent], db: Session = Depends(get_db)):
    marks = [
        Marks(
            student_id=d.student_id,
            exam_subject_id=d.exam_subject_id,
            marks_obtained=d.marks_obtained,
        )
        for d in data
    ]

    try:
        db.add_all(marks)
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
