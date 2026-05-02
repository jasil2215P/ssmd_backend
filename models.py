from datetime import date
from enum import StrEnum
from pydantic import BaseModel
from typing import List

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import relationship
from db import Base


class UserRole(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"


class User(BaseModel):
    id: int
    username: str
    role: UserRole


class UserInDb(User):
    password_hash: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenData(BaseModel):
    username: str


class CreateAttendance(BaseModel):
    student_id: int
    class_section_id: int
    status: AttendanceStatus


class AnnouncementCreate(BaseModel):
    subject: str
    details: str
    roles: List[UserRole]


class HealthCheckResponse(BaseModel):
    status: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class StudentCreateInfo(BaseModel):
    name: str
    father_name: str
    mother_name: str
    admission_date: date
    reg_no: int


class StaffCreateInfo(BaseModel):
    name: str
    position: str


class AdminCreateInfo(BaseModel):
    name: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole
    student_info: StudentCreateInfo | None = None
    staff_info: StaffCreateInfo | None = None
    admin_info: AdminCreateInfo | None = None


class EnrollmentCreate(BaseModel):
    student_id: int
    class_section_id: int
    roll_no: int


class ExamSubjectCreate(BaseModel):
    class_subject_id: int
    max_marks: int


class ExamCreate(BaseModel):
    name: str
    class_section_id: int
    subjects: List[ExamSubjectCreate]
    date: date


class SubjectCreate(BaseModel):
    name: str


class ClassSectionCreate(BaseModel):
    class_name: str
    section: str
    academic_year: int


class ClassSubjectLink(BaseModel):
    subject_id: int
    class_section_id: int


class TeachingAssignmentCreate(BaseModel):
    staff_id: int
    class_subject_id: int


class YearlyStatsResponse(BaseModel):
    year: int
    student_count: int
    staff_count: int


class AdminProfileResponse(BaseModel):
    id: int
    name: str


class OperationStatusResponse(BaseModel):
    status: str


class DeleteResponse(BaseModel):
    done: bool


class AttendanceCreateResponse(BaseModel):
    student_id: int


class AttendanceRecordResponse(BaseModel):
    student_id: int
    class_section_id: int
    status: AttendanceStatus


class StudentAttendanceResponse(BaseModel):
    student_id: int
    date: date
    status: AttendanceStatus


class AnnouncementResponse(BaseModel):
    id: int
    subject: str
    details: str
    username: str
    date: date


class AnnouncementCreateResponse(BaseModel):
    id: int


class StudentInfoResponse(BaseModel):
    roll_no: int
    name: str
    father_name: str
    mother_name: str
    admission_date: date
    class_name: str
    section: str
    academic_year: int


class ClassSectionResponse(BaseModel):
    id: int
    class_name: str
    section: str
    academic_year: int


class StudentSummaryResponse(BaseModel):
    id: int
    roll_no: int
    name: str


class StudentProfileResponse(BaseModel):
    id: int
    name: str
    reg_no: int
    father_name: str
    mother_name: str
    admission_date: date
    class_name: str
    section: str
    academic_year: int


class TeacherProfileResponse(BaseModel):
    id: int
    name: str
    position: str
    subjects: List[int]


class GenericUserRoleResponse(BaseModel):
    role: UserRole


_ROLE_CHECK = "role IN ('student', 'teacher', 'admin')"
_STATUS_CHECK = "status IN ('present', 'absent')"


class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False)

    __table_args__ = (CheckConstraint(_ROLE_CHECK, name="ck_users_role"),)

    students = relationship("Students", back_populates="user", uselist=False)
    staff = relationship("Staff", back_populates="user", uselist=False)
    admins = relationship("Admins", back_populates="user", uselist=False)
    announcement_posts = relationship("AnnouncementPosts", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user")


class ClassSections(Base):
    __tablename__ = "class_sections"

    id = Column(Integer, primary_key=True)
    class_name = Column(String(64), nullable=False)
    section = Column(String(8), nullable=False)
    academic_year = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "class_name",
            "section",
            "academic_year",
            name="uq_class_sections_name_section_year",
        ),
    )

    student_enrollments = relationship(
        "StudentEnrollments", back_populates="class_section"
    )
    attendances = relationship("Attendance", back_populates="class_section")
    class_subjects = relationship("ClassSubjects", back_populates="class_section")
    exams = relationship("Exams", back_populates="class_section")


