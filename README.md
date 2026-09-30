# Text_to_SQL

Text_to_SQL is a FastAPI-based natural language to SQL service for sales reporting. It accepts a user question, retrieves relevant database schema and SQL examples from Qdrant, builds an LLM prompt, validates the generated SQL, executes it against Oracle, and stores application history in PostgreSQL.

The local development stack is fully containerized for the supporting services: Oracle, PostgreSQL, Redis, and Qdrant.

## Demo Video

A demo video for the project will be included in this repository. It will show the local services running, user login, natural language query submission, schema retrieval, generated SQL execution, and returned results.

## System Overview

The system uses four backing services:

- **Oracle**: source/business database used for login validation and generated SQL execution.
- **PostgreSQL**: application database used for users, conversations, messages, query records, and pagination history.
- **Qdrant**: vector database used for schema retrieval and SQL example retrieval.
- **Redis**: cache layer for query/cache data.

High-level request flow:

```text
Client
  -> FastAPI
  -> Oracle authentication
  -> PostgreSQL user/history initialization
  -> Qdrant schema + SQL example retrieval
  -> LLM SQL generation
  -> SQL validation
  -> Oracle query execution
  -> PostgreSQL conversation/query history
  -> Response
```

## Main Technologies

- Python 3.14
- FastAPI
- Uvicorn
- SQLAlchemy + psycopg
- Oracle `oracledb`
- Qdrant
- Redis
- Sentence Transformers using `BAAI/bge-m3`
- Docker Compose

## Local Services

The Docker Compose stack defines:

| Service | Container | Port | Purpose |
| --- | --- | --- | --- |
| Oracle | `txttosql-oracle` | `1521` | Local Oracle source DB |
| PostgreSQL | `txttosql-postgres` | `5432` | App state/history DB |
| Redis | `txttosql-redis` | `6379` | Cache |
| Qdrant | `txttosql-qdrant` | `6333`, `6334` | Vector search |

Start all services:

```bash
docker compose up -d
```

Start a single service:

```bash
docker compose up -d oracle
docker compose up -d postgres
docker compose up -d qdrant
docker compose up -d redis
```

Check service status:

```bash
docker compose ps
```

## Environment Configuration

The application reads configuration from `.env` through `settings.py`. Each developer should create a local `.env` file in the project root and provide values for the services they are running.

Oracle connection settings:

```env
ORACLE_HOST=
ORACLE_PORT=
ORACLE_SERVICE=
ORACLE_DB_USER=
ORACLE_DB_PASS=
ORACLE_INSTANT_CLIENT_LOC=
```

PostgreSQL connection settings:

```env
POSTGRES_HOST=
POSTGRES_PORT=
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
```

Qdrant and Redis settings:

```env
QDRANT_HOST=
QDRANT_PORT=

REDIS_HOST=
REDIS_PORT=
REDIS_DB=
REDIS_TTL=
```

LLM settings:

```env
OLLAMA_HOST=
OLLAMA_MODEL=
LLM_PROVIDER=
LLM_PLATFORM=
NARAROUTER_BASE_URL=
NARAROUTER_API_KEY=
XKIRO_BASE_URL=
XKIRO_API_KEY=
```

When using the provided Docker Compose stack locally, these values should match the service names, ports, usernames, and passwords defined in `docker-compose.yml`.

## Database Seeding

### Oracle

Oracle is seeded from:

```text
oracle/seed/001_core_sales_demo.sql
```

The seed creates tables in the `SUYOG` schema inside `FREEPDB1`:

```sql
ALTER SESSION SET CONTAINER = FREEPDB1;
ALTER SESSION SET CURRENT_SCHEMA = SUYOG;
```

Currently seeded Oracle tables:

- `SC_APPLICATION_USERS`
- `IP_ITEM_MASTER_SETUP`
- `SA_SALES_ORDER`

Seeded login user:

```text
username: suyog
password: Test@123
company_code: 01
```

The Oracle init seed only runs when the Oracle data volume is first created. To force a fresh Oracle seed:

```bash
docker compose down
docker volume rm txttosql_oracle-data
docker compose up -d oracle
```

### PostgreSQL

PostgreSQL stores app-level user and conversation state.

Create/update app tables:

```bash
.venv/bin/python -m postgres_db.setup_db
```

Created tables:

- `users`
- `user_branches`
- `conversations`
- `messages`
- `query_records`

Optional local app-user seed:

```bash
.venv/bin/python -m postgres_db.seed_login_user
```

## Qdrant Indexing

Qdrant powers retrieval-augmented SQL generation.

Collections used by the application:

| Collection | Source | Purpose |
| --- | --- | --- |
| `sales_schema` | `sales/enriched_updated_sales_tables_schema.json` + generated text files | Table-level schema retrieval |
| `sql_examples` | `vector_db/example.json` | Similar SQL example retrieval |
| `sales_columns` | `sales/enriched_updated_sales_tables_schema.json` | Column-level retrieval/resolution |
| `semantic_cache` | runtime cache data | Semantic query cache |

Generate table text files from schema JSON:

```bash
cd sales
python3 json_to_text.py
cd ..
```

Create Qdrant collections:

```bash
.venv/bin/python - <<'PY'
from vector_db.qdrant_test import QdrantDB
from vector_db.config import SCHEMA_COLLECTION, SQL_EXAMPLES_COLLECTION, EMBEDDING_DIMENSION

qdrant = QdrantDB()
qdrant.create_collection(SCHEMA_COLLECTION, vector_size=EMBEDDING_DIMENSION)
qdrant.create_collection(SQL_EXAMPLES_COLLECTION, vector_size=EMBEDDING_DIMENSION)
print([c.name for c in qdrant.get_client().get_collections().collections])
PY
```

Insert table schema data:

```bash
cd vector_db
../.venv/bin/python insert_into_qdrant.py
cd ..
```

Insert SQL examples:

```bash
cd vector_db
../.venv/bin/python insert_sql_example.py
cd ..
```

Expected indexed counts:

```text
sales_schema: 9 points
sql_examples: 100 points
```

## API Endpoints

The API is mounted under `/api`.

Health check:

```bash
curl http://127.0.0.1:8000/api/health
```

Login:

```bash
curl -X POST "http://127.0.0.1:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "suyog",
    "password": "Test@123"
  }'
```

Query:

```bash
curl -X POST "http://127.0.0.1:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me the sales orders, sorted by order date, along with the order number, order date, customer, item, and total price.",
    "username": "suyog",
    "company_code": "01",
    "conversation_id": null,
    "query_id": null,
    "validated_sql": null,
    "model_name": "qwen2.5-coder:14b",
    "llm_provider": "ollama",
    "platform": "naraRouter",
    "page": 1,
    "page_size": 100
  }'
```

Example evaluation pair:

```json
{
  "query": "Show me the sales orders, sorted by order date, along with the order number, order date, customer, item, and total price.",
  "true_sql": "SELECT o.ORDER_NO, o.ORDER_DATE, o.CUSTOMER_CODE, o.ITEM_CODE, o.CALC_TOTAL_PRICE FROM SA_SALES_ORDER o WHERE o.COMPANY_CODE = '01' ORDER BY o.ORDER_DATE"
}
```

## Running the API

Install dependencies:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Run FastAPI:

```bash
.venv/bin/python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

If port `8000` is already in use, either stop the process using it or run on another port:

```bash
.venv/bin/python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

## Troubleshooting

### `Authentication service is temporarily unavailable`

This means Oracle authentication failed before the app could validate the user.

Check:

- Oracle container is running and healthy.
- App config points to `localhost:1521/FREEPDB1`.
- Tables exist under the `SUYOG` schema.
- `SC_APPLICATION_USERS` contains `suyog` / `Test@123`.
- Uvicorn was restarted after config changes.

### `History service is temporarily unavailable`

This means Oracle login succeeded, but PostgreSQL user/history initialization failed.

Run:

```bash
docker compose up -d postgres
.venv/bin/python -m postgres_db.setup_db
```

### Schema retrieval fails with `httpx` connection errors

This usually means Qdrant is not running.

Run:

```bash
docker compose up -d qdrant
curl http://127.0.0.1:6333/healthz
```

If Qdrant is healthy but retrieval returns nothing, re-run the indexing scripts.

### Qdrant client/server version warning

You may see:

```text
Qdrant client version 1.19.1 is incompatible with server version 1.12.6
```

The current inserts work despite the warning, but for long-term stability the Docker image version should be aligned more closely with the installed `qdrant-client` package.

## Project Structure

```text
api/                  FastAPI routes and request handling
cache/                Redis cache helpers
conversational_model/ Conversation/context helpers
llm/                  LLM client/router code
oracle/               Oracle connection and local seed scripts
postgres_db/          PostgreSQL config, models, setup, seed scripts
prompts/              Prompt construction and SQL correction prompts
retriever/            Qdrant schema/example/column retrieval
sales/                Schema metadata and text conversion
services/             SQL generation pipeline and supporting services
validator/            SQL validation/execution helpers
vector_db/            Qdrant collection/indexing/embedding scripts
```

## Notes

- Oracle DB credentials are not the same as application login credentials.
- Local Oracle DB user is `suyog` / `suyogTest`.
- Application login user is `suyog` / `Test@123`.
- PostgreSQL stores app state; Oracle stores business/login/source data.
- Qdrant stores schema and SQL example embeddings; it does not store Oracle table rows.
