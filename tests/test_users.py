import unittest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app, get_current_user_profile
from db import Base, get_db
from models import (
    ClassSections,
    ClassSubjects,
    Staff,
    StaffSubjects,
    StudentEnrollments,
    Students,
    Subjects,
    TeachingAssignments,
    User,
    UserRole,
    Users,
    StudentProfileResponse,
    TeacherProfileResponse,
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


class UserTests(unittest.IsolatedAsyncioTestCase):
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

    async def asyncTearDown(self):
        self.db.close()

    async def test_get_current_user_profile_student(self):
        # Setup: student user, student record, class section, enrollment
        user = Users(username="student1", password_hash="x", role=UserRole.STUDENT)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        student = Students(
            user_id=user.id,
            name="Alice",
            reg_no=123,
            father_name="F",
            mother_name="M",
            admission_date=date(2023, 1, 1),
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)

        cs = ClassSections(class_name="10", section="A", academic_year=2024)
        self.db.add(cs)
        self.db.commit()
        self.db.refresh(cs)

        enrollment = StudentEnrollments(
            student_id=student.id, class_section_id=cs.id, roll_no=1
        )
        self.db.add(enrollment)
        self.db.commit()

        user_model = User(id=user.id, username=user.username, role=UserRole.STUDENT)
        profile = get_current_user_profile(user_model, self.db)

        self.assertIsInstance(profile, StudentProfileResponse)
        self.assertEqual(profile.name, "Alice")
        self.assertEqual(profile.class_name, "10")
        self.assertEqual(profile.section, "A")

    async def test_get_current_user_profile_teacher(self):
        # Setup: teacher user, staff record, subject, teaching assignment
        user = Users(username="teacher1", password_hash="x", role=UserRole.TEACHER)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        staff = Staff(user_id=user.id, name="Bob", position="Senior Teacher")
        self.db.add(staff)
        self.db.commit()
        self.db.refresh(staff)

        class_section = ClassSections(class_name="A", section="2", academic_year=2026)
        self.db.add(class_section)
        self.db.commit()
        self.db.refresh(class_section)

        subject = Subjects(name="Math")
        self.db.add(subject)
        self.db.commit()
        self.db.refresh(subject)

        class_subject = ClassSubjects(
            class_section_id=class_section.id, subject_id=subject.id
        )
        self.db.add(class_subject)
        self.db.commit()
        self.db.refresh(class_subject)

        ss = TeachingAssignments(staff_id=staff.id, class_subject_id=class_subject.id)
        self.db.add(ss)
        self.db.commit()

        user_model = User(id=user.id, username=user.username, role=UserRole.TEACHER)
        profile = get_current_user_profile(user_model, self.db)

        self.assertIsInstance(profile, TeacherProfileResponse)
        self.assertEqual(profile.name, "Bob")
        self.assertEqual(profile.position, "Senior Teacher")
        self.assertIn(subject.name, profile.subjects)


if __name__ == "__main__":
    unittest.main()
