# utils/bulk_importer.py
# Contains all logic for processing bulk file uploads.

import pandas as pd
from models import db, Subject, Student, User, School, UserRole
# from app import generate_admission_number # <-- DELETED FROM HERE
from sqlalchemy.exc import IntegrityError

def process_subject_upload(file_storage, school_id):
    """
    Processes an uploaded Excel file to bulk-import subjects.
    
    Returns:
        dict: A report of added, skipped, and error items.
    """
    try:
        df = pd.read_excel(file_storage)
    except Exception as e:
        raise ValueError(f"Could not read Excel file. Error: {e}")

    if 'SubjectName' not in df.columns:
        raise ValueError("Invalid file format. Missing required column: 'SubjectName'")

    existing_subjects = {
        s.name.lower() for s in Subject.query.filter_by(school_id=school_id).all()
    }
    
    report = {"added": 0, "skipped": 0, "errors": []}
    
    for index, row in df.iterrows():
        subject_name = str(row['SubjectName']).strip()
        
        if not subject_name or pd.isna(row['SubjectName']):
            report["skipped"] += 1
            report["errors"].append(f"Row {index+2}: SubjectName is blank.")
            continue
            
        if subject_name.lower() in existing_subjects:
            report["skipped"] += 1
            report["errors"].append(f"Row {index+2}: Subject '{subject_name}' already exists.")
            continue
            
        try:
            new_subject = Subject(name=subject_name, school_id=school_id)
            db.session.add(new_subject)
            existing_subjects.add(subject_name.lower())
            report["added"] += 1
        except Exception as e:
            report["skipped"] += 1
            report["errors"].append(f"Row {index+2}: Error adding '{subject_name}'. {e}")

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        raise ValueError(f"Database error. This may be due to duplicate data. {e}")
    except Exception as e:
        db.session.rollback()
        raise ValueError(f"An unknown error occurred. {e}")

    return report


def process_student_upload(file_storage, school):
    """
    Processes an uploaded Excel file to bulk-import students.
    
    Returns:
        dict: A report of added, skipped, and error items.
    """
    
    # Import moved inside to break circular dependency
    from app import generate_admission_number 

    try:
        df = pd.read_excel(file_storage)
    except Exception as e:
        raise ValueError(f"Could not read Excel file. Error: {e}")

    required_cols = ['FullName', 'AdmissionYear', 'LoginUsername', 'InitialPassword']
    if not all(col in df.columns for col in required_cols):
        raise ValueError(f"Invalid file format. Missing one or more required columns: {required_cols}")

    existing_usernames = {u.username for u in User.query.all()}
    student_count = Student.query.filter_by(school_id=school.id).count()
    school_code_base = school.school_code.split('@')[0]
    
    report = {"added": 0, "skipped": 0, "errors": []}
    new_users_in_file = [] # To track usernames in *this file*
    
    for index, row in df.iterrows():
        full_name = str(row['FullName']).strip()
        adm_year = row['AdmissionYear']
        username = str(row['LoginUsername']).strip()
        password = str(row['InitialPassword']).strip()
        
        if any(pd.isna(row[col]) for col in required_cols) or not all([full_name, adm_year, username, password]):
            report["skipped"] += 1
            report["errors"].append(f"Row {index+2}: One or more cells are blank.")
            continue
        
        try:
            adm_year = int(adm_year)
            if not (2000 <= adm_year <= 2100):
                raise ValueError("Year must be 4 digits.")
        except ValueError:
            report["skipped"] += 1
            report["errors"].append(f"Row {index+2}: 'AdmissionYear' must be a 4-digit number (e.g., 2025).")
            continue
            
        if username in existing_usernames or username in new_users_in_file:
            report["skipped"] += 1
            report["errors"].append(f"Row {index+2}: Username '{username}' is already taken.")
            continue
        
        if len(password) < 6:
            report["skipped"] += 1
            report["errors"].append(f"Row {index+2}: Password for '{username}' must be at least 6 characters.")
            continue
        
        try:
            # 1. Create User
            new_user = User(username=username, role=UserRole.STUDENT, school_id=school.id)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush() 
            
            # 2. Create Admission Number
            student_count += 1
            year_str = str(adm_year)[-2:]
            adm_num = generate_admission_number(school_code_base, student_count, year_str)
            
            # 3. Create Student
            new_student = Student(full_name=full_name, admission_number=adm_num, admission_year=adm_year, user_id=new_user.id, school_id=school.id)
            db.session.add(new_student)
            
            new_users_in_file.append(username)
            report["added"] += 1

        except Exception as e:
            db.session.rollback() 
            report["skipped"] += 1
            report["errors"].append(f"Row {index+2}: Error for '{username}'. {e}")

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        raise ValueError(f"Database error. This may be due to duplicate data. {e}")
    except Exception as e:
        db.session.rollback()
        raise ValueError(f"An unknown error occurred. {e}")

    return report

