from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

import csv
import os
import hashlib
import time
import uuid

from datetime import datetime

from dotenv import load_dotenv
from google import genai
import razorpay


# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(__name__)
CORS(app)


# ============================================================
# BASE PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ENV_PATH = os.path.join(
    BASE_DIR,
    "..",
    ".env"
)

load_dotenv(ENV_PATH)


# ============================================================
# GEMINI AI CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    client = genai.Client(
        api_key=GEMINI_API_KEY
    )
else:
    client = None


# ============================================================
# RAZORPAY TEST MODE CONFIGURATION
# ============================================================

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    razorpay_client = razorpay.Client(
        auth=(
            RAZORPAY_KEY_ID,
            RAZORPAY_KEY_SECRET
        )
    )
else:
    razorpay_client = None


# ============================================================
# DATASET CONFIGURATION
# ============================================================

DATA_DIR = os.path.join(
    BASE_DIR,
    "..",
    "data"
)

DEFAULT_DATASET = os.path.join(
    DATA_DIR,
    "payments.csv"
)

UPLOADED_DATASET = os.path.join(
    DATA_DIR,
    "uploaded_payments.csv"
)

ACTIVE_DATASET = DEFAULT_DATASET

REQUIRED_COLUMNS = [
    "payment_id",
    "amount",
    "status",
    "failure_reason",
    "customer_type"
]


# ============================================================
# RECOVERY CONFIGURATION
# ============================================================

MAX_RETRIES = 2

recovery_probability = {
    "upi_timeout": 0.80,
    "bank_timeout": 0.70,
    "insufficient_funds": 0.40,
    "card_expired": 0.50
}


recovery_actions = {
    "upi_timeout": {
        "action": "retry_payment",
        "risk": "low",
        "reason": (
            "Temporary UPI timeout may succeed on retry."
        )
    },

    "bank_timeout": {
        "action": "retry_after_delay",
        "risk": "low",
        "reason": (
            "Temporary bank timeout may recover "
            "after a short delay."
        )
    },

    "insufficient_funds": {
        "action": "send_payment_reminder",
        "risk": "medium",
        "reason": (
            "Retrying immediately is unlikely to succeed "
            "without sufficient funds."
        )
    },

    "card_expired": {
        "action": "request_card_update",
        "risk": "medium",
        "reason": (
            "The customer needs to update the expired card."
        )
    }
}


# ============================================================
# IN-MEMORY STATE
# ============================================================

audit_log = []
retry_counts = {}
recovery_results = {}
razorpay_transactions = []


def reset_recovery_state():
    """
    Clear all recovery and audit information.
    """

    audit_log.clear()
    retry_counts.clear()
    recovery_results.clear()
    razorpay_transactions.clear()


# ============================================================
# AUDIT LOGGER
# ============================================================

def add_audit_log(
    payment_id,
    action,
    status,
    message
):
    """
    Add an action to the audit trail.
    """

    audit_log.append({
        "timestamp": datetime.now().isoformat(),
        "payment_id": payment_id,
        "action": action,
        "status": status,
        "message": message
    })


# ============================================================
# DETERMINISTIC RECOVERY SIMULATION
# ============================================================

def simulate_recovery(
    payment_id,
    probability
):
    """
    Generate a deterministic recovery result.

    The same payment ID always produces
    the same result for the same probability.
    """

    hash_value = hashlib.md5(
        payment_id.encode()
    ).hexdigest()

    number = (
        int(hash_value[:8], 16)
        /
        0xFFFFFFFF
    )

    return number < probability


# ============================================================
# GET ACTIVE DATASET
# ============================================================

