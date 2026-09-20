"""
Automated Test Suite for KIET Smart Attendance and Performance Analyser
Tests:
1. Performance Rules Engine
2. Role-Based Access Controls (RBAC)
3. Authentication & Sessions
4. Student Dashboard isolation
5. Branch Comparison Analytics & Chart Datasets
6. Attendance & Marks updates
"""

import unittest
from app import app
from database import calculate_status_and_message, get_db

class KIETSmartAttendanceTestCase(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def tearDown(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE email = 'test999@kiet.edu'")
        cursor.execute("DELETE FROM students WHERE roll_number = '23KIETAI999'")
        conn.commit()
        conn.close()

    # --------------------------------------------------------------------------
    # 1. Performance Rules Engine Verification
    # --------------------------------------------------------------------------
    def test_performance_rules(self):
        # Rule 1: Needs Attention (Att < 70 OR Marks < 40)
        status, msg = calculate_status_and_message(69.9, 85.0)
        self.assertEqual(status, "Needs Attention")

        status, msg = calculate_status_and_message(85.0, 39.0)
        self.assertEqual(status, "Needs Attention")

        status, msg = calculate_status_and_message(65.0, 35.0)
        self.assertEqual(status, "Needs Attention")

        # Rule 2: Monitor (Att 70-74.9 OR Marks 40-49.9)
        status, msg = calculate_status_and_message(72.0, 80.0)
        self.assertEqual(status, "Monitor")

        status, msg = calculate_status_and_message(85.0, 45.0)
        self.assertEqual(status, "Monitor")

        status, msg = calculate_status_and_message(71.0, 48.0)
        self.assertEqual(status, "Monitor")

        # Rule 3: On Track (Att >= 75 AND Marks >= 50)
        status, msg = calculate_status_and_message(75.0, 50.0)
        self.assertEqual(status, "On Track")

        status, msg = calculate_status_and_message(92.0, 88.0)
        self.assertEqual(status, "On Track")

    # --------------------------------------------------------------------------
    # 2. Public Pages
    # --------------------------------------------------------------------------
    def test_landing_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"KIET Institutions", response.data)
        self.assertIn(b"KIET Smart Attendance and Performance Analyser", response.data)
        self.assertIn(b"Built with Python", response.data)

    def test_login_page_renders(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Academic Portal Login", response.data)

    # --------------------------------------------------------------------------
    # 3. Authentication Flow
    # --------------------------------------------------------------------------
    def test_admin_login_success(self):
        response = self.client.post('/login', data={
            'email': 'admin@kiet.edu',
            'password': 'Admin@123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Academic Analytics Dashboard", response.data)
        self.assertIn(b"Total Students", response.data)

    def test_student_login_success(self):
        response = self.client.post('/login', data={
            'email': '23ai001@kiet.edu',
            'password': 'Student@123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Student Dashboard", response.data)
        self.assertIn(b"Personalised Academic Recommendation", response.data)

    def test_invalid_login_fails(self):
        response = self.client.post('/login', data={
            'email': 'admin@kiet.edu',
            'password': 'WrongPassword999'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid email or password", response.data)

    # --------------------------------------------------------------------------
    # 4. Role-Based Access Control (RBAC) Protection
    # --------------------------------------------------------------------------
    def test_unauthenticated_protected_routes(self):
        # Admin dashboard requires login
        resp = self.client.get('/admin/dashboard', follow_redirects=True)
        self.assertIn(b"Please log in to access this page", resp.data)

        # Student management requires login
        resp = self.client.get('/students', follow_redirects=True)
        self.assertIn(b"Please log in to access this page", resp.data)

        # Attendance requires login
        resp = self.client.get('/attendance', follow_redirects=True)
        self.assertIn(b"Please log in to access this page", resp.data)

        # Marks requires login
        resp = self.client.get('/marks', follow_redirects=True)
        self.assertIn(b"Please log in to access this page", resp.data)

        # Branch comparison requires login
        resp = self.client.get('/branch-comparison', follow_redirects=True)
        self.assertIn(b"Please log in to access this page", resp.data)

    def test_student_cannot_access_admin_pages(self):
        # Log in as Student
        self.client.post('/login', data={
            'email': '23ai001@kiet.edu',
            'password': 'Student@123'
        }, follow_redirects=True)

        # Try to access Admin Dashboard
        resp = self.client.get('/admin/dashboard', follow_redirects=True)
        self.assertIn(b"Access denied: Students cannot access administrative management pages", resp.data)
        self.assertIn(b"Student Dashboard", resp.data)

        # Try to access Student Management
        resp = self.client.get('/students', follow_redirects=True)
        self.assertIn(b"Access denied", resp.data)

        # Try to access Attendance Recording
        resp = self.client.get('/attendance', follow_redirects=True)
        self.assertIn(b"Access denied", resp.data)

        # Try to access Marks Recording
        resp = self.client.get('/marks', follow_redirects=True)
        self.assertIn(b"Access denied", resp.data)

        # Try to access Branch Comparison
        resp = self.client.get('/branch-comparison', follow_redirects=True)
        self.assertIn(b"Access denied", resp.data)

    # --------------------------------------------------------------------------
    # 5. Branch Comparison & Insights
    # --------------------------------------------------------------------------
    def test_branch_comparison_data(self):
        # Log in as Admin
        self.client.post('/login', data={
            'email': 'admin@kiet.edu',
            'password': 'Admin@123'
        }, follow_redirects=True)

        resp = self.client.get('/branch-comparison')
        self.assertEqual(resp.status_code, 200)
        # Check all 5 branches in output
        self.assertIn(b"AI", resp.data)
        self.assertIn(b"AIDS", resp.data)
        self.assertIn(b"AIML", resp.data)
        self.assertIn(b"DS", resp.data)
        self.assertIn(b"CYBER", resp.data)

    # --------------------------------------------------------------------------
    # 6. Student Lifecycle & Data Operations
    # --------------------------------------------------------------------------
    def test_student_crud_and_calculations(self):
        # Log in as Admin
        self.client.post('/login', data={
            'email': 'admin@kiet.edu',
            'password': 'Admin@123'
        }, follow_redirects=True)

        # 1. Add Student
        add_resp = self.client.post('/students/add', data={
            'name': 'Test New Student',
            'roll_number': '23KIETAI999',
            'email': 'test999@kiet.edu',
            'password': 'Student@123',
            'branch': 'AI',
            'semester': '1',
            'section': 'A'
        }, follow_redirects=True)
        self.assertIn(b"enrolled successfully", add_resp.data)

        # Verify in database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM students WHERE roll_number = '23KIETAI999'")
        st_row = cursor.fetchone()
        self.assertIsNotNone(st_row)
        student_id = st_row['id']
        conn.close()

        # 2. Edit Student
        edit_resp = self.client.post(f'/students/edit/{student_id}', data={
            'name': 'Test Updated Student',
            'roll_number': '23KIETAI999',
            'email': 'test999@kiet.edu',
            'branch': 'AI',
            'semester': '1',
            'section': 'B'
        }, follow_redirects=True)
        self.assertIn(b"updated successfully", edit_resp.data)

        # 3. Save Attendance with low value across subjects to trigger Needs Attention (< 70% average)
        for sub_id in [1, 2]:
            self.client.post('/attendance/save', data={
                'branch': 'AI',
                'sem': '1',
                'subject_id': str(sub_id),
                'student_ids': [str(student_id)],
                f'total_classes_{student_id}': '40',
                f'attended_classes_{student_id}': '10' # 25% attendance
            }, follow_redirects=True)

        # 4. Save Marks with low value
        for sub_id in [1, 2]:
            self.client.post('/marks/save', data={
                'branch': 'AI',
                'sem': '1',
                'subject_id': str(sub_id),
                'student_ids': [str(student_id)],
                f'marks_obtained_{student_id}': '20',
                f'max_marks_{student_id}': '100'
            }, follow_redirects=True)

        # Verify recommendation updated to Needs Attention
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM recommendations WHERE student_id = ?", (student_id,))
        rec_status = cursor.fetchone()['status']
        conn.close()
        self.assertEqual(rec_status, "Needs Attention")

        # 5. Delete Student
        del_resp = self.client.post(f'/students/delete/{student_id}', follow_redirects=True)
        self.assertIn(b"deleted successfully", del_resp.data)

    def test_password_change(self):
        # Log in as teacher
        self.client.post('/login', data={
            'email': 'teacher.ai@kiet.edu',
            'password': 'Teacher@123'
        }, follow_redirects=True)

        # Change password
        resp = self.client.post('/profile/change-password', data={
            'current_password': 'Teacher@123',
            'new_password': 'NewPassword@123',
            'confirm_new_password': 'NewPassword@123'
        }, follow_redirects=True)
        self.assertIn(b"password has been changed successfully", resp.data)

        # Log out
        self.client.get('/logout')

        # Log in with new password
        resp2 = self.client.post('/login', data={
            'email': 'teacher.ai@kiet.edu',
            'password': 'NewPassword@123'
        }, follow_redirects=True)
        self.assertIn(b"Welcome back", resp2.data)

        # Restore original password for tests repeatability
        self.client.post('/profile/change-password', data={
            'current_password': 'NewPassword@123',
            'new_password': 'Teacher@123',
            'confirm_new_password': 'Teacher@123'
        }, follow_redirects=True)

if __name__ == '__main__':
    unittest.main()

