# utils/csv_tools.py
# Utility to load mock data from CSVs into the SQLite database.

import pandas as pd
from models import db, School, User, Student, Teacher, Subject, Grade, UserRole
from datetime import datetime

DATA_DIR = 'data'

def load_data_from_csv():
    """Loads all mock data from CSV files into the database."""
    try:
        # We move the import inside the function to break circular imports
        from app import calculate_grade_letter, generate_admission_number

        # 1. Load Schools
        schools_df = pd.read_csv(f'{DATA_DIR}/schools.csv')
        for _, row in schools_df.iterrows():
            school = School(name=row['name'], school_code=row['school_code'])
            db.session.add(school)
        db.session.commit()
        print("Schools loaded.")

        school_map = {s.school_code: s.id for s in School.query.all()}
        
        # 2. Load Users (and their profiles)
        users_df = pd.read_csv(f'{DATA_DIR}/users.csv').fillna('')
        student_id_counter = {} 
        
        for _, row in users_df.iterrows():
            role = UserRole(row['role'])
            school_id = school_map.get(row['school_code'])
            
            if not school_id and role != UserRole.SUPER_ADMIN:
                print(f"Skipping user {row['username']} - school code {row['school_code']} not found.")
                continue

            user = User(
                username=row['username'],
                role=role,
                school_id=school_id
            )
            user.set_password(row['password'])
            db.session.add(user)
            db.session.flush() 

            # Create profiles
            if role == UserRole.STUDENT:
                school_code_base = row['school_code'].split('@')[0]
                
                if school_code_base not in student_id_counter:
                    student_id_counter[school_code_base] = 0
                student_id_counter[school_code_base] += 1
                
                # --- NEW LOGIC ---
                adm_year = int(row['admission_year'])
                year_str = str(adm_year)[-2:] # e.g., 2025 -> "25"
                
                adm_num = generate_admission_number(
                    school_code_base,
                    student_id_counter[school_code_base],
                    year_str  # Pass the 2-digit year string
                )
                
                student = Student(
                    full_name=row['full_name'],
                    admission_number=adm_num,
                    admission_year=adm_year, # Store the full admission year
                    user_id=user.id,
                    school_id=school_id
                )
                # --- END NEW LOGIC ---
                db.session.add(student)
            
            elif role == UserRole.TEACHER:
                teacher = Teacher(
                    full_name=row['full_name'],
                    user_id=user.id,
                    school_id=school_id
                )
                db.session.add(teacher)
        
        db.session.commit()
        print("Users, Students, and Teachers loaded.")

        # 3. Load Subjects
        subjects_df = pd.read_csv(f'{DATA_DIR}/subjects.csv')
        for _, row in subjects_df.iterrows():
            school_id = school_map.get(row['school_code'])
            if school_id:
                subject = Subject(name=row['name'], school_id=school_id)
                db.session.add(subject)
        db.session.commit()
        print("Subjects loaded.")

        student_map = {s.admission_number: s.id for s in Student.query.all()}
        subject_map = {(s.name, s.school_id): s.id for s in Subject.query.all()}
        teacher_map = {u.username: u.teacher_profile.id for u in User.query.filter_by(role=UserRole.TEACHER).all() if u.teacher_profile}

        # 4. Load Grades
        grades_df = pd.read_csv(f'{DATA_DIR}/grades.csv')
        for _, row in grades_df.iterrows():
            student_id = student_map.get(row['student_admission_number'])
            
            student = Student.query.get(student_id)
            if not student:
                print(f"Skipping grade - student {row['student_admission_number']} not found.")
                continue
            
            school_id = student.school_id
            subject_id = subject_map.get((row['subject_name'], school_id))
            teacher_id = teacher_map.get(row['teacher_username'])
            
            if student_id and subject_id and teacher_id:
                grade = Grade(
                    marks=int(row['marks']),
                    grade_letter=calculate_grade_letter(int(row['marks'])),
                    term=row['term'],
                    student_id=student_id,
                    subject_id=subject_id,
                    teacher_id=teacher_id
                )
                db.session.add(grade)
            else:
                print(f"Skipping grade for {row['student_admission_number']} - missing relation.")
                
        db.session.commit()
        print("Grades loaded.")
        print("--- Mock Data Load Complete ---")

    except Exception as e:
        db.session.rollback()
        print(f"An error occurred during data loading: {e}")