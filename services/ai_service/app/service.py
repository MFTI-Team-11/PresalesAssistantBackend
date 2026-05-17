import json
import re

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.gigachat import GigaChatClient
from app.schemas import AnalysisResponse, QuestionsResponse


DEFAULT_PREANALYSIS_QUESTIONS = [
    "Какая бизнес-цель проекта и какие KPI должны быть достигнуты?",
    "Кто основные пользователи системы и какие пользовательские сценарии нужно поддержать?",
    "Какие входные документы, таблицы и вложенные файлы будут загружаться для анализа?",
    "Какие результаты пресейла нужно получить: трудозатраты, архитектура, "
    "сайзинг, риски, ФТ, НФТ, поддержка, гарантия?",
    "Какие внешние системы и интеграции требуются, какие протоколы и форматы обмена используются?",
    "Какие ограничения есть по размещению: on-premise, контур компании, "
    "запрет передачи данных наружу?",
    "Какие требования есть к безопасности, ролям, аудиту, хранению и обработке "
    "персональных данных?",
    "Какая ожидаемая нагрузка: количество пользователей, пресейлов в месяц, "
    "объем документов и данных?",
    "Какие сроки, бюджетные ограничения и приоритеты по этапам проекта?",
    "Какие ставки специалистов и роли команды нужно использовать в оценке?",
    "Какая схема технической поддержки нужна после завершения проекта?",
    "Нужно ли включать годовое гарантийное обслуживание в бюджет проекта?",
    "Какие ключевые риски, ограничения и допущения уже известны?",
]

DEFAULT_RATES = {
    "Analyst": 2800,
    "Architect": 5200,
    "Backend Developer": 3600,
    "Frontend Developer": 3400,
    "QA Engineer": 2600,
    "DevOps Engineer": 3800,
    "Project Manager": 3200,
    "UX/UI Designer": 3000,
    "Support Engineer": 2400,
}


CASE_6_CONTEXT = """
Кейс 6: AI ассистент для пресейла.
Цель: ускорить и повысить точность первичной оценки IT-проектов для пресейла.
Ассистент должен принимать документы заказчика, задавать вопросы для преданализа,
формировать ФТ и НФТ, декомпозировать задачи, рекомендовать архитектуру.
Также он рассчитывает сайзинг, длительность, состав команды, трудозатраты,
бюджет поддержки, гарантийное обслуживание, риски и план митигации.
Отдельно ассистент суммирует расходы по месяцам.
Ограничения: on-premise, объем 30-50 пресейлов в месяц.
Данные нельзя передавать за пределы компании.
Сценарий: пользователь создает запрос, загружает требования и ставки.
Пользователь выбирает желаемые результаты, получает вопросы, отвечает на них
и затем получает пресейл-результат.
"""

QUESTIONS_SYSTEM_PROMPT = f"""
Ты AI ассистент для пресейла. Работай строго по описанию кейса.
{CASE_6_CONTEXT}

Сформируй вопросы к заказчику для преданализа проекта.
Вопросы должны закрывать пробелы в требованиях, интеграциях, безопасности,
нагрузке, данных, сроках, архитектурных ограничениях, поддержке, гарантии,
бюджете и рисках. Не задавай вопросы, ответы на которые уже явно есть
во входном тексте. Верни только JSON по схеме:
{{"questions": ["Вопрос 1", "Вопрос 2"]}}
"""

ANALYSIS_SYSTEM_PROMPT = f"""
Ты senior пресейл-аналитик, архитектор и менеджер оценки IT-проектов.
Работай строго по описанию кейса.
{CASE_6_CONTEXT}

На основе требований и ответов пользователя подготовь структурированный результат пресейла.
Если данных не хватает, делай явные допущения внутри соответствующих полей.
Часы указывай числами. В tasks каждый элемент обязан содержать name и estimates.
estimates - список объектов {{"role": "...", "hours": число}}.
Это поле используется для расчета бюджета.
Верни только валидный JSON без markdown по схеме:
{{
  "functional_requirements": [
    {{"code": "FR-001", "title": "...", "priority": "must|should|could"}}
  ],
  "nonfunctional_requirements": [{{"code": "NFR-001", "title": "...", "description": "..."}}],
  "tasks": [
    {{"name": "...", "description": "...", "estimates": [
      {{"role": "Analyst", "hours": 40}}
    ]}}
  ],
  "architecture_options": [
    {{"name": "...", "recommended": true, "description": "...", "tradeoffs": ["..."]}}
  ],
  "sizing": {{
    "summary": "...",
    "components": [{{"name": "...", "cpu": 2, "ram_gb": 4, "storage_gb": 50}}]
  }},
  "team_options": [{{"name": "...", "duration_months": 6, "roles": ["Analyst middle"]}}],
  "risks": [{{"risk": "...", "impact": "low|medium|high", "mitigation": "..."}}]
}}
"""

