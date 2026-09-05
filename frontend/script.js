// ============================================================
// API URLs
// ============================================================

const API_URL = "http://127.0.0.1:5000/api/summary";
const RECOMMENDATIONS_URL = "http://127.0.0.1:5000/api/recommendations";
const FAILURES_URL = "http://127.0.0.1:5000/api/failures";
const PAYMENTS_URL = "http://127.0.0.1:5000/api/payments";
const RECOVER_URL = "http://127.0.0.1:5000/api/recover";
const AUDIT_URL = "http://127.0.0.1:5000/api/audit";
const RECOVERY_METRICS_URL = "http://127.0.0.1:5000/api/recovery-metrics";
const BATCH_RECOVERY_URL = "http://127.0.0.1:5000/api/recover-batch";
const AI_ANALYSIS_URL = "http://127.0.0.1:5000/api/ai-analysis";

// ============================================================
// Dataset URLs
// ============================================================

const UPLOAD_URL = "http://127.0.0.1:5000/api/upload";
const RESET_DEMO_URL = "http://127.0.0.1:5000/api/reset-demo";
const DATASET_URL = "http://127.0.0.1:5000/api/dataset";

// ============================================================
// Razorpay Test Mode URLs
// ============================================================

const RAZORPAY_CONFIG_URL =
    "http://127.0.0.1:5000/api/razorpay/config";

const RAZORPAY_CREATE_ORDER_URL =
    "http://127.0.0.1:5000/api/razorpay/create-order";

const RAZORPAY_VERIFY_URL =
    "http://127.0.0.1:5000/api/razorpay/verify-payment";

const RAZORPAY_FAILED_URL =
    "http://127.0.0.1:5000/api/razorpay/payment-failed";

const RAZORPAY_TRANSACTIONS_URL =
    "http://127.0.0.1:5000/api/razorpay/transactions";

// ============================================================
// Razorpay Current Transaction State
// ============================================================

let currentRazorpayOrderId = "";
let currentRazorpayAmount = 2999;

// ============================================================
// Helper Functions
// ============================================================

function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.textContent = value;
    }
}

function formatCurrency(value) {
    return "₹" + Number(value || 0).toLocaleString("en-IN");
}

