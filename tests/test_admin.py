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
    Staff,
    Admins,
    ClassSections,
    Subjects,
    ClassSubjects,
    StudentEnrollments,
    TeachingAssignments,
    UserCreate,
    StudentCreateInfo,
    StaffCreateInfo,
    AdminCreateInfo,
    EnrollmentCreate,
    SubjectCreate,
    ClassSectionCreate,
    ClassSubjectLink,
    TeachingAssignmentCreate,
    UserRole,
)
from routes.admin import (
    create_user,
    create_enrollment,
    get_yearly_stats,
    create_subject,
    create_class_section,
    assign_class_subjects,
    create_teaching_assignment,
    list_students,
    list_teachers,
    list_admins,
    list_subjects,
    list_class_sections,
    list_exams,
    list_class_subjects,
    list_teaching_assignments,
    list_enrollments,
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


class AdminRouteTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_create_user_student_success(self):
        data = UserCreate(
            username="student1",
            password="password123",
            role=UserRole.STUDENT,
            student_info=StudentCreateInfo(
                name="Student One",
                father_name="Father",
                mother_name="Mother",
                admission_date=date(2023, 1, 1),
                reg_no=1001,
            ),
        )
        result = create_user(data, self.db)
        self.assertEqual(result.status, "success")

        user = self.db.query(Users).filter(Users.username == "student1").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.role, UserRole.STUDENT)

        student = self.db.query(Students).filter(Students.user_id == user.id).first()
        self.assertIsNotNone(student)
        self.assertEqual(student.name, "Student One")

    async def test_create_user_teacher_success(self):
        data = UserCreate(
            username="teacher1",
            password="password123",
            role=UserRole.TEACHER,
            staff_info=StaffCreateInfo(name="Teacher One", position="Math Teacher"),
        )
        result = create_user(data, self.db)
        self.assertEqual(result.status, "success")

        user = self.db.query(Users).filter(Users.username == "teacher1").first()
        staff = self.db.query(Staff).filter(Staff.user_id == user.id).first()
        self.assertIsNotNone(staff)
        self.assertEqual(staff.name, "Teacher One")

    async def test_create_user_admin_success(self):
        data = UserCreate(
            username="admin2",
            password="password123",
            role=UserRole.ADMIN,
            admin_info=AdminCreateInfo(name="Admin Two"),
        )
        result = create_user(data, self.db)
        self.assertEqual(result.status, "success")

        user = self.db.query(Users).filter(Users.username == "admin2").first()
        admin = self.db.query(Admins).filter(Admins.user_id == user.id).first()
        self.assertIsNotNone(admin)
        self.assertEqual(admin.name, "Admin Two")

    async def test_create_user_duplicate_username(self):
        # Create first user
        user1 = Users(username="dup", password_hash="x", role="admin")
        self.db.add(user1)
        self.db.commit()

        data = UserCreate(
            username="dup",
            password="password123",
            role=UserRole.ADMIN,
            admin_info=AdminCreateInfo(name="Admin"),
        )
        with self.assertRaises(HTTPException) as context:
            create_user(data, self.db)
        self.assertEqual(context.exception.status_code, status.HTTP_400_BAD_REQUEST)

    async def test_create_enrollment_success(self):
        # Setup student and class section
        user = Users(username="s1", password_hash="x", role="student")
        self.db.add(user)
        self.db.commit()
        student = Students(
            user_id=user.id,
            name="S",
            father_name="F",
            mother_name="M",
            admission_date=date.today(),
            reg_no=1,
        )
        cs = ClassSections(class_name="10", section="A", academic_year=2024)
        self.db.add_all([student, cs])
        self.db.commit()

        data = EnrollmentCreate(
            student_id=student.id, class_section_id=cs.id, roll_no=5
        )
        result = create_enrollment(data, self.db)
        self.assertEqual(result.status, "success")

        enrollment = (
            self.db.query(StudentEnrollments)
            .filter(StudentEnrollments.student_id == student.id)
            .first()
        )
        self.assertIsNotNone(enrollment)
        self.assertEqual(enrollment.roll_no, 5)

    async def test_create_subject_success(self):
        data = SubjectCreate(name="Science")
        result = create_subject(data, self.db)
        self.assertEqual(result.status, "success")

        subject = self.db.query(Subjects).filter(Subjects.name == "Science").first()
        self.assertIsNotNone(subject)

    async def test_create_class_section_success(self):
        data = ClassSectionCreate(class_name="12", section="B", academic_year=2025)
        result = create_class_section(data, self.db)
        self.assertEqual(result.status, "success")

        cs = (
            self.db.query(ClassSections)
            .filter(ClassSections.class_name == "12", ClassSections.section == "B")
            .first()
        )
        self.assertIsNotNone(cs)

    async def test_assign_class_subjects_success(self):
        cs = ClassSections(class_name="10", section="A", academic_year=2024)
        sub = Subjects(name="Math")
        self.db.add_all([cs, sub])
        self.db.commit()

        data = ClassSubjectLink(class_section_id=cs.id, subject_id=sub.id)
        result = assign_class_subjects(data, self.db)
        self.assertEqual(result.status, "success")

        link = (
            self.db.query(ClassSubjects)
            .filter(
                ClassSubjects.class_section_id == cs.id,
                ClassSubjects.subject_id == sub.id,
            )
            .first()
        )
        self.assertIsNotNone(link)

    async def test_create_teaching_assignment_success(self):
        # Setup staff, class, subject, and link
        u = Users(username="t1", password_hash="x", role="teacher")
        self.db.add(u)
        self.db.commit()
        staff = Staff(user_id=u.id, name="T", position="P")
        cs = ClassSections(class_name="10", section="A", academic_year=2024)
        sub = Subjects(name="Math")
        self.db.add_all([staff, cs, sub])
        self.db.commit()

        cls_sub = ClassSubjects(class_section_id=cs.id, subject_id=sub.id)
        self.db.add(cls_sub)
        self.db.commit()

        data = TeachingAssignmentCreate(staff_id=staff.id, class_subject_id=cls_sub.id)
        result = create_teaching_assignment(data, self.db)
        self.assertEqual(result.status, "success")

        ta = (
            self.db.query(TeachingAssignments)
            .filter(TeachingAssignments.staff_id == staff.id)
            .first()
        )
        self.assertIsNotNone(ta)

    async def test_get_yearly_stats(self):
        # Setup data for 2024
        cs = ClassSections(class_name="10", section="A", academic_year=2024)
        self.db.add(cs)
        self.db.commit()

        u1 = Users(username="s1", password_hash="x", role="student")
        self.db.add(u1)
        self.db.commit()
        s1 = Students(
            user_id=u1.id,
            name="S1",
            father_name="F",
            mother_name="M",
            admission_date=date.today(),
            reg_no=1,
        )
        self.db.add(s1)
        self.db.commit()

        self.db.add(
            StudentEnrollments(student_id=s1.id, class_section_id=cs.id, roll_no=1)
        )

        u2 = Users(username="t1", password_hash="x", role="teacher")
        self.db.add(u2)
        self.db.commit()
        staff = Staff(user_id=u2.id, name="T1", position="P")
        self.db.add(staff)
        self.db.commit()

        # In current implementation of get_yearly_stats, staff_count is total staff count, not filtered by year correctly in the second query
        # staff_count = db.query(func.count(func.distinct(Staff.id))).scalar()

        stats = get_yearly_stats(2024, self.db)
        self.assertEqual(stats.year, 2024)
        self.assertEqual(stats.student_count, 1)
        self.assertEqual(stats.staff_count, 1)

    async def test_list_students(self):
        u = Users(username="s1", password_hash="x", role="student")
        self.db.add(u)
        self.db.commit()
        s = Students(
            user_id=u.id,
            name="S1",
            father_name="F",
            mother_name="M",
            admission_date=date.today(),
            reg_no=1,
        )
        cs = ClassSections(class_name="10", section="A", academic_year=2024)
        self.db.add_all([s, cs])
        self.db.commit()
        self.db.add(
            StudentEnrollments(student_id=s.id, class_section_id=cs.id, roll_no=1)
        )
        self.db.commit()

        results = list_students(db=self.db)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "S1")

    async def test_list_teachers(self):
        u = Users(username="t1", password_hash="x", role="teacher")
        self.db.add(u)
        self.db.commit()
        s = Staff(user_id=u.id, name="T1", position="P")
        self.db.add(s)
        self.db.commit()

        results = list_teachers(db=self.db)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "T1")

    async def test_list_admins(self):
        u = Users(username="a1", password_hash="x", role="admin")
        self.db.add(u)
        self.db.commit()
        a = Admins(user_id=u.id, name="A1")
        self.db.add(a)
        self.db.commit()

        results = list_admins(db=self.db)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "A1")

    async def test_list_subjects(self):
        self.db.add(Subjects(name="Math"))
        self.db.commit()

        results = list_subjects(db=self.db)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Math")

    async def test_list_class_sections(self):
        self.db.add(ClassSections(class_name="10", section="A", academic_year=2024))
        self.db.commit()

        results = list_class_sections(db=self.db)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].class_name, "10")

    async def test_list_exams(self):
        cs = ClassSections(class_name="10", section="A", academic_year=2024)
        self.db.add(cs)
        self.db.commit()
        from models import Exams

        self.db.add(Exams(name="Midterm", class_section_id=cs.id, date=date.today()))
        self.db.commit()

        results = list_exams(db=self.db)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Midterm")

    async def test_list_class_subjects(self):
        cs = ClassSections(class_name="10", section="A", academic_year=2024)
        sub = Subjects(name="Math")
        self.db.add_all([cs, sub])
        self.db.commit()
        self.db.add(ClassSubjects(class_section_id=cs.id, subject_id=sub.id))
        self.db.commit()

        results = list_class_subjects(db=self.db)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].subject_id, sub.id)

    async def test_list_teaching_assignments(self):
        u = Users(username="t1", password_hash="x", role="teacher")
        self.db.add(u)
        self.db.commit()
        staff = Staff(user_id=u.id, name="T1", position="P")
        cs = ClassSections(class_name="10", section="A", academic_year=2024)
        sub = Subjects(name="Math")
        self.db.add_all([staff, cs, sub])
        self.db.commit()
        cls_sub = ClassSubjects(class_section_id=cs.id, subject_id=sub.id)
        self.db.add(cls_sub)
        self.db.commit()
        self.db.add(TeachingAssignments(staff_id=staff.id, class_subject_id=cls_sub.id))
        self.db.commit()

        results = list_teaching_assignments(db=self.db)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].staff_id, staff.id)

    async def test_list_enrollments(self):
        u = Users(username="s1", password_hash="x", role="student")
        self.db.add(u)
        self.db.commit()
        s = Students(
            user_id=u.id,
            name="S1",
            father_name="F",
            mother_name="M",
            admission_date=date.today(),
            reg_no=1,
        )
        cs = ClassSections(class_name="10", section="A", academic_year=2024)
        self.db.add_all([s, cs])
        self.db.commit()
        self.db.add(
            StudentEnrollments(student_id=s.id, class_section_id=cs.id, roll_no=1)
        )
        self.db.commit()

        results = list_enrollments(db=self.db)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].student_id, s.id)

    async def test_list_students_pagination(self):
        # Create 3 students
        cs = ClassSections(class_name="10", section="A", academic_year=2024)
        self.db.add(cs)
        self.db.commit()
        
        for i in range(1, 4):
            u = Users(username=f"student{i}", password_hash="x", role="student")
            self.db.add(u)
            self.db.commit()
            s = Students(user_id=u.id, name=f"S{i}", father_name="F", mother_name="M", admission_date=date(2024, 1, i), reg_no=1000+i)
            self.db.add(s)
            self.db.commit()
            self.db.add(StudentEnrollments(student_id=s.id, class_section_id=cs.id, roll_no=i))
            self.db.commit()
            
        # Test limit=2
        results = list_students(is_enrolled=True, skip=0, limit=2, db=self.db)
        self.assertEqual(len(results), 2)
        # Ordered by admission_date desc: S3, S2, S1
        self.assertEqual(results[0].name, "S3")
        self.assertEqual(results[1].name, "S2")
        
        # Test skip=2
        results = list_students(is_enrolled=True, skip=2, limit=2, db=self.db)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "S1")


if __name__ == "__main__":
    unittest.main()
