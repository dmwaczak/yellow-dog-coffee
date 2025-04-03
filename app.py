import os
import uuid
import re
from flask import Flask, render_template, request, jsonify, redirect, session
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "defaultsecret")

# Firebase credentials
firebase_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "firebase_credentials.json")

if not os.path.exists(firebase_creds_path):
    print(f"⚠️ Firebase credentials not found at {firebase_creds_path}! Make sure it's uploaded in Render Secrets.")
    exit(1)

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_creds_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Helper: Clean phone number
def clean_phone_number(phone):
    cleaned = re.sub(r'\D', '', phone)
    return cleaned[1:] if len(cleaned) == 11 and cleaned.startswith('1') else cleaned if len(cleaned) == 10 else None

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

        if not first_name or not last_name or not email or not phone:
            return jsonify({"error": "All fields (first name, last name, email, phone) are required."}), 400

        cleaned_phone = clean_phone_number(phone)
        if not cleaned_phone:
            return jsonify({"error": "Invalid phone number format."}), 400

        existing_users = db.collection("customers").where("phone", "==", cleaned_phone).get()
        if existing_users:
            return jsonify({"redirect": f"/thankyou?name={first_name}"}), 200

        db.collection("customers").add({
            "uuid": str(uuid.uuid4()),
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": cleaned_phone,
            "points": 0,
            "punches": 0
        })

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

        return render_template("status.html", name=name, punches=punches, points=points)

    return render_template("status_check.html")

@app.route('/rewards')
def rewards():
    return render_template("rewards.html")

@app.route('/menu')
def menu():
    return render_template("menu.html")

@app.route('/barista-login', methods=['GET', 'POST'])
def barista_login():
    if request.method == 'POST':
        password = request.form.get("password")
        if password == "1111":
            session['barista_authenticated'] = True
            return redirect("/barista")
        else:
            return render_template("barista-login.html", error="Incorrect password")
    return render_template("barista-login.html")

@app.route('/barista', methods=['GET', 'POST'])
def barista():
    if not session.get('barista_authenticated'):
        return redirect("/barista-login")

    if request.method == 'GET':
        return render_template("barista.html")

    if request.method == 'POST':
        try:
            data = request.json
            phone = data.get("phone")
            coffees = data.get("coffees")
            amount = data.get("amount")

            if not phone or coffees is None or amount is None:
                return jsonify({"error": "Phone, coffees, and amount are required."}), 400

            cleaned_phone = clean_phone_number(phone)
            if not cleaned_phone:
                return jsonify({"error": "Invalid phone number format."}), 400

            docs = db.collection("customers").where("phone", "==", cleaned_phone).get()
            if not docs:
                return jsonify({"error": "Customer not found."}), 404

            doc_ref = docs[0].reference
            customer = docs[0].to_dict()

            new_points = customer.get("points", 0) + int(float(amount))
            new_punches = customer.get("punches", 0) + int(float(coffees))

            doc_ref.update({
                "points": new_points,
                "punches": new_punches
            })

            return jsonify({
                "message": f"{coffees} punches & {amount} points added for {customer.get('first_name', 'Customer')}"
            }), 200

        except Exception as e:
            return jsonify({"error": f"Something went wrong: {e}"}), 500

@app.route('/redeem', methods=['POST'])
def redeem():
    phone = request.form.get("phone")
    cleaned_phone = clean_phone_number(phone)
    if not cleaned_phone:
        return "Invalid phone number.", 400

    docs = db.collection("customers").where("phone", "==", cleaned_phone).get()
    if not docs:
        return "Customer not found.", 404

    doc_ref = docs[0].reference
    doc_ref.update({"punches": 0})

    return "Punches reset after redemption. Free coffee claimed!"

@app.route('/admin-add-punch', methods=['POST'])
def admin_add_punch():
    phone = request.form.get("phone")
    cleaned_phone = clean_phone_number(phone)
    if not cleaned_phone:
        return "Invalid phone number.", 400

    docs = db.collection("customers").where("phone", "==", cleaned_phone).get()
    if not docs:
        return "Customer not found.", 404

    doc = docs[0]
    customer_data = doc.to_dict()
    current_punches = customer_data.get("punches", 0)

    doc.reference.update({"punches": current_punches + 1})

    return f"Punch added. Now has {current_punches + 1} punches."

if __name__ == '__main__':
    app.run(debug=True)