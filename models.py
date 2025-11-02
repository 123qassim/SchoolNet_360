# models.py
# This file defines the database schema for our entire ecosystem.
# We use a multi-tenant approach: most models are linked to a 'School'.

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Enum
import enum

db = SQLAlchemy()

# Define Enums for roles and grades
class UserRole(enum.Enum):
    SUPER_ADMIN = "super_admin"
    SCHOOL_ADMIN = "school_admin"
    TEACHER = "teacher"
    STUDENT = "student"

class GradeLetter(enum.Enum):
    AP = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"

# --- Core Models ---

class School(db.Model):
    """Represents an individual school in the ecosystem."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    school_code = db.Column(db.String(20), unique=True, nullable=False, index=True) # e.g., GHS@1
    
    # Relationships
    users = db.relationship('User', back_populates='school', lazy=True)
    students = db.relationship('Student', back_populates='school', lazy=True)
    teachers = db.relationship('Teacher', back_populates='school', lazy=True)
    subjects = db.relationship('Subject', back_populates='school', lazy=True)

    def __repr__(self):
        return f"<School {self.school_code}>"

class User(db.Model, UserMixin):
    """Unified User model for login (Admin, Teacher, Student)."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True) # Login username
    password_hash = db.Column(db.String(256))
    role = db.Column(Enum(UserRole), nullable=False)
    
    # Foreign Key to School
    # Nullable=True ONLY for SUPER_ADMIN
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=True)
    school = db.relationship('School', back_populates='users')

    # Relationships to specific profiles
    student_profile = db.relationship('Student', back_populates='user', uselist=False, cascade="all, delete-orphan")
    teacher_profile = db.relationship('Teacher', back_populates='user', uselist=False, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.role.name})>"

# --- School-Specific Data Models ---

class Student(db.Model):
    """Profile for a student user."""
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    # Format: GHS/00001/025
    admission_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    form = db.Column(db.Integer, nullable=False) # e.g., 1, 2, 3, 4
    
    # Link to the unified User login
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', back_populates='student_profile')
    
    # Link to the school (for data segregation)
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    school = db.relationship('School', back_populates='students')
    
    # Relationships
    grades = db.relationship('Grade', back_populates='student', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Student {self.full_name} ({self.admission_number})>"

class Teacher(db.Model):
    """Profile for a teacher user."""
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    
    # Link to the unified User login
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', back_populates='teacher_profile')
    
    # Link to the school
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    school = db.relationship('School', back_populates='teachers')
    
    # Relationships
    grades_given = db.relationship('Grade', back_populates='teacher', lazy='dynamic')

    def __repr__(self):
        return f"<Teacher {self.full_name}>"

class Subject(db.Model):
    """Subjects taught at a specific school."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    school = db.relationship('School', back_populates='subjects')
    
    grades = db.relationship('Grade', back_populates='subject', lazy='dynamic')

    def __repr__(self):
        return f"<Subject {self.name}>"

class Grade(db.Model):
    """A single grade entry for a student in a subject."""
    id = db.Column(db.Integer, primary_key=True)
    marks = db.Column(db.Integer, nullable=False)
    grade_letter = db.Column(Enum(GradeLetter), nullable=False)
    term = db.Column(db.String(50), nullable=False) # e.g., "Term 1 2025"
    
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False) # Teacher who entered the mark
    
    student = db.relationship('Student', back_populates='grades')
    subject = db.relationship('Subject', back_populates='grades')
    teacher = db.relationship('Teacher', back_populates='grades_given')

    def __repr__(self):
        return f"<Grade {self.student.full_name} - {self.subject.name}: {self.marks}>"