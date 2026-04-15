import os
import tempfile
import unittest
from datetime import date

from fastapi import HTTPException, status

TMP_DIR = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite:///{TMP_DIR.name}/test.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret"

from db import Base, SessionLocal, engine
from models import Attendance, ClassSections, CreateAttendance, Students, Users
from routes.attendance import (
    create_bulk_attendance_records,
    update_bulk_attendance_records,
    get_student_attendance_by_date,
)


class AttendanceRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        TMP_DIR.cleanup()

    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

        class_section = ClassSections(
            class_name="10",
            section="A",
            academic_year=date.today().year,
        )

        user_1 = Users(username="alice", password_hash="x", role="student")
        user_2 = Users(username="bob",   password_hash="x", role="student")
        self.db.add_all([class_section, user_1, user_2])
        self.db.flush()  # populates user_1.id, user_2.id before Students insert

        student_1 = Students(user_id=user_1.id, name="Alice", reg_no=1,
                            father_name="", mother_name="", admission_date=date.today())
        student_2 = Students(user_id=user_2.id, name="Bob",   reg_no=2,
                            father_name="", mother_name="", admission_date=date.today())

        self.db.add_all([student_1, student_2])
        self.db.commit()

        self.class_section_id = class_section.id
        self.student_1_id     = student_1.id
        self.student_2_id     = student_2.id

    def tearDown(self):
        self.db.close()

    def test_update_bulk_attendance_updates_existing_rows_for_today(self):
        create_bulk_attendance_records(
            [
                CreateAttendance(
                    student_id=self.student_1_id,
                    class_section_id=self.class_section_id,
                    status="present",
                ),
                CreateAttendance(
                    student_id=self.student_2_id,
                    class_section_id=self.class_section_id,
                    status="absent",
                ),
            ],
            db=self.db,
        )

        result = update_bulk_attendance_records(
            [
                CreateAttendance(
                    student_id=self.student_1_id,
                    class_section_id=self.class_section_id,
                    status="absent",
                ),
                CreateAttendance(
                    student_id=self.student_2_id,
                    class_section_id=self.class_section_id,
                    status="present",
                ),
            ],
            db=self.db,
        )

        rows = (
            self.db.query(Attendance)
            .order_by(Attendance.student_id.asc())
            .all()
        )

        self.assertEqual(result.status, "done")
        self.assertEqual([row.status for row in rows], ["absent", "present"])

    def test_update_bulk_attendance_returns_404_when_any_row_is_missing(self):
        with self.assertRaises(HTTPException) as context:
            update_bulk_attendance_records(
                [
                    CreateAttendance(
                        student_id=self.student_1_id,
                        class_section_id=self.class_section_id,
                        status="present",
                    )
                ],
                db=self.db,
            )

        self.assertEqual(context.exception.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            context.exception.detail,
            f"Attendance not found for {date.today()}",
        )

    def test_get_student_attendance_by_date_success_and_not_found(self):
        # Create an attendance record for student_1 for today
        create_bulk_attendance_records(
            [
                CreateAttendance(
                    student_id=self.student_1_id,
                    class_section_id=self.class_section_id,
                    status="present",
                )
            ],
            db=self.db,
        )

        # Test successful retrieval for student_1 today
        attendance = get_student_attendance_by_date(
            student_id=self.student_1_id, db=self.db
        )
        self.assertEqual(attendance.student_id, self.student_1_id)
        self.assertEqual(attendance.date, date.today())
        self.assertEqual(attendance.status, "present")

        # Test retrieval for student_2 (no attendance record)
        with self.assertRaises(HTTPException) as context:
            get_student_attendance_by_date(student_id=self.student_2_id, db=self.db)
        self.assertEqual(context.exception.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            context.exception.detail,
            f"Attendance record not found for student {self.student_2_id} on {date.today()}",
        )

        # Test retrieval for student_1 on a future date (no attendance record)
        future_date = date.today().replace(year=date.today().year + 1)
        with self.assertRaises(HTTPException) as context:
            get_student_attendance_by_date(
                student_id=self.student_1_id, attendance_date=future_date, db=self.db
            )
        self.assertEqual(context.exception.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            context.exception.detail,
            f"Attendance record not found for student {self.student_1_id} on {future_date}",
        )

    def test_attendance_unique_constraint(self):
        from sqlalchemy.exc import IntegrityError
        # First insertion
        record1 = Attendance(
            student_id=self.student_1_id,
            class_section_id=self.class_section_id,
            date=date.today(),
            status="present",
        )
        self.db.add(record1)
        self.db.commit()

        # Second insertion with same student, section, date
        record2 = Attendance(
            student_id=self.student_1_id,
            class_section_id=self.class_section_id,
            date=date.today(),
            status="absent",
        )
        self.db.add(record2)
        with self.assertRaises(IntegrityError):
            self.db.commit()


if __name__ == "__main__":
    unittest.main()