function formatReason(value) {
    return String(value || "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, char => char.toUpperCase());
}

// ============================================================
// Clean Gemini AI Text
// ============================================================

function cleanAIText(text) {
    if (!text) {
        return "Not available";
    }

    return String(text)
        // Remove markdown headings
        .replace(/^#{1,6}\s*/gm, "")

        // Remove bold / italic markdown
        .replace(/\*\*(.*?)\*\*/g, "$1")
        .replace(/\*(.*?)\*/g, "$1")

        // Remove escaped asterisks
        .replace(/\\\*/g, "")

        // Remove backticks
        .replace(/`/g, "")

        // Remove markdown horizontal lines
        .replace(/^[-_]{3,}$/gm, "")

        // Remove excessive spaces
        .replace(/[ \t]+/g, " ")

        // Convert multiple new lines to one space
        .replace(/\n+/g, " ")

        .trim();
}

// ============================================================
// Razorpay Checkout Script
// ============================================================

function loadRazorpayCheckout() {
    return new Promise((resolve, reject) => {

        if (window.Razorpay) {
            resolve();
            return;
        }

        const existingScript = document.querySelector(
            'script[src="https://checkout.razorpay.com/v1/checkout.js"]'
        );

        if (existingScript) {
            existingScript.onload = () => resolve();

            existingScript.onerror = () => {
                reject(
                    new Error(
                        "Could not load Razorpay Checkout."
                    )
                );
            };

            return;
        }

        const script = document.createElement("script");

        script.src =
            "https://checkout.razorpay.com/v1/checkout.js";

        script.onload = () => resolve();

        script.onerror = () => {
            reject(
                new Error(
                    "Could not load Razorpay Checkout."
                )
            );
        };

        document.head.appendChild(script);
    });
}

// ============================================================
// Test Razorpay Payment
// ============================================================

async function startRazorpayTestPayment() {

    const button = document.getElementById(
        "razorpay-test-button"
    );

    if (button) {
        button.disabled = true;
        button.textContent = "Opening Test Checkout...";
    }

    try {

        await loadRazorpayCheckout();

        // ----------------------------------------------------
        // Get Razorpay configuration
        // ----------------------------------------------------

        const configResponse = await fetch(
            RAZORPAY_CONFIG_URL,
            {
                cache: "no-store"
            }
        );

        if (!configResponse.ok) {
            throw new Error(
                "Could not connect to Razorpay configuration."
            );
        }

        const config = await configResponse.json();

        if (!config.success) {
            throw new Error(
                config.message ||
                "Razorpay configuration unavailable."
            );
        }

        // ----------------------------------------------------
        // Create Test Order
        // ----------------------------------------------------

        const orderResponse = await fetch(
            RAZORPAY_CREATE_ORDER_URL,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    amount: 2999
                })
            }
        );

        if (!orderResponse.ok) {
            throw new Error(
                "Could not create Razorpay test order."
            );
        }

        const orderData = await orderResponse.json();

        if (!orderData.success) {
            throw new Error(
                orderData.message ||
                "Could not create Razorpay test order."
            );
        }

        // ----------------------------------------------------
        // Store current order
        // ----------------------------------------------------

        currentRazorpayOrderId =
            orderData.order_id;

        currentRazorpayAmount = 2999;

        // ----------------------------------------------------
        // Razorpay Checkout Options
        // ----------------------------------------------------

        const options = {

            key: orderData.key_id,

            amount: orderData.amount,

            currency: orderData.currency || "INR",

            name: "Recovery Copilot",

            description: "Razorpay Test Payment",

            order_id: orderData.order_id,

            handler: async function (response) {

                await handleRazorpaySuccess(response);
            },

            modal: {

                ondismiss: function () {

                    resetRazorpayButton();

                    console.log(
                        "Razorpay checkout closed."
                    );
                }
            },

            theme: {
                color: "#38bdf8"
            }
        };

        // ----------------------------------------------------
        // Create Razorpay instance
        // ----------------------------------------------------

        const razorpay = new Razorpay(options);

        // ----------------------------------------------------
        // Handle Failed Payment
        // ----------------------------------------------------

        razorpay.on(
            "payment.failed",
            async function (response) {

                await handleRazorpayFailure(response);
            }
        );

        // ----------------------------------------------------
        // Open Checkout
        // ----------------------------------------------------

        razorpay.open();

    }
    catch (error) {

        console.error(
            "Razorpay Test Payment Error:",
            error
        );

        alert(
            "Could not start Razorpay Test Payment.\n\n" +
            error.message
        );

        resetRazorpayButton();
    }
}

// ============================================================
// Razorpay Successful Payment
// ============================================================

async function handleRazorpaySuccess(response) {

    try {

        const verifyResponse = await fetch(
            RAZORPAY_VERIFY_URL,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({

                    razorpay_order_id:
                        response.razorpay_order_id,

                    razorpay_payment_id:
                        response.razorpay_payment_id,

                    razorpay_signature:
                        response.razorpay_signature
                })
            }
        );

        if (!verifyResponse.ok) {
            throw new Error(
                "Payment verification request failed."
            );
        }

        const data = await verifyResponse.json();

        if (data.success) {

            alert(
                "Razorpay Test Payment Successful!\n\n" +
                "Payment ID: " +
                response.razorpay_payment_id +
                "\n\n" +
                "This was a TEST MODE payment."
            );

        }
        else {

            alert(
                "Payment received but verification failed."
            );
        }

        await loadRecoveryMetrics();
        await loadAuditTrail();
        await loadRazorpayTransactions();

    }
    catch (error) {

        console.error(
            "Payment verification error:",
            error
        );

        alert(
            "Payment verification failed.\n\n" +
            error.message
        );

    }
    finally {

        resetRazorpayButton();

        currentRazorpayOrderId = "";

        currentRazorpayAmount = 2999;
    }
}

// ============================================================
// Razorpay Failed Payment
// ============================================================

async function handleRazorpayFailure(response) {

    console.log(
        "Razorpay test payment failed:",
        response
    );

    const paymentError =
        response.error || {};

    const paymentId =
        paymentError.metadata?.payment_id ||
        paymentError.metadata?.paymentId ||
        "";

    const orderId =
        paymentError.metadata?.order_id ||
        paymentError.metadata?.orderId ||
        currentRazorpayOrderId ||
        "";

    // Demo classification
    const reason = "bank_timeout";

    try {

        const failureResponse = await fetch(
            RAZORPAY_FAILED_URL,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    payment_id: paymentId,

                    order_id: orderId,

                    amount: currentRazorpayAmount,

                    failure_reason: reason,

                    status: "failed",

                    source: "razorpay_test_mode"
                })
            }
        );

        if (!failureResponse.ok) {

            let errorData = {};

            try {
                errorData =
                    await failureResponse.json();
            }
            catch {
                errorData = {};
            }

            throw new Error(
                errorData.message ||
                "Recovery Copilot could not process the failed payment."
            );
        }

        const failureData =
            await failureResponse.json();

        console.log(
            "Razorpay recovery response:",
            failureData
        );

        await loadRecoveryMetrics();

        await loadAuditTrail();

        await loadRazorpayTransactions();

        const statusText =
            failureData.status ||
            "not_recovered";

        const actionText =
            failureData.action ||
            "recovery_action";

        const retryCount =
            failureData.retry_count ?? 0;

        alert(
            "Razorpay Test Payment Failed.\n\n" +

            "Recovery Copilot detected the failed payment.\n\n" +

            "Recovery Action: " +
            formatReason(actionText) +

            "\n\n" +

            "Status: " +
            formatReason(statusText) +

            "\n\n" +

            "Retry Count: " +
            retryCount +

            "\n\n" +

            "Reason: " +
            formatReason(reason) +

            "\n\n" +

            "TEST MODE — No real money was processed."
        );

    }
    catch (error) {

        console.error(
            "Failed payment logging error:",
            error
        );

        try {

            await loadRecoveryMetrics();

            await loadAuditTrail();

        }
        catch (refreshError) {

            console.error(
                "Dashboard refresh error:",
                refreshError
            );
        }

        alert(
            "Payment failed, but the Recovery Copilot " +
            "could not record the event.\n\n" +
            error.message
        );

    }
    finally {

        resetRazorpayButton();

        currentRazorpayOrderId = "";

        currentRazorpayAmount = 2999;
    }
}

// ============================================================
// Load Razorpay Transactions
// ============================================================

async function loadRazorpayTransactions() {

    try {

        const response = await fetch(
            RAZORPAY_TRANSACTIONS_URL,
            {
                cache: "no-store"
            }
        );

        if (!response.ok) {
            throw new Error(
                "Could not load Razorpay transactions."
            );
        }

        const data = await response.json();

        console.log(
            "Razorpay transactions:",
            data
        );

        return data;

    }
    catch (error) {

        console.log(
            "Razorpay transactions error:",
            error
        );

        return null;
    }
}

// ============================================================
// Reset Razorpay Button
// ============================================================

function resetRazorpayButton() {

    const button =
        document.getElementById(
            "razorpay-test-button"
        );

    if (button) {

        button.disabled = false;

        button.textContent =
            "Test Razorpay Payment";
    }
}

// ============================================================
// Connect Razorpay Button
// ============================================================

function setupRazorpayButton() {

    const button =
        document.getElementById(
            "razorpay-test-button"
        );

    if (!button) {
        return;
    }

    button.addEventListener(
        "click",
        startRazorpayTestPayment
    );
}

// ============================================================
// Load Dataset Information
// ============================================================

async function loadDatasetInfo() {

    try {

        const response = await fetch(
            DATASET_URL,
            {
                cache: "no-store"
            }
        );

        if (!response.ok) {
            throw new Error(
                "Could not load dataset information."
            );
        }

        const data =
            await response.json();

        setText(
            "dataset-type",
            data.dataset_type ||
            "Demo Dataset"
        );

        setText(
            "dataset-total",
            data.total_payments || 0
        );

    }
    catch (error) {

        console.log(
            "Error loading dataset information:",
            error
        );
    }
}

// ============================================================
// Upload Payment CSV
// ============================================================

function uploadPaymentCSV() {

    const fileInput =
        document.getElementById(
            "payment-csv"
        );

    const uploadButton =
        document.getElementById(
            "upload-button"
        );

    const message =
        document.getElementById(
            "upload-message"
        );

    if (
        !fileInput ||
        !fileInput.files.length
    ) {

        if (message) {
            message.textContent =
                "Please choose a CSV file first.";
        }

        return;
    }

    const file =
        fileInput.files[0];

    if (
        !file.name
            .toLowerCase()
            .endsWith(".csv")
    ) {

        if (message) {
            message.textContent =
                "Please upload a CSV file.";
        }

        return;
    }

    const formData =
        new FormData();

    formData.append(
        "file",
        file
    );

    if (uploadButton) {

        uploadButton.disabled = true;

        uploadButton.textContent =
            "Uploading...";
    }

    if (message) {

        message.textContent =
            "Uploading and analyzing your dataset...";
    }

    fetch(
        UPLOAD_URL,
        {
            method: "POST",
            body: formData
        }
    )
        .then(async response => {

            const data =
                await response.json();

            if (!response.ok) {

                throw new Error(
                    data.message ||
                    "Dataset upload failed."
                );
            }

            return data;
        })
        .then(data => {

            if (!data.success) {

                if (message) {

                    message.textContent =
                        data.message ||
                        "Dataset upload failed.";
                }

                return;
            }

            if (message) {

                message.textContent =
                    "Dataset uploaded successfully!";
            }

            fileInput.value = "";

            loadDatasetInfo();

            refreshDashboard();

            loadAIAnalysis();
        })
        .catch(error => {

            console.log(
                "Dataset upload error:",
                error
            );

            if (message) {

                message.textContent =
                    "Could not connect to the server.";
            }

        })
        .finally(() => {

            if (uploadButton) {

                uploadButton.disabled = false;

                uploadButton.textContent =
                    "Upload Dataset";
            }
        });
}

// ============================================================
// Reset to Demo Dataset
// ============================================================

function resetDemoDataset() {

    const button =
        document.getElementById(
            "reset-demo-button"
        );

    const message =
        document.getElementById(
            "upload-message"
        );

    if (button) {

        button.disabled = true;

        button.textContent =
            "Loading Demo...";
    }

    if (message) {

        message.textContent =
            "Switching to demo dataset...";
    }

    fetch(
        RESET_DEMO_URL,
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body: JSON.stringify({})
        }
    )
        .then(async response => {

            const data =
                await response.json();

            if (!response.ok) {

                throw new Error(
                    data.message ||
                    "Could not load demo dataset."
                );
            }

            return data;
        })
        .then(data => {

            if (!data.success) {

                if (message) {

                    message.textContent =
                        data.message ||
                        "Could not load demo dataset.";
                }

                return;
            }

            if (message) {

                message.textContent =
                    "Demo dataset loaded.";
            }

            loadDatasetInfo();

            refreshDashboard();

            loadAIAnalysis();
        })
        .catch(error => {

            console.log(
                "Demo dataset error:",
                error
            );

            if (message) {

                message.textContent =
                    "Could not connect to the server.";
            }

        })
        .finally(() => {

            if (button) {

                button.disabled = false;

                button.textContent =
                    "Use Demo Dataset";
            }
        });
}

// ============================================================
// Refresh Entire Dashboard
// ============================================================

function refreshDashboard() {

    loadPaymentSummary();

    loadFailedPayments();

    loadRecommendations();

    loadFailureAnalysis();

    loadRecoveryMetrics();

    loadAuditTrail();

    loadOpportunityChart();

    loadDatasetInfo();
}

// ============================================================
// Load Payment Summary
// ============================================================

async function loadPaymentSummary() {

    try {

        const response =
            await fetch(
                API_URL,
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {

            throw new Error(
                "Payment summary request failed."
            );
        }

        const data =
            await response.json();

        setText(
            "total-payments",
            data.total_payments ?? 0
        );

        setText(
            "successful-payments",
            data.successful_payments ?? 0
        );

        setText(
            "failed-payments",
            data.failed_payments ?? 0
        );

        setText(
            "failure-rate",
            (data.failure_rate ?? 0) + "%"
        );

        setText(
            "revenue-at-risk",
            formatCurrency(
                data.revenue_at_risk
            )
        );

        setText(
            "potential-recovery",
            formatCurrency(
                data.potential_recovery
            )
        );

    }
    catch (error) {

        console.log(
            "Error loading payment summary:",
            error
        );
    }
}

// ============================================================
// Load Failed Payments
// ============================================================

async function loadFailedPayments() {

    try {

        const response =
            await fetch(
                PAYMENTS_URL,
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {

            throw new Error(
                "Could not load failed payments."
            );
        }

        const data =
            await response.json();

        const container =
            document.getElementById(
                "failures-container"
            );

        if (!container) {
            return;
        }

        container.innerHTML = "";

        const samplePayments =
            Array.isArray(data)
                ? data.slice(0, 10)
                : [];

        const info =
            document.createElement("p");

        info.className =
            "failure-list-info";

        info.textContent =
            `Showing ${samplePayments.length} of ${data.length} failed payments`;

        container.appendChild(info);

        samplePayments.forEach(payment => {

            const card =
                document.createElement("div");

            card.className =
                "failure-card";

            const paymentId =
                String(
                    payment.payment_id || ""
                );

            const failureReason =
                String(
                    payment.failure_reason || ""
                );

            const customerType =
                String(
                    payment.customer_type || ""
                );

            card.innerHTML = `
                <h3>${paymentId}</h3>

                <p>
                    <strong>Amount:</strong>
                    ${formatCurrency(payment.amount)}
                </p>

                <p>
                    <strong>Reason:</strong>
                    ${formatReason(failureReason)}
                </p>

                <p>
                    <strong>Customer:</strong>
                    ${formatReason(customerType)}
                </p>

                <button
                    class="recover-button"
                    onclick="executeRecovery('${paymentId}', '${failureReason}')"
                >
                    Execute Recovery
                </button>
            `;

            container.appendChild(card);
        });

    }
    catch (error) {

        console.log(
            "Error loading failed payments:",
            error
        );

        const container =
            document.getElementById(
                "failures-container"
            );

        if (container) {

            container.innerHTML = `
                <p>
                    Unable to load failed payments.
                </p>
            `;
        }
    }
}

// ============================================================
// Load Recovery Recommendations
// ============================================================

async function loadRecommendations() {

    try {

        const response =
            await fetch(
                RECOMMENDATIONS_URL,
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {

            throw new Error(
                "Could not load recommendations."
            );
        }

        const data =
            await response.json();

        const container =
            document.getElementById(
                "recommendations-container"
            );

        if (!container) {
            return;
        }

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
                    ${formatReason(reason)}
                </h3>

                <p>
                    <strong>Action:</strong>
                    ${formatReason(recommendation.action)}
                </p>

                <p>
                    <strong>Risk:</strong>
                    ${formatReason(recommendation.risk)}
                </p>

                <p>
                    <strong>Why:</strong>
                    ${cleanAIText(recommendation.reason)}
                </p>
            `;

            container.appendChild(card);
        }

    }
    catch (error) {

        console.log(
            "Error loading recommendations:",
            error
        );
    }
}

// ============================================================
// Load Recovery Opportunity
// ============================================================

async function loadOpportunityChart() {

    try {

        const response =
            await fetch(
                FAILURES_URL,
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {

            throw new Error(
                "Could not load failure data."
            );
        }

        const data =
            await response.json();

        const payments =
            Array.isArray(data)
                ? data
                : (data.failures || []);

        const totals = {};

        payments.forEach(payment => {

            const reason =
                payment.failure_reason ||
                "unknown";

            const amount =
                Number(
                    payment.amount || 0
                );

            totals[reason] =
                (totals[reason] || 0) +
                amount;
        });

        const entries =
            Object.entries(totals)
                .sort(
                    (a, b) =>
                        b[1] - a[1]
                );

        const maxAmount =
            entries.length
                ? entries[0][1]
                : 1;

        const container =
            document.getElementById(
                "opportunity-chart"
            );

        if (!container) {
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
            entries
                .map(
                    ([reason, amount]) => {

                        const width =
                            (amount / maxAmount) *
                            100;

                        const label =
                            formatReason(reason);

                        return `
                            <div class="chart-row">

                                <div class="chart-label">

                                    <span>
                                        ${label}
                                    </span>

                                    <strong>
                                        ${formatCurrency(amount)}
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
                    }
                )
                .join("");

    }
    catch (error) {

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
    }
}

// ============================================================
// Load AI Recovery Analysis
// ============================================================

async function loadAIAnalysis() {

    const container =
        document.getElementById(
            "ai-analysis-container"
        );

    if (!container) {
        return;
    }

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

    try {

        const response =
            await fetch(
                AI_ANALYSIS_URL,
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {

            throw new Error(
                "AI analysis request failed."
            );
        }

        const data =
            await response.json();

        if (!data.success) {

            container.innerHTML = `
                <div class="ai-error">

                    <h3>
                        AI Analysis Failed
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
            String(data.analysis || "");

        // ----------------------------------------------------
        // Clean entire AI response first
        // ----------------------------------------------------

        const cleanedAnalysis =
            analysis
                .replace(/\r/g, "")
                .replace(/\\\*/g, "")
                .replace(/\*\*/g, "")
                .replace(/`/g, "")
                .replace(/^#{1,6}\s*/gm, "")
                .replace(/^[-_]{3,}$/gm, "")
                .trim();

        // ----------------------------------------------------
        // Extract sections
        // ----------------------------------------------------

        function extractSection(
            title,
            nextTitle
        ) {

            const normalized =
                cleanedAnalysis.toUpperCase();

            const start =
                normalized.indexOf(
                    title.toUpperCase()
                );

            if (start === -1) {
                return "Not available";
            }

            const contentStart =
                start + title.length;

            let end =
                cleanedAnalysis.length;

            if (nextTitle) {

                const nextIndex =
                    normalized.indexOf(
                        nextTitle.toUpperCase(),
                        contentStart
                    );

                if (nextIndex !== -1) {
                    end = nextIndex;
                }
            }

            return cleanAIText(
                cleanedAnalysis.substring(
                    contentStart,
                    end
                )
            );
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

        // ----------------------------------------------------
        // Render AI report
        // ----------------------------------------------------

        container.innerHTML = `

            <div class="ai-result">

                <div class="ai-result-header">

                    <div>

                        <span class="ai-badge">
                            GEMINI AI
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

    }
    catch (error) {

        console.log(
            "AI analysis error:",
            error
        );

        container.innerHTML = `

            <div class="ai-error">

                <h3>
                    Unable to Connect to AI
                </h3>

                <p>
                    Could not connect to the AI analysis server.
                </p>

            </div>
        `;
    }
}

// ============================================================
// Execute Single Recovery
// ============================================================

function executeRecovery(
    paymentId,
    failureReason
) {

    let resultContainer =
        document.getElementById(
            "recovery-result-container"
        );

    if (!resultContainer) {

        resultContainer =
            document.getElementById(
                "batch-recovery-result"
            );
    }

    // --------------------------------------------------------
    // If no result container exists, create one
    // --------------------------------------------------------

    if (!resultContainer) {

        resultContainer =
            document.createElement("div");

        resultContainer.id =
            "recovery-result-container";

        resultContainer.className =
            "recovery-result";

        const failuresContainer =
            document.getElementById(
                "failures-container"
            );

        if (failuresContainer) {

            failuresContainer.prepend(
                resultContainer
            );
        }
        else {

            document.body.prepend(
                resultContainer
            );
        }
    }

    resultContainer.innerHTML = `

        <p>
            Executing recovery action for
            <strong>${paymentId}</strong>...
        </p>

    `;

    fetch(
        RECOVER_URL,
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body: JSON.stringify({

                payment_id:
                    paymentId,

                failure_reason:
                    failureReason,

                retry_count:
                    0,

                merchant_approved:
                    true
            })
        }
    )
        .then(async response => {

            const data =
                await response.json();

            if (!response.ok) {

                throw new Error(
                    data.message ||
                    "Recovery request failed."
                );
            }

            return data;
        })
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
                        ${formatReason(data.action)}
                    </p>

                    <p>
                        <strong>Status:</strong>
                        ${formatReason(data.status)}
                    </p>

                    <p>
                        <strong>Amount:</strong>
                        ${formatCurrency(data.amount)}
                    </p>

                    <p>
                        ${data.message || ""}
                    </p>

                `;
            }
            else {

                resultContainer.innerHTML = `

                    <h3>
                        Recovery Action Blocked
                    </h3>

                    <p>
                        <strong>Status:</strong>
                        ${formatReason(
                            data.status || "blocked"
                        )}
                    </p>

                    <p>
                        ${data.message ||
                        "Recovery action was blocked."}
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
                    ${error.message ||
                    "Could not connect to the recovery server."}
                </p>

            `;
        });
}

// Make available to inline HTML onclick
window.executeRecovery =
    executeRecovery;

// ============================================================
// Run Batch Recovery
// ============================================================

function runBatchRecovery() {

    const button =
        document.getElementById(
            "batch-recovery-button"
        );

    const resultContainer =
        document.getElementById(
            "batch-recovery-result"
        );

    if (
        !button ||
        !resultContainer
    ) {

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

    fetch(
        BATCH_RECOVERY_URL,
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body: JSON.stringify({})
        }
    )
        .then(async response => {

            const data =
                await response.json();

            if (!response.ok) {

                throw new Error(
                    data.message ||
                    "Batch recovery request failed."
                );
            }

            return data;
        })
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
                        ${formatCurrency(data.attempted_amount)}
                    </p>

                    <p>
                        <strong>Recovered Amount:</strong>
                        ${formatCurrency(data.recovered_amount)}
                    </p>

                    <p>
                        <strong>Not Recovered Amount:</strong>
                        ${formatCurrency(data.not_recovered_amount)}
                    </p>

                    <p>
                        <strong>Recovery Rate:</strong>
                        ${data.recovery_rate}%
                    </p>

                    <p>
                        ${data.message || ""}
                    </p>

                    <p>
                        <strong>Simulation Mode:</strong>
                        No real payments were processed.
                    </p>

                `;
            }
            else {

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
                    ${error.message ||
                    "Could not connect to the recovery server."}
                </p>

            `;

        })
        .finally(() => {

            button.disabled = false;

            button.textContent =
                "Run Recovery Batch";
        });
}

// ============================================================
// Load Recovery Metrics
// ============================================================

async function loadRecoveryMetrics() {

    try {

        const response =
            await fetch(
                RECOVERY_METRICS_URL +
                "?t=" +
                Date.now(),
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {

            throw new Error(
                "Recovery metrics request failed."
            );
        }

        const data =
            await response.json();

        console.log(
            "Recovery metrics:",
            data
        );

        // ----------------------------------------------------
        // Recovery Performance
        // ----------------------------------------------------

        setText(
            "recovery-attempts",
            data.total_recovery_attempts ?? 0
        );

        setText(
            "recovered-transactions",
            data.recovered_transactions ?? 0
        );

        setText(
            "recovered-amount",
            formatCurrency(
                data.recovered_amount
            )
        );

        setText(
            "recovery-rate",
            Number(
                data.recovery_rate ?? 0
            ) + "%"
        );

        // ----------------------------------------------------
        // Recovery Overview
        // ----------------------------------------------------

        setText(
            "overview-attempts",
            data.total_recovery_attempts ?? 0
        );

        setText(
            "overview-recovered-transactions",
            data.recovered_transactions ?? 0
        );

        setText(
            "overview-recovered-amount",
            formatCurrency(
                data.recovered_amount
            )
        );

        setText(
            "overview-recovery-rate",
            Number(
                data.recovery_rate ?? 0
            ) + "%"
        );

    }
    catch (error) {

        console.error(
            "Error loading recovery metrics:",
            error
        );
    }
}

// ============================================================
// Load Audit Trail
// ============================================================

async function loadAuditTrail() {

    try {

        const [
            auditResponse,
            metricsResponse
        ] = await Promise.all([

            fetch(
                AUDIT_URL +
                "?t=" +
                Date.now(),
                {
                    cache: "no-store"
                }
            ),

            fetch(
                RECOVERY_METRICS_URL +
                "?t=" +
                Date.now(),
                {
                    cache: "no-store"
                }
            )
        ]);

        if (
            !auditResponse.ok ||
            !metricsResponse.ok
        ) {

            throw new Error(
                "Could not load audit information."
            );
        }

        const auditData =
            await auditResponse.json();

        const metricsData =
            await metricsResponse.json();

        const container =
            document.getElementById(
                "audit-container"
            );

        if (!container) {
            return;
        }

        const logs =
            Array.isArray(auditData)
                ? auditData
                : (auditData.logs || []);

        // ----------------------------------------------------
        // Recovery metrics
        // ----------------------------------------------------

        const totalAttempts =
            Number(
                metricsData.total_recovery_attempts || 0
            );

        const recovered =
            Number(
                metricsData.recovered_transactions || 0
            );

        const notRecovered =
            Math.max(
                totalAttempts -
                recovered,
                0
            );

        const approvalRequired =
            logs.filter(
                log =>
                    log.status ===
                    "approval_required"
            ).length;

        // ----------------------------------------------------
        // Update audit summary
        // ----------------------------------------------------

        setText(
            "audit-total",
            totalAttempts
        );

        setText(
            "audit-recovered",
            recovered
        );

        setText(
            "audit-not-recovered",
            notRecovered
        );

        setText(
            "audit-approval",
            approvalRequired
        );

        // ----------------------------------------------------
        // Remove AI analysis logs
        // ----------------------------------------------------

        const recoveryLogs =
            logs.filter(log => {

                const action =
                    String(
                        log.action || ""
                    ).toLowerCase();

                return (
                    action !==
                        "ai_revenue_analysis" &&

                    action !==
                        "ai_analysis"
                );
            });

        // ----------------------------------------------------
        // Show latest 10 logs
        // ----------------------------------------------------

        const latestLogs =
            recoveryLogs
                .slice()
                .reverse()
                .slice(0, 10);

        container.innerHTML = "";

        if (
            latestLogs.length === 0
        ) {

            container.innerHTML = `

                <p>
                    No recovery actions recorded yet.
                </p>

            `;

            return;
        }

        latestLogs.forEach(log => {

            const card =
                document.createElement("div");

            card.className =
                "audit-card";

            const action =
                formatReason(
                    log.action ||
                    "Recovery Action"
                );

            const status =
                formatReason(
                    log.status ||
                    "unknown"
                );

            card.innerHTML = `

                <h3>
                    ${action}
                </h3>

                <p>
                    <strong>Payment ID:</strong>
                    ${log.payment_id || "N/A"}
                </p>

                <p>
                    <strong>Status:</strong>
                    ${status}
                </p>

                <p>
                    <strong>Message:</strong>
                    ${cleanAIText(
                        log.message ||
                        "No message available."
                    )}
                </p>

                <p>
                    <strong>Time:</strong>
                    ${log.timestamp || "N/A"}
                </p>

            `;

            container.appendChild(card);
        });

    }
    catch (error) {

        console.error(
            "Error loading audit trail:",
            error
        );

        const container =
            document.getElementById(
                "audit-container"
            );

        if (container) {

            container.innerHTML = `

                <p>
                    Unable to load audit logs.
                </p>

            `;
        }
    }
}

// ============================================================
// Load Failure Analysis
// ============================================================

async function loadFailureAnalysis() {

    try {

        const response =
            await fetch(
                FAILURES_URL,
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {

            throw new Error(
                "Could not load failure analysis."
            );
        }

        const data =
            await response.json();

        console.log(
            "Failure analysis loaded:",
            data
        );

    }
    catch (error) {

        console.log(
            "Error loading failure analysis:",
            error
        );
    }
}

// ============================================================
// Initialize Dashboard
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        setupRazorpayButton();

        refreshDashboard();

        loadAIAnalysis();

        loadRazorpayTransactions();
    }
);