def get_payments():
    """
    Read the currently active payment dataset.
    """

    payments = []

    if not os.path.exists(ACTIVE_DATASET):
        return payments

    with open(
        ACTIVE_DATASET,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            payments.append(row)

    return payments


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return send_from_directory(
        os.path.join(BASE_DIR, "..", "frontend"),
        "index.html"
    )


@app.route("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(
        os.path.join(BASE_DIR, "..", "frontend"),
        filename
    )


# ============================================================
# RAZORPAY CONFIG
# ============================================================

@app.route("/api/razorpay/config")
def razorpay_config():

    if not RAZORPAY_KEY_ID:

        return jsonify({
            "success": False,
            "message": (
                "Razorpay Test Key ID is not configured."
            )
        }), 500

    return jsonify({
        "success": True,
        "key_id": RAZORPAY_KEY_ID,
        "test_mode": True
    })


# ============================================================
# CREATE RAZORPAY TEST ORDER
# ============================================================

@app.route(
    "/api/razorpay/create-order",
    methods=["POST"]
)
def create_razorpay_order():

    if razorpay_client is None:

        return jsonify({
            "success": False,
            "message": (
                "Razorpay Test API keys are not configured."
            )
        }), 500

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "message": "No payment data received."
        }), 400

    try:

        amount = float(
            data.get("amount", 0)
        )

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "Amount must be a valid number."
        }), 400

    if amount < 1:

        return jsonify({
            "success": False,
            "message": (
                "Test payment amount must be at least ₹1."
            )
        }), 400

    amount_in_paise = int(
        round(amount * 100)
    )

    receipt = (
        "rcpt_"
        + uuid.uuid4().hex[:20]
    )

    try:

        order = razorpay_client.order.create(
            data={
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": receipt,
                "notes": {
                    "application": "Recovery Copilot",
                    "mode": "TEST"
                }
            }
        )

        add_audit_log(
            "SYSTEM",
            "razorpay_test_order",
            "created",
            (
                f"Created Razorpay Test Mode order "
                f"{order['id']} for ₹{amount:.2f}."
            )
        )

        return jsonify({
            "success": True,
            "test_mode": True,
            "order_id": order["id"],
            "amount": amount_in_paise,
            "currency": "INR",
            "key_id": RAZORPAY_KEY_ID,
            "receipt": receipt
        })

    except Exception as error:

        print(
            "Razorpay order creation error:",
            error
        )

        add_audit_log(
            "SYSTEM",
            "razorpay_test_order",
            "failed",
            "Unable to create Razorpay Test Mode order."
        )

        return jsonify({
            "success": False,
            "message": (
                "Unable to create Razorpay Test Mode order."
            )
        }), 500


# ============================================================
# VERIFY RAZORPAY TEST PAYMENT
# ============================================================

@app.route(
    "/api/razorpay/verify-payment",
    methods=["POST"]
)
def verify_razorpay_payment():

    if razorpay_client is None:

        return jsonify({
            "success": False,
            "message": (
                "Razorpay Test API keys are not configured."
            )
        }), 500

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "message": (
                "No payment verification data received."
            )
        }), 400

    razorpay_order_id = data.get(
        "razorpay_order_id"
    )

    razorpay_payment_id = data.get(
        "razorpay_payment_id"
    )

    razorpay_signature = data.get(
        "razorpay_signature"
    )

    if not all([
        razorpay_order_id,
        razorpay_payment_id,
        razorpay_signature
    ]):

        return jsonify({
            "success": False,
            "message": (
                "Incomplete Razorpay payment information."
            )
        }), 400

    try:

        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        })

        amount = data.get("amount", 0)

        transaction = {
            "payment_id": razorpay_payment_id,
            "order_id": razorpay_order_id,
            "status": "success",
            "amount": amount,
            "source": "Razorpay Test Mode",
            "timestamp": datetime.now().isoformat()
        }

        razorpay_transactions.append(
            transaction
        )

        add_audit_log(
            razorpay_payment_id,
            "razorpay_test_payment",
            "success",
            (
                "Razorpay Test Mode payment signature "
                "verified successfully."
            )
        )

        return jsonify({
            "success": True,
            "status": "success",
            "payment_id": razorpay_payment_id,
            "order_id": razorpay_order_id,
            "amount": amount,
            "message": (
                "Test payment verified successfully."
            ),
            "simulation_mode": True
        })

    except Exception as error:

        print(
            "Razorpay verification error:",
            error
        )

        add_audit_log(
            razorpay_payment_id or "UNKNOWN",
            "razorpay_test_payment",
            "verification_failed",
            (
                "Razorpay payment signature "
                "verification failed."
            )
        )

        return jsonify({
            "success": False,
            "status": "verification_failed",
            "message": "Payment verification failed."
        }), 400


# ============================================================
# RAZORPAY FAILED PAYMENT
# ============================================================

