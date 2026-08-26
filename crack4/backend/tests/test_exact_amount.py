"""Unit tests for exact food amount & portion calculation features."""
import sys
import os
import asyncio
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.food import FoodLogBody, AnalyzeBody
from controllers.food_controller import create_food_log


def test_food_log_body_model_with_serving_size():
    log_data = {
        "food_name": "Grilled Chicken",
        "calories": 250.0,
        "fat_g": 5.0,
        "carbs_g": 0.0,
        "protein_g": 48.0,
        "serving_size_g": 200.0,
        "source": "ai",
    }
    item = FoodLogBody(**log_data)
    assert item.food_name == "Grilled Chicken"
    assert item.calories == 250.0
    assert item.serving_size_g == 200.0
    assert item.source == "ai"


def test_analyze_body_model():
    # Base64 string of at least 32 characters
    b64_sample = "A" * 64
    body = AnalyzeBody(image_base64=b64_sample)
    assert body.image_base64 == b64_sample


def test_create_food_log_persists_serving_size():
    async def run():
        user = {"id": "test_user_123"}
        body = FoodLogBody(
            food_name="Steak",
            calories=450.0,
            fat_g=20.0,
            carbs_g=0.0,
            protein_g=60.0,
            serving_size_g=250.0,
            source="ai",
        )
        result = await create_food_log(user, body)
        assert result["food_name"] == "Steak"
        assert result["calories"] == 450.0
        assert result["serving_size_g"] == 250.0
        assert result["user_id"] == "test_user_123"

    asyncio.run(run())
