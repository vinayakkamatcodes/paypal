const listPanel = document.getElementById("list-panel");
const detailPanel = document.getElementById("detail-panel");
const disputeList = document.getElementById("dispute-list");
const detailContent = document.getElementById("detail-content");
const backBtn = document.getElementById("back-btn");

function formatMoney(amount) {
  return `$${parseFloat(amount.value).toFixed(2)}`;
}

function formatReason(reason) {
  return reason.replaceAll("_", " ").toLowerCase();
}

function daysUntil(dateStr) {
  const diff = new Date(dateStr) - new Date();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

async function loadDisputes() {
  const res = await fetch("/disputes");
  const data = await res.json();
  disputeList.innerHTML = "";

  data.items.forEach((d) => {
    const card = document.createElement("div");
    card.className = "dispute-card";
    card.innerHTML = `
      <div>
        <div class="id">${d.dispute_id}</div>
        <div class="reason">${formatReason(d.reason)}</div>
      </div>
      <div style="text-align:right">
        <div class="amount">${formatMoney(d.dispute_amount)}</div>
        <div class="deadline">Respond in ${daysUntil(d.seller_response_due_date)} days</div>
      </div>
    `;
    card.addEventListener("click", () => showDetail(d.dispute_id));
    disputeList.appendChild(card);
  });
}

async function showDetail(disputeId) {
  listPanel.classList.add("hidden");
  detailPanel.classList.remove("hidden");

  const res = await fetch(`/disputes/${disputeId}`);
  const d = await res.json();

  detailContent.innerHTML = `
    <div class="detail-row">
      <div class="detail-label">Dispute ID</div>
      <div class="detail-value">${d.dispute_id}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Reason</div>
      <div class="detail-value">${formatReason(d.reason)}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Amount</div>
      <div class="detail-value">${formatMoney(d.dispute_amount)}</div>
    </div>
    <div class="detail-row">
      <div class="detail-label">Respond by</div>
      <div class="detail-value">${new Date(d.seller_response_due_date).toLocaleString()}</div>
    </div>
    <button class="primary" id="analyze-btn">Analyze with AI</button>
    <div id="analysis-container"></div>
  `;

  document.getElementById("analyze-btn").addEventListener("click", () => analyze(disputeId));
}

async function analyze(disputeId) {
  const btn = document.getElementById("analyze-btn");
  const container = document.getElementById("analysis-container");

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span>Agent is reviewing the dispute…`;
  container.innerHTML = "";

  try {
    const res = await fetch(`/disputes/${disputeId}/analyze`, { method: "POST" });
    if (!res.ok) throw new Error(`API returned ${res.status}`);
    const a = await res.json();

    container.innerHTML = `
      <div class="analysis">
        <h3>AI Recommendation</h3>
        <div class="recommendation ${a.recommendation}">${a.recommendation}</div>
        <p>${a.reasoning}</p>
        <h3 style="margin-top:16px">Evidence to gather</h3>
        <ul class="evidence-list">
          ${a.evidence_needed.map((e) => `<li>${e.replaceAll("_", " ")}</li>`).join("")}
        </ul>
        <h3>Draft response letter</h3>
        <div class="letter">${a.draft_letter}</div>
        <button class="primary approve" id="approve-btn">Approve &amp; Submit to PayPal</button>
        <div id="submit-result"></div>
      </div>
    `;

    document.getElementById("approve-btn").addEventListener("click", () => approve(disputeId));
  } catch (err) {
    container.innerHTML = `<div class="error-msg">Analysis failed: ${err.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Re-run analysis";
  }
}

async function approve(disputeId) {
  const btn = document.getElementById("approve-btn");
  const result = document.getElementById("submit-result");

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span>Submitting to PayPal…`;

  try {
    const res = await fetch(`/disputes/${disputeId}/submit-evidence`, { method: "POST" });
    const data = await res.json();

    if (res.ok) {
      result.innerHTML = `<div class="success-msg">✓ Evidence submitted to PayPal (${data.status})</div>`;
      btn.remove();
    } else {
      result.innerHTML = `<div class="error-msg">Submission failed: ${data.detail || res.status}</div>`;
      btn.disabled = false;
      btn.textContent = "Retry submission";
    }
  } catch (err) {
    result.innerHTML = `<div class="error-msg">Submission failed: ${err.message}</div>`;
    btn.disabled = false;
    btn.textContent = "Retry submission";
  }
}

backBtn.addEventListener("click", () => {
  detailPanel.classList.add("hidden");
  listPanel.classList.remove("hidden");
});

loadDisputes();