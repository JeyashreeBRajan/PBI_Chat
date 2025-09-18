import requests
import logging

# -----------------------------
# CONFIG
# -----------------------------
API_URL = "http://127.0.0.1:8000/api/powerbi/query-natural"
WORKSPACE = "PBI_Automation_Testing"
DATASET = "SalesAnalysis"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# -----------------------------
# FUNCTION: Get DAX (or suggestion) from API
# -----------------------------
def fetch_dax_from_api(question: str, table_schema=None, retries=1) -> dict:
    """
    Call FastAPI query-natural endpoint to get DAX or suggestions.
    Automatically passes derived columns in schema.
    """
    from app.schema_fetcher import get_or_load_schema  # import the schema module

    if table_schema is None:
        table_schema = get_or_load_schema(WORKSPACE, DATASET)

    payload = {
        "question": question,
        "connection_str": {
            "workspace": WORKSPACE,
            "dataset": DATASET
        },
        "table_schema": table_schema,
        "rules": [
            "Aggregate numeric columns using SUM",
            "Use GROUPBY or SUMMARIZE as needed",
            "Use derived date columns (Year, Month, Quarter) if available",
            "Return valid executable DAX only"
        ]
    }

    for attempt in range(retries + 1):
        try:
            logger.info(f"🟢 Sending question to API: {question}")
            response = requests.post(API_URL, json=payload)
            response.raise_for_status()

            data = response.json()
            if "dax" in data and data["dax"].strip():
                logger.info(f"✅ API Response: {data}")
                return data
            else:
                logger.warning(f"⚠️ No DAX returned. Attempt {attempt + 1}")
        except Exception as e:
            logger.error(f"❌ API call failed: {e}")

    return {"error": "Failed to generate DAX after retries"}
#---------------------------------
#Helper function
#---------------------------------
import re

def fix_dax_grouping(dax: str) -> str:
    """
    Fix common Groq mistakes in DAX before execution.
    - YEAR() → [Year]
    - Remove redundant ADDCOLUMNS when the same column already exists
    """
    import re

    # YEAR() → [Year]
    dax = re.sub(r"YEAR\(([^)]+)\)", r"\1.[Year]", dax, flags=re.IGNORECASE)
    # MONTH() → [Month]
    dax = re.sub(r"MONTH\(([^)]+)\)", r"\1.[Month]", dax, flags=re.IGNORECASE)
    # QUARTER() → [Quarter]
    dax = re.sub(r"QUARTER\(([^)]+)\)", r"\1.[Quarter]", dax, flags=re.IGNORECASE)

    # 🔹 Simplify: Remove CALCULATETABLE/ADDCOLUMNS if they're only adding a duplicate Year
    dax = re.sub(
        r"EVALUATE\s+CALCULATETABLE\(\s*ADDCOLUMNS\(\s*SUMMARIZECOLUMNS\((.*?)\),\s*\"Year\",\s*[^)]+\)\s*\)",
        r"EVALUATE\nSUMMARIZECOLUMNS(\1)",
        dax,
        flags=re.DOTALL | re.IGNORECASE
    )

    return dax


def clean_dax(dax_query: str) -> str:
    """
    Extracts only the valid DAX part from the response by:
    - Removing any trailing notes or comments
    - Keeping only lines that start from EVALUATE or DEFINE
    """
    # Keep only lines before any "Note:" or markdown-style explanation
    dax_lines = []
    for line in dax_query.splitlines():
        if line.strip().lower().startswith("note:"):
            break
        dax_lines.append(line)
    
    dax_clean = "\n".join(dax_lines).strip()
    
    # Optional: Remove accidental markdown fences like ```DAX
    dax_clean = re.sub(r"^```.*", "", dax_clean, flags=re.MULTILINE)
    dax_clean = re.sub(r"```$", "", dax_clean, flags=re.MULTILINE)

    return dax_clean

# -----------------------------
# FUNCTION: Execute DAX interactively
# -----------------------------
def execute_dax_interactive(dax_query: str):
    # 🔹 Fix Groq mistakes before running
    
    fixed_dax = fix_dax_grouping(dax_query)
    cleaned_dax = clean_dax(fixed_dax)

    logger.info("✅ Generated DAX (fixed):\n%s", cleaned_dax)
    """
    Connect to Power BI XMLA endpoint using Pyadomd interactive login.
    Returns results as (columns, rows).
    """
    from sys import path
    dll_path = 'C:\\Program Files\\Microsoft.NET\\ADOMD.NET\\160'
    path.append(dll_path)
    from pyadomd import Pyadomd

    connection_string = (
        f"Data Source=powerbi://api.powerbi.com/v1.0/myorg/{WORKSPACE};"
        f"Initial Catalog={DATASET};"
        "User ID=;Password=;"  # interactive login
    )

    results, columns = [], []
    try:
        with Pyadomd(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute(cleaned_dax)

            columns = [col.name for col in cursor.description]
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

        logger.info(f"✅ DAX executed successfully. Rows fetched: {len(results)}")
        return columns, results

    except Exception as e:
        logger.error(f"❌ Error executing DAX: {e}")
        raise e
