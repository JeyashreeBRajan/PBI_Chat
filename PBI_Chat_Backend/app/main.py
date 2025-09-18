import logging
import traceback
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.schema_fetcher import get_or_load_schema
from app.groq_service import groq_service

# --- Logging setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FastAPI app ---
app = FastAPI()


class QueryRequest(BaseModel):
    question: str
    connection_str: dict  # {"workspace": "...", "dataset": "..."}


@app.post("/api/powerbi/query-natural")
async def query_powerbi_natural(req: QueryRequest):
    """Convert a natural language question into DAX and execute it."""
    question = req.question.strip()
    workspace = req.connection_str.get("workspace")
    dataset = req.connection_str.get("dataset")

    if not workspace or not dataset:
        raise HTTPException(
            status_code=400,
            detail="Workspace and dataset must be provided",
        )

    try:
        # Load schema (cached or fetch)
        schema = get_or_load_schema(workspace, dataset)
        if not schema.get("tables"):
            raise HTTPException(status_code=500, detail="Schema is empty")

    except Exception as e:
        logger.error(
            f"❌ Schema fetch failed: {e}\n{traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Schema fetch failed: {str(e)}",
        )

    if not groq_service:
        return {"detail": "Groq service not initialized"}

    try:
        # Generate DAX
        dax_query = await groq_service.generate_dax(
            question=question,
            schema=schema,
            suggestions=[],  # No fuzzy matches
            return_raw=False,
        )

        return {
            "dax": dax_query,
            "suggestions": [],  # No suggestions
        }

    except Exception as e:
        logger.error(
            f"❌ DAX generation/execution failed: {e}\n{traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"DAX generation/execution failed: {str(e)}",
        )
