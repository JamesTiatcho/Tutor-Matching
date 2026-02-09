from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit
import sqlite3
import datetime
import socketio
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a strong, unique key
socketio = SocketIO(app)  

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a strong, unique key

# Database initialization
def init_db():
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Tutor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                firstname TEXT NOT NULL,
                lastname TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                expertise TEXT,  
                email TEXT,      
                contact TEXT     
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Student (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                firstname TEXT NOT NULL,
                lastname TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Enrollment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                tutor_id INTEGER,
                subject TEXT,
                FOREIGN KEY(student_id) REFERENCES Student(id),
                FOREIGN KEY(tutor_id) REFERENCES Tutor(id)
            )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tutor_id INTEGER,
            student_name TEXT,
            subject TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(tutor_id) REFERENCES Tutor(id)
        )
    ''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS Schedule (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            tutor_id INTEGER,
                            student_id INTEGER,
                            subject TEXT,
                            date TEXT,
                            time TEXT,
                            FOREIGN KEY(tutor_id) REFERENCES Tutor(id),
                            FOREIGN KEY(student_id) REFERENCES Student(id))''')
        conn.commit()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/home')
def home():
    first_name = session.get('firstname', 'Guest')
    return render_template('home.html', first_name=first_name)

@app.route('/tutorhomepage')
def tutorhomepage():
    username = session.get('username')
    first_name = session.get('firstname', 'Guest')

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, firstname, lastname, username, expertise, email, contact FROM Tutor WHERE username = ?', (username,))
        tutor = cursor.fetchone()

        if tutor:
            tutor_id, firstname, lastname, username, expertise, email, contact = tutor
            full_name = f"{firstname} {lastname}"

            # Get the list of students enrolled with this tutor
            cursor.execute('''
                SELECT s.firstname, s.lastname
                FROM Student s
                JOIN Enrollment e ON s.id = e.student_id
                WHERE e.tutor_id = ?
            ''', (tutor_id,))
            students = cursor.fetchall()
        else:
            full_name = 'Guest'
            expertise = email = contact = 'Not Available'
            students = []

    return render_template('tutorhomepage.html', username=username, full_name=full_name, first_name=first_name, expertise=expertise, email=email, contact=contact, students=students)

@app.route('/add_schedule', methods=['GET', 'POST'])
def add_schedule():
    tutor_username = session.get('username')

    if request.method == 'POST':
        student_id = request.form['student_id']
        subject = request.form['subject']
        date = request.form['date']
        time = request.form['time']
        
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM Tutor WHERE username = ?', (tutor_username,))
            tutor_id = cursor.fetchone()[0]

            cursor.execute('''
                INSERT INTO Schedule (tutor_id, student_id, subject, date, time)
                VALUES (?, ?, ?, ?, ?)
            ''', (tutor_id, student_id, subject, date, time))
            conn.commit()

        return redirect(url_for('tutorhomepage'))

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT s.id, s.firstname || " " || s.lastname
                          FROM Student s
                          JOIN Enrollment e ON s.id = e.student_id
                          JOIN Tutor t ON e.tutor_id = t.id
                          WHERE t.username = ?''', (tutor_username,))
        students = cursor.fetchall()

    return render_template('add_schedule.html', students=students)

@app.route('/student_classes')
def student_classes():
    student_username = session.get('username')
    
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM Student WHERE username = ?', (student_username,))
        student_id = cursor.fetchone()[0]

        cursor.execute('''SELECT t.firstname || " " || t.lastname, s.subject, s.date, s.time
                          FROM Schedule s
                          JOIN Tutor t ON s.tutor_id = t.id
                          WHERE s.student_id = ?''', (student_id,))
        schedules = cursor.fetchall()

    return render_template('student_classes.html', schedules=schedules)

@app.route('/tutor_classes')
def tutor_classes():
    tutor_username = session.get('username')  # Get the tutor's username from the session

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()

        # Fetch tutor ID using username
        cursor.execute('SELECT id FROM Tutor WHERE username = ?', (tutor_username,))
        tutor_id = cursor.fetchone()

        if tutor_id:
            tutor_id = tutor_id[0]

            # Fetch schedule for the tutor
            cursor.execute('''
                SELECT s.firstname || " " || s.lastname, sc.subject, sc.date, sc.time
                FROM Schedule sc
                JOIN Student s ON sc.student_id = s.id
                WHERE sc.tutor_id = ?
                ORDER BY sc.date, sc.time
            ''', (tutor_id,))
            schedules = cursor.fetchall()
        else:
            schedules = []

    return render_template('tutor_classes.html', schedules=schedules)


@app.route('/meeting')
def meeting():
    return render_template('meeting.html') 

@socketio.on('offer')
def handle_offer(offer):
    emit('offer', offer, broadcast=True)

@socketio.on('answer')
def handle_answer(answer):
    emit('answer', answer, broadcast=True)

