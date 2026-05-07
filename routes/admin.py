from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from starlette.status import HTTP_400_BAD_REQUEST

from auth import require_role, password_hash, get_current_user
from db import get_db
from models import (
    Admins,
    ClassSectionCreate,
    ClassSections,
    ClassSubjectLink,
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
    AdminProfileResponse,
    ClassSectionResponse,
    EnrollmentResponse,
    ExamResponse,
    StudentProfileResponse,
    SubjectResponse,
    TeacherProfileResponse,
    ClassSubjectResponse,
    TeachingAssignmentResponse,
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
def create_exam(
    data: ExamCreate, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    try:
        exam = Exams(
            name=data.name,
            class_section_id=data.class_section_id,
            date=data.date,
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
    "/class-subjects",
    response_model=OperationStatusResponse,
    summary="Link a subject to a class",
)
def assign_class_subjects(data: ClassSubjectLink, db: Session = Depends(get_db)):
    c_subject = ClassSubjects(
        class_section_id=data.class_section_id, subject_id=data.subject_id
    )
    db.add(c_subject)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))

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


@router.get("/students", response_model=List[StudentProfileResponse])
def list_students(
    is_enrolled: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    data = db.query(Students)
    if is_enrolled:
        students = (
            data.join(StudentEnrollments)
            .join(ClassSections)
            .filter(ClassSections.id == StudentEnrollments.class_section_id)
            .order_by(Students.admission_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    else:
        students = (
            data.filter(~Students.student_enrollments.any())
            .order_by(Students.admission_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    return [
        StudentProfileResponse(
            id=s.id,
            name=s.name,
            reg_no=s.reg_no,
            father_name=s.father_name,
            mother_name=s.mother_name,
            admission_date=s.admission_date,
            **get_enrollment_data(s),
        )
        for s in students
    ]


def get_enrollment_data(s):
    e = s.student_enrollments[0] if s.student_enrollments else None
    return {
        "roll_no": e.roll_no if e else None,
        "class_name": e.class_section.class_name if e else None,
        "section": e.class_section.section if e else None,
        "academic_year": e.class_section.academic_year if e else None,
    }


@router.get("/teachers", response_model=List[TeacherProfileResponse])
def list_teachers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    staff_members = (
        db.query(Staff)
        .options(
            joinedload(Staff.teaching_assignments)
            .joinedload(TeachingAssignments.class_subject)
            .joinedload(ClassSubjects.subject)
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        TeacherProfileResponse(
            id=s.id,
            name=s.name,
            position=s.position,
            subjects=list(
                set(sub.class_subject.subject.name for sub in s.teaching_assignments)
            ),
        )
        for s in staff_members
    ]


@router.get("/admins", response_model=List[AdminProfileResponse])
def list_admins(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    admins = db.query(Admins).offset(skip).limit(limit).all()
    return [AdminProfileResponse(id=a.id, name=a.name) for a in admins]


@router.get("/subjects", response_model=List[SubjectResponse])
def list_subjects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    subjects = db.query(Subjects).offset(skip).limit(limit).all()
    return [SubjectResponse(id=s.id, name=s.name) for s in subjects]


@router.get("/class-sections", response_model=List[ClassSectionResponse])
def list_class_sections(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    class_sections = db.query(ClassSections).offset(skip).limit(limit).all()
    return [
        ClassSectionResponse(
            id=cs.id,
            class_name=cs.class_name,
            section=cs.section,
            academic_year=cs.academic_year,
        )
        for cs in class_sections
    ]


@router.get("/exams", response_model=List[ExamResponse])
def list_exams(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    exams = db.query(Exams).offset(skip).limit(limit).all()
    return [
        ExamResponse(
            id=e.id,
            name=e.name,
            class_section_id=e.class_section_id,
            date=e.date,
            exam_type=e.exam_type,
            status=e.status,
        )
        for e in exams
    ]


@router.get("/class-subjects", response_model=List[ClassSubjectResponse])
def list_class_subjects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    class_subjects = db.query(ClassSubjects).offset(skip).limit(limit).all()
    return [
        ClassSubjectResponse(
            id=cs.id, class_section_id=cs.class_section_id, subject_id=cs.subject_id
        )
        for cs in class_subjects
    ]


@router.get("/teaching-assignments", response_model=List[TeachingAssignmentResponse])
def list_teaching_assignments(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    assignments = db.query(TeachingAssignments).offset(skip).limit(limit).all()
    return [
        TeachingAssignmentResponse(
            id=ta.id, staff_id=ta.staff_id, class_subject_id=ta.class_subject_id
        )
        for ta in assignments
    ]


@router.get("/enrollments", response_model=List[EnrollmentResponse])
def list_enrollments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    enrollments = db.query(StudentEnrollments).offset(skip).limit(limit).all()
    return [
        EnrollmentResponse(
            id=e.id,
            student_id=e.student_id,
            class_section_id=e.class_section_id,
            roll_no=e.roll_no,
        )
        for e in enrollments
    ]
