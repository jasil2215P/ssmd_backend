import unittest

from main import app


class OpenAPIContractTests(unittest.TestCase):
    def test_openapi_uses_canonical_route_names(self):
        schema = app.openapi()
        paths = schema["paths"]

        expected_paths = {
            "/auth/tokens",
            "/auth/tokens/refresh",
            "/health",
            "/announcements",
            "/announcements/mine",
            "/announcements/{announcement_id}",
            "/attendance/records",
            "/attendance/records/bulk",
            "/attendance/records/today",
            "/students/{student_id}",
            "/class-sections",
            "/class-sections/{class_section_id}/students",
            "/users/me",
        }
        hidden_legacy_paths = {
            "/token",
            "/refresh",
            "/health_check",
            "/announcements/all",
            "/announcements/me",
            "/attendance",
            "/attendance/bulk",
            "/attendance/today",
            "/students/{student_id}/all",
            "/classes",
            "/classes/{class_section_id}/students",
            "/user/me",
        }

        for path in expected_paths:
            self.assertIn(path, paths)

        for path in hidden_legacy_paths:
            self.assertNotIn(path, paths)

    def test_openapi_exposes_response_models(self):
        schema = app.openapi()
        paths = schema["paths"]

        announcements_response = paths["/announcements"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        bulk_attendance_response = paths["/attendance/records/bulk"]["post"][
            "responses"
        ]["200"]["content"]["application/json"]["schema"]
        user_profile_response = paths["/users/me"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]

        self.assertTrue(
            announcements_response["items"]["$ref"].endswith("AnnouncementResponse")
        )
        self.assertTrue(
            bulk_attendance_response["$ref"].endswith("OperationStatusResponse")
        )
        self.assertEqual(len(user_profile_response["anyOf"]), 3)

    def test_openapi_exposes_role_enums_for_request_and_response_models(self):
        schema = app.openapi()
        components = schema["components"]["schemas"]

        user_role_schema = components["UserRole"]
        announcement_create_schema = components["AnnouncementCreate"]
        generic_user_role_response_schema = components["GenericUserRoleResponse"]

        self.assertEqual(user_role_schema["type"], "string")
        self.assertEqual(user_role_schema["enum"], ["student", "teacher"])
        self.assertTrue(
            announcement_create_schema["properties"]["roles"]["items"]["$ref"].endswith(
                "UserRole"
            )
        )
        self.assertTrue(
            generic_user_role_response_schema["properties"]["role"]["$ref"].endswith(
                "UserRole"
            )
        )

    def test_openapi_exposes_attendance_status_enums(self):
        schema = app.openapi()
        components = schema["components"]["schemas"]

        attendance_status_schema = components["AttendanceStatus"]
        create_attendance_schema = components["CreateAttendance"]
        attendance_record_response_schema = components["AttendanceRecordResponse"]

        self.assertEqual(attendance_status_schema["type"], "string")
        self.assertEqual(attendance_status_schema["enum"], ["present", "absent"])
        self.assertTrue(
            create_attendance_schema["properties"]["status"]["$ref"].endswith(
                "AttendanceStatus"
            )
        )
        self.assertTrue(
            attendance_record_response_schema["properties"]["status"]["$ref"].endswith(
                "AttendanceStatus"
            )
        )


if __name__ == "__main__":
    unittest.main()
