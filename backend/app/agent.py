"""PACT AI Shopping Assistant.

Integrates with OpenAI API (configurable via OPENAI_MODEL) with intelligent fallback
to ensure robust operation during demos and testing.

Core Architecture Principle:
AI recommends. Deterministic code authorizes. Human approves. PayPal executes.
The AI NEVER has the ability or authority to capture payments directly.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from app.config import get_settings
from app.models import Mandate, Product

logger = logging.getLogger("pact.agent")
settings = get_settings()


class AIAgentRecommendation:
    """Structured proposal recommendation from the AI shopping agent."""

    def __init__(
        self,
        product: Product,
        quantity: int,
        ai_reasoning: str,
        confidence_score: float = 0.95,
    ):
        self.product = product
        self.quantity = quantity
        self.ai_reasoning = ai_reasoning
        self.confidence_score = confidence_score


async def generate_shopping_recommendation(
    user_prompt: str,
    mandate: Mandate,
    available_products: List[Product],
) -> AIAgentRecommendation:
    """Analyze user request and catalog to formulate a purchase proposal."""
    if not available_products:
        raise ValueError("No products available in catalog.")

    # 1. Attempt OpenAI API call if key configured
    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip():
        try:
            return await _call_openai_agent(user_prompt, mandate, available_products)
        except Exception as exc:
            logger.warning(f"OpenAI API call failed ({str(exc)}). Falling back to heuristic recommendation engine.")

    # 2. Intelligent Heuristic Recommendation Engine
    return _heuristic_agent_recommendation(user_prompt, mandate, available_products)


async def _call_openai_agent(
    user_prompt: str,
    mandate: Mandate,
    available_products: List[Product],
) -> AIAgentRecommendation:
    """Query OpenAI chat completion model with structured output."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Prepare catalog summary for AI context
    catalog_summary = [
        {
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "merchant": p.merchant,
            "price": float(p.price),
            "in_stock": p.in_stock,
            "description": p.description,
        }
        for p in available_products
    ]

    system_prompt = (
        "You are PACT Shopping Assistant, an intelligent shopping agent. "
        "Your task is to analyze the user's shopping request and select the single best matching product "
        "from the provided catalog.\n"
        "Important Constraints:\n"
        "- You only recommend a product; you do NOT capture or execute payments.\n"
        "- Only choose an ID that exists in the provided catalog.\n"
        "- Return your response as a valid JSON object with the exact keys: "
        "'product_id' (integer), 'quantity' (integer, default 1), and 'ai_reasoning' (string explaining your choice)."
    )

    user_message = (
        f"User Shopping Request: '{user_prompt}'\n\n"
        f"Available Products Catalog:\n{json.dumps(catalog_summary, indent=2)}\n\n"
        "Respond with a JSON object: {\"product_id\": <int>, \"quantity\": <int>, \"ai_reasoning\": \"<explanation>\"}"
    )

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    content = response.choices[0].message.content
    data = json.loads(content)

    prod_id = data.get("product_id")
    qty = max(1, int(data.get("quantity", 1)))
    reasoning = data.get("ai_reasoning", f"Selected item #{prod_id} based on user requirements.")

    # Find the corresponding product
    matching_product = next((p for p in available_products if p.id == prod_id), None)
    if not matching_product:
        raise ValueError(f"AI selected non-existent product ID: {prod_id}")

    return AIAgentRecommendation(
        product=matching_product,
        quantity=qty,
        ai_reasoning=reasoning,
        confidence_score=0.98,
    )


def _heuristic_agent_recommendation(
    user_prompt: str,
    mandate: Mandate,
    available_products: List[Product],
) -> AIAgentRecommendation:
    """Smart heuristic matcher when OpenAI is unavailable or not configured."""
    prompt_tokens = set(re.findall(r"\w+", user_prompt.lower()))

    # Score each product based on keyword overlaps in name, category, merchant, description
    scored_products = []
    for prod in available_products:
        score = 0
        name_tokens = set(re.findall(r"\w+", prod.name.lower()))
        desc_tokens = set(re.findall(r"\w+", prod.description.lower()))
        cat_tokens = set(re.findall(r"\w+", prod.category.lower()))
        merch_tokens = set(re.findall(r"\w+", prod.merchant.lower()))

        # Name matches count highest
        score += len(prompt_tokens & name_tokens) * 10
        # Category matches
        score += len(prompt_tokens & cat_tokens) * 5
        # Merchant matches
        score += len(prompt_tokens & merch_tokens) * 6
        # Description matches
        score += len(prompt_tokens & desc_tokens) * 2

        # Bonus if in stock
        if prod.in_stock:
            score += 1

        scored_products.append((score, prod))

    # Sort descending by score
    scored_products.sort(key=lambda x: x[0], reverse=True)

    # Pick the highest scoring item (or first product if no keywords matched)
    best_score, selected_product = scored_products[0]

    if best_score > 0:
        reasoning = (
            f"Analyzed catalog for '{user_prompt}'. Selected '{selected_product.name}' "
            f"from merchant '{selected_product.merchant}' in category '{selected_product.category}' "
            f"priced at ${selected_product.price:.2f} as the optimal match for user preferences."
        )
    else:
        reasoning = (
            f"Assessed shopping request '{user_prompt}'. Identified '{selected_product.name}' "
            f"from '{selected_product.merchant}' (${selected_product.price:.2f}) as a recommended option."
        )

    return AIAgentRecommendation(
        product=selected_product,
        quantity=1,
        ai_reasoning=reasoning,
        confidence_score=0.90 if best_score > 0 else 0.75,
    )
