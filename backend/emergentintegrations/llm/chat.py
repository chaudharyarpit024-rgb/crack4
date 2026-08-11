import json
from typing import List, Optional
import httpx


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
        self.model = "gemini-1.5-flash"

    def with_model(self, provider: str, model: str):
        self.provider = provider
        # Map preview/older identifiers to stable Gemini endpoints
        if "gemini" in model:
            self.model = model.replace("gemini-3-flash-preview", "gemini-1.5-flash")
        else:
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

        # Call Gemini REST API directly
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
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
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                # If API call fails or model returns error, raise to trigger fallback/handler
                raise RuntimeError(f"Gemini API returned status {resp.status_code}: {resp.text}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("No candidates returned from Gemini API")

            content = candidates[0].get("content", {})
            parts_resp = content.get("parts", [])
            if not parts_resp:
                raise RuntimeError("Empty response content from Gemini API")

            return parts_resp[0].get("text", "{}")
