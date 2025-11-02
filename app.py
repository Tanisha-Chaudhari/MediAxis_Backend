
from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import smtplib
from email.mime.text import MIMEText
import random
import mysql.connector
import secrets
import datetime
import os

app = Flask(__name__)
CORS(app)

# ✅ Load from environment variables (for Render or local)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "@Tanii16")
DB_NAME = os.getenv("DB_NAME", "mediaxis")

EMAIL_SENDER = os.getenv("EMAIL_SENDER", "mediaxis.demo@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "husckuriyuacamey")

# ✅ MySQL connection
db = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)
cursor = db.cursor(dictionary=True)

@app.route('/')
def home():
    return jsonify({"status": "flask ok"})

# ✅ Helper: send email (welcome / reset)
def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        print(f"📧 Email sent to {to_email}")
    except Exception as e:
        print("❌ Email sending failed:", e)

# ✅ SIGNUP
@app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        full_name = data.get("full_name")
        email = data.get("email")
        password = data.get("password")

        if not full_name or not email or not password:
            return jsonify({"message": "Missing required fields"}), 400

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()
            return jsonify({"message": "User already exists"}), 400

        cursor.execute(
            "INSERT INTO users (full_name, email, password) VALUES (%s, %s, %s)",
            (full_name, email, password)
        )
        db.commit()
        cursor.close()

        send_email(email, "Welcome to MediAxis", "Welcome to MediAxis! ❤️ Glad to have you onboard.")
        return jsonify({"message": "Signup successful"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

# ✅ LOGIN
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email_or_mobile = data.get("email")
    password = data.get("password")

    if not email_or_mobile or not password:
        return jsonify({"message": "Missing fields"}), 400

    is_email = re.match(r'^\S+@\S+\.\S+$', email_or_mobile)
    if is_email:
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email_or_mobile, password))
    else:
        cursor.execute("SELECT * FROM users WHERE phone=%s AND password=%s", (email_or_mobile, password))

    user = cursor.fetchone()
    if user:
        return jsonify({
            "message": "Login successful",
            "name": user.get("full_name") or user.get("email")
        }), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

# ✅ FORGOT PASSWORD
@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    identifier = data.get('identifier')

    if not identifier:
        return jsonify({"message": "Email or phone required"}), 400

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email=%s OR phone=%s", (identifier, identifier))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        return jsonify({"message": "User not found"}), 404

    if "@" in identifier:
        token = secrets.token_urlsafe(32)
        expiry = datetime.datetime.now() + datetime.timedelta(hours=1)

        cursor.execute("UPDATE users SET reset_token=%s, reset_expiry=%s WHERE email=%s",
                       (token, expiry, identifier))
        db.commit()
        cursor.close()

        reset_link = f"https://mediaxis.onrender.com/reset_password/{token}"
        send_email(identifier, "Password Reset - MediAxis",
                   f"Click this link to reset your MediAxis password:\n\n{reset_link}\n\n(Link valid for 1 hour.)")

        return jsonify({"message": f"Password reset email sent to {identifier}"}), 200

    else:
        otp = str(random.randint(100000, 999999))
        print(f"📱 OTP for {identifier}: {otp}")
        return jsonify({"message": f"OTP sent to {identifier}", "otp": otp}), 200

# ✅ RESET FORM
@app.route('/reset_password/<token>', methods=['GET'])
def reset_password_form(token):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE reset_token=%s AND reset_expiry > NOW()", (token,))
    user = cursor.fetchone()
    cursor.close()

    if not user:
        return "<h3>Invalid or expired password reset link.</h3>"

    return f"""
    <h2>Reset Your MediAxis Password</h2>
    <form action="/update_password" method="POST">
        <input type="hidden" name="token" value="{token}">
        <input type="password" name="new_password" placeholder="Enter new password" required>
        <button type="submit">Update Password</button>
    </form>
    """

# ✅ UPDATE PASSWORD
@app.route('/update_password', methods=['POST'])
def update_password():
    token = request.form.get('token')
    new_password = request.form.get('new_password')

    if not token or not new_password:
        return "<h3>Missing data.</h3>"

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE reset_token=%s AND reset_expiry > NOW()", (token,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        return "<h3>Invalid or expired token.</h3>"

    cursor.execute("UPDATE users SET password=%s, reset_token=NULL, reset_expiry=NULL WHERE reset_token=%s",
                   (new_password, token))
    db.commit()
    cursor.close()

    return "<h3>Password updated successfully! You can now log in again.</h3>"

# ✅ TEST DB
@app.route('/test_db')
def test_db():
    cursor.execute("SHOW TABLES;")
    tables = cursor.fetchall()
    return jsonify({"tables": tables})

# ✅ Dummy endpoints
@app.route('/book_appointment', methods=['POST'])
def book_appointment():
    return jsonify({"message": "Appointment booked"}), 200

@app.route('/emergency_alert', methods=['POST'])
def emergency_alert():
    return jsonify({"message": "Emergency alert received"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)), debug=True)



# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import re
# import smtplib
# from email.mime.text import MIMEText
# import random
# import mysql.connector
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

#         local_ip =  "192.168.1.11"
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
