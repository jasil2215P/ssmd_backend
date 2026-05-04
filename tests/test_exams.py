import unittest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException, status

from main import app
from db import Base, get_db
from models import (
    Users,
    Students,
    ClassSections,
    Subjects,
    ClassSubjects,
    Exams,
    ExamSubjects,
    Marks,
    ExamCreate,
    ExamSubjectCreate,
    MarkStudent,
    User,
    UserRole,
)
from routes.exams import (
    create_exam,
    mark_student,
    get_marks,
)

# Use a local in-memory engine for isolation
LOCAL_DB_URL = "sqlite:///:memory:"
local_engine = create_engine(LOCAL_DB_URL, connect_args={"check_same_thread": False})
LocalSessionLocal = sessionmaker(bind=local_engine)


def override_get_db():
    db = LocalSessionLocal()
    try:
        yield db
    finally:
        db.close()


class ExamRouteTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=local_engine)
        app.dependency_overrides[get_db] = override_get_db

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=local_engine)
        local_engine.dispose()

    async def asyncSetUp(self):
        Base.metadata.drop_all(bind=local_engine)
        Base.metadata.create_all(bind=local_engine)
        self.db = LocalSessionLocal()
        
        # Common setup: user, teacher, class, subject, class_subject
        self.teacher_user = Users(username="teacher1", password_hash="x", role=UserRole.TEACHER)
        self.db.add(self.teacher_user)
        self.db.commit()
        self.db.refresh(self.teacher_user)
        self.teacher_model = User(id=self.teacher_user.id, username=self.teacher_user.username, role=UserRole.TEACHER)
        
        self.cs = ClassSections(class_name="10", section="A", academic_year=2024)
        self.sub = Subjects(name="Math")
        self.db.add_all([self.cs, self.sub])
        self.db.commit()
        
        self.cls_sub = ClassSubjects(class_section_id=self.cs.id, subject_id=self.sub.id)
        self.db.add(self.cls_sub)
        self.db.commit()
        
        # Student
        self.stu_user = Users(username="student1", password_hash="x", role=UserRole.STUDENT)
        self.db.add(self.stu_user)
        self.db.commit()
        self.student = Students(user_id=self.stu_user.id, name="S1", father_name="F", mother_name="M", admission_date=date.today(), reg_no=1)
        self.db.add(self.student)
        self.db.commit()

    async def asyncTearDown(self):
        self.db.close()

    async def test_create_exam_success(self):
        data = ExamCreate(
            name="Midterm",
            class_section_id=self.cs.id,
            date=date(2024, 6, 15),
            subjects=[
                ExamSubjectCreate(class_subject_id=self.cls_sub.id, max_marks=100)
            ]
        )
        result = create_exam(data, self.db, self.teacher_model)
        self.assertEqual(result.status, "success")
        
        exam = self.db.query(Exams).filter(Exams.name == "Midterm").first()
        self.assertIsNotNone(exam)
        self.assertEqual(exam.created_by, self.teacher_user.id)
        
        exam_sub = self.db.query(ExamSubjects).filter(ExamSubjects.exam_id == exam.id).first()
        self.assertIsNotNone(exam_sub)
        self.assertEqual(exam_sub.max_marks, 100)

    async def test_mark_student_success(self):
        # Setup exam and exam_subject
        exam = Exams(name="Test", class_section_id=self.cs.id, date=date.today())
        self.db.add(exam)
        self.db.commit()
        exam_sub = ExamSubjects(exam_id=exam.id, class_subject_id=self.cls_sub.id, max_marks=100)
        self.db.add(exam_sub)
        self.db.commit()
        
        data = MarkStudent(
            student_id=self.student.id,
            exam_subject_id=exam_sub.id,
            marks_obtained=85
        )
        result = mark_student(data, self.db)
        self.assertEqual(result.status, "success")
        
        mark = self.db.query(Marks).filter(Marks.student_id == self.student.id, Marks.exam_subject_id == exam_sub.id).first()
        self.assertIsNotNone(mark)
        self.assertEqual(mark.marks_obtained, 85)

    async def test_get_marks_success(self):
        # Setup exam, exam_subject, and mark
        exam = Exams(name="Finals", class_section_id=self.cs.id, date=date.today())
        self.db.add(exam)
        self.db.commit()
        exam_sub = ExamSubjects(exam_id=exam.id, class_subject_id=self.cls_sub.id, max_marks=100)
        self.db.add(exam_sub)
        self.db.commit()
        mark = Marks(student_id=self.student.id, exam_subject_id=exam_sub.id, marks_obtained=90)
        self.db.add(mark)
        self.db.commit()
        
        result = get_marks(self.student.id, exam.id, self.db)
        self.assertEqual(result.student_id, self.student.id)
        self.assertEqual(result.exam, "Finals")
        self.assertEqual(result.total_marks, 90)
        self.assertEqual(len(result.subjects), 1)
        self.assertEqual(result.subjects[0].subject, "Math")

    async def test_get_marks_not_found(self):
        with self.assertRaises(HTTPException) as context:
            get_marks(self.student.id, 999, self.db)
        self.assertEqual(context.exception.status_code, status.HTTP_404_NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
