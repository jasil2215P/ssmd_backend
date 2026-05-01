from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import require_role, password_hash
from db import get_db
from models import (
    Admins,
    ClassSectionCreate,
    ClassSections,
    EnrollmentCreate,
    ExamCreate,
    ExamSubjects,
    Exams,
    OperationStatusResponse,
    Staff,
    StudentEnrollments,
    Students,
    SubjectCreate,
    Subjects,
    TeachingAssignmentCreate,
    TeachingAssignments,
    UserCreate,
    Users,
    YearlyStatsResponse,
    ClassSubjects,
)

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_role(["admin"]))]
)


@router.post(
    "/users",
    response_model=OperationStatusResponse,
    summary="Create a new user with role-specific data",
)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    if db.query(Users).filter(Users.username == data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists"
        )

    try:
        # 1. Create User
        new_user = Users(
            username=data.username,
            password_hash=password_hash.hash(data.password),
            role=data.role,
        )
        db.add(new_user)
        db.flush()  # Get new_user.id

        # 2. Create role-specific info
        if data.role == "student":
            if not data.student_info:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Student info required",
                )
            student = Students(
                user_id=new_user.id,
                name=data.student_info.name,
                father_name=data.student_info.father_name,
                mother_name=data.student_info.mother_name,
                admission_date=data.student_info.admission_date,
                reg_no=data.student_info.reg_no,
            )
            db.add(student)
        elif data.role == "teacher":
            if not data.staff_info:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Staff info required",
                )
            staff = Staff(
                user_id=new_user.id,
                name=data.staff_info.name,
                position=data.staff_info.position,
            )
            db.add(staff)
        elif data.role == "admin":
            if not data.admin_info:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Admin info required",
                )
            admin = Admins(
                user_id=new_user.id,
                name=data.admin_info.name,
            )
            db.add(admin)

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

    return OperationStatusResponse(status="success")


@router.post(
    "/enrollments",
    response_model=OperationStatusResponse,
    summary="Enroll a student in a class section",
)
def create_enrollment(data: EnrollmentCreate, db: Session = Depends(get_db)):
    enrollment = StudentEnrollments(
        student_id=data.student_id,
        class_section_id=data.class_section_id,
        roll_no=data.roll_no,
    )
    db.add(enrollment)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return OperationStatusResponse(status="success")


@router.post(
    "/exams",
    response_model=OperationStatusResponse,
    summary="Create an exam with multiple subjects",
)
def create_exam(data: ExamCreate, db: Session = Depends(get_db)):
    try:
        exam = Exams(
            name=data.name,
            class_section_id=data.class_section_id,
        )
        db.add(exam)
        db.flush()

        for sub in data.subjects:
            exam_subject = ExamSubjects(
                exam_id=exam.id,
                subject_id=sub.subject_id,
                max_marks=sub.max_marks,
            )
            db.add(exam_subject)

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return OperationStatusResponse(status="success")


@router.get(
    "/stats/yearly/{year}",
    response_model=YearlyStatsResponse,
    summary="Get student and staff counts for a year",
)
def get_yearly_stats(year: int, db: Session = Depends(get_db)):
    student_count = (
        db.query(func.count(func.distinct(StudentEnrollments.student_id)))
        .join(ClassSections)
        .filter(ClassSections.academic_year == year)
        .scalar()
    )

    staff_count = (
        db.query(func.count(func.distinct(TeachingAssignments.staff_id)))
        .join(ClassSubjects)
        .join(ClassSections)
        .filter(ClassSections.academic_year == year)
        .scalar()
    )

    staff_count = db.query(func.count(func.distinct(Staff.id))).scalar()

    return YearlyStatsResponse(
        year=year,
        student_count=student_count or 0,
        staff_count=staff_count or 0,
    )


@router.post(
    "/subjects", response_model=OperationStatusResponse, summary="Create a new subject"
)
def create_subject(data: SubjectCreate, db: Session = Depends(get_db)):
    subject = Subjects(name=data.name)
    db.add(subject)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return OperationStatusResponse(status="success")


@router.post(
    "/class-sections",
    response_model=OperationStatusResponse,
    summary="Create a new class section",
)
def create_class_section(data: ClassSectionCreate, db: Session = Depends(get_db)):
    cs = ClassSections(
        class_name=data.class_name,
        section=data.section,
        academic_year=data.academic_year,
    )
    db.add(cs)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return OperationStatusResponse(status="success")


@router.post(
    "/teaching-assignments",
    response_model=OperationStatusResponse,
    summary="Assign a teacher to a subject in a class section",
)
def create_teaching_assignment(
    data: TeachingAssignmentCreate, db: Session = Depends(get_db)
):
    ta = TeachingAssignments(
        staff_id=data.staff_id,
        class_subject_id=data.class_subject_id,
    )
    db.add(ta)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return OperationStatusResponse(status="success")
