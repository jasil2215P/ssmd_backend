from datetime import date, datetime
from enum import StrEnum
from typing import List, Optional

from pydantic import BaseModel
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
from sqlalchemy.orm import relationship, Mapped, mapped_column

from db import Base


class UserRole(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"


class ExamStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


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


class MarkStudent(BaseModel):
    student_id: int
    exam_subject_id: int
    marks_obtained: int


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


class SubjectMarkResponse(BaseModel):
    subject: str
    marks_obtained: int
    max_marks: int


class StudentExamMarksResponse(BaseModel):
    student_id: int
    exam: str
    total_marks: int
    max_marks: int
    subjects: list[SubjectMarkResponse]


class SubjectResponse(BaseModel):
    id: int
    name: str


class ExamResponse(BaseModel):
    id: int
    name: str
    class_section_id: int
    date: date
    exam_type: str
    status: str


class ClassSubjectResponse(BaseModel):
    id: int
    class_section_id: int
    subject_id: int


class TeachingAssignmentResponse(BaseModel):
    id: int
    staff_id: int
    class_subject_id: int


class EnrollmentResponse(BaseModel):
    id: int
    student_id: int
    class_section_id: int
    roll_no: int


class GenericUserRoleResponse(BaseModel):
    role: UserRole


_ROLE_CHECK = "role IN ('student', 'teacher', 'admin')"
_STATUS_CHECK = "status IN ('present', 'absent')"
_EXAM_STATUS_CHECK = "status IN ('pending', 'completed')"


class Users(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (CheckConstraint(_ROLE_CHECK, name="ck_users_role"),)

    students: Mapped[Optional["Students"]] = relationship(
        "Students", back_populates="user", uselist=False
    )
    staff: Mapped[Optional["Staff"]] = relationship(
        "Staff", back_populates="user", uselist=False
    )
    admins: Mapped[Optional["Admins"]] = relationship(
        "Admins", back_populates="user", uselist=False
    )
    announcement_posts: Mapped[List["AnnouncementPosts"]] = relationship(
        "AnnouncementPosts", back_populates="user"
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user"
    )


class ClassSections(Base):
    __tablename__ = "class_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_name: Mapped[str] = mapped_column(String(64), nullable=False)
    section: Mapped[str] = mapped_column(String(8), nullable=False)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "class_name",
            "section",
            "academic_year",
            name="uq_class_sections_name_section_year",
        ),
    )

    student_enrollments: Mapped[List["StudentEnrollments"]] = relationship(
        "StudentEnrollments", back_populates="class_section"
    )
    attendances: Mapped[List["Attendance"]] = relationship(
        "Attendance", back_populates="class_section"
    )
    class_subjects: Mapped[List["ClassSubjects"]] = relationship(
        "ClassSubjects", back_populates="class_section"
    )
    exams: Mapped[List["Exams"]] = relationship("Exams", back_populates="class_section")


class Students(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    father_name: Mapped[str] = mapped_column(String(128), nullable=False)
    mother_name: Mapped[str] = mapped_column(String(128), nullable=False)
    admission_date: Mapped[date] = mapped_column(Date, nullable=False)
    reg_no: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)

    __table_args__ = (Index("ix_students_user_id", "user_id"),)

    user: Mapped["Users"] = relationship("Users", back_populates="students")
    student_enrollments: Mapped[List["StudentEnrollments"]] = relationship(
        "StudentEnrollments", back_populates="student"
    )
    attendances: Mapped[List["Attendance"]] = relationship(
        "Attendance", back_populates="student"
    )
    marks: Mapped[List["Marks"]] = relationship("Marks", back_populates="student")


class Admins(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (Index("ix_admins_user_id", "user_id"),)

    user: Mapped["Users"] = relationship("Users", back_populates="admins")


class StudentEnrollments(Base):
    __tablename__ = "student_enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    class_section_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_sections.id", ondelete="CASCADE"), nullable=False
    )
    roll_no: Mapped[int] = mapped_column(Integer, nullable=False)

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

    student: Mapped["Students"] = relationship(
        "Students", back_populates="student_enrollments"
    )
    class_section: Mapped["ClassSections"] = relationship(
        "ClassSections", back_populates="student_enrollments"
    )


class Subjects(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    staff_subjects: Mapped[List["StaffSubjects"]] = relationship(
        "StaffSubjects", back_populates="subject"
    )
    class_subjects: Mapped[List["ClassSubjects"]] = relationship(
        "ClassSubjects", back_populates="subject"
    )


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    position: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (Index("ix_staff_user_id", "user_id"),)

    user: Mapped["Users"] = relationship("Users", back_populates="staff")
    staff_subjects: Mapped[List["StaffSubjects"]] = relationship(
        "StaffSubjects", back_populates="staff"
    )
    teaching_assignments: Mapped[List["TeachingAssignments"]] = relationship(
        "TeachingAssignments", back_populates="staff"
    )


class StaffSubjects(Base):
    """Many-to-many: a staff member can teach multiple subjects."""

    __tablename__ = "staff_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("staff_id", "subject_id", name="uq_staff_subjects"),
        Index("ix_staff_subjects_staff_id", "staff_id"),
        Index("ix_staff_subjects_subject_id", "subject_id"),
    )

    staff: Mapped["Staff"] = relationship("Staff", back_populates="staff_subjects")
    subject: Mapped["Subjects"] = relationship("Subjects", back_populates="staff_subjects")


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    class_section_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_sections.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False)

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

    student: Mapped["Students"] = relationship("Students", back_populates="attendances")
    class_section: Mapped["ClassSections"] = relationship(
        "ClassSections", back_populates="attendances"
    )


