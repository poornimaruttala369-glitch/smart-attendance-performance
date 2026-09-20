import re
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from database import (
    get_db, init_db, update_student_recommendation,
    calculate_status_and_message
)
from data.first_year_subjects import get_subjects_by_semester

app = Flask(__name__)
app.config.from_object(Config)

# ==============================================================================
# Authentication Decorators & Role Guards
# ==============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def teacher_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        if session.get('role') not in ['admin', 'teacher']:
            flash("Access denied: Students cannot access administrative management pages.", "danger")
            return redirect(url_for('student_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def student_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access your student portal.", "warning")
            return redirect(url_for('login'))
        if session.get('role') != 'student':
            flash("Redirected to faculty dashboard.", "info")
            return redirect(url_for('admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Context processor for global template variables
@app.context_processor
def inject_global_vars():
    return {
        'branches': Config.BRANCHES,
        'branch_codes': Config.BRANCH_CODES,
        'semesters': Config.SEMESTERS
    }

# ==============================================================================
# Public & Authentication Routes
# ==============================================================================

@app.route('/')
def index():
    """Landing Page showcasing KIET Institutions and project objectives."""
    return render_template('index.html', active_page='home')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login route with email validation and role-based redirects."""
    if 'user_id' in session:
        if session.get('role') == 'student':
            return redirect(url_for('student_dashboard'))
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash("Please provide both email address and password.", "danger")
            return render_template('login.html', email=email, active_page='login')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['email'] = user['email']
            session['role'] = user['role']
            session['branch'] = user['branch']
            session['semester'] = user['semester']

            flash(f"Welcome back, {user['name']}!", "success")
            if user['role'] == 'student':
                return redirect(url_for('student_dashboard'))
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid email or password. Please verify your credentials.", "danger")
            return render_template('login.html', email=email, active_page='login')

    return render_template('login.html', active_page='login')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Teacher & Admin Registration with validation and passcode protection."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'teacher')
        branch = request.form.get('branch', 'AI')
        semester = int(request.form.get('semester', 1))
        admin_key = request.form.get('admin_key', '').strip()

        form_data = {
            'name': name, 'email': email, 'role': role,
            'branch': branch, 'semester': semester
        }

        # Validation
        if not name or not email or not password or not confirm_password:
            flash("All fields are mandatory.", "danger")
            return render_template('signup.html', form_data=form_data, active_page='signup')

        # Email format validation
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(email_pattern, email):
            flash("Please enter a valid email address.", "danger")
            return render_template('signup.html', form_data=form_data, active_page='signup')

        if password != confirm_password:
            flash("Passwords do not match. Please re-enter.", "danger")
            return render_template('signup.html', form_data=form_data, active_page='signup')

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('signup.html', form_data=form_data, active_page='signup')

        # Admin passcode requirement
        if role == 'admin':
            if admin_key != 'KIET@Admin2024':
                flash("Incorrect Administrator Passcode. Only authorized HODs can create Admin accounts.", "danger")
                return render_template('signup.html', form_data=form_data, active_page='signup')

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
        if cursor.fetchone():
            conn.close()
            flash("An account with this email address already exists. Please log in.", "warning")
            return render_template('signup.html', form_data=form_data, active_page='signup')

        pw_hash = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role, branch, semester)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, email, pw_hash, role, branch, semester))
        conn.commit()
        conn.close()

        flash("Registration successful! You can now log in with your credentials.", "success")
        return redirect(url_for('login'))

    return render_template('signup.html', form_data={'role': 'teacher', 'branch': 'AI', 'semester': 1}, active_page='signup')

@app.route('/logout')
def logout():
    """Clear session and log out."""
    session.clear()
    flash("You have been securely logged out.", "info")
    return redirect(url_for('login'))

# ==============================================================================
# Admin / Teacher Dashboard & Analytics
# ==============================================================================

@app.route('/admin/dashboard')
@teacher_or_admin_required
def admin_dashboard():
    """Main administrative dashboard with summary cards and at-risk students."""
    conn = get_db()
    cursor = conn.cursor()

    # Total students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    # Overall Average Attendance
    cursor.execute("SELECT COALESCE(AVG(attendance_percentage), 0.0) FROM attendance")
    overall_avg_attendance = round(cursor.fetchone()[0], 1)

    # Overall Average Marks
    cursor.execute("SELECT COALESCE(AVG(percentage), 0.0) FROM marks")
    overall_avg_marks = round(cursor.fetchone()[0], 1)

    # Students Needing Attention count
    cursor.execute("SELECT COUNT(*) FROM recommendations WHERE status = 'Needs Attention'")
    needs_attention_count = cursor.fetchone()[0]

    # Branch-wise statistics
    branch_distribution = []
    best_marks_branch = {'branch': 'N/A', 'avg_marks': 0.0}
    highest_att_branch = {'branch': 'N/A', 'avg_att': 0.0}

    for b in Config.BRANCHES:
        b_code = b['code']
        # Student count
        cursor.execute("SELECT COUNT(*) FROM students WHERE branch = ?", (b_code,))
        b_count = cursor.fetchone()[0]

        # Avg attendance
        cursor.execute("""
            SELECT COALESCE(AVG(a.attendance_percentage), 0.0)
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE s.branch = ?
        """, (b_code,))
        b_att = round(cursor.fetchone()[0], 1)

        # Avg marks
        cursor.execute("""
            SELECT COALESCE(AVG(m.percentage), 0.0)
            FROM marks m
            JOIN students s ON m.student_id = s.id
            WHERE s.branch = ?
        """, (b_code,))
        b_marks = round(cursor.fetchone()[0], 1)

        branch_distribution.append({
            'branch': b_code,
            'name': b['name'],
            'count': b_count,
            'avg_att': b_att,
            'avg_marks': b_marks
        })

        if b_marks > best_marks_branch['avg_marks']:
            best_marks_branch = {'branch': b_code, 'avg_marks': b_marks}
        if b_att > highest_att_branch['avg_att']:
            highest_att_branch = {'branch': b_code, 'avg_att': b_att}

    # Students Needing Attention Detailed Table
    cursor.execute("""
        SELECT 
            s.id as student_id,
            u.name,
            s.roll_number,
            s.branch,
            s.semester,
            s.section,
            r.status,
            r.message,
            COALESCE(att.avg_att, 0.0) as avg_attendance,
            COALESCE(mk.avg_marks, 0.0) as avg_marks
        FROM students s
        JOIN users u ON s.user_id = u.id
        JOIN recommendations r ON s.id = r.student_id
        LEFT JOIN (
            SELECT student_id, ROUND(AVG(attendance_percentage), 1) as avg_att
            FROM attendance GROUP BY student_id
        ) att ON s.id = att.student_id
        LEFT JOIN (
            SELECT student_id, ROUND(AVG(percentage), 1) as avg_marks
            FROM marks GROUP BY student_id
        ) mk ON s.id = mk.student_id
        WHERE r.status = 'Needs Attention'
        ORDER BY avg_attendance ASC, avg_marks ASC
    """)
    at_risk_students = cursor.fetchall()

    conn.close()

    stats = {
        'total_students': total_students,
        'overall_avg_attendance': overall_avg_attendance,
        'overall_avg_marks': overall_avg_marks,
        'needs_attention_count': needs_attention_count,
        'best_marks_branch': best_marks_branch,
        'highest_att_branch': highest_att_branch
    }

    return render_template(
        'admin_dashboard.html',
        stats=stats,
        branch_distribution=branch_distribution,
        at_risk_students=at_risk_students,
        active_page='dashboard'
    )

# ==============================================================================
# Student Management
# ==============================================================================

@app.route('/students')
@teacher_or_admin_required
def students_view():
    """List all students with search and filter capabilities."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            s.id,
            u.name,
            u.email,
            s.roll_number,
            s.branch,
            s.semester,
            s.section,
            COALESCE(r.status, 'On Track') as status,
            COALESCE(r.message, '') as message,
            COALESCE(att.avg_att, 0.0) as avg_attendance,
            COALESCE(mk.avg_marks, 0.0) as avg_marks
        FROM students s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN recommendations r ON s.id = r.student_id
        LEFT JOIN (
            SELECT student_id, ROUND(AVG(attendance_percentage), 1) as avg_att
            FROM attendance GROUP BY student_id
        ) att ON s.id = att.student_id
        LEFT JOIN (
            SELECT student_id, ROUND(AVG(percentage), 1) as avg_marks
            FROM marks GROUP BY student_id
        ) mk ON s.id = mk.student_id
        ORDER BY s.branch ASC, s.roll_number ASC
    """)
    students = cursor.fetchall()
    conn.close()

    return render_template('students.html', students=students, active_page='students')

@app.route('/students/add', methods=['POST'])
@teacher_or_admin_required
def add_student():
    """Create a new student and student user credentials."""
    name = request.form.get('name', '').strip()
    roll_number = request.form.get('roll_number', '').strip().upper()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', 'Student@123')
    branch = request.form.get('branch', 'AI')
    semester = int(request.form.get('semester', 1))
    section = request.form.get('section', 'A').upper()

    if not name or not roll_number or not email:
        flash("Student name, roll number, and email are required.", "danger")
        return redirect(url_for('students_view'))

    conn = get_db()
    cursor = conn.cursor()

    # Check for duplicate email or roll number
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    if cursor.fetchone():
        conn.close()
        flash("A user with this email address already exists.", "danger")
        return redirect(url_for('students_view'))

    cursor.execute("SELECT id FROM students WHERE roll_number = ?", (roll_number,))
    if cursor.fetchone():
        conn.close()
        flash("A student with this Roll Number already exists.", "danger")
        return redirect(url_for('students_view'))

    # Create User account
    pw_hash = generate_password_hash(password)
    cursor.execute("""
        INSERT INTO users (name, email, password_hash, role, branch, semester)
        VALUES (?, ?, ?, 'student', ?, ?)
    """, (name, email, pw_hash, branch, semester))
    user_id = cursor.lastrowid

    # Create Student record
    cursor.execute("""
        INSERT INTO students (user_id, roll_number, branch, semester, section)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, roll_number, branch, semester, section))
    student_id = cursor.lastrowid

    # Initialize attendance and marks entries for first-year semester subjects
    cursor.execute("SELECT id FROM subjects WHERE semester = ?", (semester,))
    subjects = cursor.fetchall()
    for sub in subjects:
        cursor.execute("""
            INSERT INTO attendance (student_id, subject_id, total_classes, attended_classes, attendance_percentage)
            VALUES (?, ?, 40, 32, 80.0)
        """, (student_id, sub['id']))
        cursor.execute("""
            INSERT INTO marks (student_id, subject_id, marks_obtained, maximum_marks, percentage)
            VALUES (?, ?, 75.0, 100.0, 75.0)
        """, (student_id, sub['id']))

    conn.commit()

    # Compute initial recommendation
    update_student_recommendation(student_id, conn)

    conn.close()
    flash(f"Student {name} ({roll_number}) enrolled successfully.", "success")
    return redirect(url_for('students_view'))

@app.route('/students/edit/<int:student_id>', methods=['POST'])
@teacher_or_admin_required
def edit_student(student_id):
    """Edit student details."""
    name = request.form.get('name', '').strip()
    roll_number = request.form.get('roll_number', '').strip().upper()
    email = request.form.get('email', '').strip().lower()
    branch = request.form.get('branch', 'AI')
    semester = int(request.form.get('semester', 1))
    section = request.form.get('section', 'A').upper()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM students WHERE id = ?", (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        flash("Student record not found.", "danger")
        return redirect(url_for('students_view'))

    user_id = student['user_id']

    # Check for email collision
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ? AND id != ?", (email, user_id))
    if cursor.fetchone():
        conn.close()
        flash("Email address is already in use by another user.", "danger")
        return redirect(url_for('students_view'))

    # Check for roll number collision
    cursor.execute("SELECT id FROM students WHERE roll_number = ? AND id != ?", (roll_number, student_id))
    if cursor.fetchone():
        conn.close()
        flash("Roll number is already in use by another student.", "danger")
        return redirect(url_for('students_view'))

    cursor.execute("""
        UPDATE users SET name = ?, email = ?, branch = ?, semester = ?
        WHERE id = ?
    """, (name, email, branch, semester, user_id))

    cursor.execute("""
        UPDATE students SET roll_number = ?, branch = ?, semester = ?, section = ?
        WHERE id = ?
    """, (roll_number, branch, semester, section, student_id))

    conn.commit()
    conn.close()

    flash(f"Student details for {name} updated successfully.", "success")
    return redirect(url_for('students_view'))

@app.route('/students/delete/<int:student_id>', methods=['POST'])
@teacher_or_admin_required
def delete_student(student_id):
    """Delete student and linked user account."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id, roll_number FROM students WHERE id = ?", (student_id,))
    st = cursor.fetchone()
    if st:
        user_id = st['user_id']
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
        flash(f"Student ({st['roll_number']}) record deleted successfully.", "info")
    else:
        flash("Student not found.", "danger")

    conn.close()
    return redirect(url_for('students_view'))

# ==============================================================================
# Attendance Management
# ==============================================================================

@app.route('/attendance')
@teacher_or_admin_required
def attendance_view():
    """Branch -> Semester -> Subject -> Student attendance management view."""
    branch = request.args.get('branch', 'AI')
    sem = int(request.args.get('sem', 1))
    subject_id = request.args.get('subject_id', type=int)

    conn = get_db()
    cursor = conn.cursor()

    # Fetch subjects for selected semester
    cursor.execute("""
        SELECT id, subject_name, subject_type 
        FROM subjects 
        WHERE semester = ?
        ORDER BY id
    """, (sem,))
    subjects = cursor.fetchall()

    current_subject = None
    student_records = []

    if subjects:
        if not subject_id or not any(s['id'] == subject_id for s in subjects):
            subject_id = subjects[0]['id']

        # Get current subject details
        cursor.execute("SELECT id, subject_name, subject_type FROM subjects WHERE id = ?", (subject_id,))
        current_subject = cursor.fetchone()

        # Load students for this branch & semester with their attendance in this subject
        cursor.execute("""
            SELECT 
                s.id as student_id,
                u.name,
                s.roll_number,
                s.section,
                COALESCE(a.total_classes, 40) as total_classes,
                COALESCE(a.attended_classes, 0) as attended_classes,
                COALESCE(a.attendance_percentage, 0.0) as attendance_percentage
            FROM students s
            JOIN users u ON s.user_id = u.id
            LEFT JOIN attendance a ON s.id = a.student_id AND a.subject_id = ?
            WHERE s.branch = ? AND s.semester = ?
            ORDER BY s.roll_number ASC
        """, (subject_id, branch, sem))
        student_records = cursor.fetchall()

    conn.close()

    return render_template(
        'attendance.html',
        selected_branch=branch,
        selected_sem=sem,
        selected_subject_id=subject_id,
        subjects=subjects,
        current_subject=current_subject,
        student_records=student_records,
        active_page='attendance'
    )

@app.route('/attendance/save', methods=['POST'])
@teacher_or_admin_required
def save_attendance():
    """Save/update attendance records and recalculate student performance status."""
    branch = request.form.get('branch', 'AI')
    sem = int(request.form.get('sem', 1))
    subject_id = int(request.form.get('subject_id'))
    student_ids = request.form.getlist('student_ids')

    conn = get_db()
    cursor = conn.cursor()

    for s_id_str in student_ids:
        s_id = int(s_id_str)
        total = int(request.form.get(f'total_classes_{s_id}', 40))
        attended = int(request.form.get(f'attended_classes_{s_id}', 0))

        if total <= 0:
            total = 1
        if attended > total:
            attended = total
        if attended < 0:
            attended = 0

        pct = round((attended / total) * 100.0, 2)

        cursor.execute("""
            INSERT INTO attendance (student_id, subject_id, total_classes, attended_classes, attendance_percentage, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(student_id, subject_id) DO UPDATE SET
                total_classes = excluded.total_classes,
                attended_classes = excluded.attended_classes,
                attendance_percentage = excluded.attendance_percentage,
                updated_at = CURRENT_TIMESTAMP
        """, (s_id, subject_id, total, attended, pct))

        # Re-evaluate student's overall recommendation
        update_student_recommendation(s_id, conn)

    conn.commit()
    conn.close()

    flash(f"Attendance for {len(student_ids)} students successfully saved and updated.", "success")
    return redirect(url_for('attendance_view', branch=branch, sem=sem, subject_id=subject_id))

# ==============================================================================
# Marks Management
# ==============================================================================

@app.route('/marks')
@teacher_or_admin_required
def marks_view():
    """Branch -> Semester -> Subject -> Student marks entry view."""
    branch = request.args.get('branch', 'AI')
    sem = int(request.args.get('sem', 1))
    subject_id = request.args.get('subject_id', type=int)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, subject_name, subject_type 
        FROM subjects 
        WHERE semester = ?
        ORDER BY id
    """, (sem,))
    subjects = cursor.fetchall()

    current_subject = None
    student_records = []

    if subjects:
        if not subject_id or not any(s['id'] == subject_id for s in subjects):
            subject_id = subjects[0]['id']

        cursor.execute("SELECT id, subject_name, subject_type FROM subjects WHERE id = ?", (subject_id,))
        current_subject = cursor.fetchone()

        cursor.execute("""
            SELECT 
                s.id as student_id,
                u.name,
                s.roll_number,
                s.section,
                COALESCE(m.marks_obtained, 0.0) as marks_obtained,
                COALESCE(m.maximum_marks, 100.0) as maximum_marks,
                COALESCE(m.percentage, 0.0) as percentage
            FROM students s
            JOIN users u ON s.user_id = u.id
            LEFT JOIN marks m ON s.id = m.student_id AND m.subject_id = ?
            WHERE s.branch = ? AND s.semester = ?
            ORDER BY s.roll_number ASC
        """, (subject_id, branch, sem))
        student_records = cursor.fetchall()

    conn.close()

    return render_template(
        'marks.html',
        selected_branch=branch,
        selected_sem=sem,
        selected_subject_id=subject_id,
        subjects=subjects,
        current_subject=current_subject,
        student_records=student_records,
        active_page='marks'
    )

@app.route('/marks/save', methods=['POST'])
@teacher_or_admin_required
def save_marks():
    """Save/update subject marks and re-calculate student status."""
    branch = request.form.get('branch', 'AI')
    sem = int(request.form.get('sem', 1))
    subject_id = int(request.form.get('subject_id'))
    student_ids = request.form.getlist('student_ids')

    conn = get_db()
    cursor = conn.cursor()

    for s_id_str in student_ids:
        s_id = int(s_id_str)
        obtained = float(request.form.get(f'marks_obtained_{s_id}', 0))
        max_marks = float(request.form.get(f'max_marks_{s_id}', 100))

        if max_marks <= 0:
            max_marks = 100.0
        if obtained > max_marks:
            obtained = max_marks
        if obtained < 0:
            obtained = 0.0

        pct = round((obtained / max_marks) * 100.0, 2)

        cursor.execute("""
            INSERT INTO marks (student_id, subject_id, marks_obtained, maximum_marks, percentage, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(student_id, subject_id) DO UPDATE SET
                marks_obtained = excluded.marks_obtained,
                maximum_marks = excluded.maximum_marks,
                percentage = excluded.percentage,
                updated_at = CURRENT_TIMESTAMP
        """, (s_id, subject_id, obtained, max_marks, pct))

        # Re-evaluate student's overall recommendation
        update_student_recommendation(s_id, conn)

    conn.commit()
    conn.close()

    flash(f"Academic marks for {len(student_ids)} students successfully recorded and updated.", "success")
    return redirect(url_for('marks_view', branch=branch, sem=sem, subject_id=subject_id))

# ==============================================================================
# Branch Comparison Page & Chart.js Data
# ==============================================================================

@app.route('/branch-comparison')
@teacher_or_admin_required
def branch_comparison_view():
    """Multi-branch comparison for AI, AIDS, AIML, DS, and CYBER with 6 Chart.js graphs."""
    conn = get_db()
    cursor = conn.cursor()

    branch_table = []
    labels = []
    student_counts = []
    avg_att_list = []
    avg_marks_list = []

    status_dist = {'onTrack': 0, 'monitor': 0, 'needsAttention': 0}

    best_marks_branch = {'branch': 'N/A', 'avg_marks': -1.0}
    best_att_branch = {'branch': 'N/A', 'avg_att': -1.0}
    needs_improvement_branch = {'branch': 'N/A', 'combined_score': 999.0}
    total_at_risk = 0

    for b in Config.BRANCHES:
        code = b['code']
        name = b['name']
        labels.append(code)

        # Student count
        cursor.execute("SELECT COUNT(*) FROM students WHERE branch = ?", (code,))
        cnt = cursor.fetchone()[0]
        student_counts.append(cnt)

        # Avg attendance
        cursor.execute("""
            SELECT COALESCE(AVG(a.attendance_percentage), 0.0)
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE s.branch = ?
        """, (code,))
        b_att = round(cursor.fetchone()[0], 1)
        avg_att_list.append(b_att)

        # Avg marks
        cursor.execute("""
            SELECT COALESCE(AVG(m.percentage), 0.0)
            FROM marks m
            JOIN students s ON m.student_id = s.id
            WHERE s.branch = ?
        """, (code,))
        b_marks = round(cursor.fetchone()[0], 1)
        avg_marks_list.append(b_marks)

        # Status counts
        cursor.execute("""
            SELECT r.status, COUNT(*) as cnt
            FROM recommendations r
            JOIN students s ON r.student_id = s.id
            WHERE s.branch = ?
            GROUP BY r.status
        """, (code,))
        st_rows = dict(cursor.fetchall())
        on_track = st_rows.get('On Track', 0)
        monitor = st_rows.get('Monitor', 0)
        needs_attention = st_rows.get('Needs Attention', 0)

        status_dist['onTrack'] += on_track
        status_dist['monitor'] += monitor
        status_dist['needsAttention'] += needs_attention
        total_at_risk += needs_attention

        # Insights comparison
        if b_marks > best_marks_branch['avg_marks']:
            best_marks_branch = {'branch': code, 'avg_marks': b_marks}
        if b_att > best_att_branch['avg_att']:
            best_att_branch = {'branch': code, 'avg_att': b_att}

        combined_score = round((b_att * 0.4) + (b_marks * 0.6), 1)
        if combined_score < needs_improvement_branch['combined_score']:
            needs_improvement_branch = {'branch': code, 'combined_score': combined_score}

        branch_table.append({
            'branch': code,
            'name': name,
            'count': cnt,
            'avg_att': b_att,
            'avg_marks': b_marks,
            'on_track': on_track,
            'monitor': monitor,
            'needs_attention': needs_attention
        })

    # Student points for scatter chart (attendance vs marks)
    cursor.execute("""
        SELECT 
            u.name,
            s.roll_number,
            s.branch,
            ROUND(AVG(a.attendance_percentage), 1) as att,
            ROUND(AVG(m.percentage), 1) as mrk
        FROM students s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN attendance a ON s.id = a.student_id
        LEFT JOIN marks m ON s.id = m.student_id
        GROUP BY s.id
    """)
    pts = cursor.fetchall()
    student_points = []
    for p in pts:
        if p['att'] is not None and p['mrk'] is not None:
            student_points.append({
                'x': p['att'],
                'y': p['mrk'],
                'name': p['name'],
                'roll': p['roll_number'],
                'branch': p['branch']
            })

    # Subject-wise average marks across first year
    cursor.execute("""
        SELECT sub.subject_name, ROUND(AVG(m.percentage), 1) as avg_pct
        FROM subjects sub
        JOIN marks m ON sub.id = m.subject_id
        GROUP BY sub.id
        ORDER BY avg_pct DESC
    """)
    sub_rows = cursor.fetchall()
    subject_marks = {
        'labels': [r['subject_name'] for r in sub_rows],
        'values': [r['avg_pct'] for r in sub_rows]
    }

    conn.close()

    chart_data = {
        'branches': labels,
        'studentCounts': student_counts,
        'avgAttendance': avg_att_list,
        'avgMarks': avg_marks_list,
        'statusDistribution': status_dist,
        'studentPoints': student_points,
        'subjectMarks': subject_marks
    }

    insights = {
        'best_marks_branch': best_marks_branch,
        'best_att_branch': best_att_branch,
        'needs_improvement_branch': needs_improvement_branch,
        'total_at_risk': total_at_risk
    }

    return render_template(
        'branch_comparison.html',
        branch_table=branch_table,
        chart_data=chart_data,
        insights=insights,
        active_page='branch_comparison'
    )

# ==============================================================================
# Student Dashboard (Student Access Only)
# ==============================================================================

@app.route('/student/dashboard')
@student_only
def student_dashboard():
    """Dedicated student view showing personal attendance, marks, and recommendations."""
    user_id = session.get('user_id')
    conn = get_db()
    cursor = conn.cursor()

    # Student profile
    cursor.execute("""
        SELECT s.id as student_id, u.name, u.email, s.roll_number, s.branch, s.semester, s.section
        FROM students s
        JOIN users u ON s.user_id = u.id
        WHERE s.user_id = ?
    """, (user_id,))
    student = cursor.fetchone()

    if not student:
        conn.close()
        flash("Student profile record not found. Please contact administration.", "danger")
        return redirect(url_for('login'))

    student_id = student['student_id']

    # Recommendation
    cursor.execute("""
        SELECT status, message FROM recommendations WHERE student_id = ?
    """, (student_id,))
    rec = cursor.fetchone()
    if not rec:
        # Generate default
        update_student_recommendation(student_id, conn)
        cursor.execute("SELECT status, message FROM recommendations WHERE student_id = ?", (student_id,))
        rec = cursor.fetchone()

    # Subject-wise attendance
    cursor.execute("""
        SELECT 
            sub.subject_name,
            sub.subject_type,
            a.total_classes,
            a.attended_classes,
            a.attendance_percentage
        FROM attendance a
        JOIN subjects sub ON a.subject_id = sub.id
        WHERE a.student_id = ?
        ORDER BY sub.id
    """, (student_id,))
    attendance_records = cursor.fetchall()

    # Subject-wise marks
    cursor.execute("""
        SELECT 
            sub.subject_name,
            sub.subject_type,
            m.marks_obtained,
            m.maximum_marks,
            m.percentage
        FROM marks m
        JOIN subjects sub ON m.subject_id = sub.id
        WHERE m.student_id = ?
        ORDER BY sub.id
    """, (student_id,))
    marks_records = cursor.fetchall()

    # Overall metrics
    overall_attendance = 0.0
    if attendance_records:
        overall_attendance = round(sum(r['attendance_percentage'] for r in attendance_records) / len(attendance_records), 1)

    overall_marks = 0.0
    if marks_records:
        overall_marks = round(sum(r['percentage'] for r in marks_records) / len(marks_records), 1)

    # Chart datasets
    att_chart = {
        'labels': [r['subject_name'] for r in attendance_records],
        'values': [r['attendance_percentage'] for r in attendance_records]
    }
    marks_chart = {
        'labels': [r['subject_name'] for r in marks_records],
        'values': [r['percentage'] for r in marks_records]
    }

    conn.close()

    student_chart_data = {
        'attendance': att_chart,
        'marks': marks_chart
    }

    return render_template(
        'student_dashboard.html',
        student=student,
        recommendation=rec,
        overall_attendance=overall_attendance,
        overall_marks=overall_marks,
        attendance_records=attendance_records,
        marks_records=marks_records,
        student_chart_data=student_chart_data,
        active_page='student_dashboard'
    )

# ==============================================================================
# User Profile & Password Management
# ==============================================================================

@app.route('/profile')
@login_required
def profile_view():
    """View user profile details."""
    user_id = session.get('user_id')
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, email, role, branch, semester, created_at FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    student_details = None
    if user['role'] == 'student':
        cursor.execute("SELECT roll_number, branch, semester, section FROM students WHERE user_id = ?", (user_id,))
        student_details = cursor.fetchone()

    conn.close()
    return render_template('profile.html', user=user, student_details=student_details, active_page='profile')

@app.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    """Secure password change for the logged-in user."""
    user_id = session.get('user_id')
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_new_password = request.form.get('confirm_new_password', '')

    if not current_password or not new_password or not confirm_new_password:
        flash("All password fields are required.", "danger")
        return redirect(url_for('profile_view'))

    if new_password != confirm_new_password:
        flash("New password and confirm password do not match.", "danger")
        return redirect(url_for('profile_view'))

    if len(new_password) < 6:
        flash("New password must be at least 6 characters long.", "danger")
        return redirect(url_for('profile_view'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if not user or not check_password_hash(user['password_hash'], current_password):
        conn.close()
        flash("Incorrect current password.", "danger")
        return redirect(url_for('profile_view'))

    new_hash = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    conn.commit()
    conn.close()

    flash("Your password has been changed successfully.", "success")
    return redirect(url_for('profile_view'))

# ==============================================================================
# Error Handlers
# ==============================================================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('base.html', content="<div class='card' style='text-align:center; padding:3rem;'><h2>404 - Page Not Found</h2><p>The requested page does not exist.</p><a href='/' class='btn btn-primary' style='margin-top:1rem;'>Return Home</a></div>"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('base.html', content="<div class='card' style='text-align:center; padding:3rem;'><h2>500 - Internal Error</h2><p>An unexpected server error occurred.</p><a href='/' class='btn btn-primary' style='margin-top:1rem;'>Return Home</a></div>"), 500

# ==============================================================================
# Application Entry Point
# ==============================================================================

if __name__ == '__main__':
    # Initialize schema and seed data on startup if not present
    init_db(seed=True)
    app.run(host='127.0.0.1', port=5000, debug=True)
