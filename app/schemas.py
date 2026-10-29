from datetime import date
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


_CURRENCIES = {"₦": "NGN", "N": "NGN", "NAIRA": "NGN", "NGN": "NGN", "KSH": "KES", "KSHS": "KES", "KES": "KES",
               "$": "USD", "US$": "USD", "USD": "USD"}


class ClaimExtraction(BaseModel):
    claimant_name: Optional[str] = None
    policy_number: Optional[str] = None
    incident_date: Optional[date] = None
    claim_amount: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = None
    claim_type: Optional[Literal["motor", "health", "property", "life", "other"]] = None
    missing_fields: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)

    @field_validator("currency", mode="before")
    @classmethod
    def _normalise_currency(cls, v):
        if v is None:
            return None
        key = str(v).strip().upper().rstrip(".")
        return _CURRENCIES.get(key, key)  # unknown codes pass through unchanged


class ExtractionResult(BaseModel):
    status: Literal["ok", "needs_human_review"]
    data: Optional[ClaimExtraction] = None
    reasons: List[str] = Field(default_factory=list)
    attempts: int = 0
    redactions: dict = Field(default_factory=dict)
