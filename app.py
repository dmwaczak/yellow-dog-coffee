import os
import uuid
import re
import base64
import random
import string
import smtplib
from io import BytesIO
from email.mime.text import MIMEText
from flask import Flask, render_template, request, jsonify, redirect, session
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import qrcode

load_dotenv()

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "defaultsecret")

firebase_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "firebase_credentials.json")
if not os.path.exists(firebase_creds_path):
    print(f"\u26a0\ufe0f Firebase credentials not found at {firebase_creds_path}!")
    exit(1)
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_creds_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

def send_welcome_email(to_address, name):
    subject = "Welcome to Yellow Dog Rewards 🐾"
    body = f"""
    Hi {name},

    Thanks for signing up for Yellow Dog Coffee Rewards!
    You're now earning punches and points with every visit.

    Next time you're in the shop, just let a barista know you're a rewards member.
    You can check your status anytime at: https://yellow-dog-coffee.onrender.com/

    Stay pawsitive ☕🐾,
    Yellow Dog Coffee
    """
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = to_address

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
            print(f"✅ Sent welcome email to {to_address}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def clean_phone_number(phone):
    cleaned = re.sub(r'\D', '', phone)
    return cleaned[1:] if len(cleaned) == 11 and cleaned.startswith('1') else cleaned if len(cleaned) == 10 else None

def generate_redeem_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

@app.route('/')
def homepage():
    return render_template("home.html")

@app.route('/signup')
def signup():
    return render_template("signup.html")

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.json
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        email = data.get("email")
        phone = data.get("phone")

        if not all([first_name, last_name, email, phone]):
            return jsonify({"error": "All fields are required."}), 400

        cleaned_phone = clean_phone_number(phone)
        if not cleaned_phone:
            return jsonify({"error": "Invalid phone number format."}), 400

        existing_users = db.collection("customers").where("phone", "==", cleaned_phone).get()
        if existing_users:
            return jsonify({"error": "Whoops! Looks like this number is already in use."}), 400

        db.collection("customers").add({
            "uuid": str(uuid.uuid4()),
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": cleaned_phone,
            "points": 0,
            "punches": 0
        })

        send_welcome_email(email, first_name)

        return jsonify({"redirect": f"/thankyou?name={first_name}"}), 200

    except Exception as e:
        return jsonify({"error": f"Something went wrong: {e}"}), 500

@app.route('/thankyou')
def thankyou():
    name = request.args.get("name", "there")
    return render_template("thankyou.html", first_name=name)

@app.route('/status', methods=['GET', 'POST'])
def status():
    if request.method == 'POST':
        phone = request.form.get("phone")
        cleaned_phone = clean_phone_number(phone)
        if not cleaned_phone:
            return "Invalid phone number.", 400

        customer_ref = db.collection("customers").where("phone", "==", cleaned_phone).get()
        if not customer_ref:
            return "No customer found.", 404

        customer = customer_ref[0].to_dict()
        name = customer.get("first_name", "there")
        punches = customer.get("punches", 0)
        points = customer.get("points", 0)

        return render_template("status.html", name=name, punches=punches, points=points, phone=cleaned_phone)

    return render_template("status_check.html")

@app.route('/barista', methods=['POST'])
def barista():
    try:
        data = request.json
        phone = data.get("phone")
        coffees = data.get("coffees", 0)
        amount = data.get("amount", 0)

        if not phone:
            return jsonify({"error": "Phone number required."}), 400

        cleaned_phone = clean_phone_number(phone)
        if not cleaned_phone:
            return jsonify({"error": "Invalid phone number."}), 400

        docs = db.collection("customers").where("phone", "==", cleaned_phone).get()
        if not docs:
            return jsonify({"error": "Customer not found."}), 404

        doc_ref = docs[0].reference
        customer = docs[0].to_dict()

        new_punches = customer.get("punches", 0) + int(coffees)
        new_points = customer.get("points", 0) + int(float(amount))

        doc_ref.update({"punches": new_punches, "points": new_points})

        return jsonify({"message": f"Added {coffees} punch(es) and {amount} point(s) to {customer.get('first_name', 'Customer')}."}), 200

    except Exception as e:
        return jsonify({"error": f"Something went wrong: {e}"}), 500

@app.route('/redeem-check', methods=['POST'])
def redeem_check():
    phone = request.form.get("phone")
    cleaned_phone = clean_phone_number(phone)
    if not cleaned_phone:
        return "Invalid phone.", 400

    docs = db.collection("customers").where("phone", "==", cleaned_phone).get()
    if not docs:
        return "Customer not found.", 404

    doc_ref = docs[0].reference
    doc_ref.update({"punches": 0})

    return "✅ Coffee redeemed. Punches reset."

@app.route('/redeem-points', methods=['POST'])
def redeem_points():
    phone = request.form.get("phone")
    points = int(request.form.get("points", 0))

    cleaned_phone = clean_phone_number(phone)
    if not cleaned_phone:
        return "Invalid phone number.", 400

    docs = db.collection("customers").where("phone", "==", cleaned_phone).get()
    if not docs:
        return "Customer not found.", 404

    doc_ref = docs[0].reference
    customer = docs[0].to_dict()
    current_points = customer.get("points", 0)

    if points > current_points:
        return "Not enough points.", 400

    doc_ref.update({"points": current_points - points})

    return f"✅ Redeemed {points} points."

@app.route('/barista-login', methods=['GET', 'POST'])
def barista_login():
    if request.method == 'POST':
        password = request.form.get("password")
        if password == "1111":
            session['barista_authenticated'] = True
            return redirect("/barista")
        return render_template("barista-login.html", error="Incorrect password")
    return render_template("barista-login.html")

@app.route('/logout')
def logout():
    session.pop('barista_authenticated', None)
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
