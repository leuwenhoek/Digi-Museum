from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sqlite3

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'

# Use the Flask instance folder for the DB (creates one if missing)
db_path = os.path.join(app.instance_path, 'users.db')
os.makedirs(app.instance_path, exist_ok=True)


def get_db():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.commit()
    finally:
        conn.close()


def get_user(username):
    conn = get_db()
    try:
        cur = conn.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cur.fetchone()
        return row
    finally:
        conn.close()


def user_exists(username):
    return get_user(username) is not None


def create_user(username, email, password_hash):
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, password_hash)
        )
        conn.commit()
    finally:
        conn.close()


# Ensure DB is created before the app starts
with app.app_context():
    init_db()


@app.route('/')
def index():
    if 'user' in session:
        username = session['user']
        # Optional: fetch user additional info (e.g., email)
        user_row = get_user(username)
        email = user_row['email'] if user_row else None
        return f'<h1>Welcome {username}!</h1>' + (f'<p>Email: {email}</p>' if email else '') + '<a href="/logout">Logout</a>'
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user_row = get_user(username)
        if user_row and check_password_hash(user_row['password_hash'], password):
            session['user'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if user_exists(username):
            flash('Username already exists', 'error')
        elif password != confirm_password:
            flash('Passwords do not match', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
        else:
            password_hash = generate_password_hash(password)
            try:
                create_user(username, email, password_hash)
                flash('Account created successfully! Please login.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                # In case of a race condition where username was created concurrently
                flash('Username already exists', 'error')

    return render_template('signup.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)