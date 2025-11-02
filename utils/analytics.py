# utils/analytics.py
# Functions to query the DB and structure data for Chart.js and analytics.

from models import db, Student, Grade, School, UserRole
from sqlalchemy.sql import func
import pandas as pd

def get_student_grade_trend(student_id):
    """Fetches average marks per term for a specific student."""
    
    # Query to get average marks grouped by term
    trend_data = db.session.query(
        Grade.term,
        func.avg(Grade.marks).label('average_marks')
    ).filter(
        Grade.student_id == student_id
    ).group_by(
        Grade.term
    ).order_by(
        Grade.term
    ).all()
    
    if not trend_data:
        return {'labels': [], 'data': []}
        
    labels = [row.term for row in trend_data]
    data = [round(row.average_marks, 2) for row in trend_data]
    
    return {
        'labels': labels,
        'data': data
    }

def get_class_grade_distribution(school_id, form):
    """Calculates the distribution of grades (A, B, C...) for a form."""
    
    grades = db.session.query(
        Grade.grade_letter
    ).join(Student).filter(
        Student.school_id == school_id,
        Student.form == form
    ).all()
    
    # Count occurrences
    distribution = {
        'A+': 0, 'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0
    }
    for grade in grades:
        key = grade.grade_letter.name.replace("AP", "A+") # Handle Enum name
        if key in distribution:
            distribution[key] += 1
            
    labels = list(distribution.keys())
    data = list(distribution.values())
    
    return {
        'labels': labels,
        'data': data
    }

def get_subject_averages(school_id, form):
    """Calculates the average mark per subject for a given form."""
    # (Implementation would be similar to get_student_grade_trend)
    pass

def get_school_comparison():
    """(Bonus) Generates data for Super Admin to compare schools."""
    
    # This query joins School, Student, and Grade, then groups by school
    # to find the average mark across all students in all schools.
    query = db.session.query(
        School.name,
        func.avg(Grade.marks).label('average_score')
    ).join(
        Student, School.id == Student.school_id
    ).join(
        Grade, Student.id == Grade.student_id
    ).group_by(
        School.name
    ).order_by(
        func.avg(Grade.marks).desc()
    ).all()
    
    labels = [row.name for row in query]
    data = [round(row.average_score, 2) for row in query]
    
    return {'labels': labels, 'data': data}