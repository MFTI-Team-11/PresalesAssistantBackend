import json
import re
from collections.abc import AsyncGenerator

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.core.config import settings
from app.gigachat import GigaChatClient
from app.openai_client import OpenAIClient
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
    "Какие ставки специалистов и роли команды нужно использовать в оценке? "
    "Если ставок нет, оставьте поле пустым - ассистент предложит состав команды сам.",
    "Какая схема технической поддержки нужна после завершения проекта?",
    "Нужно ли включать годовое гарантийное обслуживание в бюджет проекта?",
    "Какие ключевые риски, ограничения и допущения уже известны?",
]

DEFAULT_PREANALYSIS_QUESTION_META = [
    {
        "id": "business_goal",
        "category": "business",
        "placeholder": "Например: ускорить пресейл, снизить ручной труд, повысить точность оценки",
    },
    {
        "id": "users_and_scenarios",
        "category": "scope",
        "placeholder": "Опишите роли пользователей и основные сценарии работы",
    },
    {
        "id": "input_documents",
        "category": "data",
        "allow_file": True,
        "file_hint": "Можно приложить ТЗ, письмо заказчика или документ с требованиями",
        "placeholder": "Если файла нет, опишите входные документы текстом",
    },
    {
        "id": "desired_outputs",
        "category": "result",
        "placeholder": "Например: архитектура, бюджет, сайзинг, риски, ФТ/НФТ",
    },
    {
        "id": "integrations",
        "category": "integrations",
        "placeholder": "Укажите системы, API, протоколы, форматы обмена",
    },
    {
        "id": "deployment_constraints",
        "category": "infrastructure",
        "placeholder": "Например: on-premise, закрытый контур, запрет внешних облаков",
    },
    {
        "id": "security_requirements",
        "category": "security",
        "placeholder": "Опишите роли, аудит, персональные данные, требования ИБ",
    },
    {
        "id": "load",
        "category": "sizing",
        "placeholder": "Пользователи, запросы, пресейлы в месяц, объем файлов и данных",
    },
    {
        "id": "timeline_budget_priorities",
        "category": "planning",
        "placeholder": "Сроки, бюджетные ограничения, приоритеты MVP/этапов",
    },
    {
        "id": "rates_and_roles",
        "category": "budget",
        "required": False,
        "allow_file": True,
        "file_hint": "Можно приложить таблицу ставок. Если ее нет, ассистент использует рыночные допущения",
        "placeholder": "Необязательно. Например: бэкендер 1000р/час, архитектор 2000р/час",
    },
    {
        "id": "support_scheme",
        "category": "support",
        "placeholder": "Например: 24/7 1-3 линии или только 3 линия в рабочее время",
    },
    {
        "id": "warranty",
        "category": "support",
        "placeholder": "Да/нет, срок гарантии, процент или бюджетный лимит",
    },
    {
        "id": "known_risks",
        "category": "risks",
        "placeholder": "Опишите известные ограничения, зависимости, риски и допущения",
    },
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
Цель: ускорить и повысить точность первичной оценки IT-проектов для пресейла.
Ассистент должен принимать документы заказчика, задавать вопросы для преданализа,
формировать ФТ и НФТ, декомпозировать задачи, рекомендовать архитектуру.
Также он рассчитывает сайзинг, длительность, состав команды, трудозатраты,
бюджет поддержки, гарантийное обслуживание, риски и план митигации.
Отдельно ассистент суммирует расходы по месяцам.
Ограничения: on-premise, объем 30-50 пресейлов в месяц.
Данные нельзя передавать за пределы компании.
Сценарий: пользователь создает запрос, загружает требования и при наличии ставки.
Пользователь выбирает желаемые результаты, получает вопросы, отвечает на них
и затем получает пресейл-результат.
"""

PRESALE_CHAT_SYSTEM_PROMPT = f"""
Ты AI ассистент для пресейла. Отвечай на вопросы пользователя по конкретному пресейлу.
Используй только переданный контекст: краткую форму, ответы преданализа, документы,
результат оценки и предыдущий диалог. Если данных не хватает, явно скажи, что нужно уточнить.
Отвечай по-русски, кратко и прикладно.
{CASE_6_CONTEXT}
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

PRESALE_ESTIMATE_SYSTEM_PROMPT = f"""
Ты AI ассистент для пресейла, системный аналитик, архитектор и оценщик проекта.
Работай по Кейс 6.
{CASE_6_CONTEXT}

Пользователь передает один свободный текст и может приложить файлы: требования,
изображение с данными о сотрудниках, фото таблиц со ставками, документы. Самостоятельно
извлеки из текста и файлов:
1. требования заказчика;
2. ответы пользователя на вопросы преданализа;
3. роли сотрудников, грейды, количество людей, почасовые ставки;
4. желаемые результаты пресейла;
5. ограничения по срокам, поддержке, гарантии, on-premise, безопасности.

Ставки специалистов необязательны. Если пользователь не передал ставки, не задавай
дополнительный вопрос и не останавливай оценку: самостоятельно предложи состав
команды, роли, грейды и загрузку специалистов без простоя, используй рыночные
ставки из контекста и явно пометь их как допущение.

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
      {{"name": "...", "duration_months": 6, "without_idle_time": true, "roles": ["Backend Developer middle 1.0 FTE"]}}
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
    def __init__(self, client: GigaChatClient | OpenAIClient | None = None) -> None:
        self.client = client or self._client_from_settings()

    def _client_from_settings(self) -> GigaChatClient | OpenAIClient:
        if settings.ai_provider == "openai":
            return OpenAIClient()

        return GigaChatClient()

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

    def default_question_items(self) -> list[dict]:
        return [
            {
                "id": meta["id"],
                "text": question,
                "category": meta["category"],
                "required": bool(meta.get("required", True)),
                "answer_type": "text",
                "allow_file": bool(meta.get("allow_file", False)),
                "file_required": bool(meta.get("file_required", False)),
                "file_hint": meta.get("file_hint"),
                "placeholder": meta.get("placeholder"),
            }
            for question, meta in zip(
                DEFAULT_PREANALYSIS_QUESTIONS,
                DEFAULT_PREANALYSIS_QUESTION_META,
                strict=True,
            )
        ]

    def format_ordered_answers(self, answers: list[str]) -> str:
        lines = ["Ответы пользователя на вопросы преданализа:"]
        for index, question in enumerate(self.default_question_items()):
            answer = answers[index].strip() if index < len(answers) and answers[index] else ""
            lines.append(f"{index + 1}. {question['text']}")
            lines.append(f"Ответ: {answer or 'Не заполнено'}")
        return "\n".join(lines)

    async def presale_estimate(
        self,
        answers: list[str],
        attachment_groups: list[list[str]],
    ) -> dict:
        input_text = self.format_ordered_answers(answers)
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
            attachment_groups=attachment_groups,
            function_call_auto=True,
        )
        payload = self._parse_json(content)
        analysis = AnalysisResponse.model_validate(payload.get("analysis", {})).model_dump()
        project_months = int(payload.get("project_months") or 6)
        project_months = min(max(project_months, 1), 36)
        if not analysis.get("team_options"):
            analysis["team_options"] = self.default_team_options(analysis["tasks"], project_months)
        extracted_rates = payload.get("extracted_rates", [])
        if not isinstance(extracted_rates, list):
            extracted_rates = []
        if not extracted_rates:
            extracted_rates = self.default_rate_items(analysis["tasks"])
        support_scheme = str(payload.get("support_scheme") or "three_lines_24x7")
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

    async def presale_chat(self, messages: list[dict]) -> str:
        content = await self.client.chat_json(
            [
                {"role": "system", "content": PRESALE_CHAT_SYSTEM_PROMPT},
                *messages,
            ],
            temperature=0.2,
        )
        return content.strip()

    async def presale_chat_stream(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        async for chunk in self.client.chat_stream(
            [
                {"role": "system", "content": PRESALE_CHAT_SYSTEM_PROMPT},
                *messages,
            ],
            temperature=0.2,
        ):
            yield chunk

    def normalize_rates(self, raw_rates: list[dict]) -> dict[str, float]:
        rates = dict(DEFAULT_RATES)
        for item in raw_rates:
            role = item.get("role")
            hourly_rate = item.get("hourly_rate")
            if role and hourly_rate:
                rates[str(role)] = float(hourly_rate)
        return rates

    def default_rate_items(self, tasks: list[dict]) -> list[dict]:
        roles = self._task_roles(tasks) or list(DEFAULT_RATES)
        return [
            {
                "role": role,
                "grade": "middle",
                "hourly_rate": DEFAULT_RATES.get(role, 3000),
                "source": "market_assumption",
            }
            for role in roles
        ]

    def default_team_options(self, tasks: list[dict], project_months: int) -> list[dict]:
        role_hours: dict[str, float] = {}
        for task in tasks:
            for estimate in task.get("estimates", []):
                role = str(estimate.get("role") or "Backend Developer")
                role_hours[role] = role_hours.get(role, 0.0) + float(estimate.get("hours") or 0)
        if not role_hours:
            role_hours = {
                "Analyst": 320,
                "Architect": 160,
                "Backend Developer": 640,
                "Frontend Developer": 480,
                "QA Engineer": 320,
                "DevOps Engineer": 160,
                "Project Manager": 240,
            }
        monthly_capacity = max(project_months, 1) * 160
        roles = []
        for role, hours in sorted(role_hours.items()):
            fte = max(0.25, round((hours / monthly_capacity) * 4) / 4)
            roles.append(f"{role} middle {fte:g} FTE")
        return [
            {
                "name": "Сбалансированная команда",
                "duration_months": project_months,
                "without_idle_time": True,
                "roles": roles,
                "assumption": "Состав рассчитан по трудозатратам и рыночным ставкам, так как ставки не были переданы.",
            }
        ]

    def _task_roles(self, tasks: list[dict]) -> list[str]:
        roles = {
            str(estimate.get("role"))
            for task in tasks
            for estimate in task.get("estimates", [])
            if estimate.get("role")
        }
        return sorted(roles)

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
