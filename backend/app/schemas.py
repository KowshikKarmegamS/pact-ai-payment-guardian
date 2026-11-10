"""Pydantic data schemas for request validation, serialization, and policy results."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import ProposalStatus


# ============================================================================
# Product Schemas
# ============================================================================

class ProductBase(BaseModel):
    """Base attributes for catalog products."""

    name: str = Field(..., min_length=1, max_length=255, description="Product display name")
    description: str = Field(default="", description="Detailed product description")
    price: Decimal = Field(..., gt=0, decimal_places=2, description="Product unit price in the configured currency")
    category: str = Field(..., min_length=1, max_length=100, description="Product category")
    merchant: str = Field(..., min_length=1, max_length=100, description="Merchant or vendor name")
    image_url: Optional[str] = Field(default=None, max_length=500, description="Optional image URL")
    in_stock: bool = Field(default=True, description="Availability flag")


class ProductCreate(ProductBase):
    pass


class ProductOut(ProductBase):
    id: int = Field(..., description="Unique product identifier")
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Mandate Schemas
# ============================================================================

def _clean_str_list(value: Optional[List[str]]) -> List[str]:
    seen: Dict[str, str] = {}
    for item in value or []:
        s = str(item).strip()
        if s and s.lower() not in seen:
            seen[s.lower()] = s
    return list(seen.values())


class MandateRestrictions(BaseModel):
    """Typed fine-grained restrictions. Stored as JSON on the mandate."""

    model_config = ConfigDict(extra="forbid")

    max_price_per_item: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2)
    min_price_per_item: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)
    max_quantity: Optional[int] = Field(default=None, ge=1, le=20)
    prohibited_keywords: List[str] = Field(default_factory=list)
    prohibited_merchants: List[str] = Field(default_factory=list)

    @field_validator("prohibited_keywords", "prohibited_merchants")
    @classmethod
    def _clean(cls, v: List[str]) -> List[str]:
        return _clean_str_list(v)

    def to_json(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for key in ("max_price_per_item", "min_price_per_item"):
            val = getattr(self, key)
            if val is not None:
                out[key] = float(val)
        if self.max_quantity is not None:
            out["max_quantity"] = self.max_quantity
        if self.prohibited_keywords:
            out["prohibited_keywords"] = self.prohibited_keywords
        if self.prohibited_merchants:
            out["prohibited_merchants"] = self.prohibited_merchants
        return out


def _normalize_restrictions(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("restrictions must be an object")
    data = dict(value)
    # Accept legacy aliases.
    if "max_item_price" in data and "max_price_per_item" not in data:
        data["max_price_per_item"] = data.pop("max_item_price")
    if "min_item_price" in data and "min_price_per_item" not in data:
        data["min_price_per_item"] = data.pop("min_item_price")
    data = {k: v for k, v in data.items() if v is not None and v != ""}
    return MandateRestrictions(**data).to_json()


class MandateBase(BaseModel):
    """Base spending mandate constraints defined by the user."""

    name: str = Field(..., min_length=1, max_length=255, description="Name of this mandate")
    max_budget: Decimal = Field(..., gt=0, le=Decimal("100000"), decimal_places=2, description="Total budget")
    allowed_merchants: List[str] = Field(default_factory=list, description="Authorized merchant names")
    allowed_categories: List[str] = Field(default_factory=list, description="Authorized product categories")
    restrictions: Dict[str, Any] = Field(
        default_factory=dict,
        description="max_price_per_item, min_price_per_item, max_quantity, prohibited_keywords, prohibited_merchants",
    )
    expires_at: Optional[datetime] = Field(default=None, description="After this instant every purchase is blocked")


class MandateCreate(MandateBase):
    """Schema for creating a new spending mandate."""

    @field_validator("allowed_merchants", "allowed_categories")
    @classmethod
    def validate_non_empty_lists(cls, value: List[str]) -> List[str]:
        cleaned = _clean_str_list(value)
        if not cleaned:
            raise ValueError("Must contain at least one valid entry.")
        return cleaned

    @field_validator("restrictions", mode="before")
    @classmethod
    def validate_restrictions(cls, value: Any) -> Dict[str, Any]:
        return _normalize_restrictions(value)


class MandateUpdate(BaseModel):
    """Schema for updating an existing spending mandate."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    max_budget: Optional[Decimal] = Field(default=None, gt=0, le=Decimal("100000"), decimal_places=2)
    allowed_merchants: Optional[List[str]] = None
    allowed_categories: Optional[List[str]] = None
    restrictions: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = Field(default=None, description="Send null to remove the expiry")

    @field_validator("allowed_merchants", "allowed_categories")
    @classmethod
    def validate_lists(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        cleaned = _clean_str_list(value)
        if not cleaned:
            raise ValueError("Must contain at least one valid entry.")
        return cleaned

    @field_validator("restrictions", mode="before")
    @classmethod
    def validate_restrictions(cls, value: Any) -> Optional[Dict[str, Any]]:
        if value is None:
            return None
        return _normalize_restrictions(value)


class MandateOut(MandateBase):
    """Mandate details including live budget accounting."""

    id: str
    currency: str
    is_active: bool
    revoked_at: Optional[datetime] = None
    status: str = Field(default="active", description="active | paused | expired | revoked")
    created_at: datetime
    updated_at: datetime
    spent_budget: Decimal = Field(default=Decimal("0.00"), description="Verified captured spend")
    committed_budget: Decimal = Field(default=Decimal("0.00"), description="Approved, not yet captured")
    remaining_budget: Decimal = Field(default=Decimal("0.00"), description="max_budget - spent - committed")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Policy Engine Result Schemas
# ============================================================================

class PolicyCheck(BaseModel):
    """Outcome of one deterministic rule."""

    rule: str
    label: str
    passed: bool
    detail: str
    actual: Optional[str] = Field(default=None, description="What the proposal has")
    limit: Optional[str] = Field(default=None, description="What the mandate allows")


class PolicyResult(BaseModel):
    """Deterministic evaluation result against mandate rules."""

    passed: bool
    violations: List[str] = Field(default_factory=list)
    checks: List[PolicyCheck] = Field(default_factory=list)
    remaining_budget: Optional[Decimal] = None
    currency: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# ============================================================================
# Proposal Schemas
# ============================================================================

class ProposalApproval(BaseModel):
    """Explicit human approval, bound to the fingerprint the user reviewed."""

    expected_fingerprint: str = Field(
        ..., min_length=64, max_length=64,
        description="The proposal fingerprint displayed to the user when they clicked approve",
    )


class ProposalOut(BaseModel):
    """Proposal state. Never contains secrets."""

    id: str
    mandate_id: str
    product_id: int
    product_name: str
    merchant: str
    category: str
    price: Decimal
    quantity: int
    total_amount: Decimal
    currency: str
    status: ProposalStatus
    status_reason: Optional[str] = None
    user_prompt: Optional[str] = None
    ai_reasoning: Optional[str] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    ai_fallback_reason: Optional[str] = None
    supersedes_id: Optional[str] = None
    alternatives: Optional[List[Dict[str, Any]]] = None
    policy_checks: Optional[List[Dict[str, Any]]] = None
    remaining_budget_at_decision: Optional[Decimal] = None
    proposal_fingerprint: Optional[str] = None
    approval_fingerprint: Optional[str] = None
    approved_at: Optional[datetime] = None
    idempotency_key: str
    paypal_order_id: Optional[str] = None
    paypal_order_status: Optional[str] = None
    paypal_approval_url: Optional[str] = None
    paypal_capture_id: Optional[str] = None
    paypal_capture_status: Optional[str] = None
    captured_amount: Optional[Decimal] = None
    captured_currency: Optional[str] = None
    captured_at: Optional[datetime] = None
    paypal_debug_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Audit Log Schemas
# ============================================================================

class AuditLogOut(BaseModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Authorization Receipt
# ============================================================================

class ReceiptMandate(BaseModel):
    id: str
    name: str
    is_active: bool
    status: str = "active"
    expires_at: Optional[datetime] = None
    max_budget: Decimal
    currency: str
    allowed_merchants: List[str]
    allowed_categories: List[str]
    restrictions: Dict[str, Any]


class ReceiptIntegrity(BaseModel):
    proposal_fingerprint: Optional[str]
    approval_fingerprint: Optional[str]
    current_fingerprint: str
    intact: bool
    changes: List[str] = Field(default_factory=list)


class ReceiptBudget(BaseModel):
    """Live budget position of the mandate, relative to this proposal."""

    max_budget: Decimal
    spent: Decimal
    committed_other: Decimal
    available: Decimal
    this_purchase: Decimal
    remaining_after: Decimal
    counted: bool = Field(description="True when this proposal already holds or has consumed budget")


class AuthorizationReceipt(BaseModel):
    """Server-assembled explanation of why a purchase was permitted or blocked."""

    proposal: ProposalOut
    product: Optional[ProductOut] = None
    budget: Optional[ReceiptBudget] = None
    mandate: ReceiptMandate
    decision: str  # "BLOCKED" | "AUTHORIZED"
    decision_checks: List[PolicyCheck]
    revalidation_checks: Optional[List[PolicyCheck]] = None
    revalidated_at: Optional[datetime] = None
    integrity: ReceiptIntegrity
    timeline: List[AuditLogOut]