@app.route(
    "/api/razorpay/payment-failed",
    methods=["POST"]
)
def razorpay_payment_failed():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "message": (
                "No failed payment data received."
            )
        }), 400

    payment_id = data.get(
        "razorpay_payment_id"
    )

    order_id = data.get(
        "razorpay_order_id",
        ""
    )

    amount = data.get(
        "amount",
        0
    )

    try:

        amount = float(amount)

    except (TypeError, ValueError):

        amount = 0

    # --------------------------------------------------------
    # GENERATE PAYMENT ID IF NEEDED
    # --------------------------------------------------------

    if not payment_id:

        payment_id = (
            "RZP_FAIL_"
            + uuid.uuid4().hex[:10].upper()
        )

    # --------------------------------------------------------
    # FAILURE REASON
    # --------------------------------------------------------

    failure_reason = data.get("reason")

    if not failure_reason:
        failure_reason = "bank_timeout"

    if failure_reason not in recovery_actions:
        failure_reason = "bank_timeout"

    # --------------------------------------------------------
    # STORE FAILED TRANSACTION
    # --------------------------------------------------------

    transaction = {
        "payment_id": payment_id,
        "order_id": order_id,
        "status": "failed",
        "amount": amount,
        "failure_reason": failure_reason,
        "source": "Razorpay Test Mode",
        "timestamp": datetime.now().isoformat()
    }

    razorpay_transactions.append(
        transaction
    )

    # --------------------------------------------------------
    # STEP 1 — DETECT FAILURE
    # --------------------------------------------------------

    add_audit_log(
        payment_id,
        "razorpay_payment_failed",
        "detected",
        (
            "Razorpay Test Mode payment failed. "
            "Recovery Copilot detected the failed payment."
        )
    )

    # --------------------------------------------------------
    # STEP 2 — RECOMMEND ACTION
    # --------------------------------------------------------

    recommendation = recovery_actions[
        failure_reason
    ]

    action = recommendation["action"]
    risk = recommendation["risk"]
    probability = recovery_probability[
        failure_reason
    ]

    add_audit_log(
        payment_id,
        action,
        "recommended",
        (
            f"Recovery Copilot recommends {action} "
            f"for {failure_reason}. "
            f"Risk level: {risk}."
        )
    )

    # --------------------------------------------------------
    # STEP 3 — SAFETY CHECK
    # --------------------------------------------------------

    if risk == "medium":

        add_audit_log(
            payment_id,
            action,
            "approval_required",
            (
                "Recovery action requires merchant "
                "approval because it is medium risk."
            )
        )

        return jsonify({
            "success": True,
            "status": "approval_required",
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": amount,
            "failure_reason": failure_reason,
            "action": action,
            "risk": risk,
            "recovered": False,
            "message": (
                "Failed Razorpay payment detected. "
                "Merchant approval is required before "
                "the recovery action can execute."
            ),
            "simulation_mode": True
        })

    # --------------------------------------------------------
    # STEP 4 — BOUNDED RETRY CHECK
    # --------------------------------------------------------

    current_retry_count = retry_counts.get(
        payment_id,
        0
    )

    if action in [
        "retry_payment",
        "retry_after_delay"
    ]:

        if current_retry_count >= MAX_RETRIES:

            add_audit_log(
                payment_id,
                action,
                "blocked",
                "Maximum retry limit reached."
            )

            return jsonify({
                "success": False,
                "status": "blocked",
                "payment_id": payment_id,
                "action": action,
                "retry_count": current_retry_count,
                "message": (
                    "Recovery blocked because "
                    "the maximum retry limit was reached."
                )
            }), 403

        retry_counts[payment_id] = (
            current_retry_count + 1
        )

    # --------------------------------------------------------
    # STEP 5 — SIMULATE RECOVERY
    # --------------------------------------------------------

    recovered = simulate_recovery(
        payment_id,
        probability
    )

    recovery_results[payment_id] = {
        "amount": amount,
        "recovered": recovered,
        "failure_reason": failure_reason,
        "action": action
    }

    # --------------------------------------------------------
    # STEP 6 — AUDIT RESULT
    # --------------------------------------------------------

    if recovered:

        add_audit_log(
            payment_id,
            action,
            "recovered",
            (
                "Razorpay Test Mode payment "
                "recovered successfully in simulation mode."
            )
        )

        status = "recovered"

        message = (
            "Recovery Copilot recovered the failed "
            "payment successfully in simulation mode."
        )

    else:

        add_audit_log(
            payment_id,
            action,
            "not_recovered",
            (
                "Recovery action executed, but the "
                "payment was not recovered in simulation mode."
            )
        )

        status = "not_recovered"

        message = (
            "Recovery action was executed, but the "
            "payment was not recovered in simulation mode."
        )

    return jsonify({
        "success": True,
        "status": status,
        "payment_id": payment_id,
        "order_id": order_id,
        "amount": amount,
        "failure_reason": failure_reason,
        "action": action,
        "risk": risk,
        "recovered": recovered,
        "retry_count": retry_counts.get(
            payment_id,
            0
        ),
        "message": message,
        "simulation_mode": True
    })


# ============================================================
# RAZORPAY TRANSACTIONS
# ============================================================

@app.route("/api/razorpay/transactions")
def get_razorpay_transactions():

    return jsonify({
        "success": True,
        "test_mode": True,
        "transactions": razorpay_transactions
    })


# ============================================================
# UPLOAD PAYMENT CSV
# ============================================================

