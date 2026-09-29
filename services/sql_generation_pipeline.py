import logging
from vector_db.embeddings import EmbeddingModel
from retriever.schema_retriever import SchemaRetriever
# from retriever.column_retriever import ColumnRetriever
from retriever.sql_example_retriever import SQLExampleRetriever
# from services.column_extractor import ColumnExtractor
# from services.table_selector import TableSelector
from services.schema_column_lookup import SchemaColumnLookup
from prompts.prompt_builder import PromptBuilder
from services.get_table_enriched import TableMetadataRetriever
from llm.ollama_client import OllamaClient
from llm.llm_router import LLMFactory
from settings import LLM_PLATFORM
from services.query_intent_extractor import QueryIntentExtractor
from validator.sql_validator import SQLValidator

from validator.sql_executor import SQLExecutor
from services.current_date_context import CurrentDateContext
from cache.cache_manager import CacheManager

from validator.column_resolver import ColumnResolver
from prompts.sql_correction_prompt import SQLCorrectionPrompt
from conversational_model.conversation_memory import ConversationMemory
from conversational_model.contextual_question import ContextualQuestionBuilder
from services.row_limit_handler import RowLimitHandler
from api.session_context import SessionContext
import re
logger = logging.getLogger("sql_generation_pipeline")
class SQLGenerationPipeline:

    def __init__(self, oracle_pool=None):
        self.embedding_model = EmbeddingModel()
        self.conversation_memory = ConversationMemory(max_messages=3)
        self.contextual_question_builder = ContextualQuestionBuilder()

        self.schema_retriever = SchemaRetriever()
        self.column_resolver = ColumnResolver()
        # self.column_extractor = ColumnExtractor()
        
        self.schema_column_lookup = SchemaColumnLookup()
        

        # self.column_retriever = ColumnRetriever()

        self.example_retriever = SQLExampleRetriever()

        # self.semantic_cache = SemanticCache()

        self.prompt_builder = PromptBuilder()

        self.llm = OllamaClient()
        self.query_intent_extractor = QueryIntentExtractor(self.llm)
        # self.column_extractor = ColumnExtractor(self.llm)

        self.metadata_retriever = TableMetadataRetriever()

        self.validator = SQLValidator()

        self.row_limit_handler = RowLimitHandler()

        try:
            self.executor = SQLExecutor(oracle_pool=oracle_pool) if oracle_pool is not None else SQLExecutor()
        except TypeError:
            # SQLExecutor doesn't accept oracle_pool yet -- update it to pull
            # connections from the pool instead of a single shared
            # OracleConnection (see oracle_pool.py) to actually get the
            # concurrency benefit. Falling back so this doesn't break today.
            logger.warning(
                "SQLExecutor does not yet accept oracle_pool -- falling back to its "
                "default construction. Update SQLExecutor to use the pooled connection."
            )
            self.executor = SQLExecutor()

        self.date_context = CurrentDateContext()

        self.cache_manager = CacheManager()

        self.MAX_SQL_RETRIES = 4

        self.MAX_RESULT_ROWS = 1000

    ##############################################################

    def clean_sql(self, sql):

        if not sql:
            return ""

        sql = sql.strip()

      
        if sql.startswith("```sql"):
            sql = sql[len("```sql"):]

        elif sql.startswith("```"):
            sql = sql[len("```"):]

        if sql.endswith("```"):
            sql = sql[:-3]

        sql = sql.strip()

        # Remove trailing semicolon
        if sql.endswith(";"):
            sql = sql[:-1].strip()

        return sql


    def extract_invalid_column(self, validation_error):

        pattern = r"Column ['\"]([^'\"]+)['\"] does not exist"

        match = re.search(
            pattern,
            validation_error,
            re.IGNORECASE
        )

        if match:
            return match.group(1)

        return None

    def _get_session_key(self, session: "SessionContext") -> str:
        if session is None:
            return "default"

        session_id = getattr(session, "session_id", None)
        if session_id:
            return str(session_id)

        company_code = getattr(session, "company_code", None) or "unknown"

        return str(company_code)

    def run(
        self,
        user_query,
        session: "SessionContext",
        model_name,
        llm_provider,
        platform=None,
        page=1,
        page_size=100,
    ):

        ##########################################################
        # STEP 0 : CHECK REDIS CACHE
        ##########################################################

        print("=" * 80)
        print("STEP 0 : Checking Redis Cache")
        print("=" * 80)

        session_key = self._get_session_key(session)

        try:

            cached_result = self.cache_manager.get_cache_by_query(
                user_query,
                scope=session_key,
            )

            if cached_result:

                cached_sql = cached_result.get(
                    "base_sql",
                    cached_result.get("sql", "")
                )

                if page > 1:
                    paginated_sql = self.row_limit_handler.apply_pagination(
                        cached_sql,
                        page=page,
                        page_size=page_size,
                    )
                    page_result = self.executor.execute(paginated_sql)

                    if not page_result["success"]:
                        return {
                            "success": False,
                            "stage": "oracle",
                            "error": page_result["error"],
                            "generated_sql": paginated_sql,
                            "base_sql": cached_sql,
                        }

                    return {
                        "success": True,
                        "cache_hit": True,
                        "generated_sql": paginated_sql,
                        "base_sql": cached_sql,
                        "columns": page_result["columns"],
                        "rows": page_result["rows"],
                        "row_count": page_result["row_count"],
                    }

                print("CACHE HIT")
                print("Returning result from Redis.")

                return {
                    "success": True,
                    "cache_hit": True,

                    "generated_sql": cached_result["sql"],

                    "base_sql": cached_result.get(
                        "base_sql",
                        cached_result["sql"]
                    ),

                    "columns": cached_result["columns"],

                    "rows": cached_result["rows"],

                    "row_count": cached_result["row_count"],

                    # "cache_key": cached_result["cache_key"]
                }

            print("CACHE MISS")

        except Exception as e:

            # Redis failure should not stop the application
            print(f"Redis cache check failed: {e}")

        last_user_message = self.conversation_memory.get_last_user_message(
            session_key
        )

        contextual_question = (
            self.contextual_question_builder.build(
                question=user_query,
                history=last_user_message
            )
        )
        print("contextual question is ", contextual_question)
        
        if not contextual_question or re.match(r"^\s*I don't know\b", contextual_question, re.IGNORECASE) or len(contextual_question.strip()) < 3:
            contextual_question = user_query
        # searching for semantic cache

        query_vector = self.embedding_model.embed(contextual_question)

        # print("query vector", query_vector)

        # cache_result = self.semantic_cache.search(
        #     query_vector=query_vector
        # )

        # if cache_result:

        #     print("\nSemantic Cache HIT")

        #     cache_key = cache_result["cache_key"]

        #     # Now retrieve actual SQL + data from teu
        #     cached_data = self.cache_manager.get_cache(cache_key)

        #     if cached_data:

        #         return {
        #             "success": True,
        #             "cache_hit": True,
        #             # "similarity_score": cache_result["similarity_score"],
        #             "generated_sql": cached_data["sql"],
        #             "columns": cached_data["columns"],
        #             "rows": cached_data["rows"],
        #             "row_count": cached_data["row_count"]
        #         }

        #     print("Qdrant matched but Redis data was not found.")

        # else:

        #     print("\nSemantic Cache MISS")


        # ============================================
        # STEP 1: Extract query intent
        # ============================================

        query_intent = (
            self.query_intent_extractor.extract(
                user_query
            )
        )

        print(
            "Query Intent:",
            query_intent
        )

        print("=" * 80)
        print("STEP 1 : Retrieving Schema")
        print("=" * 80)

        retrieved_schema = self.schema_retriever.retrieve(
            query_vector=query_vector,
            top_k=5
        )
        # print("retrieved schema is ", retrieved_schema)

        # retrieved_tables = [tbl["table_name"] for tbl in retrieved_schema]

        # print(f"Retrieved {len(retrieved_schema)} tables")

        # columns = self.column_extractor.extract_columns(
        #     user_query
        # )


        # print(
        #     "Extracted columns:",
        #     columns
        # )

        # lookup = SchemaColumnLookup()

        # column_table_map = (
        #     lookup.find_tables_for_columns(
        #         columns
        #     )
        # )

        # print(
        #     "Column Table Map:",
        #     column_table_map
        # )

        # selected_tables = (
        #     TableSelector.select_tables(
        #         column_table_map,
        #         retrieved_tables
        #     )
        # )

        # print(
        #     "Selected Tables:",
        #     selected_tables
        # )


        # filtered_schema_table = self.metadata_retriever.get_tables(
        #     selected_tables
        # )

        ##########################################################

        # print("\n" + "=" * 80)
        # print("STEP 2 : Retrieving Columns")
        # print("=" * 80)

        # retrieved_columns = self.column_retriever.retrieve(
        #     query_vector=query_vector,
        #     top_k=20
        # )

        # print(f"Retrieved {len(retrieved_columns)} columns")

        # ##########################################################

        print("\n" + "=" * 80)
        print("STEP 3 : Retrieving SQL Examples")
        print("=" * 80)

        retrieved_examples = self.example_retriever.retrieve(
            query_vector=query_vector,
            top_k=5
        )

        # print(f"Retrieved {len(retrieved_examples)} examples")

        ##########################################################

        print("\n" + "=" * 80)
        print("STEP 4 : Building Prompt")
        print("=" * 80)

        # date_context, date_range  = self.date_context.get_context(contextual_question)
        
        # print(f"Current Date Context: {date_context}")

        messages = self.prompt_builder.build_messages(
            user_question=contextual_question,
            session=session,
            retrieved_schema=retrieved_schema,
            query_intent=query_intent,
            retrieved_examples=retrieved_examples,
            # current_date_context=date_context,

        )

        print("Sanjib Prompt has been created.................")

        system_prompt =  messages[0]["content"]
        # print(messages[0]["content"])

        print("=" * 100)
        user_prompt = messages[1]["content"] 
        # print(messages[1]["content"]) 

        ##########################################################

        print("\n" + "=" * 80)
        print("STEP 5 : Generating SQL")
        print("=" * 80)

        llm = LLMFactory.get_llm(
            model_name=model_name,
            llm_provider=llm_provider,
            platform=platform or LLM_PLATFORM
        )

        generated_sql = llm.generate(
            user_prompt=user_prompt,
            system_prompt=system_prompt
        )

        # generated_sql = self.llm.chat_with_model(user_prompt, system_prompt)

        generated_sql = self.clean_sql(generated_sql)
        initial_generated_sql = generated_sql

        print("\n Initial Generated SQL\n")
        print(generated_sql)



        ##########################################################

        print("\n" + "=" * 80)
        print("STEP 6 : Validating SQL")
        print("=" * 80)

        sql_valid = False
        validation_message = ""

        for attempt in range(self.MAX_SQL_RETRIES + 1):

            print(
                f"\nSQL Validation Attempt "
                f"{attempt + 1}/{self.MAX_SQL_RETRIES + 1}"
            )

            date_filter = query_intent.get("date_filter", {})

            if date_filter.get("required", True):

                is_valid, message = self.validator.validate(
                    sql=generated_sql,
                    retrieved_schema=retrieved_schema,
                    expected_start_date=date_filter.get("start_date"),
                    expected_end_date=date_filter.get("end_date"),
                    session=session
                )

            else:

                is_valid, message = self.validator.validate(
                    sql=generated_sql,
                    retrieved_schema=retrieved_schema,
                    session=session
                )

            column_resolution = None
            if not is_valid:

                invalid_column = self.extract_invalid_column(
                    message
                )

                # -----------------------------------------------
                # COLUMN RESOLUTION
                # -----------------------------------------------

                if invalid_column:

                    print(
                        f"\nInvalid column detected: "
                        f"{invalid_column}"
                    )

                    column_resolution = (
                        self.column_resolver.resolve(
                            invalid_column
                        )
                    )

                    print(
                        "\nColumn Resolver Result:"
                    )

                    print(column_resolution)

            if is_valid:

                print("SQL Validation Successful")

                sql_valid = True
                break

            print("SQL Validation Failed")
            print(message)

            validation_message = message

            # ------------------------------------------------------
            # Don't retry after final attempt
            # ------------------------------------------------------

            if attempt >= self.MAX_SQL_RETRIES:

                break

            print("\nSending validation error back to LLM...")

            correction_prompt = SQLCorrectionPrompt.build(
                user_question=contextual_question,
                generated_sql=generated_sql,
                validation_error=validation_message,
                retrieved_schema=retrieved_schema,
                column_resolution=column_resolution
            )

            generated_sql = llm.generate(
                user_prompt=correction_prompt,
                system_prompt=system_prompt
            )

            generated_sql = self.clean_sql(generated_sql)

            print("\nCorrected SQL:\n")
            print(generated_sql)

            
        if not sql_valid:

            return {
                "success": False,
                "stage": "validator",
                "error": validation_message,
                "generated_sql": generated_sql,
                "base_sql": generated_sql,
                "final_generated_sql": generated_sql
            }
        # ==========================================================
        # APPLY USER REQUESTED ROW LIMIT
        # ==========================================================

        print("\n" + "=" * 80)
        print("STEP 7 : Applying Row Limit")
        print("=" * 80)

        original_sql = generated_sql
        
        # print("original sql ",original_sql)
        row_limit = query_intent.get(
            "row_limit",
            {}
        )
        if row_limit.get("required", True):
            print('Applying row limit as per user request')

            limit = row_limit.get("value")

            generated_sql = self.row_limit_handler.apply_limit(
                generated_sql=generated_sql,
                limit=limit
            )

            print("Generated SQL after applying row limit:\n")
            print(generated_sql)

        base_sql = generated_sql
        generated_sql = self.row_limit_handler.apply_pagination(
            base_sql,
            page=page,
            page_size=page_size,
        )
        
        
        ##########################################################

        print("\n" + "=" * 80)
        print("STEP 7 : Executing SQL")
        print("=" * 80)

        result = self.executor.execute(generated_sql, max_rows=self.MAX_RESULT_ROWS)

        if not result["success"]:

            print(result["error"])

            return {
                "success": False,
                "stage": "oracle",
                "error": result["error"],
                "generated_sql": generated_sql,
                "base_sql": base_sql,
                "final_generated_sql": generated_sql
            }

        #storing into conversational memory
        self.conversation_memory.add_message(
            session_id=session_key,
            role="user",
            content=user_query
        )

        self.conversation_memory.add_message(
            session_id=session_key,
            role="assistant",
            content=(
                f"Generated SQL:\n{generated_sql}\n"
                f"Returned {result['row_count']} rows."
            )
        )

        ##########################################################
        # STEP 7 : STORE SUCCESSFUL RESULT IN REDIS
        ##########################################################
        print("\n" + "=" * 80)
        print("STEP 7 : Storing Result in Redis")
        print("=" * 80)

        try:

            cache_key = self.cache_manager.save_cache(

                query=user_query,

                sql=generated_sql,

                columns=result["columns"],

                rows=result["rows"],

                execution_time=None,

                base_sql=base_sql,

                scope=session_key,
            )

            print("Successfully stored in Redis")

            print(f"Cache Key : {cache_key}")

        except Exception as e:

            print(f"Redis cache storage failed: {e}")

            cache_key = None

        # self.semantic_cache.store(
        #     query=user_query,
        #     query_vector=query_vector,
        #     cache_key=cache_key
        # )

        return {
            "success": True,
            "generated_sql": generated_sql,
            "base_sql": base_sql,
            "final_generated_sql": generated_sql,
            "columns": result["columns"],
            "rows": result["rows"],
            "row_count": result["row_count"],
        }


