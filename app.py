# app.py
# Main Flask application file for the Multi-School Academic System v8.0

import os
import pandas as pd
from datetime import datetime, date
from functools import wraps
import io 

from flask import (
    Flask, render_template, redirect, url_for, flash, request,
    session, abort, jsonify, Response, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    current_user, login_required
)
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField
from wtforms.fields import DateField, FileField
from wtforms.validators import DataRequired, EqualTo, ValidationError, Length, NumberRange
from flask_wtf.file import FileAllowed
from flask_wtf.csrf import CSRFProtect
from weasyprint import HTML
from sqlalchemy.sql import func

# Import models and db instance
from models import (
    db, School, User, Student, Teacher, Subject, Grade, UserRole, GradeLetter,
    Parent, StudentLinkCode, Attendance, AttendanceStatus
)
# Import utilities
from utils.analytics import (
    get_student_grade_trend, get_class_grade_distribution, 
    get_subject_averages, get_school_comparison
)
from utils.ai_predictor import generate_ai_remark, predict_next_term
from utils.pdf_generator import generate_pdf_report
from utils.csv_tools import load_data_from_csv
# --- UPDATED IMPORT ---
from utils.bulk_importer import (
    process_subject_upload, process_student_upload, process_school_upload
)

# --- APP CONFIGURATION ---

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
login_manager.login_view = 'select_school'
login_manager.login_message = "You must be logged in to access this page."
login_manager.login_message_category = "danger"

# --- HELPER FUNCTIONS & DECORATORS ---

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_current_school():
    if current_user.is_authenticated and current_user.role != UserRole.SUPER_ADMIN:
        return School.query.get(current_user.school_id)
    return None

def calculate_grade_letter(marks):
    if marks >= 90: return GradeLetter.AP
    if marks >= 80: return GradeLetter.A
    if marks >= 70: return GradeLetter.B
    if marks >= 60: return GradeLetter.C
    if marks >= 50: return GradeLetter.D
    return GradeLetter.F

def generate_admission_number(school_code_base, student_id, year_str):
    return f"{school_code_base}/{student_id:05d}/{year_str}"

# --- DATABASE INITIALIZATION ---

@app.cli.command("init-db")
def init_db_command():
    print("Dropping and recreating database...")
    db.drop_all()
    db.create_all()
    print("Loading data from CSV files...")
    load_data_from_csv()
    print("Database initialized successfully!")

with app.app_context():
    if not os.path.exists(os.path.join(basedir, 'data', 'ecosystem.db')):
        print("Database not found. Creating and initializing...")
        db.create_all()
        load_data_from_csv()
        print("Database created and initialized.")

# --- FORMS (WTForms) ---

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SchoolRegistrationForm(FlaskForm):
    school_name = StringField('School Name', validators=[DataRequired(), Length(min=3, max=150)])
    school_code = StringField('School Code (e.g., GHS@1)', validators=[DataRequired(), Length(min=3, max=20)])
    admin_username = StringField('Admin Username', validators=[DataRequired(), Length(min=4, max=100)])
    admin_password = PasswordField('Admin Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Register School')
    def validate_school_code(self, field):
        if School.query.filter_by(school_code=field.data).first(): raise ValidationError('This School Code is already taken.')
    def validate_admin_username(self, field):
        if User.query.filter_by(username=field.data).first(): raise ValidationError('This Admin Username is already taken.')

class GradeEntryForm(FlaskForm):
    student_admission = StringField('Student Admission Number', validators=[DataRequired()])
    subject_id = SelectField('Subject', coerce=int, validators=[DataRequired()])
    term = SelectField('Term', choices=[('Term 1 2025', 'Term 1 2025'), ('Term 2 2025', 'Term 2 2025'), ('Term 3 2025', 'Term 3 2025')], validators=[DataRequired()])
    marks = IntegerField('Marks (0-100)', validators=[DataRequired()])
    submit = SubmitField('Submit Grade')

class SubjectForm(FlaskForm):
    name = StringField('Subject Name', validators=[DataRequired(), Length(min=3, max=100)])
    submit = SubmitField('Add Subject')
    def validate_name(self, field):
        if Subject.query.filter_by(name=field.data, school_id=current_user.school_id).first(): raise ValidationError('This subject already exists for your school.')

class StudentRegistrationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=3, max=150)])
    admission_year = IntegerField('Admission Year (e.g., 2025)', validators=[DataRequired(), NumberRange(min=2000, max=2100, message="Please enter a valid 4-digit year.")])
    username = StringField('Login Username', validators=[DataRequired(), Length(min=4, max=100)])
    password = PasswordField('Initial Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Register Student')
    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first(): raise ValidationError('This username is already taken.')

class ParentRegistrationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=3, max=150)])
    username = StringField('Login Username', validators=[DataRequired(), Length(min=4, max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    submit = SubmitField('Create Account')
    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first(): raise ValidationError('This username is already taken.')

class LinkStudentForm(FlaskForm):
    link_code = StringField('Student Link Code', validators=[DataRequired(), Length(min=36, max=36)])
    submit = SubmitField('Link Student')

class AttendanceSelectionForm(FlaskForm):
    form_num = SelectField('Select Form', choices=[(1, 'Form 1'), (2, 'Form 2'), (3, 'Form 3'), (4, 'Form 4')], coerce=int, validators=[DataRequired()])
    date = DateField('Select Date', validators=[DataRequired()], default=date.today)
    submit = SubmitField('Load Roster')

# --- UPDATED BULK UPLOAD FORMS ---
class SubjectUploadForm(FlaskForm):
    subject_file = FileField('Subjects Excel File', validators=[DataRequired(), FileAllowed(['xlsx'], 'Excel files only!')])
    submit_subjects = SubmitField('Upload Subjects')

class StudentUploadForm(FlaskForm):
    student_file = FileField('Students Excel File', validators=[DataRequired(), FileAllowed(['xlsx'], 'Excel files only!')])
    submit_students = SubmitField('Upload Students')

class SchoolUploadForm(FlaskForm):
    school_file = FileField('Schools Excel File', validators=[DataRequired(), FileAllowed(['xlsx'], 'Excel files only!')])
    submit_schools = SubmitField('Upload Schools')

# --- ERROR HANDLERS ---
@app.errorhandler(403)
def forbidden(error): return render_template('errors/403.html'), 403
@app.errorhandler(404)
def not_found(error): return render_template('errors/404.html'), 404
@app.errorhandler(500)
def internal_server(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# --- AUTHENTICATION & PUBLIC ROUTES ---
@app.route('/')
def select_school():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    schools = School.query.order_by(School.name).all()
    return render_template('school_select.html', schools=schools)

@app.route('/register/parent/<school_code>', methods=['GET', 'POST'])
def parent_register(school_code):
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    school = School.query.filter_by(school_code=school_code).first_or_404()
    form = ParentRegistrationForm()
    if form.validate_on_submit():
        try:
            new_user = User(username=form.username.data, role=UserRole.PARENT, school_id=school.id)
            new_user.set_password(form.password.data)
            db.session.add(new_user)
            db.session.flush()
            new_parent = Parent(full_name=form.full_name.data, user_id=new_user.id, school_id=school.id)
            db.session.add(new_parent)
            db.session.commit()
            login_user(new_user)
            flash('Account created successfully! Now, please link your first student.', 'success')
            return redirect(url_for('parent_link_student'))
        except Exception as e:
            db.session.rollback()
            if 'UNIQUE constraint failed: user.username' in str(e): flash('This username is already taken.', 'danger')
            else: flash(f'Error creating account: {e}', 'danger')
    return render_template('parent_register.html', form=form, school=school)

@app.route('/login/<role>/<school_code>', methods=['GET', 'POST'])
def login(role, school_code):
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    form = LoginForm()
    if role == "super_admin": school = None
    else: school = School.query.filter_by(school_code=school_code).first_or_404()
    template_map = {
        "admin": ("admin_login.html", UserRole.SCHOOL_ADMIN), "teacher": ("teacher_login.html", UserRole.TEACHER),
        "student": ("student_login.html", UserRole.STUDENT), "super_admin": ("admin_login.html", UserRole.SUPER_ADMIN),
        "parent": ("parent_login.html", UserRole.PARENT)
    }
    if role not in template_map: abort(404)
    template, role_enum = template_map[role]
    if form.validate_on_submit():
        if school: user = User.query.filter_by(username=form.username.data, school_id=school.id, role=role_enum).first()
        else: user = User.query.filter_by(username=form.username.data, role=UserRole.SUPER_ADMIN).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        else: flash('Invalid username or password.', 'danger')
    if template == "parent_login.html": template = "admin_login.html"
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
    if current_user.role == UserRole.SUPER_ADMIN: return redirect(url_for('super_admin_dashboard'))
    elif current_user.role == UserRole.SCHOOL_ADMIN: return redirect(url_for('admin_dashboard'))
    elif current_user.role == UserRole.TEACHER: return redirect(url_for('teacher_dashboard'))
    elif current_user.role == UserRole.STUDENT: return redirect(url_for('student_dashboard'))
    elif current_user.role == UserRole.PARENT: return redirect(url_for('parent_dashboard'))
    else: abort(403)

# --- 1. SUPER ADMIN DASHBOARD ---
@app.route('/dashboard/super_admin', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.SUPER_ADMIN)
def super_admin_dashboard():
    form = SchoolRegistrationForm()
    bulk_form = SchoolUploadForm() # <-- NEW
    report = None
    
    # Check which form was submitted
    if form.submit.data and form.validate_on_submit(): # Manual add
        try:
            new_school = School(name=form.school_name.data, school_code=form.school_code.data)
            db.session.add(new_school)
            db.session.flush()
            admin_user = User(username=form.admin_username.data, role=UserRole.SCHOOL_ADMIN, school_id=new_school.id)
            admin_user.set_password(form.admin_password.data)
            db.session.add(admin_user)
            db.session.commit()
            flash(f"School '{new_school.name}' and admin '{admin_user.username}' created!", 'success')
            return redirect(url_for('super_admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating school: {e}", 'danger')
            
    # --- NEW: HANDLE BULK UPLOAD ---
    if bulk_form.submit_schools.data and bulk_form.validate_on_submit():
        try:
            file = bulk_form.school_file.data
            report = process_school_upload(file)
            flash(f"School import complete! Added: {report['added']}, Skipped: {report['skipped']}.", "success")
            if report['errors']:
                flash("Some rows were skipped (see details below).", "warning")
        except Exception as e:
            flash(f"An error occurred during school import: {e}", "danger")
        # Need to reload schools list after import
        schools = School.query.all()
        return render_template('dashboards/super_admin_dashboard.html', form=form, bulk_form=bulk_form, schools=schools, comparison_data=get_school_comparison(), report=report)

    schools = School.query.all()
    comparison_data = get_school_comparison()
    return render_template('dashboards/super_admin_dashboard.html', form=form, bulk_form=bulk_form, schools=schools, comparison_data=comparison_data, report=report)

# --- NEW: SUPER ADMIN TEMPLATE DOWNLOAD ---
@app.route('/super_admin/bulk/download/schools_template')
@login_required
@role_required(UserRole.SUPER_ADMIN)
def super_admin_download_template():
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df = pd.DataFrame(columns=['SchoolName', 'SchoolCode', 'AdminUsername', 'AdminPassword'])
    df.to_excel(writer, index=False, sheet_name='Schools')
    writer.close()
    output.seek(0)
    
    return Response(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment;filename=schools_template.xlsx"}
    )

# --- 2. SCHOOL ADMIN DASHBOARD ---
@app.route('/dashboard/admin')
@login_required
@role_required(UserRole.SCHOOL_ADMIN)
def admin_dashboard():
    school = get_current_school()
    student_count = Student.query.filter_by(school_id=school.id).count()
    teacher_count = Teacher.query.filter_by(school_id=school.id).count()
    subject_count = Subject.query.filter_by(school_id=school.id).count()
    parent_count = Parent.query.filter_by(school_id=school.id).count()
    stats = {"student_count": student_count, "teacher_count": teacher_count, "subject_count": subject_count, "parent_count": parent_count}
    return render_template('dashboards/admin_dashboard.html', school=school, stats=stats)

@app.route('/admin/students', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.SCHOOL_ADMIN)
def admin_manage_students():
    school = get_current_school(); form = StudentRegistrationForm()
    if form.validate_on_submit():
        try:
            new_user = User(username=form.username.data, role=UserRole.STUDENT, school_id=school.id)
            new_user.set_password(form.password.data); db.session.add(new_user); db.session.flush()
            student_count = Student.query.filter_by(school_id=school.id).count() + 1
            school_code_base = school.school_code.split('@')[0]; adm_year = form.admission_year.data
            year_str = str(adm_year)[-2:]
            adm_num = generate_admission_number(school_code_base, student_count, year_str)
            new_student = Student(full_name=form.full_name.data, admission_number=adm_num, admission_year=adm_year, user_id=new_user.id, school_id=school.id)
            db.session.add(new_student); db.session.commit()
            flash(f'Student {new_student.full_name} ({adm_num}) created successfully!', 'success')
            return redirect(url_for('admin_manage_students'))
        except Exception as e:
            db.session.rollback()
            if 'UNIQUE constraint failed: user.username' in str(e): flash('This username is already taken.', 'danger')
            else: flash(f'Error creating student: {e}', 'danger')
    students = Student.query.filter_by(school_id=school.id).order_by(Student.admission_year.desc(), Student.full_name).all()
    return render_template('admin/manage_students.html', form=form, students=students, school=school)

@app.route('/admin/students/generate_code/<int:student_id>', methods=['POST'])
@login_required
@role_required(UserRole.SCHOOL_ADMIN)
def admin_generate_link_code(student_id):
    student = Student.query.get_or_404(student_id)
    if student.school_id != current_user.school_id: abort(403)
    if student.link_code: db.session.delete(student.link_code)
    new_code = StudentLinkCode(student_id=student.id)
    db.session.add(new_code); db.session.commit()
    flash(f"New link code generated for {student.full_name}. The old code is now invalid.", "success")
    return redirect(url_for('admin_manage_students'))

@app.route('/admin/subjects', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.SCHOOL_ADMIN)
def admin_manage_subjects():
    school = get_current_school(); form = SubjectForm()
    if form.validate_on_submit():
        try:
            new_subject = Subject(name=form.name.data, school_id=school.id)
            db.session.add(new_subject); db.session.commit()
            flash(f'Subject "{new_subject.name}" added successfully!', 'success')
            return redirect(url_for('admin_manage_subjects'))
        except Exception as e:
            db.session.rollback(); flash(f'Error adding subject: {e}', 'danger')
    subjects = Subject.query.filter_by(school_id=school.id).order_by(Subject.name).all()
    return render_template('admin/manage_subjects.html', form=form, subjects=subjects, school=school)

# --- UPDATED BULK DATA ROUTES ---
@app.route('/admin/bulk_manage', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.SCHOOL_ADMIN)
def admin_bulk_manage():
    subject_form = SubjectUploadForm()
    student_form = StudentUploadForm() 
    report = None
    if subject_form.submit_subjects.data and subject_form.validate_on_submit():
        try:
            file = subject_form.subject_file.data
            report = process_subject_upload(file, current_user.school_id)
            flash(f"Subject import complete! Added: {report['added']}, Skipped: {report['skipped']}.", "success")
            if report['errors']: flash("Some rows were skipped (see details below).", "warning")
        except Exception as e:
            flash(f"An error occurred during subject import: {e}", "danger")
    if student_form.submit_students.data and student_form.validate_on_submit():
        try:
            file = student_form.student_file.data
            school = get_current_school()
            report = process_student_upload(file, school)
            flash(f"Student import complete! Added: {report['added']}, Skipped: {report['skipped']}.", "success")
            if report['errors']: flash("Some rows were skipped (see details below).", "warning")
        except Exception as e:
            flash(f"An error occurred during student import: {e}", "danger")
    return render_template('admin/bulk_manage.html', subject_form=subject_form, student_form=student_form, report=report)

@app.route('/admin/bulk/download/<template_type>')
@login_required
@role_required(UserRole.SCHOOL_ADMIN)
def download_template(template_type):
    output = io.BytesIO(); writer = pd.ExcelWriter(output, engine='xlsxwriter')
    if template_type == 'subjects':
        df = pd.DataFrame(columns=['SubjectName'])
        df.to_excel(writer, index=False, sheet_name='Subjects')
        filename = "subjects_template.xlsx"
    elif template_type == 'students':
        df = pd.DataFrame(columns=['FullName', 'AdmissionYear', 'LoginUsername', 'InitialPassword'])
        df.to_excel(writer, index=False, sheet_name='Students')
        filename = "students_template.xlsx"
    else: abort(404)
    writer.close(); output.seek(0)
    return Response(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment;filename={filename}"})

# --- 3. TEACHER DASHBOARD ---
@app.route('/dashboard/teacher', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.TEACHER)
def teacher_dashboard():
    school = get_current_school(); teacher = current_user.teacher_profile; form = GradeEntryForm()
    form.subject_id.choices = [(s.id, s.name) for s in Subject.query.filter_by(school_id=school.id).order_by(Subject.name).all()]
    if form.validate_on_submit():
        student = Student.query.filter_by(admission_number=form.student_admission.data, school_id=school.id).first()
        if not student: flash('Error: Student admission number not found for this school.', 'danger')
        else:
            try:
                existing_grade = Grade.query.filter_by(student_id=student.id, subject_id=form.subject_id.data, term=form.term.data).first()
                if existing_grade:
                    existing_grade.marks = form.marks.data; existing_grade.grade_letter = calculate_grade_letter(form.marks.data); existing_grade.teacher_id = teacher.id
                    flash('Grade updated successfully!', 'success')
                else:
                    new_grade = Grade(marks=form.marks.data, grade_letter=calculate_grade_letter(form.marks.data), term=form.term.data, student_id=student.id, subject_id=form.subject_id.data, teacher_id=teacher.id)
                    db.session.add(new_grade)
                db.session.commit()
                flash('Grade submitted successfully!', 'success')
                return redirect(url_for('teacher_dashboard'))
            except Exception as e:
                db.session.rollback(); flash(f"Error submitting grade: {e}", 'danger')
    recent_grades = Grade.query.filter_by(teacher_id=teacher.id).order_by(Grade.id.desc()).limit(10).all()
    return render_template('dashboards/teacher_dashboard.html', school=school, teacher=teacher, form=form, recent_grades=recent_grades)

# --- ATTENDANCE ROUTES ---
@app.route('/teacher/attendance', methods=['GET'])
@login_required
@role_required(UserRole.TEACHER)
def teacher_attendance():
    form = AttendanceSelectionForm()
    form.date.data = datetime.strptime(request.args.get('date'), '%Y-%m-%d').date() if request.args.get('date') else date.today()
    form.form_num.data = int(request.args.get('form_num')) if request.args.get('form_num') else 1
    return render_template('teacher/take_attendance.html', form=form)

@app.route('/teacher/attendance/roster', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.TEACHER)
def teacher_attendance_roster():
    teacher = current_user.teacher_profile; school_id = current_user.school_id
    if request.method == 'POST':
        try:
            date_str = request.form.get('date'); date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            teacher_id = teacher.id; form_num = request.form.get('form_num')
            for key, status in request.form.items():
                if key.startswith('student_'):
                    student_id = key.split('_')[1]
                    att = Attendance.query.filter_by(date=date_obj, student_id=student_id).first()
                    if att: att.status = AttendanceStatus(status); att.teacher_id = teacher_id
                    else: att = Attendance(date=date_obj, status=AttendanceStatus(status), student_id=student_id, teacher_id=teacher_id); db.session.add(att)
            db.session.commit()
            flash(f"Attendance for Form {form_num} on {date_str} saved successfully!", "success")
            return redirect(url_for('teacher_attendance'))
        except Exception as e:
            db.session.rollback(); flash(f"Error saving attendance: {e}", "danger")
            return redirect(url_for('teacher_attendance'))
    form_num = request.args.get('form_num', 1, type=int); date_str = request.args.get('date')
    if not date_str: date_obj = date.today(); date_str = date_obj.isoformat()
    else: date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    current_year = date.today().year; required_admission_year = (current_year - form_num) + 1
    students = Student.query.filter_by(school_id=school_id, admission_year=required_admission_year).order_by(Student.full_name).all()
    existing_records_raw = Attendance.query.filter_by(date=date_obj).all()
    existing_records = {rec.student_id: rec.status for rec in existing_records_raw}
    return render_template('teacher/attendance_roster.html', students=students, date=date_obj, date_str=date_str, form_num=form_num, existing_records=existing_records, AttendanceStatus=AttendanceStatus)

# --- 4. STUDENT DASHBOARD ---
@app.route('/dashboard/student')
@login_required
@role_required(UserRole.STUDENT)
def student_dashboard():
    school = get_current_school(); student = current_user.student_profile
    grades_by_term = {}; all_grades = Grade.query.filter_by(student_id=student.id).order_by(Grade.term).all()
    for grade in all_grades:
        if grade.term not in grades_by_term: grades_by_term[grade.term] = []
        grades_by_term[grade.term].append(grade)
    latest_term = "Term 1 2025"; ai_remarks = {}
    if latest_term in grades_by_term:
        latest_grades = grades_by_term[latest_term]
        ai_remarks = {"summary": generate_ai_remark(latest_grades), "prediction": predict_next_term(student.id)}
    attendance_summary = db.session.query(Attendance.status, func.count(Attendance.status)).filter(Attendance.student_id == student.id).group_by(Attendance.status).all()
    att_summary_dict = {status.name: count for status, count in attendance_summary}
    return render_template('dashboards/student_dashboard.html', school=school, student=student, grades_by_term=grades_by_term, ai_remarks=ai_remarks, attendance_summary=att_summary_dict)

# --- 5. PARENT DASHBOARD & LINKING ---
@app.route('/dashboard/parent')
@login_required
@role_required(UserRole.PARENT)
def parent_dashboard():
    parent = current_user.parent_profile; students = parent.children
    if not students:
        flash("Please link a student to view your dashboard.", "info")
        return redirect(url_for('parent_link_student'))
    student_data = []
    for student in students:
        grades_by_term = {}; all_grades = Grade.query.filter_by(student_id=student.id).order_by(Grade.term.desc()).all()
        for grade in all_grades:
            if grade.term not in grades_by_term: grades_by_term[grade.term] = []
            grades_by_term[grade.term].append(grade)
        attendance_summary = db.session.query(Attendance.status, func.count(Attendance.status)).filter(Attendance.student_id == student.id).group_by(Attendance.status).all()
        att_summary_dict = {status.name: count for status, count in attendance_summary}
        student_data.append({"student": student, "grades_by_term": grades_by_term, "attendance_summary": att_summary_dict})
    return render_template('dashboards/parent_dashboard.html', parent=parent, student_data=student_data)

@app.route('/parent/link_student', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.PARENT)
def parent_link_student():
    form = LinkStudentForm(); parent = current_user.parent_profile
    if form.validate_on_submit():
        code = form.link_code.data
        link_code_obj = StudentLinkCode.query.filter_by(code=code, is_used=False).first()
        if link_code_obj:
            student = link_code_obj.student
            if student.school_id != parent.school_id:
                flash("This link code is for a student at a different school.", "danger")
                return redirect(url_for('parent_link_student'))
            parent.children.append(student); link_code_obj.is_used = True; db.session.commit()
            flash(f"Successfully linked {student.full_name} to your account!", "success")
            return redirect(url_for('parent_dashboard'))
        else:
            flash("Invalid, already used, or non-existent code. Please check for typos or contact your school admin for a new one.", "danger")
    return render_template('parent_link_student.html', form=form, parent=parent)

# --- 6. PDF REPORTING & ANALYTICS API ---
@app.route('/report/pdf/<int:student_id>/<term>')
@login_required
def download_report_card(student_id, term):
    student = Student.query.get_or_404(student_id)
    if current_user.role == UserRole.STUDENT and current_user.student_profile.id != student_id: abort(403)
    if (current_user.role == UserRole.TEACHER or current_user.role == UserRole.SCHOOL_ADMIN) and current_user.school_id != student.school_id: abort(403)
    if current_user.role == UserRole.PARENT:
        if student not in current_user.parent_profile.children: abort(403)
    grades = Grade.query.filter_by(student_id=student.id, term=term).all()
    if not grades:
        flash(f"No grades found for {student.full_name} in {term}.", 'warning')
        return redirect(request.referrer or url_for('dashboard'))
    pdf_bytes = generate_pdf_report(student, grades, term)
    filename = f"{student.admission_number.replace('/', '-')}_{term.replace(' ', '_')}_Report.pdf"
    return Response(pdf_bytes, mimetype="application/pdf", headers={"Content-disposition": f"attachment; filename={filename}"})

@app.route('/api/analytics/student_trend/<int:student_id>')
@login_required
def api_student_trend(student_id):
    student = Student.query.get_or_404(student_id)
    if current_user.role == UserRole.STUDENT and current_user.student_profile.id != student_id: abort(403)
    if current_user.role == UserRole.PARENT:
        if student not in current_user.parent_profile.children: abort(403)
    data = get_student_grade_trend(student_id)
    return jsonify(data)

@app.route('/api/analytics/class_distribution/<form_num>')
@login_required
@role_required(UserRole.SCHOOL_ADMIN)
def api_class_distribution(form_num):
    data = get_class_grade_distribution(current_user.school_id, int(form_num))
    return jsonify(data)

# --- RUN APPLICATION ---

if __name__ == '__main__':
    app.run(debug=True)