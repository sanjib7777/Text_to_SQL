import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException, Depends
from starlette.concurrency import run_in_threadpool
from oracle.connection import OracleConnectionPool
from schemas.request_response import (
    LoginRequest,
    LoginResponse,
    ConversationSummary,
    ConversationHistoryResponse,
    SQLQueryRequest,
    SQLQueryResponse
)
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from postgres_db.database import get_db
from postgres_db.models import Conversation, Message, QueryRecord
from services.sql_generation_pipeline import (
    SQLGenerationPipeline
)
from services.conversation_history import (
    get_or_create_user,
    get_user,
    get_user_conversation,
    list_user_conversations,
    save_query_turn,
    save_query_page,
)
from services.result_charting import enrich_result

from api.session_context import SessionContext

logger = logging.getLogger("ai_sql_generator")

router = APIRouter()


oracle_pool = OracleConnectionPool(min_connections=1, max_connections=10)
oracle_pool.start()

pipeline = SQLGenerationPipeline(oracle_pool=oracle_pool)

# --------------------------------------------------------------------------
# CONCURRENCY GUARD
# --------------------------------------------------------------------------
# pipeline.run() presumably calls an LLM API and executes SQL against Oracle
# -- both are external, resource-limited backends. Without a cap, N
# simultaneous requests fire N simultaneous LLM calls + N simultaneous DB
# queries, which can overwhelm either backend and degrade latency for
# EVERYONE rather than failing fast for excess requests. This bounds how
# many pipeline.run() calls execute at once; anything beyond that queues
# (up to MAX_QUEUE_WAIT_SECONDS) instead of piling on unbounded load.
#
# Tune MAX_CONCURRENT_QUERIES to what your Oracle connection pool / LLM
# rate limits can actually sustain -- this number is a placeholder.
MAX_CONCURRENT_QUERIES = 5
MAX_QUEUE_WAIT_SECONDS = 5

_query_semaphore = asyncio.Semaphore(MAX_CONCURRENT_QUERIES)

# --------------------------------------------------------------------------
# PAGE SIZE LIMITS
# --------------------------------------------------------------------------
# Prevents a client from requesting an absurd page_size (huge payload,
# slow serialization) or page_size=0 (ZeroDivisionError in the pagination
# math below -- this WILL crash the request today with a 500 if a client
# ever sends page_size=0). Ideally these constraints live in the Pydantic
# schema itself (schemas/request_response.py) via Field(gt=0, le=500) so
# invalid requests are rejected before they even reach this function --
# clamping here is a defensive fallback, not a substitute for that.
MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 100


def _count_rows(executor, validated_sql: str) -> int | None:
    count_sql = f"SELECT COUNT(*) FROM ({validated_sql}) count_query"
    count_result = executor.execute(count_sql, max_rows=1)
    if not count_result.get("success") or not count_result.get("rows"):
        return None
    try:
        return int(count_result["rows"][0][0])
    except (TypeError, ValueError, IndexError):
        return None


# =========================================================
# HEALTH CHECK
# =========================================================

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AI SQL Generator"
    }


# =========================================================
# AUTHENTICATION
# =========================================================

