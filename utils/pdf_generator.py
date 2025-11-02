# utils/pdf_generator.py
# Uses WeasyPrint to convert a rendered HTML template into a PDF report.

from flask import render_template
from weasyprint import HTML, CSS
import io
from datetime import datetime # <--- ADDED IMPORT

def generate_pdf_report(student, grades, term):
    """
    Generates a PDF report card for a student for a specific term.
    
    Args:
        student (Student): The student object.
        grades (list[Grade]): List of grade objects for the term.
        term (str): The specific term (e.g., "Term 1 2025").
        
    Returns:
        bytes: The generated PDF as a byte string.
    """
    
    # Calculate summary statistics
    total_marks = sum(g.marks for g in grades)
    num_subjects = len(grades)
    average_marks = total_marks / num_subjects if num_subjects > 0 else 0
    
    # (A real system would calculate rank here by querying other students)
    class_rank = "N/A" 
    
    summary = {
        "total_marks": total_marks,
        "average_marks": f"{average_marks:.2f}",
        "class_rank": class_rank,
        "principal_remark": "A promising term. Keep up the good work.",
        "teacher_remark": "Consistent effort shown in all subjects."
    }
    
    # Render the HTML template with data
    # We pass 'base_url' to help WeasyPrint find static assets if any
    rendered_html = render_template(
        'reports/pdf_template.html',
        student=student,
        grades=grades,
        term=term,
        summary=summary,
        now=datetime.utcnow(),  # <--- THIS IS THE FIX
        base_url='.' 
    )
    
    # Use WeasyPrint to generate the PDF in memory
    pdf_bytes = HTML(string=rendered_html).write_pdf()
    
    return pdf_bytes