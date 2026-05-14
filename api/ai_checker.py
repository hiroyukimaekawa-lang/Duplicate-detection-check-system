import os
import json
import google.generativeai as genai
import logging

logger = logging.getLogger("ai_checker")

class GeminiChecker:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_GEMINI_API_KEY")
        self.model = None
        self.cooling_until = 0
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-2.0-flash')
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
        else:
            logger.warning("Gemini API key not found. AI Checker will be disabled.")

    def is_duplicate(self, row_a: dict, row_b: dict) -> tuple[bool, str]:
        """
        Ask Gemini if two records are the same restaurant.
        Returns (is_duplicate, reasoning)
        """
        if not self.model:
            return False, "Gemini not configured"

        import time
        if time.time() < self.cooling_until:
            return False, "Gemini is cooling down due to rate limit"

        prompt = f"""
以下の2つのレストランデータが「同一店舗」かどうかを判定してください。
店舗名、住所、電話番号の表記ゆれを考慮して判断してください。

【レコード A】
店名: {row_a.get('name')}
住所: {row_a.get('address')}
電話番号: {row_a.get('phone')}

【レコード B】
店名: {row_b.get('name')}
住所: {row_b.get('address')}
電話番号: {row_b.get('phone')}

判定基準:
1. 建物名や階数の有無だけで判断せず、住所の根幹が同じか確認してください。
2. 店名の英語表記と日本語表記、略称なども考慮してください。
3. 商業施設（ショッピングモール）内の店舗の場合、テナント名まで一致するか確認してください。

返答形式（JSONのみ）:
{{
  "is_duplicate": true/false,
  "reason": "判断理由の簡潔な説明"
}}
"""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            res_json = json.loads(response.text)
            return res_json.get("is_duplicate", False), res_json.get("reason", "")
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "quota" in err_msg.lower():
                logger.warning("Gemini API Rate Limit hit. Cooling down for 60s.")
                import time
                self.cooling_until = time.time() + 60
            else:
                logger.error(f"Gemini API error: {e}")
            return False, f"Error: {err_msg}"
