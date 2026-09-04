
from flask import Flask, jsonify, request
from flask_cors import CORS
import csv
import os
import random
import time
from datetime import datetime

from dotenv import load_dotenv
from google import genai


app = Flask(__name__)
CORS(app)


# =========================
# Gemini AI Configuration
# =========================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

ENV_PATH = os.path.join(
    BASE_DIR,
    "..",
    ".env"
)

load_dotenv(ENV_PATH)

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

if GEMINI_API_KEY:

    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

else:

    client = None


# =========================
# Recovery Configuration
# =========================

MAX_RETRIES = 2

recovery_probability = {

    "upi_timeout": 0.80,

    "bank_timeout": 0.70,

    "insufficient_funds": 0.40,

    "card_expired": 0.50
}


recovery_actions = {

    "upi_timeout": {

        "action":
            "retry_payment",

        "risk":
            "low",

        "reason":
            "Temporary UPI timeout may succeed on retry."
    },

    "bank_timeout": {

        "action":
            "retry_after_delay",

        "risk":
            "low",

        "reason":
            "Temporary bank timeout may recover after a short delay."
    },

    "insufficient_funds": {

        "action":
            "send_payment_reminder",

        "risk":
            "medium",

        "reason":
            "Retrying immediately is unlikely to succeed without sufficient funds."
    },

    "card_expired": {

        "action":
            "request_card_update",

        "risk":
            "medium",

        "reason":
            "The customer needs to update the expired card."
    }
}


# =========================
# Audit Log
# =========================

audit_log = []

retry_counts = {}

recovery_results = {}


def add_audit_log(
    payment_id,
    action,
    status,
    message
):

    audit_log.append({

        "timestamp":
            datetime.now().isoformat(),

        "payment_id":
            payment_id,

        "action":
            action,

        "status":
            status,

        "message":
            message
    })


# =========================
# Helper: Get Payments
# =========================