@app.route(
    "/api/upload",
    methods=["POST"]
)
def upload_dataset():

    global ACTIVE_DATASET

    if "file" not in request.files:

        return jsonify({
            "success": False,
            "message": "Please upload a CSV file."
        }), 400

    file = request.files["file"]

    if file.filename == "":

        return jsonify({
            "success": False,
            "message": "No file selected."
        }), 400

    if not file.filename.lower().endswith(".csv"):

        return jsonify({
            "success": False,
            "message": "Only CSV files are supported."
        }), 400

    try:

        content = file.stream.read().decode(
            "utf-8-sig"
        )

        lines = content.splitlines()

        if not lines:

            return jsonify({
                "success": False,
                "message": "The uploaded CSV is empty."
            }), 400

        reader = csv.DictReader(lines)

        if not reader.fieldnames:

            return jsonify({
                "success": False,
                "message": "CSV header row is missing."
            }), 400

        uploaded_columns = [
            column.strip()
            for column in reader.fieldnames
            if column
        ]

        missing_columns = [
            column
            for column in REQUIRED_COLUMNS
            if column not in uploaded_columns
        ]

        if missing_columns:

            return jsonify({
                "success": False,
                "message": (
                    "Missing required columns: "
                    + ", ".join(missing_columns)
                )
            }), 400

        rows = list(reader)

        if len(rows) == 0:

            return jsonify({
                "success": False,
                "message": (
                    "The uploaded CSV contains "
                    "no payment records."
                )
            }), 400

        valid_statuses = {
            "success",
            "failed"
        }

        # ----------------------------------------------------
        # VALIDATE EACH ROW
        # ----------------------------------------------------

        for index, row in enumerate(
            rows,
            start=2
        ):

            payment_id = (
                row.get(
                    "payment_id",
                    ""
                ).strip()
            )

            amount = (
                row.get(
                    "amount",
                    ""
                ).strip()
            )

            status = (
                row.get(
                    "status",
                    ""
                )
                .strip()
                .lower()
            )

            failure_reason = (
                row.get(
                    "failure_reason",
                    ""
                ).strip()
            )

            if not payment_id:

                return jsonify({
                    "success": False,
                    "message": (
                        f"Row {index}: "
                        "payment_id is required."
                    )
                }), 400

            try:

                amount_value = float(amount)

                if amount_value < 0:
                    raise ValueError

            except (TypeError, ValueError):

                return jsonify({
                    "success": False,
                    "message": (
                        f"Row {index}: "
                        "amount must be a valid "
                        "positive number."
                    )
                }), 400

            if status not in valid_statuses:

                return jsonify({
                    "success": False,
                    "message": (
                        f"Row {index}: "
                        "status must be success or failed."
                    )
                }), 400

            if (
                status == "failed"
                and not failure_reason
            ):

                return jsonify({
                    "success": False,
                    "message": (
                        f"Row {index}: failed payments "
                        "require a failure_reason."
                    )
                }), 400

        # ----------------------------------------------------
        # SAVE UPLOADED DATASET
        # ----------------------------------------------------

        with open(
            UPLOADED_DATASET,
            "w",
            newline="",
            encoding="utf-8"
        ) as output_file:

            writer = csv.DictWriter(
                output_file,
                fieldnames=REQUIRED_COLUMNS
            )

            writer.writeheader()

            for row in rows:

                writer.writerow({
                    "payment_id": row.get(
                        "payment_id",
                        ""
                    ).strip(),

                    "amount": row.get(
                        "amount",
                        ""
                    ).strip(),

                    "status": row.get(
                        "status",
                        ""
                    ).strip().lower(),

                    "failure_reason": row.get(
                        "failure_reason",
                        ""
                    ).strip(),

                    "customer_type": row.get(
                        "customer_type",
                        ""
                    ).strip()
                })

        ACTIVE_DATASET = UPLOADED_DATASET

        reset_recovery_state()

        add_audit_log(
            "SYSTEM",
            "dataset_upload",
            "completed",
            "New payment dataset uploaded successfully."
        )

        return jsonify({
            "success": True,
            "message": (
                "Payment dataset uploaded successfully."
            ),
            "filename": file.filename,
            "total_payments": len(rows)
        })

    except Exception as error:

        print(
            "CSV upload error:",
            error
        )

        return jsonify({
            "success": False,
            "message": (
                "Unable to process the uploaded CSV."
            )
        }), 500


# ============================================================
# RESET DEMO DATASET
# ============================================================

@app.route(
    "/api/reset-demo",
    methods=["POST"]
)
def reset_demo_dataset():

    global ACTIVE_DATASET

    if not os.path.exists(DEFAULT_DATASET):

        return jsonify({
            "success": False,
            "message": (
                "Demo dataset is not available."
            )
        }), 404

    ACTIVE_DATASET = DEFAULT_DATASET

    reset_recovery_state()

    add_audit_log(
        "SYSTEM",
        "reset_demo_dataset",
        "completed",
        (
            "Dashboard reset to the default "
            "demo dataset."
        )
    )

    return jsonify({
        "success": True,
        "message": (
            "Dashboard reset to the demo dataset."
        ),
        "total_payments": len(
            get_payments()
        )
    })


# ============================================================
# DATASET INFORMATION
# ============================================================

