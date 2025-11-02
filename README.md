# 🏫 Multi-School Academic Management System (v7.0)

![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0-blueviolet.svg)
![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

A modern, scalable, multi-tenant academic grading ecosystem built with Python and Flask. This platform allows multiple independent schools to manage their students, teachers, subjects, and grades. It features role-based access, powerful analytics dashboards, and AI-powered report card generation.

## ✨ Key Features

* **Multi-Tenant Architecture:** Each school (e.g., `GHS@1`, `MHS@2`) operates in its own sandboxed environment.
* **Role-Based Access Control (RBAC):**
    * **Super Admin:** Manages all schools on the platform.
    * **School Admin:** Manages students, subjects, and teachers for their *own* school.
    * **Teacher:** Enters and updates student grades.
    * **Student:** Views their personal dashboard, analytics, and downloads reports.
* **Student & Subject Management:** School Admins can dynamically add, view, edit, and delete students and subjects.
* **Advanced Gradebook:** Teachers can enter marks by student admission number, which automatically calculates and assigns a letter grade.
* **PDF Report Generation:** Students and admins can download high-quality, print-ready PDF report cards for any term.
* **Visual Analytics:** Interactive charts (via Chart.js) for:
    * Student's personal grade trends over time.
    * School-wide grade distribution (e.g., "how many A's in Form 1").
    * Super Admin comparison of average scores between schools.
* **AI-Powered Insights:** (v7.0+)
    * AI-generated qualitative remarks for report cards.
    * Predictive engine to estimate next term's performance.

## 💻 Tech Stack

* **Backend:** Flask (Python)
* **Database:** SQLAlchemy (with SQLite for development, PostgreSQL-ready)
* **Authentication:** Flask-Login, Flask-WTF (with CSRF Protection)
* **Data & Analytics:** Pandas
* **PDF Generation:** WeasyPrint
* **Frontend:** TailwindCSS, Alpine.js
* **Charts:** Chart.js

## 🗂️ File Structure

```

Advanced\_Grading\_System/
├── app.py              \# Main Flask application (routes, forms, logic)
├── models.py           \# SQLAlchemy database schema
├── requirements.txt    \# Python dependencies
├── data/               \# Data files
│   ├── schools.csv     \# Mock data
│   ├── users.csv       \# Mock data
│   ├── subjects.csv    \# Mock data
│   ├── grades.csv      \# Mock data
│   └── ecosystem.db    \# The SQLite database (auto-generated)
├── utils/              \# Helper modules
│   ├── analytics.py    \# Functions for Chart.js data
│   ├── ai\_predictor.py \# AI remark generation logic
│   ├── csv\_tools.py    \# Database-seeding script
│   └── pdf\_generator.py\# WeasyPrint PDF generation logic
└── templates/          \# All HTML templates
├── admin/          \# Admin CRUD pages
├── dashboards/     \# Role-specific dashboards
├── errors/         \# 403, 404, 500 pages
├── reports/        \# PDF report card template
└── ...             \# Login, base, etc.

````

## 🚀 Getting Started

Follow these instructions to get the project running on your local machine.

### 1. Prerequisites

* **Python 3.11+**
* **Pip** (Python Package Installer)
* **Git** (optional, for cloning)

### 2. WeasyPrint Installation (CRITICAL)

The PDF generation **will fail** without this step. `WeasyPrint` relies on system libraries that `pip` cannot install.

* **On Windows:**
    1.  Download and run the GTK+ for Windows installer. You can find a link on the WeasyPrint documentation or search for "GTK+ for Windows Runtime Environment Installer".
    2.  Install it to the default location.
* **On macOS:**
    ```bash
    brew install pango cairo gdk-pixbuf libffi
    ```
* **On Linux (Debian/Ubuntu):**
    ```bash
    sudo apt-get install python3-pango libcairo2 libpango-1.0-0 libpangoft2-1.0-0
    ```

### 3. Setup and Installation

1.  **Clone or Download the Project:**
    ```bash
    git clone <your-repo-url>
    cd Advanced_Grading_System
    ```
    (Or just use the files you already have)

2.  **Create a Virtual Environment** (Recommended):
    ```bash
    python -m venv venv
    ```
    * Windows: `venv\Scripts\activate`
    * macOS/Linux: `source venv/bin/activate`

3.  **Install Python Dependencies:**
    (Make sure you have fixed the `requirements.txt` file as per our conversation - i.e., removed Chart.js and Alpine.js).
    ```bash
    pip install -r requirements.txt
    ```

### 4. Run the Application

1.  **Run the Flask Server:**
    ```bash
    flask run
    ```
    The application will automatically create and populate the `data/ecosystem.db` file from the CSVs the first time it runs.

2.  **Access the System:**
    Open your browser and navigate to: **http://127.0.0.1:5000**

## 🔐 Sample Logins

Use these credentials (from `data/users.csv`) to test the different roles.

| Role | School | Flow | Username | Password |
| :--- | :--- | :--- | :--- | :--- |
| **Super Admin** | N/A | Homepage -> "Super Admin Login" | `superadmin` | `super123` |
| **School Admin** | Greenhill | Select "Greenhill" -> "School Admin" | `ghs_admin` | `admin123` |
| **Teacher** | Greenhill | Select "Greenhill" -> "Teacher" | `ghs_teacher1` | `teacher123` |
| **Student** | Greenhill | Select "Greenhill" -> "Student" | `ghs_student1` | `student123` |
| **Student** | Mountainview | Select "Mountainview" -> "Student" | `mhs_student1` | `student123` |

## License

This project is licensed under the MIT License.
````