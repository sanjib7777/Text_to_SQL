import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from postgres_db.models import Conversation, Message, QueryRecord, User
from services.result_charting import enrich_result


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _json_value(value):
    return json.dumps(value, default=_json_default)


def _json_list(value):
    if not value:
        return []
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return decoded if isinstance(decoded, list) else []


def get_or_create_user(db: Session, username: str, company_code: str) -> User:
    user = db.scalar(select(User).where(User.username == username))

    if user is None:
        user = User(
            username=username,
            password_hash="oracle-authenticated",
            company_code=str(company_code),
        )
        db.add(user)
    else:
        user.company_code = str(company_code)

    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def list_user_conversations(db: Session, username: str) -> list[dict]:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        return []

    conversations = db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
    ).all()

    return [
        {
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
        }
        for conversation in conversations
    ]


def get_user_conversation(
    db: Session,
    username: str,
    conversation_id: int,
) -> dict | None:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        return None

    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if conversation is None:
        return None

    messages = []
    for message in conversation.messages:
        item = {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at,
        }
        if message.query_record is not None:
            query_record = message.query_record
            columns = _json_list(query_record.result_columns)
            rows = _json_list(query_record.result_rows)
            enriched = enrich_result(columns, rows)
            item["query"] = {
                "query_id": query_record.id,
                "question": query_record.question,
                "generated_sql": query_record.generated_sql,
                "validated_sql": query_record.validated_sql or query_record.generated_sql,
                "company_code": query_record.company_code,
                "row_count": query_record.row_count,
                "columns": enriched["columns"],
                "rows": enriched["rows"],
                "column_metadata": enriched["column_metadata"],
                "chart_data": enriched["chart_data"],
                "chart_error": enriched["chart_error"],
                "page": query_record.page,
                "page_size": query_record.page_size,
                "total_pages": query_record.total_pages,
                "has_more": query_record.has_more,
                "created_at": query_record.created_at,
            }
        messages.append(item)

    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": messages,
    }


def save_query_turn(
    db: Session,
    username: str,
    company_code: str,
    question: str,
    result: dict,
    conversation_id: int | None = None,
    page: int = 1,
    page_size: int = 100,
    total_pages: int | None = None,
    has_more: bool | None = None,
 ) -> tuple[int, int, int]:
    user = get_or_create_user(db, username, company_code)

    conversation = None
    if conversation_id is not None:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
            )
        )

    if conversation is None:
        conversation = Conversation(
            user_id=user.id,
            title=question[:255],
        )
        db.add(conversation)
        db.flush()

    conversation.updated_at = datetime.now(timezone.utc)

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=question,
    )
    db.add(user_message)
    db.flush()

    query_record = QueryRecord(
        query_id=str(uuid.uuid4()),
        message_id=user_message.id,
        question=question,
        generated_sql=result.get("generated_sql") or "",
        validated_sql=result.get("base_sql") or result.get("generated_sql") or "",
        company_code=str(company_code),
        row_count=result.get("row_count") or 0,
        result_columns=_json_value(result.get("columns") or []),
        result_rows=_json_value(result.get("rows") or []),
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_more=has_more,
    )
    db.add(query_record)

    assistant_content = result.get("error") or "Query completed successfully."
    db.add(Message(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_content,
    ))

    db.commit()
    return user.id, conversation.id, query_record.id


def save_query_page(
    db: Session,
    query_record: QueryRecord,
    rows: list,
    page: int,
    page_size: int,
    total_rows: int,
    total_pages: int,
    has_more: bool,
) -> None:
    stored_rows = _json_list(query_record.result_rows)
    offset = max(0, (page - 1) * page_size)

    if len(stored_rows) < offset:
        stored_rows.extend([None] * (offset - len(stored_rows)))

    for index, row in enumerate(rows):
        target = offset + index
        if target < len(stored_rows):
            stored_rows[target] = row
        else:
            stored_rows.append(row)

    query_record.result_rows = _json_value(stored_rows)
    query_record.row_count = total_rows
    query_record.page = page
    query_record.page_size = page_size
    query_record.total_pages = total_pages
    query_record.has_more = has_more
    db.commit()