@app.route("/api/dataset")
def dataset_info():

    payments = get_payments()

    if ACTIVE_DATASET == DEFAULT_DATASET:
        dataset_type = "Demo Dataset"
    else:
        dataset_type = "Uploaded Dataset"

    return jsonify({
        "success": True,
        "dataset_type": dataset_type,
        "total_payments": len(payments)
    })


# ============================================================
# PAYMENT SUMMARY
# ============================================================

@app.route("/api/summary")
def summary():

    payments = get_payments()

    total = len(payments)

    successful = 0
    failed = 0

    revenue_at_risk = 0
    potential_recovery = 0

    for payment in payments:

        if payment["status"] == "success":

            successful += 1

        elif payment["status"] == "failed":

            failed += 1

            amount = float(
                payment["amount"]
            )

            revenue_at_risk += amount

            reason = payment["failure_reason"]

            if reason in recovery_probability:

                potential_recovery += (
                    amount
                    *
                    recovery_probability[reason]
                )

    if total > 0:

        failure_rate = (
            failed / total
        ) * 100

    else:

        failure_rate = 0

    return jsonify({
        "total_payments": total,

        "successful_payments": successful,

        "failed_payments": failed,

        "failure_rate": round(
            failure_rate,
            2
        ),

        "revenue_at_risk": round(
            revenue_at_risk,
            2
        ),

        "potential_recovery": round(
            potential_recovery,
            2
        )
    })


# ============================================================
# FAILURE ANALYSIS
# ============================================================

@app.route("/api/failures")
def failures():

    payments = get_payments()

    failed_payments = []

    for row in payments:

        if row["status"] == "failed":

            failed_payments.append({
                "payment_id": row["payment_id"],

                "amount": float(
                    row["amount"]
                ),

                "failure_reason": (
                    row["failure_reason"]
                ),

                "customer_type": (
                    row["customer_type"]
                )
            })

    return jsonify(
        failed_payments
    )


# ============================================================
# FAILED PAYMENTS
# ============================================================

@app.route("/api/payments")
def payments():

    all_payments = get_payments()

    failed_payments = []

    for row in all_payments:

        if row["status"] == "failed":

            failed_payments.append({
                "payment_id": row["payment_id"],

                "amount": float(
                    row["amount"]
                ),

                "failure_reason": (
                    row["failure_reason"]
                ),

                "customer_type": (
                    row["customer_type"]
                )
            })

    return jsonify(
        failed_payments
    )


# ============================================================
# RECOVERY RECOMMENDATIONS
# ============================================================

@app.route("/api/recommendations")
def recommendations():

    return jsonify(
        recovery_actions
    )


# ============================================================
# AI REVENUE ANALYSIS
# ============================================================