def get_payments():

    file_path = os.path.join(
        BASE_DIR,
        "..",
        "data",
        "payments.csv"
    )

    payments = []

    with open(
        file_path,
        "r",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            payments.append(row)

    return payments


# =========================
# Home
# =========================

@app.route("/")
def home():

    return "Recovery Copilot is running!"


# =========================
# Payment Summary
# =========================

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

            reason = payment[
                "failure_reason"
            ]

            if reason in recovery_probability:

                probability = (
                    recovery_probability[
                        reason
                    ]
                )

                potential_recovery += (
                    amount * probability
                )


    if total > 0:

        failure_rate = (
            failed / total
        ) * 100

    else:

        failure_rate = 0


    return jsonify({

        "total_payments":
            total,

        "successful_payments":
            successful,

        "failed_payments":
            failed,

        "failure_rate":
            round(
                failure_rate,
                2
            ),

        "revenue_at_risk":
            round(
                revenue_at_risk,
                2
            ),

        "potential_recovery":
            round(
                potential_recovery,
                2
            )
    })


# =========================
# Failure Analysis
# =========================

@app.route("/api/failures")
def failures():

    payments = get_payments()

    failed_payments = []


    for row in payments:

        if row["status"] == "failed":

            failed_payments.append({

                "payment_id":
                    row["payment_id"],

                "amount":
                    float(
                        row["amount"]
                    ),

                "failure_reason":
                    row["failure_reason"],

                "customer_type":
                    row["customer_type"]
            })


    return jsonify(
        failed_payments
    )


# =========================
# Failed Payments
# =========================

@app.route("/api/payments")
def payments():

    all_payments = get_payments()

    failed_payments = []


    for row in all_payments:

        if row["status"] == "failed":

            failed_payments.append({

                "payment_id":
                    row["payment_id"],

                "amount":
                    float(
                        row["amount"]
                    ),

                "failure_reason":
                    row["failure_reason"],

                "customer_type":
                    row["customer_type"]
            })


    return jsonify(
        failed_payments
    )


# =========================
# Recovery Recommendations
# =========================

@app.route("/api/recommendations")
def recommendations():

    return jsonify(
        recovery_actions
    )


# =========================
# AI Revenue Analysis
# =========================

@app.route(
    "/api/ai-analysis",
    methods=["GET"]
)
def ai_analysis():

    payments = get_payments()


    # =========================
    # Build Failure Summary
    # =========================

    failure_summary = {}


    for payment in payments:

        if payment["status"] != "failed":

            continue


        reason = payment[
            "failure_reason"
        ]

        amount = float(
            payment["amount"]
        )


        if reason not in failure_summary:

            failure_summary[reason] = {

                "count":
                    0,

                "amount":
                    0
            }


        failure_summary[
            reason
        ]["count"] += 1


        failure_summary[
            reason
        ]["amount"] += amount


    # =========================
    # Calculate Totals
    # =========================

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


    # =========================
    # Prepare AI Prompt
    # =========================

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


    # =========================
    # Try Gemini AI
    # =========================

    if client is not None:

        response = None

        max_attempts = 3


        for attempt in range(
            max_attempts
        ):

            try:

                print(
                    f"Gemini AI attempt "
                    f"{attempt + 1}/{max_attempts}"
                )


                response = (
                    client.models.generate_content(

                        model=
                            "gemini-3.8-flash",

                        contents=
                            prompt
                    )
                )


                break


            except Exception as gemini_error:

                print(
                    f"Gemini attempt "
                    f"{attempt + 1} failed:",
                    gemini_error
                )


                if attempt < (
                    max_attempts - 1
                ):

                    delay = 3 * (
                        2 ** attempt
                    )


                    print(
                        f"Retrying Gemini in "
                        f"{delay} seconds..."
                    )


                    time.sleep(
                        delay
                    )

                else:

                    print(
                        "Gemini unavailable."
                    )

                    print(
                        "Using local fallback analysis."
                    )


        # =========================
        # Gemini Successful
        # =========================

        if response is not None:

            ai_text = response.text


            add_audit_log(

                "SYSTEM",

                "ai_revenue_analysis",

                "completed",

                "Gemini AI analyzed failed payment patterns and generated a recovery strategy."
            )


            return jsonify({

                "success":
                    True,

                "analysis":
                    ai_text,

                "analysis_source":
                    "Gemini AI",

                "failure_summary":
                    failure_summary,

                "total_failed":
                    total_failed,

                "revenue_at_risk":
                    round(
                        total_failed_amount,
                        2
                    ),

                "potential_recovery":
                    round(
                        potential_recovery,
                        2
                    )
            })


    # =========================
    # Local Fallback Analysis
    # =========================

    sorted_failures = sorted(

        failure_summary.items(),

        key=lambda item:
            item[1]["amount"],

        reverse=True
    )


    if sorted_failures:

        top_reason = (
            sorted_failures[0][0]
        )

        top_data = (
            sorted_failures[0][1]
        )

        top_label = (
            top_reason.replace(
                "_",
                " "
            )
        )

    else:

        top_reason = "unknown"

        top_data = {

            "count": 0,

            "amount": 0
        }

        top_label = "unknown"


    # =========================
    # Technical Recovery
    # =========================

    technical_recovery = 0


    for reason in [

        "upi_timeout",

        "bank_timeout"

    ]:

        if reason in failure_summary:

            technical_recovery += (

                failure_summary[
                    reason
                ]["amount"]

                *

                recovery_probability[
                    reason
                ]

            )


    # =========================
    # Generate Fallback Analysis
    # =========================

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


    # =========================
    # Audit Fallback
    # =========================

    add_audit_log(

        "SYSTEM",

        "ai_revenue_analysis",

        "fallback",

        "Gemini was temporarily unavailable. Local rule-based revenue recovery analysis was generated."
    )


    # =========================
    # Return Fallback Result
    # =========================

    return jsonify({

        "success":
            True,

        "analysis":
            fallback_analysis,

        "analysis_source":
            "Recovery Copilot Fallback Analysis",

        "failure_summary":
            failure_summary,

        "total_failed":
            total_failed,

        "revenue_at_risk":
            round(
                total_failed_amount,
                2
            ),

        "potential_recovery":
            round(
                potential_recovery,
                2
            )
    })


# =========================
# Execute Single Recovery
# =========================

@app.route(
    "/api/recover",
    methods=["POST"]
)
def recover():

    data = request.get_json()


    if not data:

        return jsonify({

            "success":
                False,

            "message":
                "No recovery request received."

        }), 400


    payment_id = data.get(
        "payment_id"
    )

    failure_reason = data.get(
        "failure_reason"
    )


    # =========================
    # Check Payment ID
    # =========================

    if not payment_id:

        return jsonify({

            "success":
                False,

            "message":
                "Payment ID is required."

        }), 400


    # =========================
    # Check Failure Reason
    # =========================

    if failure_reason not in recovery_actions:

        add_audit_log(

            payment_id,

            "unknown_action",

            "blocked",

            "Unknown failure reason."
        )


        return jsonify({

            "success":
                False,

            "status":
                "blocked",

            "message":
                "Unknown failure reason. Recovery action blocked."

        }), 400


    recommendation = (
        recovery_actions[
            failure_reason
        ]
    )


    action = recommendation[
        "action"
    ]

    risk = recommendation[
        "risk"
    ]


    # =========================
    # Current Retry Count
    # =========================

    retry_count = retry_counts.get(
        payment_id,
        0
    )


    # =========================
    # Safety Rule 1
    # Maximum 2 Retries
    # =========================

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

                "success":
                    False,

                "status":
                    "blocked",

                "message":
                    "Recovery blocked: maximum of 2 retries reached.",

                "retry_count":
                    retry_count

            }), 403


    # =========================
    # Safety Rule 2
    # Medium Risk Requires Approval
    # =========================

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

                "success":
                    False,

                "status":
                    "approval_required",

                "message":
                    "Merchant approval is required for this recovery action.",

                "action":
                    action

            }), 403


    # =========================
    # Increase Retry Count
    # =========================

    if action in [

        "retry_payment",

        "retry_after_delay"

    ]:

        retry_counts[payment_id] = (

            retry_count + 1

        )


    # =========================
    # Find Payment Amount
    # =========================

    payment_amount = 0


    for payment in get_payments():

        if payment["payment_id"] == payment_id:

            payment_amount = float(
                payment["amount"]
            )

            break


    # =========================
    # Simulate Recovery
    # =========================

    probability = (
        recovery_probability[
            failure_reason
        ]
    )


    recovered = (

        random.random()
        <
        probability

    )


    # =========================
    # Store Recovery Result
    # =========================

    recovery_results[payment_id] = {

        "amount":
            payment_amount,

        "recovered":
            recovered,

        "failure_reason":
            failure_reason,

        "action":
            action
    }


    # =========================
    # Audit Log
    # =========================

    if recovered:

        add_audit_log(

            payment_id,

            action,

            "recovered",

            "Payment successfully recovered in simulation mode."
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

            "Recovery action executed but payment was not recovered."
        )


        status = "not_recovered"


        message = (

            "Recovery action executed, "
            "but payment was not recovered "
            "in simulation mode."

        )


    # =========================
    # Return Result
    # =========================

    return jsonify({

        "success":
            True,

        "status":
            status,

        "payment_id":
            payment_id,

        "action":
            action,

        "amount":
            payment_amount,

        "recovered":
            recovered,

        "retry_count":
            retry_counts.get(
                payment_id,
                0
            ),

        "message":
            message
    })


