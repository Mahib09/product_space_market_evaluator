import logging

from fastapi import FastAPI, HTTPException

from app.core.orchestrator import run_pipeline
from app.schemas import EvaluateRequest, FinalResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="Product Space Market Evaluator")


@app.post("/evaluate", response_model=FinalResult)
async def evaluate(request: EvaluateRequest) -> FinalResult:
    product_space = request.product_space.strip()

    if not product_space:
        raise HTTPException(status_code=400, detail="product_space must be non-empty")

    try:
        return await run_pipeline(product_space)
    except Exception as exc:
        logging.getLogger(__name__).error("Pipeline failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")