@app.route(
    "/api/ai-analysis",
    methods=["GET"]
)
def ai_analysis():

    payments = get_payments()

    failure_summary = {}

    # --------------------------------------------------------
    # BUILD FAILURE SUMMARY
    # --------------------------------------------------------

    for payment in payments:

        if payment["status"] != "failed":
            continue

        reason = payment["failure_reason"]

        amount = float(
            payment["amount"]
        )

        if reason not in failure_summary:

            failure_summary[reason] = {
                "count": 0,
                "amount": 0
            }

        failure_summary[reason]["count"] += 1

        failure_summary[reason]["amount"] += amount

    # --------------------------------------------------------
    # CALCULATE TOTALS
    # --------------------------------------------------------

    total_failed = 0
    total_failed_amount = 0
    potential_recovery = 0

    for reason, data in failure_summary.items():

        total_failed += data["count"]

        total_failed_amount += data["amount"]

        if reason in recovery_probability:

            potential_recovery += (
                data["amount"]
                *
                recovery_probability[reason]
            )

    # --------------------------------------------------------
    # GEMINI PROMPT
    # --------------------------------------------------------

    prompt = f"""
You are an AI revenue recovery analyst for a payment platform.

Analyze the following failed payment data.

Total failed transactions:
{total_failed}

Total revenue at risk:
₹{total_failed_amount:.2f}

Failure patterns:
{failure_summary}

Potential recovery:
₹{potential_recovery:.2f}

Available recovery actions:

UPI timeout:
- Action: retry_payment
- Risk: low
- Recovery probability: 80%

Bank timeout:
- Action: retry_after_delay
- Risk: low
- Recovery probability: 70%

Insufficient funds:
- Action: send_payment_reminder
- Risk: medium
- Recovery probability: 40%

Card expired:
- Action: request_card_update
- Risk: medium
- Recovery probability: 50%

Safety rules:

1. Maximum 2 retries.
2. Do not change payment amounts.
3. Do not automatically issue refunds.
4. Medium-risk actions require merchant approval.
5. Repeated failures should be escalated.
6. Recovery actions are simulation-only.

Return exactly these sections:

TOP RISK
RECOVERY OPPORTUNITY
RECOMMENDED STRATEGY
SAFETY DECISION
EXPLANATION

Keep the analysis concise and business-focused.
"""

    # ========================================================
    # GEMINI AI
    # ========================================================

    if client is not None:

        response = None

        max_attempts = 3

        for attempt in range(max_attempts):

            try:

                print(
                    f"Gemini AI attempt "
                    f"{attempt + 1}/{max_attempts}"
                )

                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=prompt
                )

                break

            except Exception as gemini_error:

                print(
                    f"Gemini attempt "
                    f"{attempt + 1} failed:",
                    gemini_error
                )

                if attempt < max_attempts - 1:

                    delay = 3 * (
                        2 ** attempt
                    )

                    time.sleep(delay)

        # ----------------------------------------------------
        # GEMINI SUCCESS
        # ----------------------------------------------------

        if response is not None:

            ai_text = response.text

            add_audit_log(
                "SYSTEM",
                "ai_revenue_analysis",
                "completed",
                (
                    "Gemini AI analyzed failed payment "
                    "patterns and generated a "
                    "recovery strategy."
                )
            )

            return jsonify({
                "success": True,

                "analysis": ai_text,

                "analysis_source": "Gemini AI",

                "failure_summary": failure_summary,

                "total_failed": total_failed,

                "revenue_at_risk": round(
                    total_failed_amount,
                    2
                ),

                "potential_recovery": round(
                    potential_recovery,
                    2
                )
            })

    # ========================================================
    # LOCAL FALLBACK ANALYSIS
    # ========================================================

    sorted_failures = sorted(
        failure_summary.items(),
        key=lambda item: item[1]["amount"],
        reverse=True
    )

    if sorted_failures:

        top_reason = sorted_failures[0][0]

        top_data = sorted_failures[0][1]

        top_label = top_reason.replace(
            "_",
            " "
        )

    else:

        top_data = {
            "count": 0,
            "amount": 0
        }

        top_label = "unknown"

    # --------------------------------------------------------
    # TECHNICAL RECOVERY
    # --------------------------------------------------------

    technical_recovery = 0

    for reason in [
        "upi_timeout",
        "bank_timeout"
    ]:

        if reason in failure_summary:

            technical_recovery += (
                failure_summary[reason]["amount"]
                *
                recovery_probability[reason]
            )

    # --------------------------------------------------------
    # FALLBACK ANALYSIS
    # --------------------------------------------------------

    fallback_analysis = f"""
TOP RISK

{top_label.title()} represents the largest revenue risk with ₹{top_data["amount"]:,.0f} across {top_data["count"]} failed transactions.


RECOVERY OPPORTUNITY

The dataset contains ₹{total_failed_amount:,.0f} in revenue at risk, with an estimated potential recovery of ₹{potential_recovery:,.0f}. Technical timeout failures represent approximately ₹{technical_recovery:,.0f} of potential recovery.


RECOMMENDED STRATEGY

Prioritize low-risk technical failures such as UPI and bank timeouts using controlled retries. These actions have the highest recovery probability and can be automated within the retry limit.

Medium-risk failures such as insufficient funds and expired cards should trigger customer communication or card-update workflows and require merchant approval.


SAFETY DECISION

Allow only bounded recovery actions. Maximum 2 retries per payment. Do not change payment amounts or automatically issue refunds. Medium-risk actions require merchant approval. Repeated failures should be escalated.


EXPLANATION

The safest recovery opportunity comes from temporary technical failures because retrying may resolve the issue without changing the payment or customer terms. Permanent or customer-dependent failures require intervention rather than repeated automated retries.
"""

    add_audit_log(
        "SYSTEM",
        "ai_revenue_analysis",
        "fallback",
        (
            "Gemini was unavailable. Local rule-based "
            "revenue recovery analysis was generated."
        )
    )

    return jsonify({
        "success": True,

        "analysis": fallback_analysis,

        "analysis_source": (
            "Recovery Copilot Fallback Analysis"
        ),

        "failure_summary": failure_summary,

        "total_failed": total_failed,

        "revenue_at_risk": round(
            total_failed_amount,
            2
        ),

        "potential_recovery": round(
            potential_recovery,
            2
        )
    })


# ============================================================
# EXECUTE SINGLE RECOVERY
# ============================================================

