import atexit
from contextlib import contextmanager
import os
import concurrent.futures
import oracledb
import time

from oracle.config import (
    ORACLE_SERVICE,
    ORACLE_HOST,
    ORACLE_PORT,
    ORACLE_DB_USER,
    ORACLE_DB_PASS,
    ORACLE_INSTANT_CLIENT_LOC,
)


class OracleConnectionPool:
    def __init__(self, min_connections: int = 2, max_connections: int = 10, increment: int = 1):
        self.user = ORACLE_DB_USER
        self.password = ORACLE_DB_PASS
        self.host = ORACLE_HOST
        self.port = ORACLE_PORT
        self.service = ORACLE_SERVICE
        self.instant_client_loc = ORACLE_INSTANT_CLIENT_LOC
        self.connection = None
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.increment = increment
        self.pool = None  

    def _build_dsn(self):
        if not self.host or not self.port:
            raise ValueError("Oracle host and port must be configured")

        return oracledb.makedsn(self.host, self.port, service_name=self.service)

    def start(self):
        if self.instant_client_loc and os.path.exists(self.instant_client_loc):
            oracledb.init_oracle_client(lib_dir=self.instant_client_loc)
            print("Thin mode:", oracledb.is_thin_mode())

        dsn = self._build_dsn()
        print(f"Attempting Oracle connection to {self.host}:{self.port}/{self.service}")

        try:
            self.pool = oracledb.create_pool(
                user=self.user,
                password=self.password,
                dsn=dsn,
                min=self.min_connections,
                max=self.max_connections,
                increment=self.increment
            )
            print("Successfully created Oracle connection pool")
        except Exception as exc:
            raise RuntimeError(
                f"Unable to create Oracle connection pool at {self.host}:{self.port}/{self.service}. "
                f"Check the listener, service name, and credentials. Original error: {exc}"
            ) from exc
        atexit.register(self.close)

    
    def connect(self):
        if self.pool is None:
            raise RuntimeError("Pool not started. Call start() first (e.g. on app startup).")
        return self.pool.acquire()
    
        # if self.instant_client_loc and os.path.exists(self.instant_client_loc):
        #     oracledb.init_oracle_client(lib_dir=self.instant_client_loc)
        #     print("Thin mode:", oracledb.is_thin_mode())

        # dsn = self._build_dsn()
        # print(f"Attempting Oracle connection to {self.host}:{self.port}/{self.service}")

        # try:
        #     self.connection = oracledb.connect(user=self.user, password=self.password, dsn=dsn)
        #     print("Successfully connected to Oracle Database")
        # except Exception as exc:
        #     raise RuntimeError(
        #         f"Unable to connect to Oracle database at {self.host}:{self.port}/{self.service}. "
        #         f"Check the listener, service name, and credentials. Original error: {exc}"
        #     ) from exc

    def execute_query(self, query, params=None, max_rows=None):
        """Convenience one-shot helper mirroring the old OracleConnection
        API, but pulling a connection from the pool per call instead of
        reusing one shared connection. Safe to call concurrently from
        multiple threads/requests.
 
        max_rows: if set, caps rows fetched (safety limit -- without this,
        a single runaway or overly-broad generated query can pull an
        unbounded result set into memory, and that risk multiplies under
        concurrent load since several large fetches can happen at once).
        """
        with self.connect() as conn:
            cur = conn.cursor()
            try:
                cur.execute(query, params or {})
                if max_rows is not None:
                    rows = cur.fetchmany(max_rows)
                else:
                    rows = cur.fetchall()
                columns = [d[0] for d in cur.description] if cur.description else []
                return {"columns": columns, "rows": rows}
            finally:
                cur.close()

    def close(self):
        if self.pool is not None:
            try:
                self.pool.close()
                print("Oracle connection pool closed")
            except Exception as e:
                print(f"Error closing Oracle connection pool: {e}")
            finally:
                self.pool = None

#executing test query
# if __name__ == "__main__":
#     # 1. Instantiate and start the pool
#     oracle_pool = OracleConnectionPool(min_connections=2, max_connections=5)
#     print("--- Starting Oracle Pool ---")
#     oracle_pool.start()