class Students(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name = Column(String(128), nullable=False)
    father_name = Column(String(128), nullable=False)
    mother_name = Column(String(128), nullable=False)
    admission_date = Column(Date, nullable=False)
    reg_no = Column(Integer, unique=True, nullable=False)

    __table_args__ = (Index("ix_students_user_id", "user_id"),)

    user = relationship("Users", back_populates="students")
    student_enrollments = relationship("StudentEnrollments", back_populates="student")
    attendances = relationship("Attendance", back_populates="student")
    marks = relationship("Marks", back_populates="student")


class Admins(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name = Column(String(128), nullable=False)

    __table_args__ = (Index("ix_admins_user_id", "user_id"),)

    user = relationship("Users", back_populates="admins")


class StudentEnrollments(Base):
    __tablename__ = "student_enrollments"

    id = Column(Integer, primary_key=True)
    student_id = Column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    class_section_id = Column(
        Integer, ForeignKey("class_sections.id", ondelete="CASCADE"), nullable=False
    )
    roll_no = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "class_section_id", "roll_no", name="uq_enrollment_section_roll"
        ),
        UniqueConstraint(
            "student_id", "class_section_id", name="uq_enrollment_student_section"
        ),
        Index("ix_student_enrollments_student_id", "student_id"),
        Index("ix_student_enrollments_class_section_id", "class_section_id"),
    )

    student = relationship("Students", back_populates="student_enrollments")
    class_section = relationship("ClassSections", back_populates="student_enrollments")


class Subjects(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False)

    staff_subjects = relationship("StaffSubjects", back_populates="subject")
    class_subjects = relationship("ClassSubjects", back_populates="subject")


class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name = Column(String(128), nullable=False)
    position = Column(String(128), nullable=False)

    __table_args__ = (Index("ix_staff_user_id", "user_id"),)

    user = relationship("Users", back_populates="staff")
    staff_subjects = relationship("StaffSubjects", back_populates="staff")
    teaching_assignments = relationship("TeachingAssignments", back_populates="staff")


class StaffSubjects(Base):
    """Many-to-many: a staff member can teach multiple subjects."""

    __tablename__ = "staff_subjects"

    id = Column(Integer, primary_key=True)
    staff_id = Column(
        Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    subject_id = Column(
        Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("staff_id", "subject_id", name="uq_staff_subjects"),
        Index("ix_staff_subjects_staff_id", "staff_id"),
        Index("ix_staff_subjects_subject_id", "subject_id"),
    )

    staff = relationship("Staff", back_populates="staff_subjects")
    subject = relationship("Subjects", back_populates="staff_subjects")


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)
    student_id = Column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    class_section_id = Column(
        Integer, ForeignKey("class_sections.id", ondelete="CASCADE"), nullable=False
    )
    date = Column(Date, nullable=False, server_default=func.current_date())
    status = Column(String(10), nullable=False)

    __table_args__ = (
        # Prevents duplicate attendance entries
        UniqueConstraint(
            "student_id",
            "class_section_id",
            "date",
            name="uq_attendance_student_section_date",
        ),
        CheckConstraint(_STATUS_CHECK, name="ck_attendance_status"),
        Index("ix_attendance_student_id", "student_id"),
        Index("ix_attendance_class_section_id", "class_section_id"),
        # Composite index for the most common query pattern
        Index("ix_attendance_section_date", "class_section_id", "date"),
    )

    student = relationship("Students", back_populates="attendances")
    class_section = relationship("ClassSections", back_populates="attendances")


class AnnouncementPosts(Base):
    __tablename__ = "announcement_posts"

    id = Column(Integer, primary_key=True)
    subject = Column(String(255), nullable=False)
    details = Column(String, nullable=False)
    issuer = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # server_default ensures Alembic generates proper DDL
    date = Column(Date, nullable=False, server_default=func.current_date())

    __table_args__ = (
        Index("ix_announcement_posts_issuer", "issuer"),
        Index("ix_announcement_posts_date", "date"),
    )

    announcement_roles = relationship(
        "AnnouncementRoles",
        back_populates="announcement_post",
        cascade="all, delete-orphan",
    )
    user = relationship("Users", back_populates="announcement_posts")


