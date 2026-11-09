"""
/api/v1/ai/* — the AI integration boundary.

POST /tickets/{ticket_id}/trigger   staff-only (JWT): starts a run. async —
                                     the only route that does real outbound
                                     I/O (app/ai/client.py), see that
                                     module's docstring for why.
GET  /tickets/{ticket_id}/recommendation
                                     staff-only (JWT): returns the latest
                                     AI recommendation and its evidence.
POST /recommendations               AI-service-only (shared secret): delivers a result.
GET  /similar-cases                 AI-service-only (shared secret): the completed-tickets
                                     candidate pool used to build SIMILAR_CASE evidence,
                                     as a privacy-minimized SimilarCaseOut (FIX 4) — no
                                     citizen_id, phone/email, or exact address.
POST /legal-search                  AI-service-only (shared secret): FIX 3 — the Legal RAG
                                     boundary. Searches ONLY legal_knowledge_chunks via
                                     pgvector cosine similarity; never touches tickets.

All three AI-service-only routes share one thing: the AI service reaches
Postgres data exclusively through these endpoints, authenticated by a shared
secret (never a user JWT, never direct database credentials) — see
app/dependencies/ai_auth.py.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.ai_auth import verify_ai_service_secret
from app.dependencies.auth import CurrentUser, require_role
from app.schemas.ai import (
    AiEvidenceOut,
    AiRecommendationCallbackIn,
    AiRecommendationOut,
    AiRunOut,
    LegalSearchIn,
    LegalSearchResultOut,
    SimilarCaseOut,
)
from app.services import ai as ai_service
from app.services import legal_rag as legal_rag_service

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.post("/tickets/{ticket_id}/trigger", response_model=AiRunOut, status_code=201)
async def trigger_run(
    ticket_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role("supervisor", "admin")),
    db: Session = Depends(get_db),
) -> AiRunOut:
    return await ai_service.trigger_ai_run(
        db,
        ticket_id,
        actor_id=current_user.id,
    )


@router.get(
    "/tickets/{ticket_id}/recommendation",
    response_model=AiRecommendationOut | None,
)
def get_recommendation(
    ticket_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role("supervisor", "admin")),
    db: Session = Depends(get_db),
) -> AiRecommendationOut | None:
    result = ai_service.get_latest_recommendation_with_evidence(
        db,
        ticket_id,
    )

    if result is None:
        return None

    recommendation, evidence = result

    return AiRecommendationOut(
        id=recommendation.id,
        ai_run_id=recommendation.ai_run_id,
        ticket_id=recommendation.ticket_id,
        category_id=recommendation.category_id,
        severity=recommendation.severity,
        department_id=recommendation.department_id,
        confidence=recommendation.confidence,
        explanation=recommendation.explanation,
        factors=recommendation.factors,
        evidence=[
            AiEvidenceOut.model_validate(item)
            for item in evidence
        ],
    )


@router.post(
    "/recommendations",
    response_model=AiRunOut,
    dependencies=[Depends(verify_ai_service_secret)],
)
def receive_recommendation(
    payload: AiRecommendationCallbackIn,
    db: Session = Depends(get_db),
) -> AiRunOut:
    return ai_service.process_ai_recommendation_callback(
        db,
        payload,
    )


@router.get(
    "/similar-cases",
    response_model=list[SimilarCaseOut],
    dependencies=[Depends(verify_ai_service_secret)],
)
def similar_cases(
    category_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[SimilarCaseOut]:
    return ai_service.list_similar_case_candidates(
        db,
        category_id=category_id,
        limit=limit,
    )


@router.post(
    "/legal-search",
    response_model=list[LegalSearchResultOut],
    dependencies=[Depends(verify_ai_service_secret)],
)
def legal_search(
    payload: LegalSearchIn,
    db: Session = Depends(get_db),
) -> list[LegalSearchResultOut]:
    results = legal_rag_service.search_legal_knowledge(
        db,
        payload.query_embedding,
        limit=payload.limit,
        source_type=payload.source_type,
        department_id=payload.department_id,
    )

    return [
        LegalSearchResultOut(**row)
        for row in results
    ]