from __future__ import annotations

import json
import logging
from typing import TypeVar
import time

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.config import OPENAI_API_KEY, OPENAI_MODEL_EXTRACT
from app.schemas import ErrorItem, Source

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

T = TypeVar("T", bound=BaseModel)

_SYSTEM_PROMPT = (
    "You are a structured-data extraction agent.\n"
    "Rules:\n"
    "- Use ONLY the evidence provided below.\n"
    "- If a field is not supported by evidence, set it to null "
    "(for optional fields) or an empty list (for list fields).\n"
    "- Do NOT guess or fabricate data.\n"
    "- Output must strictly match the requested JSON schema. "
    "No extra keys.\n"
)


def _make_strict_schema(schema: dict) -> dict:
    """Transform a Pydantic JSON schema into one compatible with
    OpenAI structured-output strict mode.

    Strict mode requires:
      - Every object has 'additionalProperties': false
      - 'required' lists ALL property keys (optional fields use anyOf with null)
      - No unsupported 'format' values (e.g. 'uri')
    """
    # Remove unsupported format annotations
    if "format" in schema:
        del schema["format"]

    if schema.get("type") == "object":
        schema["additionalProperties"] = False
        props = schema.get("properties", {})
        # All property names must be in required
        schema["required"] = list(props.keys())
        for prop in props.values():
            _make_strict_schema(prop)

    if "items" in schema:
        _make_strict_schema(schema["items"])

    for variant in schema.get("anyOf", []):
        _make_strict_schema(variant)

    if "$defs" in schema:
        for defn in schema["$defs"].values():
            _make_strict_schema(defn)

    return schema


def _build_evidence_block(sources: list[Source]) -> str:
    lines: list[str] = []
    for i, src in enumerate(sources, 1):
        lines.append(f"[{i}] {src.title}\n    URL: {src.url}\n    {src.snippet}")
    return "\n\n".join(lines)


async def extract_structured(
    agent: str,
    schema_model: type[T],
    product_space: str,
    sources: list[Source],
    instructions: str,
    max_retries: int = 3,
) -> tuple[T | None, list[ErrorItem]]:
    errors: list[ErrorItem] = []

    if not sources:
        errors.append(ErrorItem(agent=agent, message="No sources provided for extraction"))
        return None, errors

    t0 = time.perf_counter()

    # ---- Build evidence (consider truncating inside _build_evidence_block) ----
    t_ev = time.perf_counter()
    evidence_block = _build_evidence_block(sources)
    ev_s = time.perf_counter() - t_ev

    # Useful proxy for “how big is my prompt”
    evidence_chars = len(evidence_block or "")
    logger.info(
        "[Extract] agent=%s schema=%s sources=%d evidence_chars=%d build_evidence=%.2fs",
        agent, schema_model.__name__, len(sources), evidence_chars, ev_s
    )

    user_prompt = (
        f"Product space: {product_space}\n\n"
        f"{instructions}\n\n"
        "Return ONLY valid JSON that matches the schema. No markdown.\n\n"
        f"--- EVIDENCE ---\n{evidence_block}\n--- END EVIDENCE ---"
    )

    json_schema = _make_strict_schema(schema_model.model_json_schema())

    last_validation_error: str | None = None

    # Separate counters: validation retries vs API retries
    validation_attempts = 0
    api_attempts = 0
    max_api_attempts = 6  # allows transient retries without giving up too fast

    while validation_attempts < max_retries and api_attempts < max_api_attempts:
        messages: list[dict] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        if last_validation_error and validation_attempts > 0:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous output failed validation.\n"
                        f"Validation error:\n{last_validation_error}\n\n"
                        "Fix the JSON to match the schema exactly. No extra keys."
                    ),
                }
            )

        try:
            api_attempts += 1
            t_api = time.perf_counter()
            logger.info(
                "[Extract] API_START agent=%s schema=%s api_attempt=%d/%d validation_attempt=%d/%d",
                agent, schema_model.__name__, api_attempts, max_api_attempts,
                validation_attempts + 1, max_retries
            )

            response = await _client.responses.create(
                model=OPENAI_MODEL_EXTRACT,
                input=messages,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_model.__name__,
                        "schema": json_schema,
                        "strict": True,
                    }
                },
            )

            api_s = time.perf_counter() - t_api
            raw = response.output_text

            t_parse = time.perf_counter()
            data = json.loads(raw)
            result = schema_model.model_validate(data)
            parse_s = time.perf_counter() - t_parse

            logger.info(
                "[Extract] API_DONE agent=%s schema=%s api_seconds=%.2f parse_seconds=%.2f total_seconds=%.2f",
                agent, schema_model.__name__, api_s, parse_s, time.perf_counter() - t0
            )
            return result, errors

        except (json.JSONDecodeError, ValidationError) as exc:
            validation_attempts += 1
            last_validation_error = str(exc)
            logger.warning(
                "[Extract] VALIDATION_FAILED agent=%s schema=%s attempt=%d/%d err=%s",
                agent, schema_model.__name__, validation_attempts, max_retries, exc
            )
            # continue loop -> tries again

        except Exception as exc:
            # Treat as API/transient failure; keep trying a few times
            logger.warning(
                "[Extract] API_FAILED agent=%s schema=%s api_attempt=%d/%d err=%r",
                agent, schema_model.__name__, api_attempts, max_api_attempts, exc
            )
            # If we've exhausted API attempts, return failure
            if api_attempts >= max_api_attempts:
                errors.append(ErrorItem(agent=agent, message=f"Extraction API call failed: {exc!r}"))
                return None, errors

    errors.append(
        ErrorItem(
            agent=agent,
            message=f"Extraction failed after validation_attempts={validation_attempts}/{max_retries}, "
                    f"api_attempts={api_attempts}: {last_validation_error}",
        )
    )
    return None, errors
