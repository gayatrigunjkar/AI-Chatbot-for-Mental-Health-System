from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json, bcrypt, os, random, re
from datetime import datetime, timedelta
import threading, time
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
CORS(app)

# ------------------ PATHS ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

USERS_FILE = os.path.join(BASE_DIR, "users.json")
INTENTS_FILE = os.path.join(BASE_DIR, "intents.json")

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

CHATBOT_LOGIN_URL = "http://127.0.0.1:5000/login"

# ------------------ HELPERS ------------------
def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

def load_intents():
    if not os.path.exists(INTENTS_FILE):
        return {}
    with open(INTENTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ------------------ EMAIL ------------------
def send_email(to_email):
    try:
        body = f"""
Hi 🤍

Just checking in — how are you feeling today?

If you're not feeling okay, our mental health chatbot is always here for you 🌸

👉 Login here:
{CHATBOT_LOGIN_URL}

You are not alone 🤍
Take care.
"""
        msg = MIMEText(body)
        msg["Subject"] = "🤍 Just checking in on you"
        msg["From"] = EMAIL_USER
        msg["To"] = to_email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print("Email error:", e)
        return False

# ------------------ SCHEDULER ------------------
def email_scheduler():
    while True:
        users = load_users()
        now = datetime.now()

        for user in users:
            if user.get("mail_sent"):
                continue

            last_active = user.get("last_active")
            if not last_active:
                continue

            last_active = datetime.fromisoformat(last_active)

            if now - last_active >= timedelta(seconds=30):
                if send_email(user["email"]):
                    user["mail_sent"] = True

        save_users(users)
        time.sleep(10)
        

# ------------------ FRONTEND ROUTES (FIXED) ------------------
@app.route("/")
def home():
    return send_from_directory(FRONTEND_DIR, "login.html")

@app.route("/signup", methods=["GET"])
def signup_page():
    return send_from_directory(FRONTEND_DIR, "signup.html")

@app.route("/login", methods=["GET"])
def login_page():
    return send_from_directory(FRONTEND_DIR, "login.html")

@app.route("/chat", methods=["GET"])
def chatbot_page():
    return send_from_directory(FRONTEND_DIR, "chat.html")

@app.route("/css/<path:filename>")
def css_files(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "css"), filename)

@app.route("/music/<path:filename>")
def music_files(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "music"), filename)


# ------------------ API ROUTES ------------------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Missing fields"}), 400

    users = load_users()
    if any(u["email"] == email for u in users):
        return jsonify({"message": "User already exists"}), 409

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    users.append({
        "email": email,
        "password": hashed,
        "last_active": None,
        "mail_sent": False
    })

    save_users(users)
    return jsonify({"message": "Signup successful"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    users = load_users()
    for user in users:
        if user["email"] == email:
            if bcrypt.checkpw(password.encode(), user["password"].encode()):
                # 🔥 RESET HERE
                user["mail_sent"] = False
                user["last_active"] = None
                save_users(users)
                return jsonify({"message": "Login successful"}), 200

    return jsonify({"message": "Invalid credentials"}), 401

@app.route("/logout", methods=["POST"])
def logout():
    data = request.json or {}
    email = data.get("email")

    users = load_users()
    for user in users:
        if user["email"] == email:
            user["last_active"] = datetime.now().isoformat()
            user["mail_sent"] = False
            save_users(users)
            return jsonify({"message": "Logout successful"}), 200

    return jsonify({"message": "User not found"}), 404

# ------------------ CHATBOT ------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json or {}
    message = data.get("message", "").lower().strip()

    if not message:
        return jsonify({"reply": "I’m here for you 🤍"})

    clean_message = re.sub(r"[^\w\s]", "", message)
    message_words = clean_message.split()

    intents = load_intents()

    for intent_name, intent_data in intents.items():
        if intent_name == "default":
            continue

        keywords = intent_data.get("keywords", [])
        responses = intent_data.get("responses", [])

        for keyword in keywords:
            keyword = keyword.lower().strip()

            if keyword in clean_message:
                return jsonify({"reply": random.choice(responses)})

            if any(word in message_words for word in keyword.split()):
                return jsonify({"reply": random.choice(responses)})

    return jsonify({
        "reply": random.choice(
            intents.get("default", {}).get(
                "responses",
                ["I’m here for you 🤍"]
            )
        )
    })

# ------------------ START BACKGROUND THREAD ------------------
threading.Thread(target=email_scheduler, daemon=True).start()

# ------------------ RUN ------------------
if __name__ == "__main__":
    app.run(debug=True)
