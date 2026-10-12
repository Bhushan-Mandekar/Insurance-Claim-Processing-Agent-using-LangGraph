
import os
from typing import TypedDict, Literal, Any
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

load_dotenv()

# Demo rules. Adjust these according to your assignment.
HIGH_VALUE_THRESHOLD = 200000

REQUIRED_DOCUMENTS = {
    "health": [
        "claim_form", "policy_copy", "hospital_bill",
        "discharge_summary", "identity_proof"
    ],
    "vehicle": [
        "claim_form", "policy_copy", "repair_estimate",
        "vehicle_registration", "identity_proof"
    ],
    "travel": [
        "claim_form", "policy_copy", "ticket_or_booking",
        "expense_proof", "identity_proof"
    ],
    "property": [
        "claim_form", "policy_copy", "damage_photos",
        "repair_estimate", "identity_proof"
    ],
}


class ClaimState(TypedDict, total=False):
    claim_id: str
    claimant_name: str
    claim_type: str
    claim_amount: float
    incident_date: str
    policy_start: str
    policy_end: str
    policy_status: str
    description: str
    submitted_documents: list[str]
    document_result: dict[str, Any]
    eligibility_result: dict[str, Any]
    fraud_result: dict[str, Any]
    claim_summary: str
    decision: str
    routing_reason: str


# AGENT 1: Document Verification Agent
def document_verification_agent(state: ClaimState) -> dict:
    claim_type = state.get("claim_type", "health").lower()
    required = REQUIRED_DOCUMENTS.get(
        claim_type, REQUIRED_DOCUMENTS["health"]
    )

    submitted = {
        str(doc).strip().lower()
        for doc in state.get("submitted_documents", [])
    }

    missing = [doc for doc in required if doc not in submitted]

    return {
        "document_result": {
            "status": "PASS" if not missing else "FAIL",
            "required_documents": required,
            "submitted_documents": sorted(submitted),
            "missing_documents": missing,
        }
    }


# AGENT 2: Policy Eligibility Check Agent
def eligibility_check_agent(state: ClaimState) -> dict:
    status = state.get("policy_status", "").strip().lower()
    start = state.get("policy_start", "").strip()
    end = state.get("policy_end", "").strip()
    incident = state.get("incident_date", "").strip()

    reasons = []

    if status not in {"active", "valid", "in_force"}:
        reasons.append("Policy status is not active.")

    if start and incident and incident < start:
        reasons.append("Incident occurred before policy start.")

    if end and incident and incident > end:
        reasons.append("Incident occurred after policy expiry.")

    if not start or not end or not incident:
        reasons.append("Policy dates are incomplete; manual review is needed.")

    hard_fail = (
        status not in {"active", "valid", "in_force"}
        or (bool(start and incident) and incident < start)
        or (bool(end and incident) and incident > end)
    )

    needs_review = (
        not hard_fail and
        (not start or not end or not incident)
    )

    if hard_fail:
        result_status = "FAIL"
    elif needs_review:
        result_status = "REVIEW"
    else:
        result_status = "PASS"

    if not reasons:
        reasons.append(
            "Policy is active and incident date is within coverage dates."
        )

    return {
        "eligibility_result": {
            "status": result_status,
            "reasons": reasons,
        }
    }


# AGENT 3: Fraud Detection Agent
def fraud_detection_agent(state: ClaimState) -> dict:
    amount = float(state.get("claim_amount", 0))
    description = state.get("description", "").lower()
    flags = []

    if amount <= 0:
        flags.append("Claim amount must be greater than zero.")

    if amount >= HIGH_VALUE_THRESHOLD:
        flags.append(
            f"High-value claim: amount is at least "
            f"INR {HIGH_VALUE_THRESHOLD}."
        )

    suspicious_terms = [
        "staged", "fake", "fabricated", "duplicate",
        "inflated", "inconsistent"
    ]

    found = [word for word in suspicious_terms if word in description]

    if found:
        flags.append(
            "Potential risk indicators in description: "
            + ", ".join(found)
        )

    return {
        "fraud_result": {
            "status": "FLAG" if flags else "CLEAR",
            "risk_flags": flags,
            "risk_level": (
                "HIGH" if amount >= HIGH_VALUE_THRESHOLD
                or len(flags) >= 2
                else "MEDIUM" if flags
                else "LOW"
            ),
            "note": "Risk indicators are not proof of fraud.",
        }
    }


