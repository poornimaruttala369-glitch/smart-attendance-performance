import sqlite3
import os
from werkzeug.security import generate_password_hash
from config import Config
from data.first_year_subjects import get_all_subjects

def get_db():
    """Connect to SQLite database and configure row factory and foreign keys."""
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def calculate_status_and_message(attendance_pct, marks_pct):
    """
    Calculate status and recommendation message according to project rules:
    Rule 1 (Needs Attention): Attendance < 70% OR Average marks < 40%
    Rule 2 (Monitor): Attendance 70% to 74% OR Average marks 40% to 49%
    Rule 3 (On Track): Attendance >= 75% AND Average marks >= 50%
    """
    # Rounding for clean precision comparison
    att = round(attendance_pct, 2)
    mrk = round(marks_pct, 2)
    
    if att < 70.0 or mrk < 40.0:
        return (
            "Needs Attention",
            "Student requires immediate support to improve attendance or academic performance."
        )
    elif (70.0 <= att < 75.0) or (40.0 <= mrk < 50.0):
        return (
            "Monitor",
            "Student needs regular monitoring and improvement."
        )
    else:
        return (
            "On Track",
            "Student is performing well. Maintain consistency."
        )

def init_db(seed=False):
    """Initialize database tables and optionally seed sample data."""
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'teacher', 'student')),
        branch TEXT,
        semester INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Students Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        roll_number TEXT UNIQUE NOT NULL,
        branch TEXT NOT NULL,
        semester INTEGER NOT NULL DEFAULT 1,
        section TEXT NOT NULL DEFAULT 'A',
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)

    # 3. Subjects Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_name TEXT NOT NULL,
        semester INTEGER NOT NULL,
        branch TEXT DEFAULT 'ALL',
        subject_type TEXT DEFAULT 'Theory'
    );
    """)

    # 4. Attendance Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        total_classes INTEGER NOT NULL DEFAULT 0,
        attended_classes INTEGER NOT NULL DEFAULT 0,
        attendance_percentage REAL NOT NULL DEFAULT 0.0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
        UNIQUE (student_id, subject_id)
    );
    """)

    # 5. Marks Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        marks_obtained REAL NOT NULL DEFAULT 0.0,
        maximum_marks REAL NOT NULL DEFAULT 100.0,
        percentage REAL NOT NULL DEFAULT 0.0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
        UNIQUE (student_id, subject_id)
    );
    """)

    # 6. Recommendations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER UNIQUE NOT NULL,
        status TEXT NOT NULL,
        message TEXT NOT NULL,
        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
    );
    """)

    conn.commit()

    # Sync subjects from configurable data source
    sync_subjects(conn)

    if seed:
        seed_sample_data(conn)

    conn.close()

def sync_subjects(conn):
    """Ensure all first-year subjects from first_year_subjects.py exist in database."""
    cursor = conn.cursor()
    subjects = get_all_subjects()
    for sub in subjects:
        cursor.execute("""
            SELECT id FROM subjects 
            WHERE subject_name = ? AND semester = ?
        """, (sub["name"], sub["semester"]))
        existing = cursor.fetchone()
        if not existing:
            cursor.execute("""
                INSERT INTO subjects (subject_name, semester, branch, subject_type)
                VALUES (?, ?, 'ALL', ?)
            """, (sub["name"], sub["semester"], sub["type"]))
    conn.commit()

def update_student_recommendation(student_id, conn=None):
    """
    Recalculate overall attendance & marks percentage for student
    and upsert recommendation record.
    """
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True

    cursor = conn.cursor()

    # Average attendance percentage
    cursor.execute("""
        SELECT 
            COALESCE(AVG(attendance_percentage), 0.0) as avg_att,
            COUNT(*) as record_count
        FROM attendance
        WHERE student_id = ?
    """, (student_id,))
    att_row = cursor.fetchone()
    avg_att = att_row['avg_att'] if att_row and att_row['record_count'] > 0 else 0.0

    # Average marks percentage
    cursor.execute("""
        SELECT 
            COALESCE(AVG(percentage), 0.0) as avg_marks,
            COUNT(*) as record_count
        FROM marks
        WHERE student_id = ?
    """, (student_id,))
    marks_row = cursor.fetchone()
    avg_marks = marks_row['avg_marks'] if marks_row and marks_row['record_count'] > 0 else 0.0

    status, message = calculate_status_and_message(avg_att, avg_marks)

    cursor.execute("""
        INSERT INTO recommendations (student_id, status, message, generated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(student_id) DO UPDATE SET
            status = excluded.status,
            message = excluded.message,
            generated_at = CURRENT_TIMESTAMP
    """, (student_id, status, message))

    conn.commit()
    if should_close:
        conn.close()

    return status, message, avg_att, avg_marks

