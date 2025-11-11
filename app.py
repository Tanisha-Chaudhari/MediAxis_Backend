from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import smtplib
from email.mime.text import MIMEText
import random
import sqlite3
import os
import secrets
import datetime
import socket

app = Flask(__name__)
CORS(app)

# =======================
# ✅ DATABASE SETUP (SQLite)
# =======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "mediaxis.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE,
            phone TEXT,
            password TEXT NOT NULL,
            reset_token TEXT,
            reset_expiry TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()  # Create table if not exists

# =======================
# ✅ EMAIL HELPER
# =======================
def send_email(to_email, subject, body):
    sender_email = "mediaxis.demo@gmail.com"
    sender_password = "husckuriyuacamey"  # App password

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        print(f"📧 Email sent to {to_email}")
    except Exception as e:
        print("❌ Email sending failed:", e)

# =======================
# ✅ ROUTES
# =======================
@app.route('/')
def home():
    return jsonify({"status": "Flask backend running ✅"})

# -----------------------
# SIGNUP
# -----------------------
@app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        full_name = data.get("full_name")
        email = data.get("email")
        password = data.get("password")

        if not full_name or not email or not password:
            return jsonify({"message": "Missing required fields"}), 400

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return jsonify({"message": "User already exists"}), 400

        cursor.execute(
            "INSERT INTO users (full_name, email, password) VALUES (?, ?, ?)",
            (full_name, email, password)
        )
        conn.commit()
        conn.close()

        send_email(email, "Welcome to MediAxis", "Welcome to MediAxis ❤️ We're glad to have you!")
        return jsonify({"message": "Signup successful"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

# -----------------------
# LOGIN
# -----------------------
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email_or_mobile = data.get("email")
    password = data.get("password")

    if not email_or_mobile or not password:
        return jsonify({"message": "Missing fields"}), 400

    conn = get_db()
    cursor = conn.cursor()

    is_email = re.match(r'^\S+@\S+\.\S+$', email_or_mobile)
    if is_email:
        cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email_or_mobile, password))
    else:
        cursor.execute("SELECT * FROM users WHERE phone=? AND password=?", (email_or_mobile, password))

    user = cursor.fetchone()
    conn.close()

    if user:
        return jsonify({
            "message": "Login successful",
            "name": user["full_name"]
        }), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

# -----------------------
# FORGOT PASSWORD
# -----------------------
@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    identifier = data.get('identifier')

    if not identifier:
        return jsonify({"message": "Email or phone required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email=? OR phone=?", (identifier, identifier))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"message": "User not found"}), 404

    if "@" in identifier:
        token = secrets.token_urlsafe(32)
        expiry = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()

        cursor.execute("UPDATE users SET reset_token=?, reset_expiry=? WHERE email=?", (token, expiry, identifier))
        conn.commit()
        conn.close()

        local_ip = socket.gethostbyname(socket.gethostname())
        reset_link = f"http://{local_ip}:5000/reset_password/{token}"

        send_email(identifier, "Password Reset - MediAxis",
                   f"Click the link to reset your password:\n\n{reset_link}\n\n(Link valid for 1 hour.)")

        return jsonify({"message": f"Password reset link sent to {identifier}"}), 200
    else:
        otp = str(random.randint(100000, 999999))
        print(f"📱 OTP for {identifier}: {otp}")
        return jsonify({"message": f"OTP sent to {identifier}", "otp": otp}), 200

# -----------------------
# RESET PASSWORD PAGE
# -----------------------
@app.route('/reset_password/<token>', methods=['GET'])
def reset_password_form(token):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE reset_token=? AND reset_expiry > ?", (token, datetime.datetime.now().isoformat()))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return "<h3>Invalid or expired link.</h3>"

    return f"""
    <h2>Reset Your MediAxis Password</h2>
    <form action="/update_password" method="POST">
        <input type="hidden" name="token" value="{token}">
        <input type="password" name="new_password" placeholder="Enter new password" required>
        <button type="submit">Update Password</button>
    </form>
    """