# --- NEW FUNCTION ---
def process_school_upload(file_storage):
    """
    Processes an uploaded Excel file to bulk-import schools.
    
    Returns:
        dict: A report of added, skipped, and error items.
    """
    try:
        df = pd.read_excel(file_storage)
    except Exception as e:
        raise ValueError(f"Could not read Excel file. Error: {e}")

    required_cols = ['SchoolName', 'SchoolCode', 'AdminUsername', 'AdminPassword']
    if not all(col in df.columns for col in required_cols):
        raise ValueError(f"Invalid file format. Missing one or more required columns: {required_cols}")

    # Get existing data to prevent duplicates
    existing_school_codes = {s.school_code for s in School.query.all()}
    existing_usernames = {u.username for u in User.query.all()}
    
    report = {"added": 0, "skipped": 0, "errors": []}
    new_codes_in_file = []
    new_users_in_file = []
    
    for index, row in df.iterrows():
        school_name = str(row['SchoolName']).strip()
        school_code = str(row['SchoolCode']).strip()
        admin_user = str(row['AdminUsername']).strip()
        admin_pass = str(row['AdminPassword']).strip()

        # --- Data Validation ---
        if any(pd.isna(row[col]) for col in required_cols) or not all([school_name, school_code, admin_user, admin_pass]):
            report["skipped"] += 1
            report["errors"].append(f"Row {index+2}: One or more cells are blank.")
            continue
        
        if school_code in existing_school_codes or school_code in new_codes_in_file:
            report["skipped"] += 1
            report["errors"].append(f"Row {index+2}: SchoolCode '{school_code}' is already taken.")
            continue
            
        if admin_user in existing_usernames or admin_user in new_users_in_file:
            report["skipped"] += 1
            report["errors"].append(f"Row {index+2}: AdminUsername '{admin_user}' is already taken.")
            continue
            
        if len(admin_pass) < 6:
            report["skipped"] += 1
            report["errors"].append(f"Row {index+2}: Password for '{admin_user}' must be at least 6 characters.")
            continue
        
        # --- Passed Validation: Create Objects ---
        try:
            # 1. Create School
            new_school = School(
                name=school_name,
                school_code=school_code
            )
            db.session.add(new_school)
            db.session.flush() # Get new_school.id

            # 2. Create School Admin User
            new_admin = User(
                username=admin_user,
                role=UserRole.SCHOOL_ADMIN,
                school_id=new_school.id
            )
            new_admin.set_password(admin_pass)
            db.session.add(new_admin)
            
            # Add to local tracking
            new_codes_in_file.append(school_code)
            new_users_in_file.append(admin_user)
            report["added"] += 1

        except Exception as e:
            db.session.rollback() # Rollback this specific school/admin pair
            report["skipped"] += 1
            report["errors"].append(f"Row {index+2}: Error for '{school_code}'. {e}")

    try:
        db.session.commit() # Commit all successful schools at once
    except IntegrityError as e:
        db.session.rollback()
        raise ValueError(f"Database error. This may be due to duplicate data. {e}")
    except Exception as e:
        db.session.rollback()
        raise ValueError(f"An unknown error occurred. {e}")

    return report