@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    username = request.username.strip()

    if not username:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    try:
        result = await run_in_threadpool(
            oracle_pool.execute_query,
            """
            SELECT LOGIN_CODE, COMPANY_CODE
            FROM SC_APPLICATION_USERS
            WHERE LOGIN_CODE = :username
              AND PASSWORD = :password
            """,
            {"username": username, "password": request.password},
            1,
        )
    except Exception:
        logger.exception("Authentication database error")
        raise HTTPException(
            status_code=500,
            detail="Authentication service is temporarily unavailable.",
        )

    if not result.get("rows"):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    authenticated_user = result["rows"][0]
    authenticated_username = authenticated_user[0]
    company_code = authenticated_user[1]

    if not company_code:
        logger.error(
            "Authenticated user has incomplete data scope: username=%s",
            authenticated_username,
        )
        raise HTTPException(
            status_code=500,
            detail="Authenticated user does not have a valid company scope.",
        )

    try:
        get_or_create_user(db, authenticated_username, str(company_code))
        conversations = list_user_conversations(db, authenticated_username)
    except Exception:
        db.rollback()
        logger.exception("PostgreSQL user/history initialization failed")
        raise HTTPException(
            status_code=503,
            detail="History service is temporarily unavailable.",
        )

    return LoginResponse(
        authenticated=True,
        username=authenticated_username,
        message="Login successful.",
        company_code=str(company_code),
        conversations=conversations,
    )


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(username: str, db: Session = Depends(get_db)):
    return list_user_conversations(db, username.strip())


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationHistoryResponse,
)
def get_conversation(
    conversation_id: int,
    username: str,
    db: Session = Depends(get_db),
):
    conversation = get_user_conversation(db, username.strip(), conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation



@router.get("/postgres-test")
def postgres_test(db: Session = Depends(get_db)):

    result = db.execute(
        text("SELECT version()")
    )

    version = result.scalar()

    return {
        "status": "success",
        "database": "PostgreSQL",
        "version": version
    }
# =========================================================
# SQL QUERY
# =========================================================

@router.post(
    "/query",
    response_model=SQLQueryResponse
)
async def generate_sql(
    request: SQLQueryRequest,
    db: Session = Depends(get_db),
):
    api_start = time.time()

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    # Defensive clamp -- see MAX_PAGE_SIZE comment above. Prefer fixing
    # this at the schema level; this just prevents a 500 in the meantime.
    page = max(1, request.page)
    page_size = min(max(MIN_PAGE_SIZE, request.page_size), MAX_PAGE_SIZE)

    try:
        username = request.username.strip()
        db_user = get_user(db, username)
        if db_user is None or db_user.company_code != request.company_code:
            raise HTTPException(
                status_code=401,
                detail="Authenticated user scope is invalid.",
            )

        session = SessionContext(
            company_code=request.company_code,
        )

        is_load_more = request.query_id is not None or request.validated_sql is not None

        if is_load_more:
            if request.query_id is None or not request.validated_sql:
                raise HTTPException(
                    status_code=400,
                    detail="query_id and validated_sql are required when loading more rows.",
                )

            query_record = db.scalar(
                select(QueryRecord)
                .join(QueryRecord.message)
                .join(Message.conversation)
                .where(
                    QueryRecord.query_id == str(request.query_id),
                    QueryRecord.company_code == str(request.company_code),
                    Conversation.user_id == db_user.id,
                )
            )

            if query_record is None and str(request.query_id).isdigit():
                query_record = db.scalar(
                    select(QueryRecord)
                    .join(QueryRecord.message)
                    .where(
                        QueryRecord.id == int(request.query_id),
                        QueryRecord.company_code == str(request.company_code),
                        Message.conversation.has(Conversation.user_id == db_user.id),
                    )
                )

            if query_record is None or query_record.message.conversation.user_id != db_user.id:
                raise HTTPException(status_code=404, detail="Query not found.")

            stored_sql = query_record.validated_sql or query_record.generated_sql
            if request.validated_sql.strip() != stored_sql.strip():
                raise HTTPException(
                    status_code=400,
                    detail="validated_sql does not match the stored query.",
                )

            paginated_sql = pipeline.row_limit_handler.apply_pagination(
                stored_sql,
                page=request.page,
                page_size=page_size,
            )
            replay_result = await run_in_threadpool(
                pipeline.executor.execute,
                paginated_sql,
                pipeline.MAX_RESULT_ROWS,
            )
            if not replay_result.get("success"):
                raise HTTPException(status_code=503, detail=replay_result.get("error"))

            returned_rows = replay_result.get("rows") or []
            total_rows = None
            if stored_sql:
                total_rows = await run_in_threadpool(
                    _count_rows,
                    pipeline.executor,
                    stored_sql,
                )
            if total_rows is None:
                total_rows = query_record.row_count or len(returned_rows)
            total_pages = max(1, (total_rows + page_size - 1) // page_size)
            has_more = request.page < total_pages
            chart_columns = replay_result.get("columns")
            chart_rows = returned_rows
            if total_rows > page_size:
                chart_result = await run_in_threadpool(
                    pipeline.executor.execute,
                    stored_sql,
                    pipeline.MAX_RESULT_ROWS,
                )
                if chart_result.get("success"):
                    chart_columns = chart_result.get("columns")
                    chart_rows = chart_result.get("rows") or []
            table_enriched = enrich_result(replay_result.get("columns"), returned_rows)
            chart_enriched = enrich_result(chart_columns, chart_rows)
            try:
                save_query_page(
                    db=db,
                    query_record=query_record,
                    rows=returned_rows,
                    page=request.page,
                    page_size=page_size,
                    total_rows=total_rows,
                    total_pages=total_pages,
                    has_more=has_more,
                )
            except Exception:
                db.rollback()
                logger.exception("Failed to persist loaded conversation page")
                raise HTTPException(
                    status_code=503,
                    detail="Query completed, but conversation history could not be saved.",
                )
            return SQLQueryResponse(
                success=True,
                message="Query completed successfully.",
                query_id=query_record.id,
                conversation_id=query_record.message.conversation_id,
                validated_sql=stored_sql,
                generated_sql=paginated_sql,
                base_sql=stored_sql,
                columns=table_enriched["columns"],
                rows=table_enriched["rows"],
                column_metadata=chart_enriched["column_metadata"],
                chart_data=chart_enriched["chart_data"],
                chart_error=chart_enriched["chart_error"],
                row_count=total_rows,
                page=request.page,
                page_size=page_size,
                total_pages=total_pages,
                has_more=has_more,
                cache_hit=False,
            )

        logger.info(
            "Query start: provider=%s platform=%s model=%s company=%s",
            request.llm_provider, request.platform, request.model_name,
            request.company_code
        )

        # --------------------------------------------------------------
        # Bounded concurrency: wait for a free slot, but don't wait
        # forever -- if the system is saturated for too long, fail fast
        # with a 503 instead of letting requests queue indefinitely and
        # the client time out anyway with no useful signal.
        # --------------------------------------------------------------
        try:
            await asyncio.wait_for(
                _query_semaphore.acquire(),
                timeout=MAX_QUEUE_WAIT_SECONDS
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=503,
                detail="Server is busy handling other queries. Please retry shortly."
            )

        try:
            # pipeline.run() is presumably still a blocking/sync call
            # (sync LLM client, sync oracledb calls). run_in_threadpool
            # hands it to Starlette's worker threadpool so this request
            # doesn't block the event loop while waiting on it -- other
            # requests (health checks, fast validation failures, etc.)
            # keep being served in the meantime.
            #
            # NOTE: this does NOT make pipeline.run() itself faster or
            # more parallel -- it's still one OS thread per in-flight
            # query, bounded by MAX_CONCURRENT_QUERIES above and by
            # Starlette's threadpool size. The real throughput win comes
            # from making SQLGenerationPipeline's internals (LLM calls,
            # DB calls) natively async, and from an Oracle connection
            # POOL rather than a single shared connection -- both live
            # outside this file.
            result = await run_in_threadpool(
                pipeline.run,
                user_query=question,
                session=session,
                model_name=request.model_name,
                llm_provider=request.llm_provider,
                platform=request.platform,
                page=page,
                page_size=page_size,
            )
        finally:
            _query_semaphore.release()

        # Pagination is applied by Oracle inside the pipeline.
        all_rows = result.get("rows") or []
        count_sql = result.get("base_sql") or result.get("generated_sql") or ""
        total_rows = None
        if result.get("success") and count_sql:
            total_rows = await run_in_threadpool(
                _count_rows,
                pipeline.executor,
                count_sql,
            )
        if total_rows is None:
            total_rows = result.get("row_count") or len(all_rows)
        total_pages = max(1, (total_rows + page_size - 1) // page_size)
        has_more = page < total_pages

        chart_columns = result.get("columns")
        chart_rows = all_rows
        if result.get("success") and total_rows > page_size and count_sql:
            chart_result = await run_in_threadpool(
                pipeline.executor.execute,
                count_sql,
                pipeline.MAX_RESULT_ROWS,
            )
            if chart_result.get("success"):
                chart_columns = chart_result.get("columns")
                chart_rows = chart_result.get("rows") or []
        table_enriched = enrich_result(result.get("columns"), all_rows)
        chart_enriched = enrich_result(chart_columns, chart_rows)
        persisted_result = dict(result)
        persisted_result.update(table_enriched)
        persisted_result["row_count"] = total_rows
        persisted_result["base_sql"] = (
            result.get("base_sql") or result.get("generated_sql") or ""
        )

        response = SQLQueryResponse(
            success=result.get("success", False),
            conversation_id=request.conversation_id,
            message="Query completed successfully." if result.get("success") else result.get("error"),
            query_id=result.get("query_id"),
            validated_sql=result.get("base_sql") or result.get("generated_sql"),
            generated_sql=result.get("generated_sql"),
            base_sql=result.get("base_sql"),
            columns=table_enriched["columns"],
            rows=table_enriched["rows"],
            column_metadata=chart_enriched["column_metadata"],
            chart_data=chart_enriched["chart_data"] if result.get("success") else None,
            chart_error=chart_enriched["chart_error"] if result.get("success") else None,
            row_count=total_rows,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_more=has_more,
            cache_hit=result.get("cache_hit", False),
            error=result.get("error"),
            stage=result.get("stage")
        )

        try:
            _, conversation_id, query_id = save_query_turn(
                db=db,
                username=username,
                company_code=request.company_code,
                question=question,
                result=persisted_result,
                conversation_id=request.conversation_id,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                has_more=has_more,
            )
            response.conversation_id = conversation_id
            response.query_id = query_id
        except Exception:
            db.rollback()
            logger.exception("Failed to persist conversation history")
            raise HTTPException(
                status_code=503,
                detail="Query completed, but conversation history could not be saved.",
            )

        logger.info("Total API time: %.3fs", time.time() - api_start)

        return response

    except HTTPException:
        raise  # already the right shape, don't wrap it in a 500 below

    except Exception as e:
        logger.exception("Pipeline error")
        raise HTTPException(
            status_code=500,
            # Avoid leaking internal exception details (stack info, driver
            # error text) to the client -- log the full exception above
            # (logger.exception captures the traceback) and return a
            # generic message instead.
            detail="Internal error while generating SQL. Please try again."
        )