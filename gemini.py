import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from sas_knowledge import format_context, load_knowledge_items, retrieve_relevant_items


def _get_gemini_client() -> genai.Client:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment or .env file.")
    return genai.Client(api_key=api_key)


def gemini_answer_armenian(
    user_text: str,
    model: str = "gemini-2.5-flash",
    context_block: str | None = None,
) -> str:
    client = _get_gemini_client()
    response = client.models.generate_content(
        model=model,
        contents=[
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Դու SAS սուպերմարկետի HR call center օգնական ես։ "
                            "Պատասխանիր միայն հայերենով։ "
                            "Եթե տրված SAS կոնտեքստում տվյալ չկա, ասա, որ տվյալը հասանելի չէ "
                            "և առաջարկիր կապվել կենդանի օպերատորի հետ։ "
                            "Պատասխանը պահիր հստակ և կոնկրետ։\n\n"
                            f"SAS կոնտեքստ՝\n{context_block or 'Կոնտեքստ չի տրամադրվել'}\n\n"
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


def gemini_answer_armenian_with_knowledge(
    user_text: str,
    knowledge_path: str | Path = "data/sas_knowledge.json",
    top_k: int = 5,
    model: str = "gemini-2.5-flash",
) -> str:
    items = load_knowledge_items(Path(knowledge_path))
    if not items:
        return gemini_answer_armenian(user_text=user_text, model=model)

    relevant = retrieve_relevant_items(query=user_text, items=items, top_k=top_k)
    context = format_context(relevant if relevant else items[:top_k])
    return gemini_answer_armenian(user_text=user_text, model=model, context_block=context)


def main() -> None:
    prompt = "Ինչպե՞ս է եղանակը Երևանում գարնանը։"
    print(gemini_answer_armenian_with_knowledge(prompt))


if __name__ == "__main__":
    main()
