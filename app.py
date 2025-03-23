import os
import uuid
import re
from flask import Flask, render_template, request
import firebase_admin
from firebase_admin import credentials, firestore
from twilio.rest import Client

# Initialize Flask app
app = Flask(__name__, template_folder="templates")

# Firebase credentials
firebase_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "firebase_credentials.json")

if not os.path.exists(firebase_creds_path):
    print(f"⚠️ Firebase credentials not found at {firebase_creds_path}! Make sure it's uploaded in Render Secrets.")
    exit(1)

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_creds_path)
    firebase_admin.initialize_app(cred)

try:
    db = firestore.client()
except Exception as e:
    print(f"Error connecting to Firestore: {e}")

# Clean phone numbers
def clean_phone_number(phone):
    cleaned_phone = re.sub(r'\D', '', phone)
    if len(cleaned_phone) == 11 and cleaned_phone.startswith("1"):
        cleaned_phone = cleaned_phone[1:]
    if len(cleaned_phone) != 10:
        return None
    return cleaned_phone

# Send welcome SMS
def send_welcome_sms(phone_number, first_name):
    try:
        print("📨 Sending SMS...")
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_number = os.getenv("TWILIO_PHONE_NUMBER")

        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=f"Hey {first_name}! Thanks for signing up with Yellow Dog Coffee ☕🐶 You're now on the digital punch card!",
            from_=twilio_number,
            to=f"+1{phone_number}"
        )
        print(f"✅ SMS sent to {phone_number}: SID {message.sid}")
    except Exception as e:
        print(f"❌ Failed to send SMS to {phone_number}: {e}")

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/submit', methods=['POST'])
def submit():
    try:
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        phone = request.form.get("phone")

        if not first_name or not last_name or not phone:
            return "All fields are required.", 400

        cleaned_phone = clean_phone_number(phone)
        if not cleaned_phone:
            return "Invalid phone number format.", 400

        existing = db.collection("customers").where("phone", "==", cleaned_phone).get()
        if existing:
            return "Phone number already registered!", 400

        user_id = str(uuid.uuid4())

        # 🔥 Add punches and points on signup
        db.collection("customers").add({
            "first_name": first_name,
            "last_name": last_name,
            "phone": cleaned_phone,
            "uuid": user_id,
            "punches": 0,
            "points": 0
        })

        send_welcome_sms(cleaned_phone, first_name)
        return render_template("thankyou.html", first_name=first_name)

    except Exception as e:
        return f"Something went wrong: {e}", 500

# 🔥 Sprint 3 Preview: Status page for customers
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
        punches = customer.get("punches", 0)
        points = customer.get("points", 0)
        name = customer.get("first_name", "there")

        return render_template("status.html", name=name, punches=punches, points=points)
    return render_template("status_check.html")

# 🔥 Optional: Admin route to manually add a punch
@app.route('/admin-add-punch', methods=['POST'])
def admin_add_punch():
    phone = request.form.get("phone")
    cleaned_phone = clean_phone_number(phone)
    if not cleaned_phone:
        return "Invalid phone number.", 400

    customer_ref = db.collection("customers").where("phone", "==", cleaned_phone).get()
    if not customer_ref:
        return "Customer not found.", 404

    doc_id = customer_ref[0].id
    customer_data = customer_ref[0].to_dict()
    current_punches = customer_data.get("punches", 0)

    db.collection("customers").document(doc_id).update({
        "punches": current_punches + 1
    })

    return f"Punch added. {cleaned_phone} now has {current_punches + 1} punches."
