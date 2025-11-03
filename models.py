# models.py
# This file defines the database schema for our entire ecosystem.

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Enum
import enum
import uuid
from datetime import date

db = SQLAlchemy()

# --- Enums ---

class UserRole(enum.Enum):
    SUPER_ADMIN = "super_admin"
    SCHOOL_ADMIN = "school_admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"

class GradeLetter(enum.Enum):
    AP = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"

class AttendanceStatus(enum.Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    LATE = "Late"
    EXCUSED = "Excused"

# --- Association Table for Parent-Student ---

parent_student_association = db.Table('parent_student_association',
    db.Column('parent_id', db.Integer, db.ForeignKey('parent.id'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('student.id'), primary_key=True)
)

# --- Core Models ---

class School(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    school_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    users = db.relationship('User', back_populates='school', lazy=True)
    students = db.relationship('Student', back_populates='school', lazy=True)
    teachers = db.relationship('Teacher', back_populates='school', lazy=True)
    subjects = db.relationship('Subject', back_populates='school', lazy=True)
    parents = db.relationship('Parent', back_populates='school', lazy=True)

    def __repr__(self):
        return f"<School {self.school_code}>"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256))
    role = db.Column(Enum(UserRole), nullable=False)
    
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=True)
    school = db.relationship('School', back_populates='users')

    student_profile = db.relationship('Student', back_populates='user', uselist=False, cascade="all, delete-orphan")
    teacher_profile = db.relationship('Teacher', back_populates='user', uselist=False, cascade="all, delete-orphan")
    parent_profile = db.relationship('Parent', back_populates='user', uselist=False, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.role.name})>"

# --- School-Specific Data Models ---

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    admission_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # --- NEW LOGIC ---
    # We no longer store 'form'. We store when they were admitted.
    admission_year = db.Column(db.Integer, nullable=False) 
    # --- END NEW LOGIC ---
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', back_populates='student_profile')
    
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    school = db.relationship('School', back_populates='students')
    
    parents = db.relationship('Parent', secondary=parent_student_association, back_populates='children')
    link_code = db.relationship('StudentLinkCode', back_populates='student', uselist=False, cascade="all, delete-orphan")
    grades = db.relationship('Grade', back_populates='student', lazy='dynamic', cascade="all, delete-orphan")
    attendance_records = db.relationship('Attendance', back_populates='student', lazy='dynamic', cascade="all, delete-orphan")

    # --- NEW SMART PROPERTY ---
    @property
    def form(self):
        """Calculates the student's current form based on admission year."""
        current_year = date.today().year
        # (2025 - 2025) + 1 = Form 1
        # (2025 - 2024) + 1 = Form 2
        # (2025 - 2023) + 1 = Form 3
        # (2025 - 2022) + 1 = Form 4
        calculated_form = (current_year - self.admission_year) + 1
        # A student cannot be higher than Form 4
        return min(calculated_form, 4)
    # --- END NEW ---

    def __repr__(self):
        return f"<Student {self.full_name} ({self.admission_number})>"

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', back_populates='teacher_profile')
    
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    school = db.relationship('School', back_populates='teachers')
    
    grades_given = db.relationship('Grade', back_populates='teacher', lazy='dynamic')
    attendance_taken = db.relationship('Attendance', back_populates='teacher', lazy='dynamic')

    def __repr__(self):
        return f"<Teacher {self.full_name}>"

class Parent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', back_populates='parent_profile')
    
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    school = db.relationship('School', back_populates='parents')
    
    children = db.relationship('Student', secondary=parent_student_association, back_populates='parents')

    def __repr__(self):
        return f"<Parent {self.full_name}>"

class StudentLinkCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    is_used = db.Column(db.Boolean, default=False, nullable=False)
    
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), unique=True, nullable=False)
    student = db.relationship('Student', back_populates='link_code')

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    school = db.relationship('School', back_populates='subjects')
    
    grades = db.relationship('Grade', back_populates='subject', lazy='dynamic')

    def __repr__(self):
        return f"<Subject {self.name}>"

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    marks = db.Column(db.Integer, nullable=False)
    grade_letter = db.Column(Enum(GradeLetter), nullable=False)
    term = db.Column(db.String(50), nullable=False)
    
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    
    student = db.relationship('Student', back_populates='grades')
    subject = db.relationship('Subject', back_populates='grades')
    teacher = db.relationship('Teacher', back_populates='grades_given')

    def __repr__(self):
        return f"<Grade {self.student.full_name} - {self.subject.name}: {self.marks}>"

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(Enum(AttendanceStatus), nullable=False)
    
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    
    student = db.relationship('Student', back_populates='attendance_records')
    teacher = db.relationship('Teacher', back_populates='attendance_taken')

    def __repr__(self):
        return f"<Attendance {self.student.full_name} on {self.date}: {self.status.name}>"