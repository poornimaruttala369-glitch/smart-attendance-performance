import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'kiet-smart-attendance-super-secret-key-2024')
    DATABASE = os.path.join(BASE_DIR, 'database.db')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # KIET Branches
    BRANCHES = [
        {'code': 'AI', 'name': 'Artificial Intelligence'},
        {'code': 'AIDS', 'name': 'Artificial Intelligence and Data Science'},
        {'code': 'AIML', 'name': 'Artificial Intelligence and Machine Learning'},
        {'code': 'DS', 'name': 'Data Science'},
        {'code': 'CYBER', 'name': 'Cyber Security'}
    ]
    
    BRANCH_CODES = ['AI', 'AIDS', 'AIML', 'DS', 'CYBER']
    
    SEMESTERS = [1, 2]
    SECTIONS = ['A', 'B', 'C']
    
    # Performance Evaluation Thresholds
    ATTENDANCE_CUTOFF_LOW = 70.0
    ATTENDANCE_CUTOFF_MID = 75.0
    MARKS_CUTOFF_LOW = 40.0
    MARKS_CUTOFF_MID = 50.0
