import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="DisputeDefender")

app.mount("/static", StaticFiles(directory="static"), name="static")

SEED_PATH = Path(__file__).parent / "disputes_seed.json"

SYSTEM_PROMPT = """
You are DisputeDefender, an expert dispute-resolution agent for small PayPal sellers. Your job is to analyze a PayPal dispute and recommend the best course of action.

You will receive a JSON object representing a PayPal dispute. Analyze it carefully and return ONLY a valid JSON object with this exact structure:

{
  "recommendation": "fight" | "refund" | "accept",
  "reasoning": "A clear, 2-4 sentence explanation of why this is the best move, weighing the dispute amount, the reason code, and the win likelihood.",
  "evidence_needed": ["list", "of", "specific", "evidence", "items"],
  "draft_letter": "A professional response letter the seller can send to PayPal, referencing the evidence."
}

Rules:
- "fight" means provide evidence to contest the dispute.
- "refund" means issue a full refund to the buyer.
- "accept" means accept the claim without fighting (used when the seller is clearly at fault or the amount is too small to justify the effort).
- For MERCHANDISE_OR_SERVICE_NOT_RECEIVED: if tracking is likely available, recommend "fight" and request tracking_number, carrier, delivery_date. If no tracking exists, recommend "refund" because fighting without proof loses.
- For MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED: recommend "fight" and request listing_photos, item_photos, description_screenshot.
- For UNAUTHORIZED_TRANSACTION: recommend "refund" unless the amount is very small and the seller has strong proof of authorization, because unauthorized claims are hard to win.
- If the dispute amount is under $10, lean toward "refund" because the dispute fee and time cost exceed the amount.
- The reasoning must explicitly mention the dollar amount.
- The draft_letter must be polite, professional, and under 150 words.
- Return ONLY the JSON object. No markdown, no explanation outside the JSON.
"""


@app.get("/")
def serve_ui():
    return FileResponse("static/index.html")


def load_disputes() -> list[dict[str, Any]]:
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/disputes")
def list_disputes():
    """Return the seeded dispute list."""
    return {"items": load_disputes(), "total_items": len(load_disputes())}


@app.get("/disputes/{dispute_id}")
def get_dispute(dispute_id: str):
    """Return one dispute by ID."""
    for d in load_disputes():
        if d["dispute_id"] == dispute_id:
            return d
    raise HTTPException(status_code=404, detail=f"Dispute {dispute_id} not found")


class AnalyzeResponse(BaseModel):
    recommendation: str
    reasoning: str
    evidence_needed: list[str]
    draft_letter: str


@app.post("/disputes/{dispute_id}/analyze", response_model=AnalyzeResponse)
def analyze_dispute(dispute_id: str):
    dispute = get_dispute(dispute_id)

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    interaction = client.interactions.create(
        model="gemini-3.5-flash-lite",
        input=json.dumps(dispute),
        system_instruction=SYSTEM_PROMPT,
        generation_config={"thinking_level": "low"},
    )

    raw = interaction.output_text.strip().removeprefix("```json").removesuffix("```").strip()
    result = json.loads(raw)

    return AnalyzeResponse(**result)


@app.post("/disputes/{dispute_id}/submit-evidence")
def submit_evidence(dispute_id: str):
    dispute = get_dispute(dispute_id)

    client_id = os.getenv("PAYPAL_CLIENT_ID")
    secret = os.getenv("PAYPAL_SECRET")
    base_url = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")

    token_resp = httpx.post(
        f"{base_url}/v1/oauth2/token",
        auth=(client_id, secret),
        data={"grant_type": "client_credentials"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )
    if token_resp.status_code != 200:
        logger.error(f"PayPal token failed: {token_resp.status_code} {token_resp.text[:300]}")
        return {"status": "error", "detail": "Failed to get PayPal token"}

    access_token = token_resp.json()["access_token"]

    reason = dispute["reason"]
    evidence_list = []

    if reason == "MERCHANDISE_OR_SERVICE_NOT_RECEIVED":
        evidence_list.append({
            "evidence_type": "PROOF_OF_FULFILLMENT",
            "evidence_info": {
                "tracking_info": [{
                    "carrier_name": "OTHER",
                    "carrier_name_other": "Demo Carrier",
                    "tracking_number": "DEMO123456789",
                }]
            },
        })
    elif reason == "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED":
        evidence_list.append({
            "evidence_type": "OTHER",
            "notes": "Item matched the original listing description. Photos and listing screenshots attached in demo.",
        })
    else:
        evidence_list.append({
            "evidence_type": "OTHER",
            "notes": "Seller has proof of fulfillment and customer communication for this transaction.",
        })

    payload = {"evidences": evidence_list}

    # Use a clearly fake ID to force PayPal to return an error for the demo.
    # Replace this with dispute_id once you have a real sandbox dispute.
    fake_id = "FAKE-DISPUTE-999"

    resp = httpx.post(
        f"{base_url}/v1/customer/disputes/{fake_id}/provide-evidence",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30.0,
    )

    # These lines are what you will look for in the uvicorn terminal.
    logger.warning(f"PayPal provide-evidence status: {resp.status_code}")
    logger.warning(f"PayPal provide-evidence body: {resp.text[:500]}")

    if resp.status_code in (200, 201, 204):
        return {
            "status": "submitted",
            "paypal_response": resp.json() if resp.text else {},
        }
    else:
        return {
            "status": "error",
            "detail": f"PayPal returned {resp.status_code}: {resp.text[:300]}",
        }