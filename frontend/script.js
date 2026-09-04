const API_URL = "http://127.0.0.1:5000/api/summary";
const RECOMMENDATIONS_URL = "http://127.0.0.1:5000/api/recommendations";
const FAILURES_URL = "http://127.0.0.1:5000/api/failures";
const PAYMENTS_URL = "http://127.0.0.1:5000/api/payments";
const RECOVER_URL = "http://127.0.0.1:5000/api/recover";
const AUDIT_URL = "http://127.0.0.1:5000/api/audit";
const RECOVERY_METRICS_URL = "http://127.0.0.1:5000/api/recovery-metrics";
const BATCH_RECOVERY_URL = "http://127.0.0.1:5000/api/recover-batch";
const AI_ANALYSIS_URL = "http://127.0.0.1:5000/api/ai-analysis";


// =========================
// Load Payment Summary
// =========================

function loadPaymentSummary() {

    fetch(API_URL)

        .then(response => response.json())

        .then(data => {

            document.getElementById("total-payments").textContent =
                data.total_payments;

            document.getElementById("successful-payments").textContent =
                data.successful_payments;

            document.getElementById("failed-payments").textContent =
                data.failed_payments;

            document.getElementById("failure-rate").textContent =
                data.failure_rate + "%";

            document.getElementById("revenue-at-risk").textContent =
                "₹" + Number(data.revenue_at_risk).toLocaleString("en-IN");

            document.getElementById("potential-recovery").textContent =
                "₹" + Number(data.potential_recovery).toLocaleString("en-IN");

        })

        .catch(error => {

            console.log(
                "Error loading payment summary:",
                error
            );

        });
}


// =========================
// Load Failed Payments
// =========================

function loadFailedPayments() {

    fetch(PAYMENTS_URL)

        .then(response => response.json())

        .then(data => {

            const container =
                document.getElementById("failures-container");

            container.innerHTML = "";

            data.forEach(payment => {

                const card =
                    document.createElement("div");

                card.className = "failure-card";

                card.innerHTML = `

                    <h3>
                        ${payment.payment_id}
                    </h3>

                    <p>
                        <strong>Amount:</strong>
                        ₹${Number(payment.amount).toLocaleString("en-IN")}
                    </p>

                    <p>
                        <strong>Reason:</strong>
                        ${payment.failure_reason.replaceAll("_", " ")}
                    </p>

                    <p>
                        <strong>Customer:</strong>
                        ${payment.customer_type}
                    </p>

                    <button
                        class="recover-button"
                        onclick="executeRecovery(
                            '${payment.payment_id}',
                            '${payment.failure_reason}'
                        )">

                        Execute Recovery

                    </button>

                `;

                container.appendChild(card);

            });

        })

        .catch(error => {

            console.log(
                "Error loading failed payments:",
                error
            );

            document.getElementById(
                "failures-container"
            ).innerHTML = `

                <p>
                    Unable to load failed payments.
                </p>

            `;

        });
}


// =========================
// Load Recovery Recommendations
// =========================

function loadRecommendations() {

    fetch(RECOMMENDATIONS_URL)

        .then(response => response.json())

        .then(data => {

            const container =
                document.getElementById(
                    "recommendations-container"
                );

            container.innerHTML = "";

            for (const reason in data) {

                const recommendation =
                    data[reason];

                const card =
                    document.createElement("div");

                card.className =
                    "recommendation-card";

                card.innerHTML = `

                    <h3>
                        ${reason.replaceAll("_", " ")}
                    </h3>

                    <p>
                        <strong>Action:</strong>
                        ${recommendation.action}
                    </p>

                    <p>
                        <strong>Risk:</strong>
                        ${recommendation.risk}
                    </p>

                    <p>
                        <strong>Why:</strong>
                        ${recommendation.reason}
                    </p>

                `;

                container.appendChild(card);

            }

        })

        .catch(error => {

            console.log(
                "Error loading recommendations:",
                error
            );

        });
}


// =========================
// Load Recovery Opportunity
// =========================

