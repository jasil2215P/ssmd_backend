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
from models import Attendance, ClassSections, CreateAttendance, Students
from routes.attendance import (
    create_bulk_attendance_records,
    update_bulk_attendance_records,
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
        student_1 = Students(name="Alice", reg_no=1)
        student_2 = Students(name="Bob", reg_no=2)

        self.db.add_all([class_section, student_1, student_2])
        self.db.commit()

        self.class_section_id = class_section.id
        self.student_1_id = student_1.id
        self.student_2_id = student_2.id

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


if __name__ == "__main__":
    unittest.main()