#     # 2. Sequential Query Test using convenience execute_query()
#     print("\n--- Test 1: Sequential Queries ---")
#     queries = [
#         ("SELECT o.ORDER_NO, o.ORDER_DATE, o.CUSTOMER_CODE, o.ITEM_CODE, o.CALC_TOTAL_PRICE FROM SA_SALES_ORDER o WHERE o.COMPANY_CODE = '01' AND o.BRANCH_CODE = '01.01' AND o.DELETED_FLAG = 'N' ORDER BY o.ORDER_DATE", None, None),
#         ("SELECT i.SALES_NO, i.SALES_DATE, i.CUSTOMER_CODE, i.ITEM_CODE, i.CALC_TOTAL_PRICE FROM SA_SALES_INVOICE i WHERE i.COMPANY_CODE = '01' AND i.BRANCH_CODE = '01.02' AND i.DELETED_FLAG = 'N' ORDER BY i.SALES_DATE", None, None),
#         ("SELECT c.CHALAN_NO, c.CHALAN_DATE, c.CUSTOMER_CODE, c.ITEM_CODE, c.CALC_TOTAL_PRICE FROM SA_SALES_CHALAN c WHERE c.COMPANY_CODE = '01' AND c.BRANCH_CODE = '01.03' AND c.DELETED_FLAG = 'N' ORDER BY c.CHALAN_DATE", None, None),
#         ("SELECT t.ORDER_MONTH, t.TOTAL_REVENUE, LAG(t.TOTAL_REVENUE) OVER (ORDER BY t.ORDER_MONTH) AS PREVIOUS_MONTH_REVENUE, t.TOTAL_REVENUE - LAG(t.TOTAL_REVENUE) OVER (ORDER BY t.ORDER_MONTH) AS GROWTH_AMOUNT FROM (SELECT TO_CHAR(o.ORDER_DATE, 'YYYY-MM') AS ORDER_MONTH, SUM(o.CALC_TOTAL_PRICE) AS TOTAL_REVENUE FROM SA_SALES_ORDER o WHERE o.COMPANY_CODE = '01' AND o.BRANCH_CODE = '01.04' AND o.DELETED_FLAG = 'N' AND TRUNC(o.ORDER_DATE) >= TO_DATE('2025-01-01', 'YYYY-MM-DD') AND TRUNC(o.ORDER_DATE) < TO_DATE('2026-01-01', 'YYYY-MM-DD') GROUP BY TO_CHAR(o.ORDER_DATE, 'YYYY-MM')) t ORDER BY t.ORDER_MONTH", None, None) # Capped at 5 rows
#     ]
#     total_seq_start = time.perf_counter()
#     for q, params, max_r in queries:
#         try:
#             result = oracle_pool.execute_query(q, params=params, max_rows=max_r)
#             print(f"\nQuery: {q}")
#             # print(f"Columns: {result['columns']}")
#             # print(f"Rows: {result['rows']}")
#         except Exception as e:
#             print(f"Query failed: {e}")

#     total_seq_duration = time.perf_counter() - total_seq_start
#     print(f"\nTotal Sequential Duration: {total_seq_duration:.4f} seconds")

#     # 3. Concurrent Query Test using ThreadPoolExecutor
#     print("\n--- Test 2: Concurrent Queries Across Pool ---")
    
#     def worker_query(worker_id):
#         # Simulate simultaneous DB hits across distinct connections in the pool
#         query = "SELECT :id AS worker_id, SYSDATE FROM DUAL"
#         res = oracle_pool.execute_query(query, params={"id": worker_id})
#         return res['rows'][0]

#     concurrent_start = time.perf_counter()

#     with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
#         futures = [executor.submit(worker_query, i) for i in range(1, 5)]
#         for future in concurrent.futures.as_completed(futures):
#             try:
#                 print("Worker result:", future.result())
#             except Exception as e:
#                 print("Worker error:", e)

#     concurrent_duration = time.perf_counter() - concurrent_start
#     print(f"\nTotal Concurrent Batch Duration: {concurrent_duration:.4f} seconds")

#     # 4. Cleanup
#     print("\n--- Closing Pool ---")
#     oracle_pool.close()

# try:
#     with open('conn.txt', 'r', encoding='utf-8') as file:
#         port_service_host = json.load(file)
# except Exception as exc:
#     print(f"Error: Could not read conn.txt file: {exc}")

# if port_service_host:
#     lib_dir = port_service_host.get("instant_client_loc")
#     print("lib_dir is ", lib_dir)
#     print("port_service_host =", port_service_host)
#     print("lib_dir =", repr(lib_dir))
#     print("exists =", os.path.exists(lib_dir) if lib_dir else "lib_dir is None")

# if lib_dir and os.path.exists(lib_dir):
#     # print("sanjib shah")
#     print(os.listdir(lib_dir))
#     try:
#         oracledb.init_oracle_client(lib_dir=lib_dir)

#         print("Thin mode:", oracledb.is_thin_mode())
#     except Exception as exc:
#         print(f"Oracle client initialization failed: {exc}")
# else:
#     print("Oracle instant client path is not configured or does not exist")

# dsn = oracledb.makedsn(
#     port_service_host.get("host"),
#     port_service_host.get("port"),
#     service_name=port_service_host.get("service")
# )

# connection = oracledb.connect(
#     user="ALLMODULE",
#     password="ALLMODULE",
#     dsn=dsn,
# )

# print("successfully connected to Oracle Database")
# cursor = connection.cursor()
# cursor.execute("""
#     SELECT * 
#     FROM HRIS_SALARY_SHEET_EMP_DETAIL 
#     WHERE ROWNUM <= 5
# """)

# row = cursor.fetchall()

# print("salary sheet data:")
# for r in row:
#     print(r)

# cursor.close()
# connection.close()