class AnnouncementRoles(Base):
    __tablename__ = "announcement_roles"

    id = Column(Integer, primary_key=True)
    announcement_post_id = Column(
        Integer, ForeignKey("announcement_posts.id", ondelete="CASCADE"), nullable=False
    )
    for_role = Column(String(16), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "announcement_post_id", "for_role", name="uq_announcement_roles"
        ),
        CheckConstraint(
            _ROLE_CHECK.replace("role", "for_role"), name="ck_announcement_roles_role"
        ),
        Index("ix_announcement_roles_post_id", "announcement_post_id"),
    )

    announcement_post = relationship(
        "AnnouncementPosts", back_populates="announcement_roles"
    )


class ClassSubjects(Base):
    __tablename__ = "class_subjects"

    id = Column(Integer, primary_key=True)
    class_section_id = Column(
        Integer, ForeignKey("class_sections.id", ondelete="CASCADE"), nullable=False
    )
    subject_id = Column(
        Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("class_section_id", "subject_id", name="uq_class_subjects"),
        Index("ix_class_subjects_class_section_id", "class_section_id"),
        Index("ix_class_subjects_subject_id", "subject_id"),
    )

    class_section = relationship("ClassSections", back_populates="class_subjects")
    subject = relationship("Subjects", back_populates="class_subjects")
    teaching_assignments = relationship(
        "TeachingAssignments", back_populates="class_subject"
    )
    exam_subjects = relationship("ExamSubjects", back_populates="class_subject")


class TeachingAssignments(Base):
    __tablename__ = "teaching_assignments"

    id = Column(Integer, primary_key=True)
    staff_id = Column(
        Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    class_subject_id = Column(
        Integer, ForeignKey("class_subjects.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "staff_id", "class_subject_id", name="uq_teaching_assignments"
        ),
        Index("ix_teaching_assignments_staff_id", "staff_id"),
        Index("ix_teaching_assignments_class_subject_id", "class_subject_id"),
    )

    staff = relationship("Staff", back_populates="teaching_assignments")
    class_subject = relationship("ClassSubjects", back_populates="teaching_assignments")


class Exams(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    class_section_id = Column(
        Integer, ForeignKey("class_sections.id", ondelete="CASCADE"), nullable=False
    )
    date = Column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("class_section_id", "name", name="uq_exams_section_name"),
        Index("ix_exams_class_section_id", "class_section_id"),
    )

    class_section = relationship("ClassSections", back_populates="exams")
    exam_subjects = relationship(
        "ExamSubjects", back_populates="exam", cascade="all, delete-orphan"
    )


class ExamSubjects(Base):
    __tablename__ = "exam_subjects"

    id = Column(Integer, primary_key=True)
    exam_id = Column(
        Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False
    )
    class_subject_id = Column(
        Integer, ForeignKey("class_subjects.id", ondelete="CASCADE"), nullable=False
    )
    max_marks = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("exam_id", "class_subject_id", name="uq_exam_subjects"),
        CheckConstraint("max_marks > 0", name="ck_exam_subjects_max_marks"),
        Index("ix_exam_subjects_exam_id", "exam_id"),
        Index("ix_exam_subjects_subject_id", "class_subject_id"),
    )

    exam = relationship("Exams", back_populates="exam_subjects")
    class_subject = relationship("ClassSubjects", back_populates="exam_subjects")
    marks = relationship(
        "Marks", back_populates="exam_subject", cascade="all, delete-orphan"
    )


class Marks(Base):
    __tablename__ = "marks"

    id = Column(Integer, primary_key=True)
    student_id = Column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    exam_subject_id = Column(
        Integer, ForeignKey("exam_subjects.id", ondelete="CASCADE"), nullable=False
    )
    marks_obtained = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "student_id", "exam_subject_id", name="uq_marks_student_exam_subject"
        ),
        CheckConstraint("marks_obtained >= 0", name="ck_marks_obtained_non_negative"),
        Index("ix_marks_student_id", "student_id"),
        Index("ix_marks_exam_subject_id", "exam_subject_id"),
    )

    student = relationship("Students", back_populates="marks")
    exam_subject = relationship("ExamSubjects", back_populates="marks")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    token_hash = Column(String(255), unique=True, nullable=False)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    # server_default instead of Python-side default — Alembic generates correct DDL
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    user = relationship("Users", back_populates="refresh_tokens")
