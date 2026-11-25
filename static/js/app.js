const $ = (id) => document.getElementById(id);

async function api(url, options = {}) {
    const response = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options
    });

    const data = await response.json().catch(() => ({
        success: false,
        message: "Unexpected server response."
    }));

    if (!response.ok) {
        throw new Error(data.message || "Request failed.");
    }

    return data;
}

function showLoginMessage(message) {
    const el = $("loginMessage");
    if (!el) return;
    el.textContent = message;
    el.classList.remove("hidden");
}

function toast(message) {
    const el = $("toast");
    if (!el) return;
    el.textContent = message;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2800);
}

async function handleLogin(event) {
    event.preventDefault();

    const card = $("cardNumber").value.replace(/\s/g, "");
    const pin = $("pin").value.trim();

    try {
        const result = await api("/api/login", {
            method: "POST",
            body: JSON.stringify({
                card_number: card,
                pin: pin
            })
        });

        if (result.success) {
            window.location.href = "/dashboard";
        }
    } catch (error) {
        showLoginMessage(error.message);
    }
}

async function loadAccount() {
    if (!$("userName")) return;

    try {
        const data = await api("/api/me");
        $("userName").textContent = data.name;
        $("balance").textContent = formatMoney(data.balance);
        $("maskedCard").textContent = maskCard(data.card_number);
    } catch (error) {
        window.location.href = "/";
    }
}

function formatMoney(amount) {
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 2
    }).format(amount);
}

function maskCard(card) {
    return "•••• •••• •••• " + card.slice(-4);
}

function openPanel(title, html) {
    $("transactionTitle").textContent = title;
    $("transactionContent").innerHTML = html;
    $("transactionPanel").classList.remove("hidden");
    $("transactionPanel").scrollIntoView({ behavior: "smooth", block: "center" });
}

function closePanel() {
    $("transactionPanel").classList.add("hidden");
    $("transactionContent").innerHTML = "";
}

function errorBox(message) {
    return `<div class="result error"><strong>Transaction failed</strong><p>${message}</p></div>`;
}

function successBox(message, balance) {
    return `
        <div class="result success">
            <strong>✓ Transaction successful</strong>
            <p>${message}</p>
            <h3>${formatMoney(balance)}</h3>
            <small>Updated available balance</small>
        </div>`;
}

async function showBalance() {
    try {
        const data = await api("/api/me");
        openPanel("Balance Inquiry", `
            <div class="result">
                <span class="eyebrow">AVAILABLE BALANCE</span>
                <h3>${formatMoney(data.balance)}</h3>
                <p>Your current balance is available for eligible transactions.</p>
            </div>
        `);
    } catch (error) {
        toast(error.message);
    }
}

function showWithdraw() {
    openPanel("Cash Withdrawal", `
        <div class="form-grid">
            <label>Withdrawal amount</label>
            <input id="withdrawAmount" type="number" min="100" step="100" placeholder="e.g. 2000">
            <button class="btn" onclick="withdraw()">Withdraw Cash</button>
            <small class="muted">Limit: ₹20,000 per transaction. Amount must be a multiple of ₹100.</small>
        </div>
    `);
}

async function withdraw() {
    const amount = Number($("withdrawAmount").value);

    try {
        const data = await api("/api/withdraw", {
            method: "POST",
            body: JSON.stringify({ amount })
        });

        $("transactionContent").innerHTML = successBox(data.message, data.balance);
        $("balance").textContent = formatMoney(data.balance);
    } catch (error) {
        $("transactionContent").insertAdjacentHTML("beforeend", errorBox(error.message));
    }
}

function showDeposit() {
    openPanel("Cash Deposit", `
        <div class="form-grid">
            <label>Deposit amount</label>
            <input id="depositAmount" type="number" min="1" placeholder="e.g. 5000">
            <button class="btn" onclick="deposit()">Deposit Money</button>
            <small class="muted">Maximum deposit: ₹50,000.</small>
        </div>
    `);
}

async function deposit() {
    const amount = Number($("depositAmount").value);

    try {
        const data = await api("/api/deposit", {
            method: "POST",
            body: JSON.stringify({ amount })
        });

        $("transactionContent").innerHTML = successBox(data.message, data.balance);
        $("balance").textContent = formatMoney(data.balance);
    } catch (error) {
        $("transactionContent").insertAdjacentHTML("beforeend", errorBox(error.message));
    }
}

function showTransfer() {
    openPanel("Fund Transfer", `
        <div class="form-grid">
            <label>Receiver account number</label>
            <input id="receiver" inputmode="numeric" maxlength="12" placeholder="10-12 digit account">
            <label>Transfer amount</label>
            <input id="transferAmount" type="number" min="1" placeholder="e.g. 1500">
            <button class="btn" onclick="transferMoney()">Transfer Money</button>
            <small class="muted">Maximum transfer: ₹50,000.</small>
        </div>
    `);
}

