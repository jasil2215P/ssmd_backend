from datetime import date

from fastapi import Depends, FastAPI
from sqlalchemy import text

from auth import get_current_user, require_role
from db import get_db
from models import User
from routes import attendance, health_check
from routes.auth import token

app = FastAPI(title="SSMD", description="Main API for SSMD school management software.")

app.include_router(attendance.router)
app.include_router(token.router)
app.include_router(health_check.router)


@app.get(
    "/students/{student_id}/all", dependencies=[Depends(require_role(["teacher"]))]
)
def get_student_info(student_id: int, db=Depends(get_db)):
    query = text("""
        SELECT se.roll_no, st.name, st.father_name,
        st.mother_name, st.admission_date, cs.class_name,
        cs.section, cs.academic_year from students st
        join student_enrollments se on st.id = se.student_id
        AND st.id = :student_id
        JOIN class_sections cs
        ON se.class_section_id = cs.id;
    """)

    result = db.execute(query, {"student_id": student_id}).fetchone()

    return result._mapping


@app.get(
    "/classes",
    dependencies=[Depends(require_role(["teacher", "student"]))],
)
def get_classes(db=Depends(get_db)):
    query = text("SELECT * FROM class_sections WHERE academic_year = :year")
    data = db.execute(query, {"year": date.today().year}).fetchall()
    return [dict(row._mapping) for row in data]


@app.get(
    "/classes/{class_id}/students", dependencies=[Depends(require_role(["teacher"]))]
)
def get_students_of_class(class_id: int, db=Depends(get_db)):
    query = text("""
        select s.id, se.roll_no, s.name FROM student_enrollments se
        JOIN students s on (se.class_section_id = :class_id) AND (s.id = se.student_id)
        ORDER BY se.roll_no
    """)

    data = db.execute(query, {"class_id": class_id}).fetchall()

    return [dict(row._mapping) for row in data]


@app.get("/user/me")
def about_user(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    current_role = current_user.role
    if current_role == "student":
        return get_student_data(db=db, user_id=current_user.id)
    elif current_role == "teacher":
        return get_teacher_data(db, user_id=current_user.id)
    else:
        return current_role


def get_student_data(db, user_id):
    query = text("""
        SELECT stu.id, stu.name, stu.father_name, stu.mother_name, stu.admission_date, stu.reg_no, 
        cs.class_name, cs.section, cs.academic_year FROM students stu 
        JOIN student_enrollments se ON (stu.id = se.student_id) 
        JOIN class_sections cs ON (se.class_section_id = cs.id) 
        WHERE stu.user_id = :user_id
    """)

    result = db.execute(query, {"user_id": user_id}).fetchone()

    return result._mapping


def get_teacher_data(db, user_id):
    query = text("""
    SELECT st.id, st.name, st.position, sub.name as subject FROM staff st
    JOIN subjects sub ON (st.subject = sub.id) WHERE user_id = :user_id;
    """)

    result = db.execute(query, {"user_id": user_id}).fetchone()

    return result._mapping