PRESALE_ESTIMATE_SYSTEM_PROMPT = f"""
Ты AI ассистент для пресейла, системный аналитик, архитектор и оценщик проекта.
Работай по Кейс 6.
{CASE_6_CONTEXT}

Пользователь передает один свободный текст и может приложить файлы: требования,
скриншоты, фото таблиц со ставками, документы, картинки из Figma. Самостоятельно
извлеки из текста и файлов:
1. требования заказчика;
2. ответы пользователя на вопросы преданализа;
3. роли сотрудников, грейды, количество людей, почасовые ставки;
4. желаемые результаты пресейла;
5. ограничения по срокам, поддержке, гарантии, on-premise, безопасности.

Если ставка написана как "бэкендер 1000р в час", преобразуй роль в
"Backend Developer" и hourly_rate=1000. Если ставка есть только на фото или
в таблице, извлеки ее из файла. Если какой-то ставки нет, явно укажи допущение
и используй рыночную ставку из контекста.

Верни только валидный JSON без markdown по схеме:
{{
  "analysis": {{
    "functional_requirements": [
      {{"code": "FR-001", "title": "...", "priority": "must|should|could"}}
    ],
    "nonfunctional_requirements": [
      {{"code": "NFR-001", "title": "...", "description": "..."}}
    ],
    "tasks": [
      {{"name": "...", "description": "...", "estimates": [
        {{"role": "Backend Developer", "hours": 120}}
      ]}}
    ],
    "architecture_options": [
      {{"name": "...", "recommended": true, "description": "...", "tradeoffs": ["..."]}}
    ],
    "sizing": {{
      "summary": "...",
      "components": [{{"name": "...", "cpu": 2, "ram_gb": 4, "storage_gb": 50}}]
    }},
    "team_options": [
      {{"name": "...", "duration_months": 6, "roles": ["Backend Developer middle"]}}
    ],
    "risks": [
      {{"risk": "...", "impact": "low|medium|high", "mitigation": "..."}}
    ]
  }},
  "extracted_rates": [
    {{"role": "Backend Developer", "grade": "middle", "hourly_rate": 1000}}
  ],
  "support_scheme": "three_lines_24x7",
  "project_months": 6
}}
"""


