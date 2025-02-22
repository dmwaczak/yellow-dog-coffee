from flask import Flask, render_template, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os
import re  # Import regex for cleaning phone numbers

# Initialize Flask app & explicitly set template folder
app = Flask(__name__, template_folder="templates")

# Ensure Firebase is only initialized once
if not firebase_admin._apps:
    cred = credentials.Certificate(os.path.join(os.getcwd(), "firebase_credentials.json"))
    firebase_admin.initialize_app(cred)

# Connect to Firestore
try:
    db = firestore.client()
except Exception as e:
    print(f"Error connecting to Firestore: {e}")


# Function to clean and standardize phone numbers
def clean_phone_number(phone):
    """Removes all non-numeric characters and ensures a 10-digit format."""
    cleaned_phone = re.sub(r'\D', '', phone)  # Remove non-numeric characters

    if len(cleaned_phone) == 11 and cleaned_phone.startswith("1"):  # Handle +1 country code
        cleaned_phone = cleaned_phone[1:]  # Remove the leading '1'

    if len(cleaned_phone) != 10:  # Ensure it's exactly 10 digits
        return None  

    return cleaned_phone

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
        phone = data.get("phone")

        if not phone:
            return jsonify({"error": "Phone number required"}), 400

        # Clean and validate phone number
        cleaned_phone = clean_phone_number(phone)
        if not cleaned_phone:
            return jsonify({"error": "Invalid phone number format"}), 400

        # Store phone number in Firestore
        db.collection("customers").add({"phone": cleaned_phone})

        return jsonify({"message": f"Phone number {cleaned_phone} saved!"}), 200
    except Exception as e:
        return jsonify({"error": f"Something went wrong: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
