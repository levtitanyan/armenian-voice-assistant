import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _get_gemini_client() -> genai.Client:
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
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
                            "Դու Սասի HR AI Agent ես։ "
                            "Միշտ պատասխանիր հայերենով։ "
                            "Պատասխանը պահիր շատ կարճ՝ 1-2 կարճ նախադասություն։ "
                            "Պատասխաններում խուսափիր երկար բացատրություններից։ "
                            "Եթե հարցնեն՝ ով ես, հստակ ասա, որ Սասի HR AI Agent ես։ "
                            "Եթե տվյալը վստահ չգիտես, ասա կարճ, որ տվյալը չունես։\n\n"
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
