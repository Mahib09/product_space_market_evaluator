import logging

from fastapi import FastAPI, HTTPException
import time

from app.core.orchestrator import run_pipeline
from app.schemas import EvaluateRequest, FinalResult
import uuid

request_id = str(uuid.uuid4())
start_time = time.perf_counter()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Product Space Market Evaluator")


@app.post("/evaluate", response_model=FinalResult)
async def evaluate(request: EvaluateRequest) -> FinalResult:
    product_space = request.product_space.strip()
    logger.info('[API] START request_id=%s product_space="%s"', request_id, product_space)


    if not product_space:
        raise HTTPException(status_code=400, detail="product_space must be non-empty")

    try:
        result = await run_pipeline(product_space)

        total_s = time.perf_counter() - start_time
        logger.info(
            '[API] DONE request_id=%s status=200 total=%.2fs',
            request_id,
            total_s,
        )

        return result
    
    except Exception as exc:
        logging.getLogger(__name__).error("Pipeline failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")
