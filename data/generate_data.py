import csv
import random

failure_reasons = [
    "upi_timeout",
    "insufficient_funds",
    "bank_timeout",
    "card_expired"
]

customer_types = [
    "new",
    "returning"
]

with open("data/payments.csv", "w", newline="") as file:

    writer = csv.writer(file)

    writer.writerow([
        "payment_id",
        "amount",
        "status",
        "failure_reason",
        "customer_type"
    ])

    for i in range(1, 501):

        payment_id = f"PAY{i:03d}"
        amount = random.choice([
            500, 1000, 1500, 2000, 2500,
            3000, 4000, 5000, 7500, 10000
        ])

        customer_type = random.choice(customer_types)

        status = random.choices(
            ["success", "failed"],
            weights=[70, 30]
        )[0]

        if status == "failed":
            failure_reason = random.choice(failure_reasons)
        else:
            failure_reason = ""

        writer.writerow([
            payment_id,
            amount,
            status,
            failure_reason,
            customer_type
        ])

print("500 payment records generated successfully!")