# -----------------------
# UPDATE PASSWORD
# -----------------------
@app.route('/update_password', methods=['POST'])
def update_password():
    token = request.form.get('token')
    new_password = request.form.get('new_password')

    if not token or not new_password:
        return "<h3>Missing data.</h3>"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE reset_token=? AND reset_expiry > ?", (token, datetime.datetime.now().isoformat()))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return "<h3>Invalid or expired token.</h3>"

    cursor.execute("UPDATE users SET password=?, reset_token=NULL, reset_expiry=NULL WHERE reset_token=?", (new_password, token))
    conn.commit()
    conn.close()

    return "<h3>Password updated successfully ✅</h3>"

# -----------------------
# OTHER ROUTES
# -----------------------
@app.route('/book_appointment', methods=['POST'])
def book_appointment():
    data = request.get_json()
    return jsonify({"message": "Appointment booked"}), 200

@app.route('/emergency_alert', methods=['POST'])
def emergency_alert():
    data = request.get_json()
    return jsonify({"message": "Emergency alert received"}), 200

# -----------------------
# TEST DATABASE
# -----------------------
@app.route('/test_db')
def test_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify({"tables": tables})

# =======================
# ✅ MAIN ENTRY POINT
# =======================
if __name__ == '__main__':
    app.run(debug=True)









# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import re
# import smtplib
# from email.mime.text import MIMEText
# import random
# # import mysql.connector

# import secrets
# import datetime
# import socket

# app = Flask(__name__)
# CORS(app)

# # ✅ MySQL connection
# db = mysql.connector.connect(
#     host="localhost",
#     user="root",
#     password="@Tanii16",   # replace with your actual MySQL password
#     database="mediaxis"
# )
# cursor = db.cursor(dictionary=True)

# @app.route('/')
# def home():
#     return jsonify({"status": "flask ok"})

# # ✅ Helper: send email (for welcome or reset)
# def send_email(to_email, subject, body):
#     sender_email = "mediaxis.demo@gmail.com"
#     sender_password = "husckuriyuacamey"  # Gmail App Password

#     msg = MIMEText(body)
#     msg["Subject"] = subject
#     msg["From"] = sender_email
#     msg["To"] = to_email

#     try:
#         with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
#             server.login(sender_email, sender_password)
#             server.sendmail(sender_email, to_email, msg.as_string())
#         print(f"📧 Email sent to {to_email}")
#     except Exception as e:
#         print("❌ Email sending failed:", e)


# # ✅ SIGNUP ROUTE
# @app.route('/signup', methods=['POST'])
# def signup():
#     try:
#         data = request.get_json()
#         full_name = data.get("full_name")
#         email = data.get("email")
#         password = data.get("password")

#         if not full_name or not email or not password:
#             return jsonify({"message": "Missing required fields"}), 400

#         cursor = db.cursor(dictionary=True)
#         cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
#         existing_user = cursor.fetchone()

#         if existing_user:
#             cursor.close()
#             return jsonify({"message": "User already exists"}), 400

#         cursor.execute(
#             "INSERT INTO users (full_name, email, password) VALUES (%s, %s, %s)",
#             (full_name, email, password)
#         )
#         db.commit()
#         cursor.close()

#         send_email(email, "Welcome to MediAxis", "Welcome to MediAxis! ❤️ Glad to have you onboard.")
#         return jsonify({"message": "Signup successful"}), 200

#     except Exception as e:
#         print("Error:", e)
#         return jsonify({"message": f"Server error: {str(e)}"}), 500


# # ✅ LOGIN ROUTE
# @app.route('/login', methods=['POST'])
# def login():
#     data = request.get_json()
#     email_or_mobile = data.get("email")
#     password = data.get("password")

#     if not email_or_mobile or not password:
#         return jsonify({"message": "Missing fields"}), 400

#     is_email = re.match(r'^\S+@\S+\.\S+$', email_or_mobile)
#     if is_email:
#         cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email_or_mobile, password))
#     else:
#         cursor.execute("SELECT * FROM users WHERE phone=%s AND password=%s", (email_or_mobile, password))

