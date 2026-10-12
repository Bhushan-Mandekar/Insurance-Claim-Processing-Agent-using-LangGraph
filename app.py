
import streamlit as st
from dotenv import load_dotenv
from workflow import process_claim, REQUIRED_DOCUMENTS

load_dotenv()

st.set_page_config(
    page_title="Insurance Claim Processing Agent",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ Insurance Claim Processing Agent")
st.caption(
    "LangGraph | Gemini 2.5 Flash | Parallel checks | Human review"
)

st.warning(
    "Educational demo only. Review every claim before using "
    "any result for a real insurance decision."
)

# Demo scenarios
SCENARIOS = {
    "Valid claim - Auto approve": {
        "claim_id": "CLM-1001",
        "claimant_name": "Meera Patil",
        "claim_type": "vehicle",
        "claim_amount": 42000.0,
        "incident_date": "2026-09-15",
        "policy_start": "2026-01-01",
        "policy_end": "2026-12-31",
        "policy_status": "active",
        "description": "Vehicle damage with repair estimate.",
        "documents": REQUIRED_DOCUMENTS["vehicle"],
    },
    "Missing documents - Reject": {
        "claim_id": "CLM-1002",
        "claimant_name": "Rohan Das",
        "claim_type": "health",
        "claim_amount": 32000.0,
        "incident_date": "2026-09-20",
        "policy_start": "2026-01-01",
        "policy_end": "2026-12-31",
        "policy_status": "active",
        "description": "Hospitalization claim.",
        "documents": ["claim_form", "policy_copy"],
    },
    "High value - Human review": {
        "claim_id": "CLM-1003",
        "claimant_name": "Ananya Rao",
        "claim_type": "property",
        "claim_amount": 350000.0,
        "incident_date": "2026-08-10",
        "policy_start": "2026-01-01",
        "policy_end": "2026-12-31",
        "policy_status": "active",
        "description": "Property damage after a storm.",
        "documents": REQUIRED_DOCUMENTS["property"],
    },
    "Expired policy - Reject": {
        "claim_id": "CLM-1004",
        "claimant_name": "Kabir Singh",
        "claim_type": "travel",
        "claim_amount": 18000.0,
        "incident_date": "2026-09-01",
        "policy_start": "2025-01-01",
        "policy_end": "2025-12-31",
        "policy_status": "expired",
        "description": "Travel expense claim.",
        "documents": REQUIRED_DOCUMENTS["travel"],
    },
}

scenario_name = st.sidebar.selectbox(
    "Choose a demo scenario",
    list(SCENARIOS.keys()),
)

sample = SCENARIOS[scenario_name]

st.subheader("1. Claim information")

with st.form("claim_form"):
    col1, col2, col3 = st.columns(3)

    claim_id = col1.text_input(
        "Claim ID", sample["claim_id"]
    )
    claimant_name = col2.text_input(
        "Claimant name", sample["claimant_name"]
    )
    claim_type = col3.selectbox(
        "Claim type",
        ["health", "vehicle", "travel", "property"],
        index=[
            "health", "vehicle", "travel", "property"
        ].index(sample["claim_type"]),
    )

    col1, col2, col3 = st.columns(3)

    claim_amount = col1.number_input(
        "Claim amount (INR)",
        min_value=0.0,
        value=float(sample["claim_amount"]),
        step=1000.0,
    )
    incident_date = col2.text_input(
        "Incident date (YYYY-MM-DD)",
        sample["incident_date"],
    )
    policy_status = col3.selectbox(
        "Policy status",
        ["active", "expired", "cancelled", "lapsed"],
        index=[
            "active", "expired", "cancelled", "lapsed"
        ].index(sample["policy_status"]),
    )

    col1, col2 = st.columns(2)

    policy_start = col1.text_input(
        "Policy start date (YYYY-MM-DD)",
        sample["policy_start"],
    )
    policy_end = col2.text_input(
        "Policy expiry date (YYYY-MM-DD)",
        sample["policy_end"],
    )

    description = st.text_area(
        "Claim description", sample["description"]
    )

    st.subheader("2. Supporting documents")

    all_documents = sorted({
        doc
        for docs in REQUIRED_DOCUMENTS.values()
        for doc in docs
    })

    selected_documents = st.multiselect(
        "Documents received",
        options=all_documents,
        default=sample["documents"],
    )

    st.caption(
        "This demo verifies document names only, "
        "not the contents or authenticity of actual files."
    )

    submitted = st.form_submit_button(
        "Process Insurance Claim",
        type="primary",
        use_container_width=True,
    )

if submitted:
    claim = {
        "claim_id": claim_id,
        "claimant_name": claimant_name,
        "claim_type": claim_type,
        "claim_amount": float(claim_amount),
        "incident_date": incident_date.strip(),
        "policy_start": policy_start.strip(),
        "policy_end": policy_end.strip(),
        "policy_status": policy_status,
        "description": description,
        "submitted_documents": selected_documents,
    }

    try:
        with st.spinner("Running LangGraph agents..."):
            result = process_claim(claim)

        st.session_state["result"] = result

    except Exception as exc:
        st.error(f"Workflow error: {exc}")

if "result" in st.session_state:
    result = st.session_state["result"]

    st.divider()
    st.subheader("3. Agent results")

    decision = result.get("decision", "UNKNOWN")

    if decision == "AUTO_APPROVED":
        st.success("Decision: AUTO APPROVED")
    elif decision == "REJECTED":
        st.error("Decision: REJECTED")
    elif decision == "PENDING_HUMAN_REVIEW":
        st.warning("Decision: PENDING HUMAN REVIEW")
    elif decision == "HUMAN_APPROVED":
        st.success("Final decision: HUMAN APPROVED")
    elif decision == "HUMAN_REJECTED":
        st.error("Final decision: HUMAN REJECTED")
    elif decision == "MORE_INFORMATION_REQUIRED":
        st.info("Final decision: MORE INFORMATION REQUIRED")

    st.write("**Routing reason:**", result.get("routing_reason", ""))

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### Document Verification")
        st.json(result.get("document_result", {}))

    with col2:
        st.markdown("#### Eligibility Check")
        st.json(result.get("eligibility_result", {}))

    with col3:
        st.markdown("#### Fraud Detection")
        st.json(result.get("fraud_result", {}))

    st.markdown("#### Claim Summary")
    st.write(result.get("claim_summary", ""))

    # Human review interface
    if decision == "PENDING_HUMAN_REVIEW":
        st.divider()
        st.subheader("4. Human Approval")

        st.write(
            "Review the claim evidence and risk flags before "
            "recording a decision. Risk flags are not proof of fraud."
        )

        with st.form("review_form"):
            reviewer_decision = st.radio(
                "Reviewer decision",
                [
                    "Approve",
                    "Reject",
                    "Request more information",
                ],
            )

            reviewer_notes = st.text_area(
                "Reviewer notes",
                placeholder="Enter your reasoning...",
            )

            confirmed = st.checkbox(
                "I have reviewed the claim details."
            )

            review_submitted = st.form_submit_button(
                "Submit Review", type="primary"
            )

        if review_submitted:
            if not confirmed:
                st.error("Confirm the review before submitting.")
            else:
                final_result = dict(result)

                mapping = {
                    "Approve": "HUMAN_APPROVED",
                    "Reject": "HUMAN_REJECTED",
                    "Request more information":
                        "MORE_INFORMATION_REQUIRED",
                }

                final_result["decision"] = mapping[
                    reviewer_decision
                ]
                final_result["reviewer_decision"] = reviewer_decision
                final_result["reviewer_notes"] = reviewer_notes
                final_result["routing_reason"] = (
                    result.get("routing_reason", "")
                    + f" | Reviewer selected: {reviewer_decision}"
                )

                st.session_state["result"] = final_result
                st.rerun()

    elif decision in {
        "HUMAN_APPROVED",
        "HUMAN_REJECTED",
        "MORE_INFORMATION_REQUIRED",
    }:
        st.subheader("Reviewer outcome")
        st.write("Notes:", result.get("reviewer_notes", ""))

    with st.expander("View complete claim state"):
        st.json(st.session_state["result"])
