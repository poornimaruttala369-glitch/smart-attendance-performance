"""
KIET Institutions - First-Year Subject Curriculum
Configurable list for 1st Year (B.Tech) applicable across:
AI, AIDS, AIML, DS, and CYBER branches.

Easily updateable for KIET / JNTUK / AKTU syllabus revisions.
"""

FIRST_YEAR_SUBJECTS = {
    1: [
        {"name": "Communicative English", "type": "Theory", "code": "HS101"},
        {"name": "Linear Algebra and Calculus", "type": "Theory", "code": "BS101"},
        {"name": "Engineering Chemistry", "type": "Theory", "code": "BS102"},
        {"name": "Programming for Problem Solving using C", "type": "Theory", "code": "ES101"},
        {"name": "Basic Electrical and Electronics Engineering", "type": "Theory", "code": "ES102"},
        {"name": "Engineering Graphics", "type": "Theory", "code": "ES103"},
        {"name": "Engineering Workshop", "type": "Lab", "code": "ES104L"},
        {"name": "English Communication Skills Lab", "type": "Lab", "code": "HS102L"},
        {"name": "Engineering Chemistry Lab", "type": "Lab", "code": "BS103L"},
        {"name": "Programming for Problem Solving Lab", "type": "Lab", "code": "ES105L"},
    ],
    2: [
        {"name": "Differential Equations and Vector Calculus", "type": "Theory", "code": "BS201"},
        {"name": "Applied Physics", "type": "Theory", "code": "BS202"},
        {"name": "Data Structures", "type": "Theory", "code": "ES201"},
        {"name": "Digital Logic Design", "type": "Theory", "code": "ES202"},
        {"name": "Basic Civil and Mechanical Engineering", "type": "Theory", "code": "ES203"},
        {"name": "Applied Physics Lab", "type": "Lab", "code": "BS203L"},
        {"name": "Data Structures Lab", "type": "Lab", "code": "ES204L"},
        {"name": "English Communication Skills Lab", "type": "Lab", "code": "HS201L"},
        {"name": "Skill-Oriented Course / Workshop", "type": "Workshop", "code": "SC201"},
    ]
}

def get_subjects_by_semester(semester):
    """Retrieve subjects for a given semester (1 or 2)."""
    return FIRST_YEAR_SUBJECTS.get(int(semester), [])

def get_all_subjects():
    """Retrieve all first-year subjects across both semesters."""
    all_subs = []
    for sem, subs in FIRST_YEAR_SUBJECTS.items():
        for s in subs:
            all_subs.append({**s, "semester": sem})
    return all_subs
