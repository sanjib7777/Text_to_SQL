import json
import os

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
INPUT_JSON_FILE = "enriched_updated_sales_tables_schema.json"
OUTPUT_DIR = "txt_sales_tables"  
COMBINED_TXT_FILE = "all_sales_tables_combined.txt"  


def format_table_to_txt(table_data: dict) -> str:
    """Formats a single table JSON dictionary into a clean text format for RAG embeddings."""
    table_name = table_data.get("table_name", "UNKNOWN")
    module = table_data.get("module", "General")  # Default to 'General' if module key is missing
    purpose = table_data.get("purpose", "N/A")

    # Format Business Usage (used_for)
    used_for_list = table_data.get("used_for", [])
    used_for_text = "\n".join([f"- {item}" for item in used_for_list]) if used_for_list else "N/A"

    # Format Primary Keys
    primary_keys = table_data.get("primary_key", [])
    pk_text = "\n".join(primary_keys) if primary_keys else "None"

    # Format Foreign Keys
    foreign_keys = table_data.get("foreign_keys", [])
    fk_lines = []
    for fk in foreign_keys:
        if isinstance(fk, dict):
            fk_lines.append(f"{fk.get('column', '')} -> {fk.get('references', '')}")
        else:
            fk_lines.append(str(fk))
    fk_text = "\n".join(fk_lines) if fk_lines else "None"

    # Format Columns
    columns = table_data.get("columns", [])
    col_blocks = []
    for col in columns:
        col_name = col.get("name", "")
        data_type = col.get("type", "")
        description = col.get("description", "")

        block = (
            f"{col_name}\n"
            f"Data Type : {data_type}\n"
            f"Description : {description}"
        )
        col_blocks.append(block)

    columns_text = "\n\n".join(col_blocks) if col_blocks else "None"

    # Format Sample Queries
    sample_queries = table_data.get("sample_queries", [])
    queries_text = "\n\n".join(sample_queries) if sample_queries else "None"

    # Build full text payload according to exact template specification
    formatted_text = f"""Table Name: {table_name}

Module: {module}

Purpose: {purpose}


Business Usage

This table is mainly used for:

{used_for_text}


Primary Key

{pk_text}


Foreign Keys

{fk_text}


Columns

{columns_text}


Sample Queries

{queries_text}"""

    return formatted_text


def convert_json_to_txt():
    if not os.path.exists(INPUT_JSON_FILE):
        print(f" Error: File '{INPUT_JSON_FILE}' does not exist.")
        return

    # Create output directory for individual text files
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(INPUT_JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Wrap in list if JSON file contains a single dict instead of a list of dicts
    if isinstance(data, dict):
        data = [data]

    all_formatted_texts = []

    for item in data:
        table_name = item.get("table_name", "UNKNOWN_TABLE")
        txt_content = format_table_to_txt(item)

        # 1. Save as individual file (e.g., txt_tables/ADDITIONAL_PREFERENCE.txt)
        individual_file_path = os.path.join(OUTPUT_DIR, f"{table_name}.txt")
        with open(individual_file_path, "w", encoding="utf-8") as out_f:
            out_f.write(txt_content)

        # 2. Append to combined collection list
        all_formatted_texts.append(txt_content)

    # Save a single merged text file separated by clear section dividers
    with open(COMBINED_TXT_FILE, "w", encoding="utf-8") as combined_f:
        combined_f.write("\n\n" + "=" * 80 + "\n\n".join(all_formatted_texts))

    print(f" Saved {len(data)} individual files in folder: '{OUTPUT_DIR}/'")
    print(f" Saved single combined file at: '{COMBINED_TXT_FILE}'")


if __name__ == "__main__":
    convert_json_to_txt()