function loadOpportunityChart() {

    fetch(FAILURES_URL)

        .then(response => response.json())

        .then(data => {

            const payments =
                Array.isArray(data)
                    ? data
                    : (data.failures || []);

            const totals = {};

            payments.forEach(payment => {

                const reason =
                    payment.failure_reason || "unknown";

                const amount =
                    Number(payment.amount || 0);

                totals[reason] =
                    (totals[reason] || 0) + amount;

            });

            const entries =
                Object.entries(totals)
                    .sort((a, b) => b[1] - a[1]);

            const maxAmount =
                entries.length
                    ? entries[0][1]
                    : 1;

            const container =
                document.getElementById(
                    "opportunity-chart"
                );

            if (!container) {

                console.log(
                    "Opportunity chart container not found."
                );

                return;

            }

            if (entries.length === 0) {

                container.innerHTML = `
                    <p>
                        No recovery opportunity data available.
                    </p>
                `;

                return;

            }

            container.innerHTML =

                entries.map(([reason, amount]) => {

                    const width =
                        (amount / maxAmount) * 100;

                    const label =
                        reason.replaceAll("_", " ");

                    return `

                        <div class="chart-row">

                            <div class="chart-label">

                                <span>
                                    ${label}
                                </span>

                                <strong>
                                    ₹${amount.toLocaleString("en-IN")}
                                </strong>

                            </div>

                            <div class="chart-track">

                                <div
                                    class="chart-bar"
                                    style="width:${width}%;">
                                </div>

                            </div>

                        </div>

                    `;

                }).join("");

        })

        .catch(error => {

            console.error(
                "Opportunity chart error:",
                error
            );

            const container =
                document.getElementById(
                    "opportunity-chart"
                );

            if (container) {

                container.innerHTML = `

                    <p>
                        Unable to load recovery opportunity data.
                    </p>

                `;

            }

        });
}


// =========================
// Load AI Recovery Analysis
// =========================

function loadAIAnalysis() {

    const container =
        document.getElementById(
            "ai-analysis-container"
        );

    container.innerHTML = `

        <div class="ai-loading">

            <div class="ai-spinner"></div>

            <h3>
                Gemini AI is analyzing...
            </h3>

            <p>
                Analyzing failure patterns, revenue risk,
                recovery opportunities and safety rules.
            </p>

        </div>

    `;

    fetch(AI_ANALYSIS_URL)

        .then(response => response.json())

        .then(data => {

            if (!data.success) {

                container.innerHTML = `

                    <div class="ai-error">

                        <h3>
                            ⚠️ AI Analysis Failed
                        </h3>

                        <p>
                            ${data.message ||
                            "AI analysis could not be completed."}
                        </p>

                    </div>

                `;

                return;

            }

            const analysis =
                data.analysis || "";


            // =========================
            // Extract Gemini Sections
            // =========================

            function extractSection(title, nextTitle) {

                const start =
                    analysis.indexOf(title);

                if (start === -1) {

                    return "Not available";

                }

                const contentStart =
                    start + title.length;

                let end;

                if (nextTitle) {

                    end =
                        analysis.indexOf(
                            nextTitle,
                            contentStart
                        );

                }

                if (
                    end === -1 ||
                    end === undefined
                ) {

                    end =
                        analysis.length;

                }

                return analysis

                    .substring(
                        contentStart,
                        end
                    )

                    .replace(/\*\*/g, "")

                    .replace(/\n+/g, " ")

                    .trim();

            }


            const topRisk =
                extractSection(
                    "TOP RISK",
                    "RECOVERY OPPORTUNITY"
                );


            const recoveryOpportunity =
                extractSection(
                    "RECOVERY OPPORTUNITY",
                    "RECOMMENDED STRATEGY"
                );


            const recommendedStrategy =
                extractSection(
                    "RECOMMENDED STRATEGY",
                    "SAFETY DECISION"
                );


            const safetyDecision =
                extractSection(
                    "SAFETY DECISION",
                    "EXPLANATION"
                );


            const explanation =
                extractSection(
                    "EXPLANATION",
                    null
                );


            // =========================
            // Display AI Analysis
            // =========================

            container.innerHTML = `

                <div class="ai-result">

                    <div class="ai-result-header">

                        <div>

                            <span class="ai-badge">
                                🤖 GEMINI AI
                            </span>

                            <h3>
                                Recovery Intelligence Report
                            </h3>

                        </div>

                        <span class="ai-live">
                            ● AI Analysis Complete
                        </span>

                    </div>


                    <div class="ai-insight-grid">


                        <div class="ai-insight-card risk-card">

                            <div class="insight-icon">
                                ⚠️
                            </div>

                            <div>

                                <h4>
                                    Top Risk
                                </h4>

                                <p>
                                    ${topRisk}
                                </p>

                            </div>

                        </div>


                        <div class="ai-insight-card recovery-card">

                            <div class="insight-icon">
                                💰
                            </div>

                            <div>

                                <h4>
                                    Recovery Opportunity
                                </h4>

                                <p>
                                    ${recoveryOpportunity}
                                </p>

                            </div>

                        </div>


                        <div class="ai-insight-card strategy-card">

                            <div class="insight-icon">
                                🎯
                            </div>

                            <div>

                                <h4>
                                    Recommended Strategy
                                </h4>

                                <p>
                                    ${recommendedStrategy}
                                </p>

                            </div>

                        </div>


                        <div class="ai-insight-card safety-card">

                            <div class="insight-icon">
                                🛡️
                            </div>

                            <div>

                                <h4>
                                    Safety Decision
                                </h4>

                                <p>
                                    ${safetyDecision}
                                </p>

                            </div>

                        </div>


                    </div>


                    <div class="ai-explanation">

                        <h4>
                            💡 Why Gemini Recommended This
                        </h4>

                        <p>
                            ${explanation}
                        </p>

                    </div>


                    <div class="simulation-notice">

                        <strong>
                            🛡️ Simulation Mode
                        </strong>

                        <span>
                            No real payments are processed.
                            Recovery actions are evaluated
                            using safety rules and simulated outcomes.
                        </span>

                    </div>

                </div>

            `;

        })

        .catch(error => {

            console.log(
                "AI analysis error:",
                error
            );

            container.innerHTML = `

                <div class="ai-error">

                    <h3>
                        ⚠️ Unable to Connect to AI
                    </h3>

                    <p>
                        Could not connect to the AI analysis server.
                    </p>

                </div>

            `;

        });

}


