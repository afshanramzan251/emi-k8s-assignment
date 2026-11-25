import os
import socket
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient, DESCENDING

app = Flask(__name__)

# Environment variables se configuration (koi hardcoded host/IP nahi)
MONGO_URL = os.environ.get("MONGO_URL")
if not MONGO_URL:
    raise RuntimeError("MONGO_URL environment variable is not set!")

client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=2000)
# Agar URI mein database name na ho to default 'emidb' use karega
db = client.get_default_database(default="emidb")
calculations_col = db["calculations"]


def get_pod_info():
    pod_name = os.environ.get("HOSTNAME") or socket.gethostname()
    try:
        pod_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        pod_ip = "127.0.0.1"
    return pod_name, pod_ip


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    try:
        client.admin.command("ping")
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


@app.route("/api/emi", methods=["POST"])
def calculate_emi():
    data = request.get_json(silent=True) or request.form

    try:
        principal = float(data.get("principal", 0))
        rate = float(data.get("rate", 0))
        months = int(data.get("months", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid input types. Please enter valid numbers."}), 400

    # Server-side validation: positive numbers only
    if principal <= 0 or rate <= 0 or months <= 0:
        return jsonify({"error": "Principal, rate, and months must all be positive numbers."}), 400

    # EMI Formula: P * r * (1 + r)^n / ((1 + r)^n - 1)
    r = (rate / 12.0) / 100.0
    factor = (1 + r) ** months
    emi = (principal * r * factor) / (factor - 1)

    total_payment = emi * months
    total_interest = total_payment - principal

    emi_rounded = round(emi, 2)
    total_payment_rounded = round(total_payment, 2)
    total_interest_rounded = round(total_interest, 2)

    pod_name, pod_ip = get_pod_info()
    created_at = datetime.now(timezone.utc)

    record = {
        "principal": principal,
        "rate": rate,
        "months": months,
        "emi": emi_rounded,
        "servedBy": pod_name,
        "createdAt": created_at,
    }
    calculations_col.insert_one(record)

    return jsonify({
        "principal": principal,
        "rate": rate,
        "months": months,
        "emi": emi_rounded,
        "totalPayment": total_payment_rounded,
        "totalInterest": total_interest_rounded,
        "servedBy": pod_name,
        "podIp": pod_ip,
        "createdAt": created_at.isoformat()
    }), 200


@app.route("/api/history", methods=["GET"])
def history():
    cursor = calculations_col.find({}, {"_id": 0}).sort("createdAt", DESCENDING).limit(10)
    results = []
    for doc in cursor:
        if isinstance(doc.get("createdAt"), datetime):
            doc["createdAt"] = doc["createdAt"].strftime("%Y-%m-%d %H:%M:%S UTC")
        results.append(doc)
    return jsonify(results), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)