import json
import os
import time
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration & Local Ollama Client Setup
# ---------------------------------------------------------------------------
INPUT_FILE = "database_schema_fk_pk.json"
OUTPUT_FILE = "enriched_updated_sales_tables_schema.json"
MODEL_ID = "qwen2.5:7b"
TARGET_SCHEMA = "SG8283FINALTEST"

# Explicit whitelist of tables to process
TARGET_TABLES = {
    "SA_SALES_RETURN",
    "SA_SALES_INVOICE",
    "SA_SALES_ORDER",
    "SA_SALES_CHALAN",
    "IP_ITEM_MASTER_SETUP",
    "IP_ITEM_SPEC_SETUP",
    "IP_CATEGORY_CODE",
}

# Connect to local Ollama server endpoint (No API key needed)
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",  
)

# ---------------------------------------------------------------------------
# JSON Schema for Structured Output Validation
# ---------------------------------------------------------------------------
table_json_schema = {
    "type": "object",
    "properties": {
        "table_name": {"type": "string"},
        "module": {"type": "string"},
        "purpose": {"type": "string"},
        "used_for": {
            "type": "array",
            "items": {"type": "string"}
        },
        "primary_key": {
            "type": "array",
            "items": {"type": "string"}
        },
        "foreign_keys": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "column": {"type": "string"},
                    "references": {"type": "string"}
                },
                "required": ["column", "references"]
            }
        },
        "columns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "description": {"type": "string"}
                },
                "required": ["name", "type", "description"]
            }
        },
        "sample_queries": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": [
        "table_name",
        "purpose",
        "used_for",
        "primary_key",
        "foreign_keys",
        "columns",
        "sample_queries"
    ]
}

SYSTEM_INSTRUCTION = """
You are an expert Database Administrator and Data Architect specializing in Enterprise ERP Sales Analytics.
Analyze the raw database table schema and return structured JSON metadata.

For each table provided, generate:
- 'purpose': 1-sentence summary of what this table manages in the sales/reporting pipeline.
- 'used_for': 3-5 core functional areas relying on this data (e.g. Sales Reporting, Inventory Specs, VAT Tracking).
- 'columns': List of columns with a clear, 1-sentence business description for each.
- 'sample_queries': 3-4 natural language business reporting questions (e.g., "Generate sales report for last year", "Show item specs by category").

--- EXAMPLE OUTPUT FORMAT ---
{
  "table_name": "SA_SALES_INVOICE",
  "module": "sales",
  "purpose": "Stores line-item details for sales billing transactions.",
  "used_for": ["Sales Revenue Reporting", "Tax & VAT Audit", "Customer Billing", "Item Sales Analysis"],
  "primary_key": ["INVOICE_NO", "SERIAL_NO"],
  "foreign_keys": [{"column": "CUSTOMER_CODE", "references": "SA_CUSTOMER_SETUP"}],
  "columns": [
    {"name": "INVOICE_NO", "type": "VARCHAR2", "description": "Unique sales invoice document number"},
    {"name": "NET_SALES", "type": "NUMBER", "description": "Total revenue after discounts and taxes"}
  ],
  "sample_queries": ["Total sales revenue last month", "Sales breakdown by branch", "Top selling items"]
}

"""

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def load_existing_results() -> list:
    """Safely loads existing results even if the file was corrupted during an abrupt exit."""
    if not os.path.exists(OUTPUT_FILE):
        return []
    
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        print("Unfinished JSON structure detected from abrupt exit. Cleaning up file for auto-recovery...")
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        
        if raw.startswith("["):
            last_valid_bracket = raw.rfind("}")
            if last_valid_bracket != -1:
                cleaned_json = raw[:last_valid_bracket + 1] + "\n]"
                try:
                    recovered_data = json.loads(cleaned_json)
                    print(f" Recovered {len(recovered_data)} valid tables from saved file.")
                    return recovered_data
                except Exception:
                    pass
    return []

def save_single_table(table_result: dict, existing_records: list):
    existing_records.append(table_result)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(existing_records, f, indent=2, ensure_ascii=False)

