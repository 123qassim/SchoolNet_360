# app.py
# Main Flask application file for the Multi-School Academic System v7.0

import os
import pandas as pd
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, redirect, url_for, flash, request,
    session, abort, jsonify, Response
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    current_user, login_required
)
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField
from wtforms.validators import DataRequired, EqualTo, ValidationError, Length
from flask_wtf.csrf import CSRFProtect
from weasyprint import HTML

# Import models and db instance
from models import (
    db, School, User, Student, Teacher, Subject, Grade, UserRole, GradeLetter
)
# Import utilities
from utils.analytics import (
    get_student_grade_trend, get_class_grade_distribution, 
    get_subject_averages, get_school_comparison
)
from utils.ai_predictor import generate_ai_remark, predict_next_term
from utils.pdf_generator import generate_pdf_report
from utils.csv_tools import load_data_from_csv

# --- APP CONFIGURATION ---

# Set base directory
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key_that_should_be_changed'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data', 'ecosystem.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'select_school' # Redirect to school selection if not logged in
login_manager.login_message = "You must be logged in to access this page."
login_manager.login_message_category = "danger"

# --- HELPER FUNCTIONS & DECORATORS ---

@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader."""
    return User.query.get(int(user_id))

def role_required(role):
    """Custom decorator to restrict access based on user role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                abort(403) # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_current_school():
    """Helper to get the school object for the currently logged-in user."""
    if current_user.is_authenticated and current_user.role != UserRole.SUPER_ADMIN:
        return School.query.get(current_user.school_id)
    return None

def calculate_grade_letter(marks):
    """Calculates the grade letter from marks."""
    if marks >= 90: return GradeLetter.AP
    if marks >= 80: return GradeLetter.A
    if marks >= 70: return GradeLetter.B
    if marks >= 60: return GradeLetter.C
    if marks >= 50: return GradeLetter.D
    return GradeLetter.F

def generate_admission_number(school_code_base, student_id, year):
    """Generates the standard admission number."""
    return f"{school_code_base}/{student_id:05d}/{year[2:]}"

# --- DATABASE INITIALIZATION ---

@app.cli.command("init-db")
def init_db_command():
    """CLI command to initialize the database with mock data."""
    print("Dropping and recreating database...")
    db.drop_all()
    db.create_all()
    print("Loading data from CSV files...")
    load_data_from_csv()
    print("Database initialized successfully!")

with app.app_context():
    # Automatically create DB if it doesn't exist
    if not os.path.exists(os.path.join(basedir, 'data', 'ecosystem.db')):
        print("Database not found. Creating and initializing...")
        db.create_all()
        load_data_from_csv()
        print("Database created and initialized.")

# --- FORMS (WTForms) ---

class LoginForm(FlaskForm):
    """Unified Login Form."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SchoolRegistrationForm(FlaskForm):
    """Form for Super Admin to register a new school."""
    school_name = StringField('School Name', validators=[DataRequired(), Length(min=3, max=150)])
    school_code = StringField('School Code (e.g., GHS@1)', validators=[DataRequired(), Length(min=3, max=20)])
    admin_username = StringField('Admin Username', validators=[DataRequired(), Length(min=4, max=100)])
    admin_password = PasswordField('Admin Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Register School')

    def validate_school_code(self, field):
        if School.query.filter_by(school_code=field.data).first():
            raise ValidationError('This School Code is already taken.')
    
    def validate_admin_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('This Admin Username is already taken.')

class GradeEntryForm(FlaskForm):
    """Form for Teachers to enter grades."""
    student_admission = StringField('Student Admission Number', validators=[DataRequired()])
    subject_id = SelectField('Subject', coerce=int, validators=[DataRequired()])
    term = SelectField('Term', choices=[
        ('Term 1 2025', 'Term 1 2025'),
        ('Term 2 2025', 'Term 2 2025'),
        ('Term 3 2025', 'Term 3 2025')
    ], validators=[DataRequired()])
    marks = IntegerField('Marks (0-100)', validators=[DataRequired()])
    submit = SubmitField('Submit Grade')

class SubjectForm(FlaskForm):
    """Form for Admins to add a new subject."""
    name = StringField('Subject Name', validators=[DataRequired(), Length(min=3, max=100)])
    submit = SubmitField('Add Subject')

    def validate_name(self, field):
        # Check for duplicates within the *same school*
        if Subject.query.filter_by(name=field.data, school_id=current_user.school_id).first():
            raise ValidationError('This subject already exists for your school.')

class StudentRegistrationForm(FlaskForm):
    """Form for Admins to register a new student."""
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=3, max=150)])
    form = SelectField('Form', choices=[
        (1, 'Form 1'), (2, 'Form 2'), (3, 'Form 3'), (4, 'Form 4')
    ], coerce=int, validators=[DataRequired()])
    
    # Login Credentials
    username = StringField('Login Username', validators=[DataRequired(), Length(min=4, max=100)])
    password = PasswordField('Initial Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Register Student')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('This username is already taken.')

# --- ERROR HANDLERS ---

@app.errorhandler(403)
def forbidden(error):
    return render_template('errors/403.html'), 403

@app.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server(error):
    db.session.rollback() # Rollback any failed DB transactions
    return render_template('errors/500.html'), 500

# --- AUTHENTICATION & PUBLIC ROUTES ---

@app.route('/')
def select_school():
    """Landing page to select a school before logging in."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    schools = School.query.order_by(School.name).all()
    return render_template('school_select.html', schools=schools)

