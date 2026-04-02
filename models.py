from pydantic import BaseModel
from typing import List

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from db import Base


class User(BaseModel):
    id: int
    username: str
    role: str


class UserInDb(User):
    password_hash: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str


class CreateAttendance(BaseModel):
    student_id: int
    class_section_id: int
    status: str


class AnnouncementCreate(BaseModel):
    subject: str
    details: str
    roles: List[str]


class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    password_hash = Column(String)
    role = Column(String)

    students = relationship("Students", back_populates="user", uselist=False)
    staff = relationship("Staff", back_populates="user", uselist=False)
    announcement_posts = relationship("AnnouncementPosts", back_populates="user")


class ClassSections(Base):
    __tablename__ = "class_sections"

    id = Column(Integer, primary_key=True, index=True)
    class_name = Column(String)
    section = Column(String)
    academic_year = Column(Integer)

    student_enrollments = relationship(
        "StudentEnrollments", back_populates="class_sections"
    )

    attendances = relationship("Attendance", back_populates="class_sections")
    class_subjects = relationship("ClassSubjects", back_populates="class_sections")
    exams = relationship("Exams", back_populates="class_sections")


class Students(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    father_name = Column(String)
    mother_name = Column(String)
    admission_date = Column(Date)
    reg_no = Column(Integer, unique=True)

    user = relationship("Users", back_populates="students")
    student_enrollments = relationship("StudentEnrollments", back_populates="students")

    attendances = relationship("Attendance", back_populates="students")
    marks = relationship("Marks", back_populates="students")


class StudentEnrollments(Base):
    __tablename__ = "student_enrollments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    class_section_id = Column(Integer, ForeignKey("class_sections.id"))
    roll_no = Column(Integer)

    __table_args__ = (UniqueConstraint("class_section_id", "roll_no"),)

    students = relationship("Students", back_populates="student_enrollments")
    class_sections = relationship("ClassSections", back_populates="student_enrollments")


class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    name = Column(String)
    position = Column(String)
    subject = Column(Integer, ForeignKey("subjects.id"))

    user = relationship("Users", back_populates="staff")
    subjects = relationship("Subjects", back_populates="staff")
    teaching_assignments = relationship("TeachingAssignments", back_populates="staff")


class Subjects(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

    staff = relationship("Staff", back_populates="subjects")
    class_subjects = relationship("ClassSubjects", back_populates="subjects")
    exam_subjects = relationship("ExamSubjects", back_populates="subjects")


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    class_section_id = Column(Integer, ForeignKey("class_sections.id"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(String(10), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('present', 'absent', 'leave')", name="valid_status"
        ),
    )

    students = relationship("Students", back_populates="attendances")
    class_sections = relationship("ClassSections", back_populates="attendances")


class AnnouncementRoles(Base):
    __tablename__ = "announcement_roles"

    id = Column(Integer, primary_key=True, index=True)
    announcement_post_id = Column(Integer, ForeignKey("announcement_posts.id"))
    for_role = Column(String(50))

    announcement_posts = relationship(
        "AnnouncementPosts", back_populates="announcement_roles"
    )


class AnnouncementPosts(Base):
    __tablename__ = "announcement_posts"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(255))
    details = Column(String)
    issuer = Column(Integer, ForeignKey("users.id"))
    date = Column(Date)

    announcement_roles = relationship(
        "AnnouncementRoles", back_populates="announcement_posts"
    )
    user = relationship("Users", back_populates="announcement_posts")


class ClassSubjects(Base):
    __tablename__ = "class_subjects"

    id = Column(Integer, primary_key=True, index=True)
    class_section_id = Column(Integer, ForeignKey("class_sections.id"))
    subject_id = Column(Integer, ForeignKey("subjects.id"))

    __table_args__ = (UniqueConstraint("class_section_id", "subject_id"),)

    class_sections = relationship("ClassSections", back_populates="class_subjects")
    subjects = relationship("Subjects", back_populates="class_subjects")
    teaching_assignments = relationship("TeachingAssignments", back_populates="class_subjects")


class TeachingAssignments(Base):
    __tablename__ = "teaching_assignments"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"))
    class_subject_id = Column(Integer, ForeignKey("class_subjects.id"))

    staff = relationship("Staff", back_populates="teaching_assignments")
    class_subjects = relationship("ClassSubjects", back_populates="teaching_assignments")


class Exams(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    class_section_id = Column(Integer, ForeignKey("class_sections.id"))

    class_sections = relationship("ClassSections", back_populates="exams")
    exam_subjects = relationship("ExamSubjects", back_populates="exams")


class ExamSubjects(Base):
    __tablename__ = "exam_subjects"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"))
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    max_marks = Column(Integer)

    exams = relationship("Exams", back_populates="exam_subjects")
    subjects = relationship("Subjects", back_populates="exam_subjects")
    marks = relationship("Marks", back_populates="exam_subjects")


class Marks(Base):
    __tablename__ = "marks"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    exam_subject_id = Column(Integer, ForeignKey("exam_subjects.id"))
    marks_obtained = Column(Integer)

    __table_args__ = (UniqueConstraint("student_id", "exam_subject_id"),)

    students = relationship("Students", back_populates="marks")
    exam_subjects = relationship("ExamSubjects", back_populates="marks")
