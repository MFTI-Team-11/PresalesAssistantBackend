import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_get_default_questions_returns_questionnaire(client: AsyncClient) -> None:
    response = await client.get("/questions/default")

    assert response.status_code == 200

    body = response.json()
    payload = body["payload"]
    questions = payload["questions"]

    assert body["success"] is True
    assert isinstance(questions, list)
    assert len(questions) > 0

    assert questions[0] == {
        "id": "business_goal",
        "text": "Какая бизнес-цель проекта и какие KPI должны быть достигнуты?",
        "category": "business",
        "required": True,
        "answer_type": "text",
        "allow_file": False,
        "file_required": False,
        "file_hint": None,
        "placeholder": (
            "Например: ускорить пресейл, снизить ручной труд, повысить точность оценки"
        ),
    }

    file_questions = [question for question in questions if question["allow_file"]]
    assert len(file_questions) > 0
    assert file_questions[0]["file_hint"]
