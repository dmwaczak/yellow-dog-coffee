import os
import uuid
import re
from flask import Flask, render_template, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from twilio.rest import Client  # Optional: only if using SMS

# Initialize Flask app & explicitly set template folder
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

# Phone number cleaning
def clean_phone_number(phone):
    cleaned_phone = re.sub(r'\D', '', phone)
    if len(cleaned_phone) == 11 and cleaned_phone.startswith("1"):
        cleaned_phone = cleaned_phone[1:]
    if len(cleaned_phone) != 10:
        return None
    return cleaned_phone

# Optional SMS sending function
def send_welcome_sms(phone_number, first_name):
    try:
        print("📨 Sending SMS...")
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_number = os.getenv("TWILIO_PHONE_NUMBER")

        print(f"📞 From: {twilio_number}, To: +1{phone_number}")

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
    try:
        return render_template("index.html")
    except Exception as e:
        return f"Error loading index.html: {e}", 500

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.json
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        phone = data.get("phone")

        # Validate input
        if not first_name or not last_name or not phone:
            return jsonify({"error": "First name, last name, and phone number are required."}), 400

        cleaned_phone = clean_phone_number(phone)
        if not cleaned_phone:
            return jsonify({"error": "Invalid phone number format"}), 400

        # Check for existing phone number
        existing = db.collection("customers").where("phone", "==", cleaned_phone).get()
        if existing:
            return jsonify({"message": f"Phone number {cleaned_phone} is already registered."}), 200

        # Generate UUID
        user_id = str(uuid.uuid4())

        # Save user to Firestore
        db.collection("customers").add({
            "first_name": first_name,
            "last_name": last_name,
            "phone": cleaned_phone,
            "uuid": user_id
        })

        # Optional: Send welcome SMS
        send_welcome_sms(cleaned_phone, first_name)

        return jsonify({"message": f"Welcome, {first_name}! You're all signed up."}), 200

    except Exception as e:
        return jsonify({"error": f"Something went wrong: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