@app.route('/login/<role>/<school_code>', methods=['GET', 'POST'])
def login(role, school_code):
    """Handles login for all user types based on the selected school."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    
    # --- THIS IS THE FIX ---
    # We must check for super_admin *before* querying the school,
    # otherwise 'platform' will cause a 404.
    if role == "super_admin":
        school = None # Super admins aren't tied to one school
    else:
        # This query now only runs for non-super_admins
        school = School.query.filter_by(school_code=school_code).first_or_404()
    # --- END FIX ---
    
    # Determine the template and role enum
    template_map = {
        "admin": ("admin_login.html", UserRole.SCHOOL_ADMIN),
        "teacher": ("teacher_login.html", UserRole.TEACHER),
        "student": ("student_login.html", UserRole.STUDENT),
        "super_admin": ("admin_login.html", UserRole.SUPER_ADMIN)
    }
    
    if role not in template_map:
        abort(404)
        
    template, role_enum = template_map[role]
        
    if form.validate_on_submit():
        # Find the user
        if school:
            user = User.query.filter_by(
                username=form.username.data, 
                school_id=school.id,
                role=role_enum
            ).first()
        else: # Super Admin login
             user = User.query.filter_by(
                username=form.username.data, 
                role=UserRole.SUPER_ADMIN
            ).first()

        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template(template, form=form, school=school, role=role)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('select_school'))

# --- CORE DASHBOARD ROUTE (Redirector) ---

@app.route('/dashboard')
@login_required
def dashboard():
    """Redirects user to their specific dashboard based on role."""
    if current_user.role == UserRole.SUPER_ADMIN:
        return redirect(url_for('super_admin_dashboard'))
    elif current_user.role == UserRole.SCHOOL_ADMIN:
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == UserRole.TEACHER:
        return redirect(url_for('teacher_dashboard'))
    elif current_user.role == UserRole.STUDENT:
        return redirect(url_for('student_dashboard'))
    else:
        abort(403)

# --- 1. SUPER ADMIN DASHBOARD ---

@app.route('/dashboard/super_admin', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.SUPER_ADMIN)
def super_admin_dashboard():
    form = SchoolRegistrationForm()
    if form.validate_on_submit():
        try:
            # Create new school
            new_school = School(
                name=form.school_name.data,
                school_code=form.school_code.data
            )
            db.session.add(new_school)
            db.session.flush() # Flush to get new_school.id

            # Create new school admin user
            admin_user = User(
                username=form.admin_username.data,
                role=UserRole.SCHOOL_ADMIN,
                school_id=new_school.id
            )
            admin_user.set_password(form.admin_password.data)
            db.session.add(admin_user)
            
            db.session.commit()
            flash(f"School '{new_school.name}' and admin '{admin_user.username}' created!", 'success')
            return redirect(url_for('super_admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating school: {e}", 'danger')

    schools = School.query.all()
    # Bonus: Inter-school analytics
    comparison_data = get_school_comparison()
    
    return render_template(
        'dashboards/super_admin_dashboard.html', 
        form=form, 
        schools=schools,
        comparison_data=comparison_data
    )

# --- 2. SCHOOL ADMIN DASHBOARD ---

@app.route('/dashboard/admin')
@login_required
@role_required(UserRole.SCHOOL_ADMIN)
def admin_dashboard():
    school = get_current_school()
    
    # Fetch stats
    student_count = Student.query.filter_by(school_id=school.id).count()
    teacher_count = Teacher.query.filter_by(school_id=school.id).count()
    subject_count = Subject.query.filter_by(school_id=school.id).count()
    
    stats = {
        "student_count": student_count,
        "teacher_count": teacher_count,
        "subject_count": subject_count
    }
    
    return render_template('dashboards/admin_dashboard.html', school=school, stats=stats)


@app.route('/admin/students', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.SCHOOL_ADMIN)
def admin_manage_students():
    school = get_current_school()
    form = StudentRegistrationForm()
    
    if form.validate_on_submit():
        try:
            # 1. Create the User login
            new_user = User(
                username=form.username.data,
                role=UserRole.STUDENT,
                school_id=school.id
            )
            new_user.set_password(form.password.data)
            db.session.add(new_user)
            db.session.flush() # Get new_user.id before commit

            # 2. Generate new Admission Number
            # Get count of existing students at this school for a unique ID
            student_count = Student.query.filter_by(school_id=school.id).count()
            student_id = student_count + 1 # Simple incrementer
            school_code_base = school.school_code.split('@')[0]
            year_str = str(datetime.now().year)

            adm_num = generate_admission_number(
                school_code_base,
                student_id,
                year_str
            )
            
            # 3. Create the Student profile
            new_student = Student(
                full_name=form.full_name.data,
                admission_number=adm_num,
                form=form.form.data,
                user_id=new_user.id,
                school_id=school.id
            )
            db.session.add(new_student)
            
            db.session.commit()
            flash(f'Student {new_student.full_name} ({adm_num}) created successfully!', 'success')
            return redirect(url_for('admin_manage_students'))

        except Exception as e:
            db.session.rollback()
            # Check for duplicate username constraint
            if 'UNIQUE constraint failed: user.username' in str(e):
                flash('This username is already taken.', 'danger')
            else:
                flash(f'Error creating student: {e}', 'danger')


    # GET Request: Load existing students
    students = Student.query.filter_by(school_id=school.id).order_by(Student.form, Student.full_name).all()
    
    return render_template('admin/manage_students.html', form=form, students=students, school=school)


@app.route('/admin/subjects', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.SCHOOL_ADMIN)
def admin_manage_subjects():
    school = get_current_school()
    form = SubjectForm()

    if form.validate_on_submit():
        try:
            new_subject = Subject(
                name=form.name.data,
                school_id=school.id
            )
            db.session.add(new_subject)
            db.session.commit()
            flash(f'Subject "{new_subject.name}" added successfully!', 'success')
            return redirect(url_for('admin_manage_subjects'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding subject: {e}', 'danger')

    # GET Request: Load existing subjects
    subjects = Subject.query.filter_by(school_id=school.id).order_by(Subject.name).all()

    return render_template('admin/manage_subjects.html', form=form, subjects=subjects, school=school)

# --- 3. TEACHER DASHBOARD ---

@app.route('/dashboard/teacher', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.TEACHER)
def teacher_dashboard():
    school = get_current_school()
    teacher = current_user.teacher_profile
    
    form = GradeEntryForm()
    # Populate subjects dropdown for the teacher's school
    form.subject_id.choices = [
        (s.id, s.name) for s in Subject.query.filter_by(school_id=school.id).order_by(Subject.name).all()
    ]
    
    if form.validate_on_submit():
        student = Student.query.filter_by(
            admission_number=form.student_admission.data,
            school_id=school.id
        ).first()
        
        if not student:
            flash('Error: Student admission number not found for this school.', 'danger')
        else:
            try:
                # Check for existing grade
                existing_grade = Grade.query.filter_by(
                    student_id=student.id,
                    subject_id=form.subject_id.data,
                    term=form.term.data
                ).first()
                
                if existing_grade:
                    # Update existing grade
                    existing_grade.marks = form.marks.data
                    existing_grade.grade_letter = calculate_grade_letter(form.marks.data)
                    existing_grade.teacher_id = teacher.id
                    flash('Grade updated successfully!', 'success')
                else:
                    # Create new grade
                    new_grade = Grade(
                        marks=form.marks.data,
                        grade_letter=calculate_grade_letter(form.marks.data),
                        term=form.term.data,
                        student_id=student.id,
                        subject_id=form.subject_id.data,
                        teacher_id=teacher.id
                    )
                    db.session.add(new_grade)
                
                db.session.commit()
                flash('Grade submitted successfully!', 'success')
                return redirect(url_for('teacher_dashboard'))
                
            except Exception as e:
                db.session.rollback()
                flash(f"Error submitting grade: {e}", 'danger')

    # Get recent grades entered by this teacher
    recent_grades = Grade.query.filter_by(teacher_id=teacher.id)\
        .order_by(Grade.id.desc()).limit(10).all()

    return render_template(
        'dashboards/teacher_dashboard.html', 
        school=school, 
        teacher=teacher, 
        form=form,
        recent_grades=recent_grades
    )

# --- 4. STUDENT DASHBOARD ---

@app.route('/dashboard/student')
@login_required
@role_required(UserRole.STUDENT)
def student_dashboard():
    school = get_current_school()
    student = current_user.student_profile
    
    # Get all grades for the student, grouped by term
    grades_by_term = {}
    all_grades = Grade.query.filter_by(student_id=student.id).order_by(Grade.term).all()
    
    for grade in all_grades:
        if grade.term not in grades_by_term:
            grades_by_term[grade.term] = []
        grades_by_term[grade.term].append(grade)
        
    # Get AI-powered remarks for the latest term (if available)
    latest_term = "Term 1 2025" # Hardcoding for demo; would be dynamic
    ai_remarks = {}
    if latest_term in grades_by_term:
        latest_grades = grades_by_term[latest_term]
        ai_remarks = {
            "summary": generate_ai_remark(latest_grades),
            "prediction": predict_next_term(student.id)
        }

    return render_template(
        'dashboards/student_dashboard.html',
        school=school,
        student=student,
        grades_by_term=grades_by_term,
        ai_remarks=ai_remarks
    )

# --- 5. PDF REPORTING & ANALYTICS API ---

@app.route('/report/pdf/<int:student_id>/<term>')
@login_required
def download_report_card(student_id, term):
    # Security check: Ensure the logged-in user can access this report
    student = Student.query.get_or_404(student_id)
    if current_user.role == UserRole.STUDENT and current_user.student_profile.id != student_id:
        abort(403)
    if (current_user.role == UserRole.TEACHER or current_user.role == UserRole.SCHOOL_ADMIN) and \
       current_user.school_id != student.school_id:
        abort(403)
        
    # Fetch data for the report
    grades = Grade.query.filter_by(student_id=student.id, term=term).all()
    if not grades:
        flash(f"No grades found for {student.full_name} in {term}.", 'warning')
        return redirect(request.referrer or url_for('dashboard'))

    # Generate PDF
    pdf_bytes = generate_pdf_report(student, grades, term)
    
    filename = f"{student.admission_number.replace('/', '-')}_{term.replace(' ', '_')}_Report.pdf"
    
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/analytics/student_trend/<int:student_id>')
@login_required
def api_student_trend(student_id):
    """API endpoint to feed data to the student's personal chart."""
    # Security check (abbreviated)
    if current_user.role == UserRole.STUDENT and current_user.student_profile.id != student_id:
        abort(403)
    
    data = get_student_grade_trend(student_id)
    return jsonify(data)

@app.route('/api/analytics/class_distribution/<form_num>')
@login_required
@role_required(UserRole.SCHOOL_ADMIN)
def api_class_distribution(form_num):
    """API endpoint for admin dashboard chart."""
    data = get_class_grade_distribution(current_user.school_id, int(form_num))
    return jsonify(data)

# --- RUN APPLICATION ---

if __name__ == '__main__':
    app.run(debug=True)