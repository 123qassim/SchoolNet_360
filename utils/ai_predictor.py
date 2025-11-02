# utils/ai_predictor.py
# v7.0+ AI and Automation features.
# These are simple rule-based placeholders.
# For a real app, you'd plug in an OpenAI/Gemini API or a trained model.

from models import db, Grade
from sqlalchemy.sql import func
import random

def generate_ai_remark(grades_list):
    """
    Generates a simple, rule-based summary remark for a report card.
    """
    if not grades_list:
        return "No grades available for this term."
        
    avg_mark = sum(g.marks for g in grades_list) / len(grades_list)
    
    strongest_subject = max(grades_list, key=lambda g: g.marks)
    weakest_subject = min(grades_list, key=lambda g: g.marks)
    
    remark = f"Overall performance this term was "
    if avg_mark >= 80:
        remark += f"excellent, with an average of {avg_mark:.1f}%. "
    elif avg_mark >= 60:
        remark += f"good, with an average of {avg_mark:.1f}%. "
    elif avg_mark >= 50:
        remark += f"satisfactory, with an average of {avg_mark:.1f}%. "
    else:
        remark += f"below average, with an average of {avg_mark:.1f}%. Needs improvement. "
        
    if strongest_subject.marks > 85:
        remark += f"Outstanding work in {strongest_subject.subject.name} ({strongest_subject.marks}%). "
        
    if weakest_subject.marks < 50:
        remark += f"Significant focus is required in {weakest_subject.subject.name} ({weakest_subject.marks}%)."
    elif weakest_subject.marks < 60 and avg_mark > 70:
         remark += f"Consider extra practice in {weakest_subject.subject.name} to match overall performance."

    return remark

def predict_next_term(student_id):
    """
    (Placeholder) Predicts next term's average based on a simple trend.
    A real implementation would use linear regression or a time-series model.
    """
    # Get average marks for all terms
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
    
    if len(trend_data) < 2:
        return "Not enough data to predict future performance."
        
    # Simple linear trend: (last_avg - first_avg) / num_terms
    try:
        last_avg = trend_data[-1].average_marks
        first_avg = trend_data[0].average_marks
        num_terms = len(trend_data)
        
        avg_change_per_term = (last_avg - first_avg) / (num_terms - 1)
        
        prediction = last_avg + avg_change_per_term
        
        # Add some noise for realism
        prediction += random.uniform(-2, 2)
        
        if prediction > 100: prediction = 100
        if prediction < 0: prediction = 0
        
        if avg_change_per_term > 2:
            trend = "strong upward trend"
        elif avg_change_per_term < -2:
            trend = "downward trend"
        else:
            trend = "stable performance"

        return f"Based on a {trend}, estimated average for next term is **~{prediction:.0f}%**."
        
    except Exception:
        return "Could not calculate performance trend."