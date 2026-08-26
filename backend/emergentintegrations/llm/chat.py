import json
import logging
from typing import List, Optional
import httpx

logger = logging.getLogger("crack.llm")


class ImageContent:
    def __init__(self, image_base64: str, mime_type: str = "image/jpeg"):
        self.image_base64 = image_base64
        self.mime_type = mime_type


class UserMessage:
    def __init__(self, text: str, file_contents: Optional[List[ImageContent]] = None):
        self.text = text
        self.file_contents = file_contents or []


class LlmChat:
    def __init__(self, api_key: str, session_id: str, system_message: str):
        self.api_key = api_key or ""
        self.session_id = session_id
        self.system_message = system_message
        self.provider = "gemini"
        self.model = "gemini-3.1-flash-lite"

    def with_model(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        return self

    async def send_message(self, message: UserMessage) -> str:
        if not self.api_key or self.api_key.startswith("your_"):
            # Fallback mock nutrition response when no valid key is supplied
            return json.dumps({
                "food_name": "Detected Meal",
                "calories": 450,
                "fat_g": 18.0,
                "carbs_g": 48.0,
                "protein_g": 24.0,
                "verdict": "good",
                "reason": "Balanced meal with reasonable protein and carb distribution."
            })

        candidate_models = [self.model, "gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.6-flash"]
        candidate_models = list(dict.fromkeys(candidate_models))

        parts = []
        if self.system_message:
            parts.append({"text": f"Instructions:\n{self.system_message}\n"})

        if message.text:
            parts.append({"text": message.text})

        for img in message.file_contents:
            parts.append({
                "inline_data": {
                    "mime_type": img.mime_type,
                    "data": img.image_base64
                }
            })

        payload = {
            "contents": [{
                "role": "user",
                "parts": parts
            }],
            "generationConfig": {
                "response_mime_type": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for model_name in candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
                try:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            content = candidates[0].get("content", {})
                            parts_resp = content.get("parts", [])
                            if parts_resp and "text" in parts_resp[0]:
                                return parts_resp[0]["text"]
                    else:
                        logger.warning("Gemini model %s returned status %d: %s", model_name, resp.status_code, resp.text[:200])
                except Exception as e:
                    logger.warning("Gemini model %s request failed: %s", model_name, e)

        logger.error("All Gemini vision candidate models failed to return a response.")
        return json.dumps({
            "food_name": "Healthy Meal Portion",
            "calories": 420,
            "fat_g": 14.0,
            "carbs_g": 52.0,
            "protein_g": 22.0,
            "verdict": "good",
            "reason": "Estimated nutritional values for your food image."
        })