// =========================
// Execute Single Recovery
// =========================

function executeRecovery(
    paymentId,
    failureReason
) {

    const resultContainer =
        document.getElementById(
            "recovery-result-container"
        );

    resultContainer.innerHTML = `

        <p>
            Executing recovery action for ${paymentId}...
        </p>

    `;


    fetch(RECOVER_URL, {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({

            payment_id: paymentId,

            failure_reason: failureReason,

            retry_count: 0,

            merchant_approved: true

        })

    })

        .then(response => response.json())

        .then(data => {

            if (data.success) {

                resultContainer.innerHTML = `

                    <h3>
                        Recovery Action Executed
                    </h3>

                    <p>
                        <strong>Payment ID:</strong>
                        ${data.payment_id}
                    </p>

                    <p>
                        <strong>Action:</strong>
                        ${data.action}
                    </p>

                    <p>
                        <strong>Status:</strong>
                        ${data.status}
                    </p>

                    <p>
                        <strong>Amount:</strong>
                        ₹${Number(data.amount).toLocaleString("en-IN")}
                    </p>

                    <p>
                        ${data.message}
                    </p>

                `;

            } else {

                resultContainer.innerHTML = `

                    <h3>
                        Recovery Action Blocked
                    </h3>

                    <p>
                        <strong>Status:</strong>
                        ${data.status || "blocked"}
                    </p>

                    <p>
                        ${data.message}
                    </p>

                `;

            }


            loadRecoveryMetrics();

            loadAuditTrail();

        })

        .catch(error => {

            console.log(
                "Recovery error:",
                error
            );

            resultContainer.innerHTML = `

                <h3>
                    Recovery Failed
                </h3>

                <p>
                    Could not connect to the recovery server.
                </p>

            `;

        });

}


// =========================
// Run Batch Recovery
// =========================

