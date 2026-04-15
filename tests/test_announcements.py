import unittest
from datetime import date
from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from db import Base, get_db
from models import (
    AnnouncementCreate,
    AnnouncementPosts,
    AnnouncementRoles,
    User,
    UserRole,
    Users,
)
from routes.announcements import (
    create_announcement,
    list_announcements,
    list_my_announcements,
    delete_announcement,
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


class AnnouncementTests(unittest.IsolatedAsyncioTestCase):
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

        # Create teacher and student users
        self.teacher_user = Users(username="teacher1", password_hash="x", role=UserRole.TEACHER)
        self.other_teacher = Users(username="teacher2", password_hash="x", role=UserRole.TEACHER)
        self.student_user = Users(username="student1", password_hash="x", role=UserRole.STUDENT)
        self.db.add_all([self.teacher_user, self.other_teacher, self.student_user])
        self.db.commit()
        for u in [self.teacher_user, self.other_teacher, self.student_user]:
            self.db.refresh(u)

        self.teacher_model = User(id=self.teacher_user.id, username=self.teacher_user.username, role=UserRole.TEACHER)
        self.other_teacher_model = User(id=self.other_teacher.id, username=self.other_teacher.username, role=UserRole.TEACHER)
        self.student_model = User(id=self.student_user.id, username=self.student_user.username, role=UserRole.STUDENT)

    async def asyncTearDown(self):
        self.db.close()

    async def test_create_announcement_success(self):
        data = AnnouncementCreate(subject="Test", details="Details", roles=[UserRole.STUDENT, UserRole.TEACHER])
        result = create_announcement(data, self.teacher_model, self.db)
        
        self.assertIsNotNone(result.id)
        post = self.db.query(AnnouncementPosts).filter(AnnouncementPosts.id == result.id).first()
        self.assertEqual(post.subject, "Test")
        self.assertEqual(post.issuer, self.teacher_model.id)
        
        roles = self.db.query(AnnouncementRoles).filter(AnnouncementRoles.announcement_post_id == result.id).all()
        self.assertEqual(len(roles), 2)
        role_names = [r.for_role for r in roles]
        self.assertIn(UserRole.STUDENT, role_names)
        self.assertIn(UserRole.TEACHER, role_names)

    async def test_create_announcement_invalid_roles(self):
        # Empty roles
        data = AnnouncementCreate(subject="Test", details="Details", roles=[])
        with self.assertRaises(HTTPException) as context:
            create_announcement(data, self.teacher_model, self.db)
        self.assertEqual(context.exception.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Invalid role name (though pydantic might catch it first if using TestClient,
        # but here we call the function directly with AnnouncementCreate model)
        # Note: AnnouncementCreate roles is List[UserRole], so we must pass valid enums.
        # But create_announcement checks it anyway.

    async def test_list_announcements_filtering(self):
        # Teacher creates one for students, one for teachers
        post_for_students = AnnouncementPosts(subject="For Students", details="...", issuer=self.teacher_user.id, date=date.today())
        self.db.add(post_for_students)
        self.db.commit()
        self.db.refresh(post_for_students)
        self.db.add(AnnouncementRoles(announcement_post_id=post_for_students.id, for_role=UserRole.STUDENT))

        post_for_teachers = AnnouncementPosts(subject="For Teachers", details="...", issuer=self.teacher_user.id, date=date.today())
        self.db.add(post_for_teachers)
        self.db.commit()
        self.db.refresh(post_for_teachers)
        self.db.add(AnnouncementRoles(announcement_post_id=post_for_teachers.id, for_role=UserRole.TEACHER))
        self.db.commit()

        # Student should only see student announcement
        student_list = list_announcements(self.student_model, self.db)
        self.assertEqual(len(student_list), 1)
        self.assertEqual(student_list[0].subject, "For Students")

        # Teacher should only see teacher announcement
        teacher_list = list_announcements(self.teacher_model, self.db)
        self.assertEqual(len(teacher_list), 1)
        self.assertEqual(teacher_list[0].subject, "For Teachers")

    async def test_list_my_announcements(self):
        # teacher1 creates two posts
        p1 = AnnouncementPosts(subject="P1", details="...", issuer=self.teacher_user.id, date=date.today())
        p2 = AnnouncementPosts(subject="P2", details="...", issuer=self.teacher_user.id, date=date.today())
        self.db.add_all([p1, p2])
        self.db.commit()
        self.db.add(AnnouncementRoles(announcement_post_id=p1.id, for_role=UserRole.TEACHER))
        self.db.add(AnnouncementRoles(announcement_post_id=p2.id, for_role=UserRole.TEACHER))
        self.db.commit()

        # teacher2 creates one post
        p3 = AnnouncementPosts(subject="P3", details="...", issuer=self.other_teacher.id, date=date.today())
        self.db.add(p3)
        self.db.commit()
        self.db.add(AnnouncementRoles(announcement_post_id=p3.id, for_role=UserRole.TEACHER))
        self.db.commit()

        my_list = list_my_announcements(self.teacher_model, self.db)
        self.assertEqual(len(my_list), 2)
        subjects = [p.subject for p in my_list]
        self.assertIn("P1", subjects)
        self.assertIn("P2", subjects)
        self.assertNotIn("P3", subjects)

    async def test_delete_announcement_success(self):
        post = AnnouncementPosts(subject="Delete Me", details="...", issuer=self.teacher_user.id, date=date.today())
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        self.db.add(AnnouncementRoles(announcement_post_id=post.id, for_role=UserRole.TEACHER))
        self.db.commit()

        result = delete_announcement(post.id, self.teacher_model, self.db)
        self.assertTrue(result.done)
        
        # Verify it's gone from DB
        db_post = self.db.query(AnnouncementPosts).filter(AnnouncementPosts.id == post.id).first()
        self.assertIsNone(db_post)
        db_roles = self.db.query(AnnouncementRoles).filter(AnnouncementRoles.announcement_post_id == post.id).all()
        self.assertEqual(len(db_roles), 0)

    async def test_delete_announcement_not_issuer_forbidden(self):
        post = AnnouncementPosts(subject="Safe Post", details="...", issuer=self.teacher_user.id, date=date.today())
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)

        with self.assertRaises(HTTPException) as context:
            delete_announcement(post.id, self.other_teacher_model, self.db)
        self.assertEqual(context.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(context.exception.detail, "Not allowed to delete this announcement")

    async def test_delete_announcement_not_found(self):
        with self.assertRaises(HTTPException) as context:
            delete_announcement(999, self.teacher_model, self.db)
        self.assertEqual(context.exception.status_code, status.HTTP_404_NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