async function transferMoney() {
    const receiver = $("receiver").value.trim();
    const amount = Number($("transferAmount").value);

    try {
        const data = await api("/api/transfer", {
            method: "POST",
            body: JSON.stringify({ receiver, amount })
        });

        $("transactionContent").innerHTML = successBox(data.message, data.balance);
        $("balance").textContent = formatMoney(data.balance);
    } catch (error) {
        $("transactionContent").insertAdjacentHTML("beforeend", errorBox(error.message));
    }
}

async function showStatement() {
    try {
        const data = await api("/api/transactions");

        const rows = data.transactions.map(tx => {
            const positive = tx.amount >= 0;
            return `
                <div class="tx-row">
                    <div>
                        <strong>${tx.type}</strong>
                        <div class="muted">${tx.description || ""}</div>
                    </div>
                    <div>${new Date(tx.created_at).toLocaleString()}</div>
                    <strong class="${positive ? "tx-positive" : "tx-negative"}">
                        ${positive ? "+" : "-"}${formatMoney(Math.abs(tx.amount))}
                    </strong>
                </div>
            `;
        }).join("");

        openPanel("Mini Statement", `
            <div class="statement-list">
                ${rows || "<p class='muted'>No transactions found.</p>"}
            </div>
        `);
    } catch (error) {
        toast(error.message);
    }
}

async function showProfile() {
    try {
        const data = await api("/api/me");
        const status = data.status || "ACTIVE";
        const statusClass = status.toLowerCase() === "active" ? "profile-status active" : "profile-status";

        openPanel("My Profile / Account Details", `
            <div class="profile-grid">
                <div class="profile-card">
                    <span class="profile-label">ACCOUNT HOLDER</span>
                    <strong>${data.name}</strong>
                </div>
                <div class="profile-card">
                    <span class="profile-label">CARD NUMBER</span>
                    <strong>${maskCard(data.card_number)}</strong>
                </div>
                <div class="profile-card">
                    <span class="profile-label">CURRENT BALANCE</span>
                    <strong>${formatMoney(data.balance)}</strong>
                </div>
                <div class="profile-card">
                    <span class="profile-label">ACCOUNT STATUS</span>
                    <strong class="${statusClass}">${status}</strong>
                </div>
            </div>
            <div class="profile-security-note">
                <span>🔒</span>
                <div>
                    <strong>Your details are protected</strong>
                    <p>For security, your complete card number and PIN are never displayed here.</p>
                </div>
            </div>
        `);
    } catch (error) {
        toast(error.message);
    }
}

function showPin() {
    openPanel("Change PIN", `
        <div class="form-grid">
            <label>Current PIN</label>
            <input id="oldPin" type="password" maxlength="4" inputmode="numeric" placeholder="••••">
            <label>New PIN</label>
            <input id="newPin" type="password" maxlength="4" inputmode="numeric" placeholder="••••">
            <label>Confirm new PIN</label>
            <input id="confirmPin" type="password" maxlength="4" inputmode="numeric" placeholder="••••">
            <button class="btn" onclick="changePin()">Change PIN</button>
            <small class="muted">PIN must be exactly 4 digits and different from the current PIN.</small>
        </div>
    `);
}

async function changePin() {
    const old_pin = $("oldPin").value.trim();
    const new_pin = $("newPin").value.trim();
    const confirm_pin = $("confirmPin").value.trim();

    try {
        const data = await api("/api/change-pin", {
            method: "POST",
            body: JSON.stringify({ old_pin, new_pin, confirm_pin })
        });

        $("transactionContent").innerHTML = `
            <div class="result success">
                <strong>✓ ${data.message}</strong>
                <p>Your new PIN is now active.</p>
            </div>`;
    } catch (error) {
        $("transactionContent").insertAdjacentHTML("beforeend", errorBox(error.message));
    }
}

async function logout() {
    await api("/api/logout", { method: "POST" });
    window.location.href = "/";
}

document.addEventListener("DOMContentLoaded", () => {
    const loginForm = $("loginForm");
    if (loginForm) loginForm.addEventListener("submit", handleLogin);

    if ($("dashboard")) loadAccount();
    if ($("userName")) loadAccount();

    document.querySelectorAll(".service-card").forEach(card => {
        card.addEventListener("click", () => {
            const action = card.dataset.action;
            if (action === "balance") showBalance();
            if (action === "withdraw") showWithdraw();
            if (action === "deposit") showDeposit();
            if (action === "transfer") showTransfer();
            if (action === "statement") showStatement();
            if (action === "pin") showPin();
            if (action === "profile") showProfile();
        });
    });

    const logoutBtn = $("logoutBtn");
    if (logoutBtn) logoutBtn.addEventListener("click", logout);

    const closeBtn = $("closePanel");
    if (closeBtn) closeBtn.addEventListener("click", closePanel);
});