@socketio.on('ice-candidate')
def handle_ice_candidate(candidate):
    emit('ice-candidate', candidate, broadcast=True)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    username = session.get('username')
    
    if not username:
        return redirect(url_for('index'))  # Ensure the user is logged in
    
    expertise = request.form['expertise']
    email = request.form['email']
    contact = request.form['contact']
    
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE Tutor
            SET expertise = ?, email = ?, contact = ?
            WHERE username = ?
        ''', (expertise, email, contact, username))
        conn.commit()
    
    return redirect(url_for('tutorhomepage'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            if username.isdigit():
                cursor.execute('SELECT firstname FROM Tutor WHERE username = ? AND password = ?', (username, password))
                user = cursor.fetchone()
                if user:
                    session['username'] = username
                    session['firstname'] = user[0]
                    return redirect(url_for('tutorhomepage'))
            else:
                cursor.execute('SELECT firstname FROM Student WHERE username = ? AND password = ?', (username, password))
                user = cursor.fetchone()
                if user:
                    session['username'] = username
                    session['firstname'] = user[0]
                    return redirect(url_for('home'))
        error = 'Invalid username or password'
    return render_template('index.html', error=error)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        username = request.form['newusername']
        password = request.form['newpassword']
        repassword = request.form['repassword']

        if not firstname.isalpha():
            flash("Firstname must contain letters only!", "error")
            return redirect(url_for('signup'))  # Redirect to the same signup page
        
        if password != repassword:
            flash("Passwords do not match!", "error")
            return redirect(url_for('signup'))
        
        table = 'Tutor' if username.isdigit() else 'Student'
        
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                INSERT INTO {table} (firstname, lastname, username, password)
                VALUES (?, ?, ?, ?)
            ''', (firstname, lastname, username, password))
            conn.commit()

        if table == 'Tutor':
            session['username'] = username  # Save username to session
            return redirect(url_for('complete_registration'))
        else:
            return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/complete_registration', methods=['GET', 'POST'])
def complete_registration():
    if request.method == 'POST':
        username = session.get('username')
        expertise = request.form['expertise']
        email = request.form['email']
        contact = request.form['contact']
        
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE Tutor
                SET expertise = ?, email = ?, contact = ?
                WHERE username = ?
            ''', (expertise, email, contact, username))
            conn.commit()
        
        return redirect(url_for('login'))  # Redirect to login after completing registration
    
    return render_template('complete_registration.html')

@app.route('/view_users')
def view_users():
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Tutor')
        tutors = cursor.fetchall()
        cursor.execute('SELECT * FROM Student')
        students = cursor.fetchall()

    return render_template('view_users.html', tutors=tutors, students=students)

@app.route('/delete_user', methods=['POST'])
def delete_user():
    user_id = request.form['id']
    user_type = request.form['type']

    if user_type == 'tutor':
        table = 'Tutor'
    elif user_type == 'student':
        table = 'Student'
    else:
        return redirect(url_for('view_users'))  # Invalid user type, just redirect

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM {table} WHERE id = ?', (user_id,))
        conn.commit()

    return redirect(url_for('view_users'))

@app.route('/match_tutor', methods=['GET', 'POST'])
def match_tutor():
    if request.method == 'POST':
        subject = request.form['subject'].strip().lower()
        
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT firstname, lastname, expertise FROM Tutor WHERE expertise LIKE ?', (f'%{subject}%',))
            tutor = cursor.fetchone()
        
        return render_template('match_tutor.html', tutor=tutor)
    
    return render_template('match_tutor.html')

@app.route('/find_tutor', methods=['POST'])
def find_tutor():
    subject = request.form['subject'].strip().lower()
    
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT firstname, lastname, expertise FROM Tutor WHERE expertise LIKE ?', (f'%{subject}%',))
        tutor = cursor.fetchone()
    
    return render_template('match_tutor.html', tutor=tutor)

@app.route('/enroll_with_tutor', methods=['POST'])
def enroll_with_tutor():
    if request.method == 'POST':
        student_username = session.get('username')
        tutor_name = request.form.get('tutor_name')
        subject = request.form.get('subject')

        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT id, firstname || " " || lastname FROM Student WHERE username = ?', (student_username,))
            student_row = cursor.fetchone()
            student_id = student_row[0] if student_row else None

            cursor.execute('SELECT id FROM Tutor WHERE firstname || " " || lastname = ?', (tutor_name,))
            tutor_row = cursor.fetchone()
            tutor_id = tutor_row[0] if tutor_row else None

            if student_id and tutor_id:
                cursor.execute('SELECT * FROM Enrollment WHERE student_id = ? AND tutor_id = ?', (student_id, tutor_id))
                enrollment_exists = cursor.fetchone()

                if enrollment_exists:
                    return render_template('enrollment_error.html', message=f"You are already enrolled with {tutor_name} for {subject}.")

                cursor.execute('''INSERT INTO Enrollment (student_id, tutor_id, subject) VALUES (?, ?, ?)''', (student_id, tutor_id, subject))
                
                cursor.execute('''INSERT INTO Notifications (tutor_id, student_name, subject) VALUES (?, ?, ?)''', (tutor_id, student_row[1], subject))
                
                conn.commit()

        return render_template('enrollment_confirmation.html', tutor_name=tutor_name, subject=subject)



@app.route('/tutor_inbox')
def tutor_inbox():
    username = session.get('username')
    first_name = session.get('firstname', 'Guest')

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, firstname, lastname, username FROM Tutor WHERE username = ?', (username,))
        tutor = cursor.fetchone()

        if tutor:
            tutor_id, firstname, lastname, username = tutor

            cursor.execute('SELECT student_name, subject, timestamp FROM Notifications WHERE tutor_id = ?', (tutor_id,))
            notifications = cursor.fetchall()
            notifications_count = len(notifications)
        else:
            notifications = []
            notifications_count = 0

    return render_template('inbox.html', first_name=first_name, notifications=notifications, notifications_count=notifications_count)


@app.route('/enrollment', methods=['POST'])
def enrollment():
    tutor_name = request.form['tutor_name']
    subject = request.form['subject']
    return render_template('enrollment.html', tutor_name=tutor_name, subject=subject)

@app.route('/assessment')
def assessment():
    return render_template('assessment.html')

@app.route('/submit_assessment', methods=['POST'])
def submit_assessment():
    # Retrieve form data
    subject = request.form['subject']
    answers = request.form['answers']

    print(f"Assessment received for subject: {subject}")
    print(f"User provided the following information: {answers}")

    return redirect(url_for('home'))

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)