class AiService:
    def __init__(self, client: GigaChatClient | None = None) -> None:
        self.client = client or GigaChatClient()

    async def questions(self, text: str) -> list[str]:
        content = await self.client.chat_json(
            [
                {"role": "system", "content": QUESTIONS_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Входные требования заказчика:\n{text or 'Нет данных'}",
                },
            ],
            temperature=0.15,
        )
        payload = self._parse_json(content)
        try:
            return QuestionsResponse.model_validate(payload).questions
        except ValidationError as exc:
            raise self._bad_ai_response("GigaChat returned invalid questions JSON", exc)

    def default_questions(self) -> list[str]:
        return DEFAULT_PREANALYSIS_QUESTIONS

    def questions_text(self) -> str:
        return self.format_questions_text(self.default_questions())

    def format_questions_text(self, questions: list[str]) -> str:
        if not questions:
            return "Уточняющих вопросов нет."
        lines = ["Ответьте, пожалуйста, на вопросы для преданализа:"]
        lines.extend(f"{index}. {question}" for index, question in enumerate(questions, start=1))
        return "\n".join(lines)

    async def analysis(self, text: str, answers: list[str], desired_outputs: list[str]) -> dict:
        user_payload = {
            "requirements_text": text or "Нет данных",
            "preanalysis_answers": answers,
            "desired_outputs": desired_outputs,
        }
        content = await self.client.chat_json(
            [
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            temperature=0.2,
        )
        payload = self._parse_json(content)
        try:
            return AnalysisResponse.model_validate(payload).model_dump()
        except ValidationError as exc:
            raise self._bad_ai_response("GigaChat returned invalid analysis JSON", exc)

    async def presale_estimate(
        self,
        input_text: str,
        attachments: list[str],
    ) -> dict:
        content = await self.client.chat_json(
            [
                {"role": "system", "content": PRESALE_ESTIMATE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Проанализируй входные данные и приложенные файлы. "
                        "Верни итог пресейла, ставки, длительность и схему поддержки.\n\n"
                        f"Текст пользователя:\n{input_text or 'Пользователь не ввел текст'}"
                    ),
                },
            ],
            temperature=0.2,
            attachments=attachments,
            function_call_auto=True,
        )
        payload = self._parse_json(content)
        analysis = AnalysisResponse.model_validate(payload.get("analysis", {})).model_dump()
        extracted_rates = payload.get("extracted_rates", [])
        if not isinstance(extracted_rates, list):
            extracted_rates = []
        support_scheme = str(payload.get("support_scheme") or "three_lines_24x7")
        project_months = int(payload.get("project_months") or 6)
        project_months = min(max(project_months, 1), 36)
        normalized_rates = self.normalize_rates(extracted_rates)
        effort_budget = self.effort_budget(analysis["tasks"], normalized_rates)
        warranty_budget = self.warranty_budget(effort_budget["total_cost"])
        return {
            "analysis": analysis,
            "extracted_rates": extracted_rates,
            "effort_budget": effort_budget,
            "support_budget": self.support_budget(support_scheme, normalized_rates),
            "warranty_budget": warranty_budget,
            "monthly_expenses": self.monthly_expenses(
                effort_budget["total_cost"],
                warranty_budget["annual_cost"],
                project_months,
            ),
        }

    def normalize_rates(self, raw_rates: list[dict]) -> dict[str, float]:
        rates = dict(DEFAULT_RATES)
        for item in raw_rates:
            role = item.get("role")
            hourly_rate = item.get("hourly_rate")
            if role and hourly_rate:
                rates[str(role)] = float(hourly_rate)
        return rates

    def effort_budget(self, tasks: list[dict], rates: dict[str, float]) -> dict:
        total_hours = 0.0
        total_cost = 0.0
        by_role: dict[str, dict] = {}
        for task in tasks:
            for estimate in task.get("estimates", []):
                role = str(estimate.get("role", "Backend Developer"))
                hours = float(estimate.get("hours", 0))
                cost = hours * rates.get(role, 3000)
                total_hours += hours
                total_cost += cost
                bucket = by_role.setdefault(role, {"hours": 0.0, "cost": 0.0})
                bucket["hours"] += hours
                bucket["cost"] = round(bucket["cost"] + cost, 2)
        return {
            "total_hours": round(total_hours, 2),
            "total_cost": round(total_cost, 2),
            "by_role": by_role,
        }

    def support_budget(self, scheme: str, rates: dict[str, float]) -> dict:
        hourly = rates.get("Support Engineer", 2400)
        if scheme == "third_line_business_hours":
            monthly_hours = 8 * 5 * 4
            title = "3 линия поддержки, 06:00-18:00 по рабочим дням"
        else:
            monthly_hours = 24 * 365 / 12 * 3
            title = "1/2/3 линии поддержки, 24x7x365"
        monthly_cost = monthly_hours * hourly
        return {
            "scheme": scheme,
            "title": title,
            "monthly_hours": round(monthly_hours, 2),
            "monthly_cost": round(monthly_cost, 2),
            "annual_cost": round(monthly_cost * 12, 2),
        }

    def warranty_budget(self, development_cost: float) -> dict:
        return {"percent": 8, "annual_cost": round(development_cost * 0.08, 2)}

    def monthly_expenses(
        self,
        development_cost: float,
        warranty_cost: float,
        months: int,
    ) -> list[dict]:
        development_month = development_cost / months
        warranty_month = warranty_cost / 12
        return [
            {
                "month": month,
                "development": round(development_month, 2),
                "warranty_reserve": round(warranty_month, 2),
                "total": round(development_month + warranty_month, 2),
            }
            for month in range(1, months + 1)
        ]

    def _parse_json(self, content: str) -> dict:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GigaChat returned non-JSON content",
            )

    def _bad_ai_response(self, detail: str, exc: ValidationError) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{detail}: {exc.errors()}",
        )