class AnnouncementPosts(Base):
    __tablename__ = "announcement_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)
    issuer: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # server_default ensures Alembic generates proper DDL
    date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )

    __table_args__ = (
        Index("ix_announcement_posts_issuer", "issuer"),
        Index("ix_announcement_posts_date", "date"),
    )

    announcement_roles: Mapped[List["AnnouncementRoles"]] = relationship(
        "AnnouncementRoles",
        back_populates="announcement_post",
        cascade="all, delete-orphan",
    )
    user: Mapped[Optional["Users"]] = relationship(
        "Users", back_populates="announcement_posts"
    )


class AnnouncementRoles(Base):
    __tablename__ = "announcement_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    announcement_post_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("announcement_posts.id", ondelete="CASCADE"), nullable=False
    )
    for_role: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "announcement_post_id", "for_role", name="uq_announcement_roles"
        ),
        CheckConstraint(
            _ROLE_CHECK.replace("role", "for_role"), name="ck_announcement_roles_role"
        ),
        Index("ix_announcement_roles_post_id", "announcement_post_id"),
    )

    announcement_post: Mapped["AnnouncementPosts"] = relationship(
        "AnnouncementPosts", back_populates="announcement_roles"
    )


class ClassSubjects(Base):
    __tablename__ = "class_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_section_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_sections.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("class_section_id", "subject_id", name="uq_class_subjects"),
        Index("ix_class_subjects_class_section_id", "class_section_id"),
        Index("ix_class_subjects_subject_id", "subject_id"),
    )

    class_section: Mapped["ClassSections"] = relationship(
        "ClassSections", back_populates="class_subjects"
    )
    subject: Mapped["Subjects"] = relationship("Subjects", back_populates="class_subjects")
    teaching_assignments: Mapped[List["TeachingAssignments"]] = relationship(
        "TeachingAssignments", back_populates="class_subject"
    )
    exam_subjects: Mapped[List["ExamSubjects"]] = relationship(
        "ExamSubjects", back_populates="class_subject"
    )


class TeachingAssignments(Base):
    __tablename__ = "teaching_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    class_subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_subjects.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "staff_id", "class_subject_id", name="uq_teaching_assignments"
        ),
        Index("ix_teaching_assignments_staff_id", "staff_id"),
        Index("ix_teaching_assignments_class_subject_id", "class_subject_id"),
    )

    staff: Mapped["Staff"] = relationship("Staff", back_populates="teaching_assignments")
    class_subject: Mapped["ClassSubjects"] = relationship(
        "ClassSubjects", back_populates="teaching_assignments"
    )


class Exams(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    class_section_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_sections.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    exam_type: Mapped[str] = mapped_column(
        String(25), server_default="official", nullable=False
    )
    status: Mapped[str] = mapped_column(String, server_default="pending", nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("class_section_id", "name", name="uq_exams_section_name"),
        Index("ix_exams_class_section_id", "class_section_id"),
        CheckConstraint(_EXAM_STATUS_CHECK, name="ck_exam_status"),
    )

    class_section: Mapped["ClassSections"] = relationship(
        "ClassSections", back_populates="exams"
    )
    exam_subjects: Mapped[List["ExamSubjects"]] = relationship(
        "ExamSubjects", back_populates="exam", cascade="all, delete-orphan"
    )


class ExamSubjects(Base):
    __tablename__ = "exam_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False
    )
    class_subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_subjects.id", ondelete="CASCADE"), nullable=False
    )
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("exam_id", "class_subject_id", name="uq_exam_subjects"),
        CheckConstraint("max_marks > 0", name="ck_exam_subjects_max_marks"),
        Index("ix_exam_subjects_exam_id", "exam_id"),
        Index("ix_exam_subjects_subject_id", "class_subject_id"),
    )

    exam: Mapped["Exams"] = relationship("Exams", back_populates="exam_subjects")
    class_subject: Mapped["ClassSubjects"] = relationship(
        "ClassSubjects", back_populates="exam_subjects"
    )
    marks: Mapped[List["Marks"]] = relationship(
        "Marks", back_populates="exam_subject", cascade="all, delete-orphan"
    )


class Marks(Base):
    __tablename__ = "marks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    exam_subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exam_subjects.id", ondelete="CASCADE"), nullable=False
    )
    marks_obtained: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "student_id", "exam_subject_id", name="uq_marks_student_exam_subject"
        ),
        CheckConstraint("marks_obtained >= 0", name="ck_marks_obtained_non_negative"),
        Index("ix_marks_student_id", "student_id"),
        Index("ix_marks_exam_subject_id", "exam_subject_id"),
    )

    student: Mapped["Students"] = relationship("Students", back_populates="marks")
    exam_subject: Mapped["ExamSubjects"] = relationship(
        "ExamSubjects", back_populates="marks"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # server_default instead of Python-side default — Alembic generates correct DDL
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    user: Mapped["Users"] = relationship("Users", back_populates="refresh_tokens")