# AGENT 4: Claim Summary Agent (Gemini 2.5 Flash)
def claim_summary_agent(state: ClaimState) -> dict:
    docs = state.get("document_result", {})
    eligibility = state.get("eligibility_result", {})
    fraud = state.get("fraud_result", {})

    facts = f"""
    Claim ID: {state.get('claim_id', 'N/A')}
    Claimant: {state.get('claimant_name', 'N/A')}
    Claim type: {state.get('claim_type', 'N/A')}
    Amount: INR {float(state.get('claim_amount', 0)):,.2f}
    Incident date: {state.get('incident_date', 'N/A')}
    Document status: {docs.get('status')}
    Missing documents: {docs.get('missing_documents', [])}
    Eligibility status: {eligibility.get('status')}
    Eligibility reasons: {eligibility.get('reasons', [])}
    Fraud screen: {fraud.get('status')}
    Risk flags: {fraud.get('risk_flags', [])}
    """

    summary = None
    api_key = os.getenv("GOOGLE_API_KEY")

    if api_key:
        try:
            model = ChatGoogleGenerativeAI(
                model=os.getenv(
                    "GEMINI_MODEL", "gemini-2.5-flash"
                ),
                temperature=0,
            )

            response = model.invoke([
                HumanMessage(content=(
                    "Create a concise insurance claim summary in "
                    "4 to 6 bullet points. Use only the supplied facts. "
                    "Do not make the final claim decision. "
                    "Explain that fraud flags are indicators, not proof.\n"
                    + facts
                ))
            ])

            summary = response.content
            if not isinstance(summary, str):
                summary = str(summary)

        except Exception as exc:
            print("Gemini summary unavailable:", str(exc))

    if not summary:
        summary = (
            f"Claim {state.get('claim_id', 'N/A')} is a "
            f"{state.get('claim_type', 'N/A')} claim for INR "
            f"{float(state.get('claim_amount', 0)):,.2f}.\n"
            f"Documents: {docs.get('status')}; missing: "
            f"{docs.get('missing_documents', [])}.\n"
            f"Eligibility: {eligibility.get('status')}; reasons: "
            f"{eligibility.get('reasons', [])}.\n"
            f"Fraud screen: {fraud.get('status')}; risk flags: "
            f"{fraud.get('risk_flags', [])}.\n"
            "Fallback summary used. Risk indicators are not proof of fraud."
        )

    return {"claim_summary": summary}


# CONDITIONAL ROUTER
def route_claim(
    state: ClaimState
) -> Literal["approve", "reject", "human"]:
    docs = state.get("document_result", {})
    eligibility = state.get("eligibility_result", {})
    fraud = state.get("fraud_result", {})

    if docs.get("status") == "FAIL":
        return "reject"

    if eligibility.get("status") == "FAIL":
        return "reject"

    if eligibility.get("status") == "REVIEW":
        return "human"

    if fraud.get("status") == "FLAG":
        return "human"

    return "approve"


def auto_approve_node(state: ClaimState) -> dict:
    return {
        "decision": "AUTO_APPROVED",
        "routing_reason": (
            "Required documents and eligibility checks passed; "
            "no risk flags were detected."
        ),
    }


def reject_node(state: ClaimState) -> dict:
    reasons = []

    if state.get("document_result", {}).get("status") == "FAIL":
        missing = state["document_result"].get(
            "missing_documents", []
        )
        reasons.append(f"Missing documents: {missing}")

    if state.get("eligibility_result", {}).get("status") == "FAIL":
        reasons.extend(
            state["eligibility_result"].get("reasons", [])
        )

    return {
        "decision": "REJECTED",
        "routing_reason": "; ".join(reasons),
    }


# AGENT 5: Human Approval Agent
def human_approval_agent(state: ClaimState) -> dict:
    reasons = state.get("fraud_result", {}).get("risk_flags", [])

    if state.get("eligibility_result", {}).get("status") == "REVIEW":
        reasons.extend(
            state["eligibility_result"].get("reasons", [])
        )

    return {
        "decision": "PENDING_HUMAN_REVIEW",
        "routing_reason": (
            "; ".join(reasons)
            if reasons
            else "Manual review is required."
        ),
    }


# BUILD LANGGRAPH WORKFLOW
def build_graph():
    graph = StateGraph(ClaimState)

    graph.add_node(
        "document_verification", document_verification_agent
    )
    graph.add_node("eligibility_check", eligibility_check_agent)
    graph.add_node("fraud_detection", fraud_detection_agent)
    graph.add_node("claim_summary", claim_summary_agent)
    graph.add_node("auto_approve", auto_approve_node)
    graph.add_node("reject", reject_node)
    graph.add_node("human_approval", human_approval_agent)

    # Three independent checks start in parallel.
    graph.add_edge(START, "document_verification")
    graph.add_edge(START, "eligibility_check")
    graph.add_edge(START, "fraud_detection")

    # Wait for all three checks before summarizing.
    graph.add_edge(
        [
            "document_verification",
            "eligibility_check",
            "fraud_detection",
        ],
        "claim_summary",
    )

    graph.add_conditional_edges(
        "claim_summary",
        route_claim,
        {
            "approve": "auto_approve",
            "reject": "reject",
            "human": "human_approval",
        },
    )

    graph.add_edge("auto_approve", END)
    graph.add_edge("reject", END)
    graph.add_edge("human_approval", END)

    return graph.compile()


claim_graph = build_graph()


def process_claim(claim: dict) -> dict:
    return claim_graph.invoke(claim)
