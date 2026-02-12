from __future__ import annotations

import json
import logging
from typing import TypeVar

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
    """Extract structured data from sources using OpenAI structured outputs.

    Returns:
        A tuple of (parsed model instance or None, list of errors).
    """
    errors: list[ErrorItem] = []

    if not sources:
        errors.append(
            ErrorItem(agent=agent, message="No sources provided for extraction")
        )
        return None, errors

    evidence_block = _build_evidence_block(sources)

    user_prompt = (
        f"Product space: {product_space}\n\n"
        f"{instructions}\n\n"
        f"--- EVIDENCE ---\n{evidence_block}\n--- END EVIDENCE ---"
    )

    json_schema = _make_strict_schema(schema_model.model_json_schema())

    last_validation_error: str | None = None

    for attempt in range(max_retries):
        try:
            messages: list[dict] = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            if last_validation_error and attempt > 0:
                messages.append({
                    "role": "user",
                    "content": (
                        f"Your previous output failed validation:\n"
                        f"{last_validation_error}\n\n"
                        "Fix the output to match the schema exactly. "
                        "No extra keys."
                    ),
                })

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

            raw = response.output_text
            data = json.loads(raw)
            result = schema_model.model_validate(data)
            return result, errors

        except (json.JSONDecodeError, ValidationError) as exc:
            last_validation_error = str(exc)
            logger.warning(
                "Extraction validation failed (attempt %d/%d): %s",
                attempt + 1,
                max_retries,
                exc,
            )

        except Exception as exc:
            logger.error("Extraction API call failed: %s", exc)
            errors.append(
                ErrorItem(agent=agent, message=f"Extraction API call failed: {exc}")
            )
            return None, errors

    errors.append(
        ErrorItem(
            agent=agent,
            message=f"Extraction failed after {max_retries} attempts: {last_validation_error}",
        )
    )
    return None, errors