def enrich_table_with_ollama(table_data: dict, raw_columns: list, max_retries: int = 3) -> dict:
    # Format all columns nicely for Ollama prompt
    formatted_cols = []
    for c in raw_columns:
        if isinstance(c, dict):
            formatted_cols.append({
                "name": c.get("column_name") or c.get("name"),
                "data_type": c.get("data_type", "VARCHAR2"),
                "length": c.get("length")
            })
        else:
            formatted_cols.append({"name": str(c), "data_type": "VARCHAR2"})

    prompt_content = f"""
    Analyze this Oracle table schema and generate structured metadata:

    Table Name: {table_data.get('table_name')}
    Module: sales
    Primary Keys: {json.dumps(table_data.get('primary_keys', table_data.get('primary_key', [])))}
    Foreign Keys: {json.dumps(table_data.get('foreign_keys', []))}
    Table Columns: {json.dumps(formatted_cols)}
    Note: While generating the JSON output, ensure key names and data types match the original exact schema (specially keep in mind that key name of "sample_queries" should be exact same). Return valid JSON only, no extra text.
    """

    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": prompt_content}
    ]

    for attempt in range(1, max_retries + 1):
        try:
            completion = client.chat.completions.create(
                model=MODEL_ID,
                messages=messages,
                temperature=0.2,
                response_format={
                    "type": "json_object", 
                    "json_schema": {
                        "name": "table_metadata",
                        "strict": True,
                        "schema": table_json_schema
                    }
                }
            )

            response_content = completion.choices[0].message.content
            return json.loads(response_content)

        except Exception as e:
            if attempt < max_retries:
                wait_time = attempt * 2
                print(f" [Attempt {attempt}/{max_retries}] Parsing/Local error: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise e

# ---------------------------------------------------------------------------
# Main Execution Loop
# ---------------------------------------------------------------------------
def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Could not find input file '{INPUT_FILE}'.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        db_data = json.load(f)

    # 1. Load already saved records
    enriched_tables = load_existing_results()
    
    processed_table_names = {
        t.get("table_name") for t in enriched_tables 
        if isinstance(t, dict) and t.get("table_name")
    }

    print(f" Total completed tables found in output file: {len(processed_table_names)}")

    # 2. Safely locate target schema: SG8283FINALTEST
    target_schema_obj = None
    for schema_obj in db_data.get("schemas", []):
        s_name = schema_obj.get("schema_name") or schema_obj.get("schema") or ""
        if str(s_name).strip().upper() == TARGET_SCHEMA:
            target_schema_obj = schema_obj
            break

    if not target_schema_obj:
        print(f"Warning: Schema '{TARGET_SCHEMA}' not found. Inspecting all available schemas...")
        schemas_to_process = db_data.get("schemas", [])
    else:
        schemas_to_process = [target_schema_obj]

    # 3. Iterate through schemas and process only the targeted 7 tables
    for schema_obj in schemas_to_process:
        tables = schema_obj.get("tables", [])
        current_schema_name = schema_obj.get("schema_name") or schema_obj.get("schema") or "UNKNOWN_SCHEMA"
        print(f"\n Inspecting {len(tables)} tables in schema: {current_schema_name}")

        for table in tables:
            table_name = table.get("table_name") or ""
            table_name_upper = table_name.strip().upper()

            # Strict check: only process tables in TARGET_TABLES
            if table_name_upper not in TARGET_TABLES:
                continue

            # Skip if already processed in prior runs
            if table_name in processed_table_names or table_name_upper in processed_table_names:
                print(f" Skipping '{table_name}' (already in {OUTPUT_FILE})")
                continue

            raw_columns = table.get("columns", [])
            print(f" Processing targeted table: {table_name_upper} ({len(raw_columns)} total columns)...")

            try:
                # Send full column metadata to Ollama
                enriched_data = enrich_table_with_ollama(table, raw_columns)
                save_single_table(enriched_data, enriched_tables)
                
                processed_table_names.add(table_name)
                processed_table_names.add(table_name_upper)
                print(f" Successfully saved '{table_name_upper}' to '{OUTPUT_FILE}'.")

            except Exception as e:
                print(f" Failed to process '{table_name_upper}': {e}")

    print(f"\n All done! Total {len(enriched_tables)} targeted sales tables enriched and saved in '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    main()