@app.route(
    "/api/recover",
    methods=["POST"]
)
def recover():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "message": (
                "No recovery request received."
            )
        }), 400

    payment_id = data.get("payment_id")

    failure_reason = data.get("failure_reason")

    if not payment_id:

        return jsonify({
            "success": False,
            "message": "Payment ID is required."
        }), 400

    if failure_reason not in recovery_actions:

        add_audit_log(
            payment_id,
            "unknown_action",
            "blocked",
            "Unknown failure reason."
        )

        return jsonify({
            "success": False,
            "status": "blocked",
            "message": (
                "Unknown failure reason. "
                "Recovery action blocked."
            )
        }), 400

    recommendation = recovery_actions[
        failure_reason
    ]

    action = recommendation["action"]

    risk = recommendation["risk"]

    retry_count = retry_counts.get(
        payment_id,
        0
    )

    # --------------------------------------------------------
    # MAXIMUM RETRIES
    # --------------------------------------------------------

    if action in [
        "retry_payment",
        "retry_after_delay"
    ]:

        if retry_count >= MAX_RETRIES:

            add_audit_log(
                payment_id,
                action,
                "blocked",
                "Maximum retry limit reached."
            )

            return jsonify({
                "success": False,
                "status": "blocked",
                "message": (
                    "Recovery blocked: maximum "
                    "of 2 retries reached."
                ),
                "retry_count": retry_count
            }), 403

    # --------------------------------------------------------
    # MEDIUM RISK APPROVAL
    # --------------------------------------------------------

    if risk == "medium":

        approved = data.get(
            "merchant_approved",
            False
        )

        if not approved:

            add_audit_log(
                payment_id,
                action,
                "approval_required",
                "Merchant approval is required."
            )

            return jsonify({
                "success": False,
                "status": "approval_required",
                "message": (
                    "Merchant approval is required "
                    "for this recovery action."
                ),
                "action": action
            }), 403

    # --------------------------------------------------------
    # INCREASE RETRY COUNT
    # --------------------------------------------------------

    if action in [
        "retry_payment",
        "retry_after_delay"
    ]:

        retry_counts[payment_id] = (
            retry_count + 1
        )

    # --------------------------------------------------------
    # FIND PAYMENT AMOUNT
    # --------------------------------------------------------

    payment_amount = 0

    for payment in get_payments():

        if payment["payment_id"] == payment_id:

            payment_amount = float(
                payment["amount"]
            )

            break

    # --------------------------------------------------------
    # SIMULATE RECOVERY
    # --------------------------------------------------------

    probability = recovery_probability[
        failure_reason
    ]

    recovered = simulate_recovery(
        payment_id,
        probability
    )

    recovery_results[payment_id] = {
        "amount": payment_amount,
        "recovered": recovered,
        "failure_reason": failure_reason,
        "action": action
    }

    # --------------------------------------------------------
    # AUDIT RESULT
    # --------------------------------------------------------

    if recovered:

        add_audit_log(
            payment_id,
            action,
            "recovered",
            (
                "Payment successfully recovered "
                "in simulation mode."
            )
        )

        status = "recovered"

        message = (
            "Payment recovered successfully "
            "in simulation mode."
        )

    else:

        add_audit_log(
            payment_id,
            action,
            "not_recovered",
            (
                "Recovery action executed but "
                "payment was not recovered."
            )
        )

        status = "not_recovered"

        message = (
            "Recovery action executed, "
            "but payment was not recovered "
            "in simulation mode."
        )

    return jsonify({
        "success": True,
        "status": status,
        "payment_id": payment_id,
        "action": action,
        "amount": payment_amount,
        "recovered": recovered,
        "retry_count": retry_counts.get(
            payment_id,
            0
        ),
        "message": message,
        "simulation_mode": True
    })


# ============================================================
# BATCH RECOVERY
# ============================================================

