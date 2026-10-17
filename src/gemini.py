from typing import Optional, Union
import time
from google import genai
from google.genai import errors
from dotenv import load_dotenv
from src.config import get_settings
from src.products.schemas import Products
load_dotenv()


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=get_settings().GEMINI_API_KEY
        )
    return _client

def structure_products(prompt: str) -> Union[Products, str]:
    for attempt in range(5):
        try:
            response = _get_client().models.generate_content(
                model="gemini-flash-latest",
                contents=f"""
                Extract product listings from this text.

                Rules:
                - Return one record per product.
                - Never invent missing prices or quantities.
                - Interpret abbreviations only when reasonably clear.
                - Mark ambiguous or uncertain records for review.
                - Do not calculate a unit price unless the source clearly provides enough information.
                - Preserve the original product meaning.
                - Required columns: name, price, cost_price, quantity.
                - If None of the required columns is given in query, return a graceful error message.
                - Never input in a missing required column, return a gracefull error message instead
                Raw text:
                {prompt}
                """,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": Products
                },
            )
            
            if response.parsed is not None:
                if not response.parsed.products:
                    return (
                        "No products could be extracted from the file. "
                        "Please ensure it contains product names, prices, "
                        "cost prices, and quantities, then try again."
                    )
                return response.parsed

            return (
                "Could not understand the file contents. "
                "Please check the format and try again."
            )

        except errors.ServerError as e:
            if attempt == 2:
                print("Gemini is temporarily unavailable. Try again later.")
                return "Gemini is temporarily down, please try again later"

            wait = 2 ** (attempt + 1)
            print(f"Server unavailable. Retrying in {wait} seconds...")
            time.sleep(wait)
            
    return "Failed after multiple attempts."
            
