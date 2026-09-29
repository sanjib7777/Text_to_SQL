from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class ConversationSummary(BaseModel):
    id: int
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class LoginResponse(BaseModel):
    authenticated: bool
    username: str
    message: str
    company_code: str | None = None
    conversations: list[ConversationSummary] = Field(default_factory=list)


class ConversationHistoryResponse(BaseModel):
    id: int
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    messages: list[dict[str, Any]]


class SQLQueryRequest(BaseModel):
    question: str
    username: str = Field(min_length=1)
    company_code: str = Field(min_length=1)
    conversation_id: int | None = None
    query_id: int | str | None = None
    validated_sql: str | None = None
    model_name: str
    llm_provider: str
    platform: str

    page: int = Field(default=1, ge=1, description="Page number starting at 1")
    page_size: int = Field(default=100, ge=1, le=100, description="Items per page (max 100)")


class SQLQueryResponse(BaseModel):
    success: bool
    conversation_id: int | None = None
    query_id: int | None = None
    message: Optional[str] = None
    validated_sql: Optional[str] = None

    generated_sql: Optional[str] = None

    base_sql: Optional[str] = None

    columns: Optional[List[str]] = None

    rows: Optional[List[List[Any]]] = None

    row_count: Optional[int] = None

    cache_hit: bool = False

    error: Optional[str] = None

    stage: Optional[str] = None

    # --- ADD PAGINATION OUTPUT METADATA ---
    page: Optional[int] = None
    page_size: Optional[int] = None
    total_pages: Optional[int] = None

    has_more: Optional[bool] = None

    column_metadata: Optional[List[dict[str, Any]]] = None
    chart_data: Optional[dict[str, Any]] = None
    chart_error: Optional[str] = None