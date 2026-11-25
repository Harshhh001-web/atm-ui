# ATM Management System

Full-stack Software Testing project using:

- Frontend: HTML, CSS, JavaScript
- Backend: Python Flask
- Database: SQLite
- Authentication: Flask session + hashed PIN
- Testing: Pytest

## Demo account

Card: `1234567890123456`
PIN: `1234`

## Run in VS Code

### 1. Open terminal in this folder

```bash
python -m venv venv
```

### 2. Activate virtual environment

Windows:

```bash
venv\Scripts\activate
```

### 3. Install packages

```bash
pip install -r requirements.txt
```

### 4. Start server

```bash
python app.py
```

### 5. Open browser

Go to:

http://127.0.0.1:5000

## Run automated tests

```bash
pytest
```

## Important

This is an academic/demo ATM system, not a real banking application. For production use, additional security, database controls, audit logging, CSRF protection, secure secret management, rate limiting and banking integrations would be required.