# =========================
# Batch Recovery
# =========================

@app.route(
    "/api/recover-batch",
    methods=["POST"]
)
def recover_batch():

    payments = get_payments()

    eligible_payments = []


    # =========================
    # Find Eligible Payments
    # =========================

    for payment in payments:

        if payment["status"] != "failed":

            continue


        payment_id = payment[
            "payment_id"
        ]

        failure_reason = payment[
            "failure_reason"
        ]


        if failure_reason not in recovery_actions:

            continue


        action = recovery_actions[
            failure_reason
        ]["action"]


        if action in [

            "retry_payment",

            "retry_after_delay"

        ]:

            current_retry_count = (
                retry_counts.get(
                    payment_id,
                    0
                )
            )


            if current_retry_count >= MAX_RETRIES:

                continue


        eligible_payments.append(
            payment
        )


    # =========================
    # Batch Statistics
    # =========================

    attempted = 0

    recovered = 0

    not_recovered = 0

    attempted_amount = 0

    recovered_amount = 0

    not_recovered_amount = 0


    # =========================
    # Execute Batch
    # =========================

    for payment in eligible_payments:

        payment_id = payment[
            "payment_id"
        ]

        failure_reason = payment[
            "failure_reason"
        ]

        amount = float(
            payment["amount"]
        )


        recommendation = (
            recovery_actions[
                failure_reason
            ]
        )


        action = recommendation[
            "action"
        ]

        risk = recommendation[
            "risk"
        ]


        # =========================
        # Safety Check
        # =========================

        if risk == "medium":

            add_audit_log(

                payment_id,

                action,

                "approval_required",

                "Batch recovery skipped: merchant approval required."
            )

            continue


        # =========================
        # Retry Safety
        # =========================

        current_retry_count = (
            retry_counts.get(
                payment_id,
                0
            )
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

                    "Batch recovery blocked: maximum retry limit reached."
                )

                continue


            retry_counts[payment_id] = (

                current_retry_count + 1

            )


        # =========================
        # Simulate Recovery
        # =========================

        probability = (
            recovery_probability[
                failure_reason
            ]
        )


        recovered_result = (

            random.random()
            <
            probability

        )


        attempted += 1

        attempted_amount += amount


        # =========================
        # Store Result
        # =========================

        recovery_results[payment_id] = {

            "amount":
                amount,

            "recovered":
                recovered_result,

            "failure_reason":
                failure_reason,

            "action":
                action
        }


        # =========================
        # Record Result
        # =========================

        if recovered_result:

            recovered += 1

            recovered_amount += amount


            add_audit_log(

                payment_id,

                action,

                "recovered",

                "Payment recovered successfully in batch simulation mode."
            )


        else:

            not_recovered += 1

            not_recovered_amount += amount


            add_audit_log(

                payment_id,

                action,

                "not_recovered",

                "Batch recovery attempted but payment was not recovered."
            )


    # =========================
    # Calculate Recovery Rate
    # =========================

    if attempted > 0:

        recovery_rate = (

            recovered
            /
            attempted

        ) * 100

    else:

        recovery_rate = 0


    # =========================
    # Return Batch Result
    # =========================

    return jsonify({

        "success":
            True,

        "eligible_payments":
            len(eligible_payments),

        "attempted_transactions":
            attempted,

        "recovered_transactions":
            recovered,

        "not_recovered_transactions":
            not_recovered,

        "attempted_amount":
            round(
                attempted_amount,
                2
            ),

        "recovered_amount":
            round(
                recovered_amount,
                2
            ),

        "not_recovered_amount":
            round(
                not_recovered_amount,
                2
            ),

        "recovery_rate":
            round(
                recovery_rate,
                2
            ),

        "message":
            "Batch recovery completed in simulation mode."
    })


# =========================
# Recovery Metrics
# =========================

@app.route(
    "/api/recovery-metrics"
)
def recovery_metrics():

    total_recovery_attempts = len(
        recovery_results
    )

    recovered_transactions = 0

    not_recovered_transactions = 0

    recovered_amount = 0

    not_recovered_amount = 0


    for result in recovery_results.values():

        amount = result["amount"]


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

        "total_recovery_attempts":
            total_recovery_attempts,

        "recovered_transactions":
            recovered_transactions,

        "not_recovered_transactions":
            not_recovered_transactions,

        "recovered_amount":
            round(
                recovered_amount,
                2
            ),

        "not_recovered_amount":
            round(
                not_recovered_amount,
                2
            ),

        "total_attempted_amount":
            round(
                total_attempted_amount,
                2
            ),

        "recovery_rate":
            round(
                recovery_rate,
                2
            )
    })


# =========================
# Audit Trail
# =========================

@app.route("/api/audit")
def audit():

    return jsonify({

        "total_actions":
            len(audit_log),

        "logs":
            audit_log
    })


# =========================
# Run Application
# =========================

if __name__ == "__main__":

    app.run(
        debug=True
    )

