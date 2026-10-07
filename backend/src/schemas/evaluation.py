"""Pydantic schemas for RAGAS evaluation scoring and benchmark metrics."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class EvaluationScoreCreate(BaseModel):
    """Payload for recording a RAGAS metric score calculated by the LLM Judge."""

    conversation_id: str
    system_variant: str = Field(..., description="'RAG' or 'BASELINE'")
    pillar: str = Field(..., description="'Baggage', 'Rebooking', 'Travel Docs', 'Disruptions'")
    faithfulness_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    answer_relevancy_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    context_recall_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class EvaluationScoreDTO(BaseModel):
    """Full representation of a scored evaluation record."""

    model_config = ConfigDict(from_attributes=True)

    evaluation_id: str
    conversation_id: str
    system_variant: str
    pillar: str
    faithfulness_score: Optional[float] = None
    answer_relevancy_score: Optional[float] = None
    context_recall_score: Optional[float] = None
    evaluated_at: datetime


class PillarBenchmarkSummary(BaseModel):
    """Aggregated quantitative metrics for Chapter 5 / Results section."""

    pillar: str
    system_variant: str
    avg_faithfulness: float
    avg_answer_relevancy: float
    avg_context_recall: float
    sample_count: int
