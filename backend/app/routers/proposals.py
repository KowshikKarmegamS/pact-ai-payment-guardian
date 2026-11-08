"""Proposal generation, policy evaluation, and human approval workflow routes."""

import secrets
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.agent import generate_shopping_recommendation
from app.database import get_db
from app.models import Mandate, Product, Proposal, ProposalStatus
from app.policy import PolicyEngine
from app.schemas import PolicyResult, ProposalOut
from app.services.audit import log_audit_event
from app.services.mandate_service import calculate_mandate_budget

router = APIRouter(prefix="/proposals", tags=["Proposals"])


class ShoppingPromptRequest(BaseModel):
    """Shopping request submitted to the AI agent."""

    prompt: str = Field(..., min_length=2, description="User's natural language shopping request")
    mandate_id: str = Field(..., description="ID of the spending mandate to govern this purchase")


class ProposalGenerationResponse(BaseModel):
    """Response containing the AI recommendation, created proposal, and policy evaluation result."""

    proposal: ProposalOut
    policy: PolicyResult
    message: str


@router.post(
    "/generate",
    response_model=ProposalGenerationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a purchase proposal via AI and evaluate against spending mandate",
)
async def generate_proposal(
    request: ShoppingPromptRequest,
    db: Session = Depends(get_db),
):
    """AI Shopping Assistant Workflow:

    1. AI analyzes catalog and user prompt to recommend a product.
    2. Deterministic policy engine validates proposal against mandate.
    3. If valid -> proposal created in PENDING state awaiting human approval.
    4. If violations -> proposal created in REJECTED state with explicit violation details.
    """
    # 1. Fetch and validate mandate
    mandate = db.query(Mandate).filter(Mandate.id == request.mandate_id).first()
    if not mandate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandate with ID '{request.mandate_id}' was not found.",
        )

    if not mandate.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mandate '{mandate.name}' is currently paused/inactive.",
        )

    # 2. Fetch available catalog
    products = db.query(Product).all()
    if not products:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Catalog has no products available.",
        )

    # 3. AI Agent recommendation
    try:
        recommendation = await generate_shopping_recommendation(
            user_prompt=request.prompt,
            mandate=mandate,
            available_products=products,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Agent failed to analyze shopping request: {str(exc)}",
        )

    selected_product = recommendation.product
    quantity = recommendation.quantity
    unit_price = Decimal(str(selected_product.price))
    total_amount = unit_price * Decimal(str(quantity))

    # 4. Deterministic Policy Evaluation
    _, remaining_budget = calculate_mandate_budget(db, mandate)

    # Build transient candidate object for policy evaluation
    candidate_proposal = Proposal(
        mandate_id=mandate.id,
        product_id=selected_product.id,
        product_name=selected_product.name,
        merchant=selected_product.merchant,
        category=selected_product.category,
        price=unit_price,
        quantity=quantity,
        total_amount=total_amount,
        product=selected_product,
    )

    policy_result = PolicyEngine.evaluate(
        mandate=mandate,
        proposal=candidate_proposal,
        product=selected_product,
        remaining_budget=remaining_budget,
    )

    # 5. Persist Proposal with appropriate status
    initial_status = ProposalStatus.PENDING if policy_result.passed else ProposalStatus.REJECTED
    approval_token = secrets.token_urlsafe(32) if policy_result.passed else None

    proposal = Proposal(
        mandate_id=mandate.id,
        product_id=selected_product.id,
        product_name=selected_product.name,
        merchant=selected_product.merchant,
        category=selected_product.category,
        price=unit_price,
        quantity=quantity,
        total_amount=total_amount,
        ai_reasoning=recommendation.ai_reasoning,
        status=initial_status,
        approval_token=approval_token,
    )

    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    # 6. Record Audit Log
    event_type = "POLICY_CHECK_PASSED" if policy_result.passed else "POLICY_CHECK_FAILED"
    log_audit_event(
        db=db,
        event_type=event_type,
        entity_type="Proposal",
        entity_id=proposal.id,
        details={
            "product_name": proposal.product_name,
            "merchant": proposal.merchant,
            "category": proposal.category,
            "total_amount": float(proposal.total_amount),
            "remaining_budget": float(remaining_budget),
            "passed": policy_result.passed,
            "violations": policy_result.violations,
            "ai_prompt": request.prompt,
        },
    )

    message = (
        "Proposal successfully evaluated and approved by Guardian Policy Engine. Ready for human approval."
        if policy_result.passed
        else f"Guardian Policy Engine BLOCKED proposal: {'; '.join(policy_result.violations)}"
    )

    return ProposalGenerationResponse(
        proposal=ProposalOut.model_validate(proposal),
        policy=policy_result,
        message=message,
    )


