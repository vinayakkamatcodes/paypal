# DisputeDefender

An AI agent that fights PayPal disputes for small sellers.

## The problem

Small merchants and freelancers lose money to PayPal disputes not because they are wrong, but because assembling evidence is tedious and the response deadlines are short. Most sellers either miss the deadline or refund out of exhaustion.

## What it does

1. Shows open disputes with a live countdown to the seller response deadline.
2. Classifies each dispute (item not received, not as described, unauthorized) and gathers the matching evidence.
3. Uses an LLM to decide the best move: **fight**, **refund**, or **accept**. The reasoning explicitly weighs the dollar amount, the reason code, and the win likelihood.
4. Drafts the response letter and lists the evidence the seller needs to collect.
5. **Human approves before money moves.** Only after the seller clicks Approve does the agent call PayPal's `provide-evidence` endpoint.

## Architecture
Browser (static/index.html + app.js)
|
v
FastAPI (main.py)
| |
v v
Gemini PayPal Sandbox REST API
(analyze) (OAuth token + provide-evidence)

text

## PayPal APIs used

- `POST /v1/oauth2/token` — client credentials authentication.
- `GET /v1/customer/disputes` — dispute listing (scope confirmed; list is empty in a fresh sandbox).
- `POST /v1/customer/disputes/{id}/provide-evidence` — evidence submission, called only after human approval.

## AI used

Google Gemini (`gemini-3.5-flash-lite`) via the `google-genai` SDK. The model returns structured JSON: `recommendation`, `reasoning`, `evidence_needed`, `draft_letter`.

## Transparency note

Dispute ingestion is **seeded** from `disputes_seed.json` for demo reliability, because creating a live sandbox dispute requires buyer-side consent and a JWT assertion that cannot be completed reliably within the hackathon window. The `provide-evidence` call is wired to the **real PayPal sandbox API** and returns a real PayPal error (`RESOURCE_NOT_FOUND`) because the seeded dispute IDs are not registered in the sandbox. This is expected and shown honestly in the demo.

## Setup

1. Clone the repo.
2. Create a `.env` file in the project root:
PAYPAL_CLIENT_ID=[YOUR_PAYPAL_CLIENT_ID]
PAYPAL_SECRET=[YOUR_PAYPAL_SECRET]
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
GEMINI_API_KEY=[YOUR_GEMINI_API_KEY]

text

3. Install dependencies:

```bash
pip install -r requirements.txt
Run:

bash
uvicorn main:app --reload
Open http://127.0.0.1:8000/.

Live demo
[PASTE_YOUR_RENDER_URL_HERE]

Demo video
[PASTE_YOUR_YOUTUBE_URL_HERE]

What was built during the submission period
The entire project was built during the PayPal AI Hackathon submission period: FastAPI backend, seeded dispute dataset, Gemini analysis endpoint, approval UI with deadline countdown, and the real PayPal provide-evidence integration.

License
MIT