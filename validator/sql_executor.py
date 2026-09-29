import os
import sys
import logging

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from oracle.connection import OracleConnectionPool
logger = logging.getLogger("sql_executor")

class SQLExecutor:

    def __init__(self, oracle_pool=None):
        if oracle_pool is not None:
            self.db = oracle_pool
        else:
            logger.warning(
                "SQLExecutor created without a shared oracle_pool -- creating "
                "its own pool. In the running API this should be the pool "
                "created once in api/routes.py, passed through "
                "SQLGenerationPipeline(oracle_pool=...)."
            )
            self.db = OracleConnectionPool()
            self.db.start()

    def execute(self, sql: str, max_rows: int = None):
        """
        Executes a SELECT query and returns:
        {
            success: bool,
            columns: [],
            rows: [],
            error: None
        }
        """

        try:
            # Borrows a connection from the pool for just this call, and
            # returns it automatically on exit (success OR exception) --
            # no manual connect()/close() needed, and no risk of one
            # request's cleanup affecting another request's connection,
            # since each call gets its OWN connection from the pool.
            with self.db.connect() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(sql)
 
                    columns = [desc[0] for desc in cursor.description]
 
                    if max_rows is not None:
                        rows = cursor.fetchmany(max_rows)
                    else:
                        rows = cursor.fetchall()
 
                    return {
                        "success": True,
                        "columns": columns,
                        "rows": rows,
                        "row_count": len(rows),
                        "error": None,
                    }
                finally:
                    cursor.close()
 
        except Exception as e:
            logger.warning("SQL execution failed: %s", e)
 
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "error": str(e),
            }
 

if __name__ == "__main__":
    oc = SQLExecutor()
   
    query = '''SELECT im.ITEM_CODE, im.ITEM_EDESC, o.ORDER_NO, SUM(o.CALC_TOTAL_PRICE) AS TOTAL_PRICE
                FROM SA_SALES_ORDER o
                JOIN IP_ITEM_MASTER_SETUP im ON o.ITEM_CODE = im.ITEM_CODE AND o.COMPANY_CODE = im.COMPANY_CODE
                WHERE TRUNC(o.ORDER_DATE, 'MM') = TRUNC(SYSDATE, 'MM')
                AND o.DELETED_FLAG = 'N'
                AND o.COMPANY_CODE = '01'
                GROUP BY im.ITEM_CODE, im.ITEM_EDESC, o.ORDER_NO
                ORDER BY TOTAL_PRICE DESC'''
    results = oc.execute(query)
    print(results)
  