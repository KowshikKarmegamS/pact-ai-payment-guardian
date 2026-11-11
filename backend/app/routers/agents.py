"""Control Center: register, list and revoke the AI agents allowed to use the Agent Gateway.

These endpoints belong to the human owner (the Control Center UI), not to agents.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SPENT_STATUSES, AgentClient, Mandate, Proposal, ProposalStatus, as_utc, utc_now
from app.services.agent_keys import display_prefix, hash_key, new_agent_key
from app.services.audit import log_audit_event

router = APIRouter(prefix="/agents", tags=["Connected agents (Control Center)"])


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="e.g. 'Claude Desktop (MCP)'")
    description: Optional[str] = Field(default=None, max_length=300)
    mandate_ids: List[str] = Field(..., min_length=1, description="Mandates this agent may request purchases under")


class AgentOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    key_prefix: str
    mandate_ids: List[str]
    mandate_names: List[str]
    status: str
    created_at: datetime
    last_used_at: Optional[datetime]
    revoked_at: Optional[datetime]
    requests: int
    blocked: int
    awaiting_approval: int
    captured: int


class AgentCreated(AgentOut):
    api_key: str = Field(..., description="Shown once. PACT stores only its hash.")


def _out(db: Session, agent: AgentClient) -> AgentOut:
    names = {m.id: m.name for m in db.query(Mandate).filter(Mandate.id.in_(agent.mandate_ids or [])).all()}
    counts = dict(
        db.query(Proposal.status, func.count(Proposal.id)).filter(Proposal.agent_id == agent.id).group_by(Proposal.status).all()
    )
    return AgentOut(
        id=agent.id, name=agent.name, description=agent.description, key_prefix=agent.key_prefix,
        mandate_ids=list(agent.mandate_ids or []),
        mandate_names=[names[i] for i in agent.mandate_ids or [] if i in names],
        status="revoked" if agent.revoked_at else "active",
        created_at=as_utc(agent.created_at), last_used_at=as_utc(agent.last_used_at), revoked_at=as_utc(agent.revoked_at),
        requests=sum(counts.values()),
        blocked=counts.get(ProposalStatus.POLICY_REJECTED, 0),
        awaiting_approval=counts.get(ProposalStatus.AWAITING_HUMAN_APPROVAL, 0),
        captured=sum(counts.get(s, 0) for s in SPENT_STATUSES),
    )


@router.get("", response_model=List[AgentOut], summary="Agents connected to the Agent Gateway")
def list_agents(db: Session = Depends(get_db)):
    return [_out(db, a) for a in db.query(AgentClient).order_by(AgentClient.created_at.desc()).all()]


@router.post("", response_model=AgentCreated, status_code=201, summary="Register an agent; its key is returned once")
def create_agent(body: AgentCreate, db: Session = Depends(get_db)):
    ids = list(dict.fromkeys(body.mandate_ids))
    found = {m.id for m in db.query(Mandate).filter(Mandate.id.in_(ids)).all()}
    missing = [i for i in ids if i not in found]
    if missing:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": f"Unknown mandate(s): {', '.join(missing)}"})
    key = new_agent_key()
    agent = AgentClient(name=body.name.strip(), description=(body.description or "").strip() or None,
                        key_prefix=display_prefix(key), key_hash=hash_key(key), mandate_ids=ids)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    log_audit_event(db, "AGENT_REGISTERED", "Agent", agent.id,
                    {"agent_name": agent.name, "mandate_ids": ids, "key_prefix": agent.key_prefix})
    return AgentCreated(**_out(db, agent).model_dump(), api_key=key)


@router.post("/{agent_id}/revoke", response_model=AgentOut, summary="Revoke an agent's access immediately")
def revoke_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(AgentClient).filter(AgentClient.id == agent_id).first()
    if agent is None:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found."})
    if agent.revoked_at is None:
        agent.revoked_at = utc_now()
        db.commit()
        log_audit_event(db, "AGENT_REVOKED", "Agent", agent.id, {"agent_name": agent.name})
    return _out(db, agent)