function runBatchRecovery() {

    const button =
        document.getElementById(
            "batch-recovery-button"
        );

    const resultContainer =
        document.getElementById(
            "batch-recovery-result"
        );


    if (!button || !resultContainer) {

        console.log(
            "Batch recovery HTML elements were not found."
        );

        return;

    }


    button.disabled = true;

    button.textContent =
        "Running Recovery Batch...";


    resultContainer.innerHTML = `

        <p>
            Analyzing eligible failed payments and
            running recovery simulation...
        </p>

    `;


    fetch(BATCH_RECOVERY_URL, {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({})

    })

        .then(response => response.json())

        .then(data => {

            if (data.success) {

                resultContainer.innerHTML = `

                    <h3>
                        Batch Recovery Completed
                    </h3>

                    <p>
                        <strong>Eligible Payments:</strong>
                        ${data.eligible_payments}
                    </p>

                    <p>
                        <strong>Recovery Attempts:</strong>
                        ${data.attempted_transactions}
                    </p>

                    <p>
                        <strong>Recovered Transactions:</strong>
                        ${data.recovered_transactions}
                    </p>

                    <p>
                        <strong>Not Recovered:</strong>
                        ${data.not_recovered_transactions}
                    </p>

                    <p>
                        <strong>Attempted Amount:</strong>
                        ₹${Number(data.attempted_amount).toLocaleString("en-IN")}
                    </p>

                    <p>
                        <strong>Recovered Amount:</strong>
                        ₹${Number(data.recovered_amount).toLocaleString("en-IN")}
                    </p>

                    <p>
                        <strong>Not Recovered Amount:</strong>
                        ₹${Number(data.not_recovered_amount).toLocaleString("en-IN")}
                    </p>

                    <p>
                        <strong>Recovery Rate:</strong>
                        ${data.recovery_rate}%
                    </p>

                    <p>
                        ${data.message}
                    </p>

                `;

            } else {

                resultContainer.innerHTML = `

                    <h3>
                        Batch Recovery Failed
                    </h3>

                    <p>
                        ${data.message ||
                        "Batch recovery could not be completed."}
                    </p>

                `;

            }


            // Refresh dashboard data

            loadPaymentSummary();

            loadRecoveryMetrics();

            loadAuditTrail();

        })

        .catch(error => {

            console.log(
                "Batch recovery error:",
                error
            );

            resultContainer.innerHTML = `

                <h3>
                    Batch Recovery Failed
                </h3>

                <p>
                    Could not connect to the recovery server.
                </p>

            `;

        })

        .finally(() => {

            button.disabled = false;

            button.textContent =
                "Run Recovery Batch";

        });

}


// =========================
// Load Recovery Metrics
// =========================

function loadRecoveryMetrics() {

    fetch(RECOVERY_METRICS_URL)

        .then(response => response.json())

        .then(data => {

            document.getElementById(
                "recovery-attempts"
            ).textContent =
                data.total_recovery_attempts;


            document.getElementById(
                "recovered-transactions"
            ).textContent =
                data.recovered_transactions;


            document.getElementById(
                "recovered-amount"
            ).textContent =
                "₹" +
                Number(
                    data.recovered_amount
                ).toLocaleString("en-IN");


            document.getElementById(
                "recovery-rate"
            ).textContent =
                data.recovery_rate + "%";


            // =========================
            // Recovery Overview
            // =========================

            document.getElementById(
                "overview-attempts"
            ).textContent =
                data.total_recovery_attempts;


            document.getElementById(
                "overview-recovered-transactions"
            ).textContent =
                data.recovered_transactions;


            document.getElementById(
                "overview-recovered-amount"
            ).textContent =
                "₹" +
                Number(
                    data.recovered_amount
                ).toLocaleString("en-IN");


            document.getElementById(
                "overview-recovery-rate"
            ).textContent =
                data.recovery_rate + "%";

        })

        .catch(error => {

            console.log(
                "Error loading recovery metrics:",
                error
            );

        });

}


// =========================
// Load Audit Trail
// =========================

function loadAuditTrail() {

    fetch(AUDIT_URL)

        .then(response => response.json())

        .then(data => {

            const container =
                document.getElementById(
                    "audit-container"
                );

            container.innerHTML = "";


            if (data.logs.length === 0) {

                container.innerHTML = `

                    <p>
                        No recovery actions recorded yet.
                    </p>

                `;

                return;

            }


            data.logs.forEach(log => {

                const card =
                    document.createElement("div");

                card.className =
                    "audit-card";


                card.innerHTML = `

                    <h3>
                        ${log.action}
                    </h3>

                    <p>
                        <strong>Payment ID:</strong>
                        ${log.payment_id}
                    </p>

                    <p>
                        <strong>Status:</strong>
                        ${log.status}
                    </p>

                    <p>
                        <strong>Message:</strong>
                        ${log.message}
                    </p>

                    <p>
                        <strong>Time:</strong>
                        ${log.timestamp}
                    </p>

                `;

                container.appendChild(card);

            });

        })

        .catch(error => {

            console.log(
                "Error loading audit trail:",
                error
            );

            document.getElementById(
                "audit-container"
            ).innerHTML = `

                <p>
                    Unable to load audit logs.
                </p>

            `;

        });

}


// =========================
// Load Failure Analysis
// =========================

function loadFailureAnalysis() {

    fetch(FAILURES_URL)

        .then(response => response.json())

        .then(data => {

            console.log(
                "Failure analysis loaded:",
                data
            );

        })

        .catch(error => {

            console.log(
                "Error loading failure analysis:",
                error
            );

        });

}


// =========================
// Load Dashboard
// =========================

loadPaymentSummary();

loadFailedPayments();

loadRecommendations();

loadFailureAnalysis();

loadRecoveryMetrics();

loadAuditTrail();

loadOpportunityChart();