def seed_sample_data(conn=None):
    """Seed comprehensive test data for all 5 branches with realistic attendance and marks."""
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True

    cursor = conn.cursor()

    # Check if admin already exists
    cursor.execute("SELECT id FROM users WHERE email = 'admin@kiet.edu'")
    if cursor.fetchone():
        if should_close:
            conn.close()
        return

    print("Seeding sample data for KIET Smart Attendance and Performance Analyser...")

    # 1. Admin User
    admin_pw = generate_password_hash("Admin@123")
    cursor.execute("""
        INSERT INTO users (name, email, password_hash, role, branch, semester)
        VALUES ('Dr. Manoj Kumar (HOD)', 'admin@kiet.edu', ?, 'admin', 'AI', 1)
    """, (admin_pw,))

    # 2. Teacher Users
    teacher_pw = generate_password_hash("Teacher@123")
    teachers = [
        ('Prof. Sunita Sharma', 'teacher.ai@kiet.edu', 'teacher', 'AI', 1),
        ('Dr. Rajiv Verma', 'teacher.aids@kiet.edu', 'teacher', 'AIDS', 1),
        ('Prof. Priya Singh', 'teacher.aiml@kiet.edu', 'teacher', 'AIML', 1),
        ('Dr. Amit Patel', 'teacher.ds@kiet.edu', 'teacher', 'DS', 1),
        ('Prof. Neha Gupta', 'teacher.cyber@kiet.edu', 'teacher', 'CYBER', 1),
    ]
    for t in teachers:
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role, branch, semester)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (t[0], t[1], teacher_pw, t[2], t[3], t[4]))

    # Retrieve subject IDs for semester 1
    cursor.execute("SELECT id, subject_name FROM subjects WHERE semester = 1 ORDER BY id")
    sem1_subjects = cursor.fetchall()

    # Student default password
    student_pw = generate_password_hash("Student@123")

    # Sample students dataset across all 5 branches
    # Target distribution: On Track (~60%), Monitor (~25%), Needs Attention (~15%)
    sample_students = [
        # AI Branch
        {"name": "Aarav Sharma", "email": "23ai001@kiet.edu", "roll": "23KIETAI001", "branch": "AI", "sem": 1, "sec": "A", "att_profile": 88, "marks_profile": 82},
        {"name": "Aditi Roy", "email": "23ai002@kiet.edu", "roll": "23KIETAI002", "branch": "AI", "sem": 1, "sec": "A", "att_profile": 92, "marks_profile": 89},
        {"name": "Ananya Mishra", "email": "23ai003@kiet.edu", "roll": "23KIETAI003", "branch": "AI", "sem": 1, "sec": "B", "att_profile": 72, "marks_profile": 64}, # Monitor (att 72)
        {"name": "Dhruv Kapoor", "email": "23ai004@kiet.edu", "roll": "23KIETAI004", "branch": "AI", "sem": 1, "sec": "B", "att_profile": 64, "marks_profile": 38}, # Needs Attention (both low)

        # AIDS Branch
        {"name": "Ishaan Verma", "email": "23aids001@kiet.edu", "roll": "23KIETAIDS001", "branch": "AIDS", "sem": 1, "sec": "A", "att_profile": 85, "marks_profile": 78},
        {"name": "Kavya Saxena", "email": "23aids002@kiet.edu", "roll": "23KIETAIDS002", "branch": "AIDS", "sem": 1, "sec": "A", "att_profile": 78, "marks_profile": 45}, # Monitor (marks 45)
        {"name": "Manish Tyagi", "email": "23aids003@kiet.edu", "roll": "23KIETAIDS003", "branch": "AIDS", "sem": 1, "sec": "B", "att_profile": 90, "marks_profile": 84},
        {"name": "Pooja Hegde", "email": "23aids004@kiet.edu", "roll": "23KIETAIDS004", "branch": "AIDS", "sem": 1, "sec": "B", "att_profile": 67, "marks_profile": 70}, # Needs Attention (att 67)

        # AIML Branch
        {"name": "Rohan Mehra", "email": "23aiml001@kiet.edu", "roll": "23KIETAIML001", "branch": "AIML", "sem": 1, "sec": "A", "att_profile": 86, "marks_profile": 80},
        {"name": "Sanya Chopra", "email": "23aiml002@kiet.edu", "roll": "23KIETAIML002", "branch": "AIML", "sem": 1, "sec": "A", "att_profile": 73, "marks_profile": 72}, # Monitor (att 73)
        {"name": "Siddharth Rao", "email": "23aiml003@kiet.edu", "roll": "23KIETAIML003", "branch": "AIML", "sem": 1, "sec": "B", "att_profile": 80, "marks_profile": 76},
        {"name": "Tanvi Bhatia", "email": "23aiml004@kiet.edu", "roll": "23KIETAIML004", "branch": "AIML", "sem": 1, "sec": "B", "att_profile": 58, "marks_profile": 36}, # Needs Attention

        # DS Branch
        {"name": "Utkarsh Singh", "email": "23ds001@kiet.edu", "roll": "23KIETDS001", "branch": "DS", "sem": 1, "sec": "A", "att_profile": 84, "marks_profile": 79},
        {"name": "Vaishnavi Iyer", "email": "23ds002@kiet.edu", "roll": "23KIETDS002", "branch": "DS", "sem": 1, "sec": "A", "att_profile": 91, "marks_profile": 88},
        {"name": "Varun Chawla", "email": "23ds003@kiet.edu", "roll": "23KIETDS003", "branch": "DS", "sem": 1, "sec": "B", "att_profile": 71, "marks_profile": 58}, # Monitor (att 71)
        {"name": "Yash Dixit", "email": "23ds004@kiet.edu", "roll": "23KIETDS004", "branch": "DS", "sem": 1, "sec": "B", "att_profile": 62, "marks_profile": 54}, # Needs Attention (att 62)

        # CYBER Branch
        {"name": "Zaid Khan", "email": "23cy001@kiet.edu", "roll": "23KIETCY001", "branch": "CYBER", "sem": 1, "sec": "A", "att_profile": 89, "marks_profile": 85},
        {"name": "Bhavna Joshi", "email": "23cy002@kiet.edu", "roll": "23KIETCY002", "branch": "CYBER", "sem": 1, "sec": "A", "att_profile": 76, "marks_profile": 46}, # Monitor (marks 46)
        {"name": "Chirag Sethi", "email": "23cy003@kiet.edu", "roll": "23KIETCY003", "branch": "CYBER", "sem": 1, "sec": "B", "att_profile": 82, "marks_profile": 74},
        {"name": "Divya Nambiar", "email": "23cy004@kiet.edu", "roll": "23KIETCY004", "branch": "CYBER", "sem": 1, "sec": "B", "att_profile": 63, "marks_profile": 35} # Needs Attention
    ]

    total_classes = 40

    for st in sample_students:
        # Create student user
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role, branch, semester)
            VALUES (?, ?, ?, 'student', ?, ?)
        """, (st["name"], st["email"], student_pw, st["branch"], st["sem"]))
        user_id = cursor.lastrowid

        # Create student record
        cursor.execute("""
            INSERT INTO students (user_id, roll_number, branch, semester, section)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, st["roll"], st["branch"], st["sem"], st["sec"]))
        student_id = cursor.lastrowid

        base_att_pct = st["att_profile"]
        base_marks_pct = st["marks_profile"]

        # Insert subject-wise attendance and marks
        for idx, sub in enumerate(sem1_subjects):
            sub_id = sub["id"]

            # Introduce realistic slight variations across subjects (+/- 5%)
            variance = ((idx * 3) % 7) - 3
            att_pct = max(10.0, min(100.0, base_att_pct + variance))
            attended = int(round((att_pct / 100.0) * total_classes))
            actual_att_pct = round((attended / total_classes) * 100.0, 2)

            cursor.execute("""
                INSERT INTO attendance (student_id, subject_id, total_classes, attended_classes, attendance_percentage)
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, sub_id, total_classes, attended, actual_att_pct))

            # Marks
            marks_variance = ((idx * 5) % 9) - 4
            marks_pct = max(15.0, min(99.0, base_marks_pct + marks_variance))
            marks_obtained = round(marks_pct, 1) # max marks = 100.0
            actual_marks_pct = marks_obtained

            cursor.execute("""
                INSERT INTO marks (student_id, subject_id, marks_obtained, maximum_marks, percentage)
                VALUES (?, ?, ?, 100.0, ?)
            """, (student_id, sub_id, marks_obtained, actual_marks_pct))

        # Calculate recommendation
        update_student_recommendation(student_id, conn)

    conn.commit()
    print(f"Seeded {len(sample_students)} students, admin, and teachers successfully.")

    if should_close:
        conn.close()

if __name__ == '__main__':
    init_db(seed=True)