#     user = cursor.fetchone()
#     if user:
#         # ✅ Include the user's name in the response
#         return jsonify({
#             "message": "Login successful",
#             "name": user.get("full_name") or user.get("email")  # fallback if name missing
#         }), 200
#     else:
#         return jsonify({"message": "Invalid credentials"}), 401



# # ✅ FORGOT PASSWORD — sends real reset link via email
# @app.route('/forgot_password', methods=['POST'])
# def forgot_password():
#     data = request.get_json()
#     identifier = data.get('identifier')

#     if not identifier:
#         return jsonify({"message": "Email or phone required"}), 400

#     cursor = db.cursor(dictionary=True)
#     cursor.execute("SELECT * FROM users WHERE email=%s OR phone=%s", (identifier, identifier))
#     user = cursor.fetchone()

#     if not user:
#         cursor.close()
#         return jsonify({"message": "User not found"}), 404

#     if "@" in identifier:
#         # ✅ Generate secure token & expiry
#         token = secrets.token_urlsafe(32)
#         expiry = datetime.datetime.now() + datetime.timedelta(hours=1)

#         cursor.execute("UPDATE users SET reset_token=%s, reset_expiry=%s WHERE email=%s",
#                        (token, expiry, identifier))
#         db.commit()
#         cursor.close()

        
#         # Automatically get your laptop's LAN IP
#         local_ip = socket.gethostbyname(socket.gethostname())
#         reset_link = f"http://{local_ip}:5000/reset_password/{token}"


#         send_email(identifier, "Password Reset - MediAxis",
#                    f"Click this link to reset your MediAxis password:\n\n{reset_link}\n\n(Link valid for 1 hour.)")

#         return jsonify({"message": f"Password reset email sent to {identifier}"}), 200

#     else:
#         otp = str(random.randint(100000, 999999))
#         print(f"📱 OTP for {identifier}: {otp}")
#         return jsonify({"message": f"OTP sent to {identifier}", "otp": otp}), 200


# # ✅ RESET PASSWORD HTML form (opened via email)
# @app.route('/reset_password/<token>', methods=['GET'])
# def reset_password_form(token):
#     cursor = db.cursor(dictionary=True)
#     cursor.execute("SELECT * FROM users WHERE reset_token=%s AND reset_expiry > NOW()", (token,))
#     user = cursor.fetchone()
#     cursor.close()

#     if not user:
#         return "<h3>Invalid or expired password reset link.</h3>"

#     return f"""
#     <h2>Reset Your MediAxis Password</h2>
#     <form action="/update_password" method="POST">
#         <input type="hidden" name="token" value="{token}">
#         <input type="password" name="new_password" placeholder="Enter new password" required>
#         <button type="submit">Update Password</button>
#     </form>
#     """


# # ✅ UPDATE PASSWORD (called by the above form)
# @app.route('/update_password', methods=['POST'])
# def update_password():
#     token = request.form.get('token')
#     new_password = request.form.get('new_password')

#     if not token or not new_password:
#         return "<h3>Missing data.</h3>"

#     cursor = db.cursor(dictionary=True)
#     cursor.execute("SELECT * FROM users WHERE reset_token=%s AND reset_expiry > NOW()", (token,))
#     user = cursor.fetchone()

#     if not user:
#         cursor.close()
#         return "<h3>Invalid or expired token.</h3>"

#     cursor.execute("UPDATE users SET password=%s, reset_token=NULL, reset_expiry=NULL WHERE reset_token=%s",
#                    (new_password, token))
#     db.commit()
#     cursor.close()

#     return "<h3>Password updated successfully! You can now log in again.</h3>"


# # ✅ For testing DB
# @app.route('/test_db')
# def test_db():
#     cursor.execute("SHOW TABLES;")
#     tables = cursor.fetchall()
#     return jsonify({"tables": tables})


# @app.route('/book_appointment', methods=['POST'])
# def book_appointment():
#     data = request.get_json()
#     return jsonify({"message": "Appointment booked"}), 200


# @app.route('/emergency_alert', methods=['POST'])
# def emergency_alert():
#     data = request.get_json()
#     return jsonify({"message": "Emergency alert received"}), 200


# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000, debug=True)