@router.get("", response_model=List[ProposalOut], summary="List all proposals")
def list_proposals(
    mandate_id: Optional[str] = Query(None, description="Filter by mandate ID"),
    status_filter: Optional[ProposalStatus] = Query(None, alias="status", description="Filter by status"),
    db: Session = Depends(get_db),
):
    """Retrieve proposals ordered by most recent first."""
    query = db.query(Proposal)
    if mandate_id:
        query = query.filter(Proposal.mandate_id == mandate_id)
    if status_filter:
        query = query.filter(Proposal.status == status_filter)

    return query.order_by(Proposal.created_at.desc()).all()


@router.get("/{proposal_id}", response_model=ProposalOut, summary="Get proposal by ID")
def get_proposal(proposal_id: str, db: Session = Depends(get_db)):
    """Retrieve a single proposal by ID."""
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    return proposal


@router.post(
    "/{proposal_id}/approve",
    response_model=ProposalOut,
    summary="Human explicit approval of a purchase proposal",
)
def approve_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
):
    """Human approval step with mandatory server-side revalidation.

    Security Rule: The backend must revalidate mandate, budget, merchant, and category
    before granting human approval!
    """
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    if proposal.status != ProposalStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve proposal with status '{proposal.status}'. Must be 'pending'.",
        )

    mandate = db.query(Mandate).filter(Mandate.id == proposal.mandate_id).first()
    if not mandate or not mandate.is_active:
        raise HTTPException(status_code=400, detail="Associated mandate is inactive or missing.")

    product = db.query(Product).filter(Product.id == proposal.product_id).first()

    # Revalidate policy before granting approval
    _, remaining_budget = calculate_mandate_budget(db, mandate)
    recheck = PolicyEngine.evaluate(
        mandate=mandate,
        proposal=proposal,
        product=product,
        remaining_budget=remaining_budget,
    )

    if not recheck.passed:
        proposal.status = ProposalStatus.REJECTED
        db.commit()
        log_audit_event(
            db=db,
            event_type="APPROVAL_REVALIDATION_FAILED",
            entity_type="Proposal",
            entity_id=proposal.id,
            details={"violations": recheck.violations},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Approval rejected: Policy revalidation failed: {'; '.join(recheck.violations)}",
        )

    # Policy passed - mark as APPROVED
    proposal.status = ProposalStatus.APPROVED
    db.commit()
    db.refresh(proposal)

    log_audit_event(
        db=db,
        event_type="PROPOSAL_HUMAN_APPROVED",
        entity_type="Proposal",
        entity_id=proposal.id,
        details={
            "product_name": proposal.product_name,
            "merchant": proposal.merchant,
            "total_amount": float(proposal.total_amount),
        },
    )

    return proposal


@router.post(
    "/{proposal_id}/reject",
    response_model=ProposalOut,
    summary="Human explicit rejection of a purchase proposal",
)
def reject_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
):
    """Reject a proposal."""
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    if proposal.status in (ProposalStatus.CAPTURED, ProposalStatus.REJECTED):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject proposal in '{proposal.status}' status.",
        )

    proposal.status = ProposalStatus.REJECTED
    db.commit()
    db.refresh(proposal)

    log_audit_event(
        db=db,
        event_type="PROPOSAL_HUMAN_REJECTED",
        entity_type="Proposal",
        entity_id=proposal.id,
        details={"total_amount": float(proposal.total_amount)},
    )

    return proposal
