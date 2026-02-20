import os

from dotenv import load_dotenv
from google import genai


def _get_gemini_client() -> genai.Client:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment or .env file.")
    return genai.Client(api_key=api_key)


def gemini_answer_armenian(user_text: str, model: str = "gemini-2.5-flash") -> str:
    client = _get_gemini_client()
    response = client.models.generate_content(
        model=model,
        contents=[
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Դու օգտակար օգնական ես։ "
                            "Միշտ պատասխանիր հայերենով։ "
                            "Պատասխանը պահիր հստակ և կոնկրետ։\n\n"
                            f"Հարց/մուտք՝ {user_text}"
                        )
                    }
                ],
            }
        ],
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")
    return response.text.strip()


def main() -> None:
    prompt = "Ինչպե՞ս է եղանակը Երևանում գարնանը։"
    print(gemini_answer_armenian(prompt))


if __name__ == "__main__":
    main()
