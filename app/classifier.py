import json
import logging
import os

logger = logging.getLogger(__name__)

FALLBACK_CLASSIFICATION = {"category": "question", "priority": "P3", "tags": []}

_ALLOWED_CATEGORIES = {"bug", "feature_request", "question", "urgent"}
_ALLOWED_PRIORITIES = {"P1", "P2", "P3"}


def classify_ticket(title: str, description: str) -> dict:
    """Classify a support ticket using OpenRouter. Returns FALLBACK on any error."""
    try:
        from openai import OpenAI

        logger.debug("Classifying ticket: %.80s", title)
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        prompt = (
            "Classify the following support ticket. "
            "Respond with a JSON object with exactly these fields: "
            "category (one of: bug, feature_request, question, urgent), "
            "priority (one of: P1, P2, P3), "
            "tags (array of short lowercase strings).\n\n"
            f"Title: {title}\nDescription: {description}"
        )
        response = client.chat.completions.create(
            model="gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        category = data.get("category")
        priority = data.get("priority")
        tags = data.get("tags", [])
        if category not in _ALLOWED_CATEGORIES or priority not in _ALLOWED_PRIORITIES:
            logger.error(
                "LLM returned invalid category/priority: %s / %s — using fallback",
                category,
                priority,
            )
            return FALLBACK_CLASSIFICATION
        if not isinstance(tags, list):
            tags = []
        result = {"category": category, "priority": priority, "tags": [str(t) for t in tags]}
        logger.debug(
            "Classification result: category=%s priority=%s tags=%s", category, priority, tags
        )
        return result
    except Exception:
        logger.error("Classifier failed — applying fallback", exc_info=True)
        return FALLBACK_CLASSIFICATION