@app.route(
    "/api/recover-batch",
    methods=["POST"]
)
def recover_batch():

    payments = get_payments()

    eligible_payments = []

    # --------------------------------------------------------
    # FIND ELIGIBLE PAYMENTS
    # --------------------------------------------------------

    for payment in payments:

        if payment["status"] != "failed":
            continue

        payment_id = payment["payment_id"]

        failure_reason = payment["failure_reason"]

        if failure_reason not in recovery_actions:
            continue

        action = recovery_actions[
            failure_reason
        ]["action"]

        if action in [
            "retry_payment",
            "retry_after_delay"
        ]:

            current_retry_count = retry_counts.get(
                payment_id,
                0
            )

            if current_retry_count >= MAX_RETRIES:
                continue

        eligible_payments.append(
            payment
        )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    attempted = 0
    recovered = 0
    not_recovered = 0

    attempted_amount = 0
    recovered_amount = 0
    not_recovered_amount = 0

    # --------------------------------------------------------
    # PROCESS PAYMENTS
    # --------------------------------------------------------

    for payment in eligible_payments:

        payment_id = payment["payment_id"]

        failure_reason = payment["failure_reason"]

        amount = float(
            payment["amount"]
        )

        recommendation = recovery_actions[
            failure_reason
        ]

        action = recommendation["action"]

        risk = recommendation["risk"]

        # ----------------------------------------------------
        # MEDIUM RISK
        # ----------------------------------------------------

        if risk == "medium":

            add_audit_log(
                payment_id,
                action,
                "approval_required",
                (
                    "Batch recovery skipped: "
                    "merchant approval required."
                )
            )

            continue

        current_retry_count = retry_counts.get(
            payment_id,
            0
        )

        # ----------------------------------------------------
        # RETRY LIMIT
        # ----------------------------------------------------

        if action in [
            "retry_payment",
            "retry_after_delay"
        ]:

            if current_retry_count >= MAX_RETRIES:

                add_audit_log(
                    payment_id,
                    action,
                    "blocked",
                    (
                        "Batch recovery blocked: "
                        "maximum retry limit reached."
                    )
                )

                continue

            retry_counts[payment_id] = (
                current_retry_count + 1
            )

        # ----------------------------------------------------
        # SIMULATE RECOVERY
        # ----------------------------------------------------

        probability = recovery_probability[
            failure_reason
        ]

        recovered_result = simulate_recovery(
            payment_id,
            probability
        )

        attempted += 1

        attempted_amount += amount

        recovery_results[payment_id] = {
            "amount": amount,
            "recovered": recovered_result,
            "failure_reason": failure_reason,
            "action": action
        }

        # ----------------------------------------------------
        # RECOVERY SUCCESS
        # ----------------------------------------------------

        if recovered_result:

            recovered += 1

            recovered_amount += amount

            add_audit_log(
                payment_id,
                action,
                "recovered",
                (
                    "Payment recovered successfully "
                    "in batch simulation mode."
                )
            )

        # ----------------------------------------------------
        # RECOVERY FAILURE
        # ----------------------------------------------------

        else:

            not_recovered += 1

            not_recovered_amount += amount

            add_audit_log(
                payment_id,
                action,
                "not_recovered",
                (
                    "Batch recovery attempted but "
                    "payment was not recovered."
                )
            )

    # --------------------------------------------------------
    # RECOVERY RATE
    # --------------------------------------------------------

    if attempted > 0:

        recovery_rate = (
            recovered / attempted
        ) * 100

    else:

        recovery_rate = 0

    return jsonify({
        "success": True,

        "eligible_payments": len(
            eligible_payments
        ),

        "attempted_transactions": attempted,

        "recovered_transactions": recovered,

        "not_recovered_transactions": (
            not_recovered
        ),

        "attempted_amount": round(
            attempted_amount,
            2
        ),

        "recovered_amount": round(
            recovered_amount,
            2
        ),

        "not_recovered_amount": round(
            not_recovered_amount,
            2
        ),

        "recovery_rate": round(
            recovery_rate,
            2
        ),

        "message": (
            "Batch recovery completed "
            "in simulation mode."
        ),

        "simulation_mode": True
    })


# ============================================================
# RECOVERY METRICS
# ============================================================

@app.route("/api/recovery-metrics")
def recovery_metrics():

    total_recovery_attempts = len(
        recovery_results
    )

    recovered_transactions = 0
    not_recovered_transactions = 0

    recovered_amount = 0
    not_recovered_amount = 0

    for result in recovery_results.values():

        amount = float(
            result["amount"]
        )

        if result["recovered"]:

            recovered_transactions += 1

            recovered_amount += amount

        else:

            not_recovered_transactions += 1

            not_recovered_amount += amount

    total_attempted_amount = (
        recovered_amount
        +
        not_recovered_amount
    )

    if total_recovery_attempts > 0:

        recovery_rate = (
            recovered_transactions
            /
            total_recovery_attempts
        ) * 100

    else:

        recovery_rate = 0

    return jsonify({
        "total_recovery_attempts": (
            total_recovery_attempts
        ),

        "recovered_transactions": (
            recovered_transactions
        ),

        "not_recovered_transactions": (
            not_recovered_transactions
        ),

        "recovered_amount": round(
            recovered_amount,
            2
        ),

        "not_recovered_amount": round(
            not_recovered_amount,
            2
        ),

        "total_attempted_amount": round(
            total_attempted_amount,
            2
        ),

        "recovery_rate": round(
            recovery_rate,
            2
        ),

        "simulation_mode": True
    })


# ============================================================
# AUDIT TRAIL
# ============================================================

@app.route("/api/audit")
def audit():

    return jsonify({
        "total_actions": len(audit_log),
        "logs": audit_log
    })


# ============================================================
# APPLICATION STARTUP
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("RECOVERY COPILOT")
    print("=" * 60)

    # --------------------------------------------------------
    # RAZORPAY STATUS
    # --------------------------------------------------------

    if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:

        print("Razorpay: TEST MODE")

    else:

        print("Razorpay: NOT CONFIGURED")

    # --------------------------------------------------------
    # GEMINI STATUS
    # --------------------------------------------------------

    if GEMINI_API_KEY:

        print("Gemini AI: CONFIGURED")

    else:

        print("Gemini AI: NOT CONFIGURED")

    print("=" * 60)
    print()

    app.run(
        debug=True
    )