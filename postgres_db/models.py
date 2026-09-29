from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# =========================================================
# USERS
# =========================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Company assigned to the user
    company_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # User's default/current branch
    branch_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="user",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    branches = relationship(
        "UserBranch",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    conversations = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )


# =========================================================
# USER BRANCHES
# =========================================================

class UserBranch(Base):
    """
    Stores branches that a user is authorized to access.

    Example:

    user_id = 1
    company_code = 01
    branch_code = 01.01

    user_id = 1
    company_code = 01
    branch_code = 01.02
    """

    __tablename__ = "user_branches"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    company_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    branch_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    branch_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="branches",
    )


# =========================================================
# CONVERSATIONS
# =========================================================

class Conversation(Base):
    """
    One ChatGPT-like conversation.

    Example:

    Conversation:
        "Monthly Sales Report"
    """

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="conversations",
    )

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


# =========================================================
# MESSAGES
# =========================================================

class Message(Base):
    """
    Stores individual conversation messages.

    role:
        user
        assistant
        system
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    conversation = relationship(
        "Conversation",
        back_populates="messages",
    )

    query_record = relationship(
        "QueryRecord",
        back_populates="message",
        uselist=False,
        cascade="all, delete-orphan",
    )


# =========================================================
# QUERY RECORDS
# =========================================================

class QueryRecord(Base):
    """
    Stores information about an AI-generated SQL query.

    This stores metadata and SQL.

    It should NOT be used to permanently store
    huge Oracle result sets.
    """

    __tablename__ = "query_records"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Public/application query ID
    query_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Original user question
    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Validated SQL generated by the system
    generated_sql: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Canonical SQL used to replay later pages without invoking the LLM.
    validated_sql: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Company scope used when executing SQL
    company_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Branch scope
    # Example:
    # USER_BRANCH
    # SPECIFIC_BRANCH
    # ALL_AUTHORIZED_BRANCHES
    branch_scope_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Example:
    # ["01.02", "01.03"]
    #
    # We keep this as text initially to keep the model
    # simple. We can later use PostgreSQL JSONB if needed.
    branch_scope: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Number of rows returned
    row_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # JSON-encoded result metadata retained for conversation history.
    result_columns: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    result_rows: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_more: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Query execution time
    execution_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    message = relationship(
        "Message",
        back_populates="query_record",
    )