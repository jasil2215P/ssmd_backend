from datetime import date

from fastapi import Depends, FastAPI
from sqlalchemy import and_
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from db import get_db
from models import ClassSections, Staff, StudentEnrollments, Students, Subjects, User
from routes import announcements, attendance, health_check
from routes.auth import token

app = FastAPI(title="SSMD", description="Main API for SSMD school management software.")

app.include_router(attendance.router)
app.include_router(token.router)
app.include_router(health_check.router)
app.include_router(announcements.router)


@app.get(
    "/students/{student_id}/all", dependencies=[Depends(require_role(["teacher"]))]
)
def get_student_info(student_id: int, db: Session = Depends(get_db)):
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

    return {
        "roll_no": data.student_enrollments[0].roll_no,
        "name": data.name,
        "father_name": data.father_name,
        "mother_name": data.mother_name,
        "admission_date": data.admission_date,
        "class_name": data.student_enrollments[0].class_sections.class_name,
        "section": data.student_enrollments[0].class_sections.section,
        "academic_year": data.student_enrollments[0].class_sections.academic_year,
    }


@app.get(
    "/classes",
    dependencies=[Depends(require_role(["teacher", "student"]))],
)
def get_classes(db: Session = Depends(get_db)):
    classes = (
        db.query(ClassSections)
        .filter(ClassSections.academic_year == date.today().year)
        .all()
    )

    return [vars(c) for c in classes]


@app.get(
    "/classes/{class_id}/students", dependencies=[Depends(require_role(["teacher"]))]
)
def get_students_of_class(class_id: int, db: Session = Depends(get_db)):
    data = (
        db.query(StudentEnrollments)
        .join(Students)
        .filter(StudentEnrollments.class_section_id == class_id)
        .order_by(StudentEnrollments.roll_no)
        .all()
    )

    return [
        {"id": d.students.id, "roll_no": d.roll_no, "name": d.students.name}
        for d in data
    ]


@app.get("/user/me")
def about_user(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    current_role = current_user.role
    if current_role == "student":
        return get_student_data(db=db, user_id=current_user.id)
    elif current_role == "teacher":
        return get_teacher_data(db, user_id=current_user.id)
    else:
        return current_role


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

    return {
        "id": data.id,
        "name": data.name,
        "reg_no": data.reg_no,
        "father_name": data.father_name,
        "mother_name": data.mother_name,
        "admission_date": data.admission_date,
        "class_name": data.student_enrollments[0].class_sections.class_name,
        "section": data.student_enrollments[0].class_sections.section,
        "academic_year": data.student_enrollments[0].class_sections.academic_year,
    }


def get_teacher_data(db: Session, user_id):
    data = (
        db.query(Staff)
        .join(Subjects)
        .filter(Staff.subject == Subjects.id)
        .where(Staff.user_id == user_id)
        .one()
    )

    return {
        "id": data.id,
        "name": data.name,
        "position": data.position,
        "subject": data.subject,
    }
