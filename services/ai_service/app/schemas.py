from pydantic import BaseModel


class QuestionsRequest(BaseModel):
    text: str = ""


class QuestionsResponse(BaseModel):
    questions: list[str]


class PreanalysisQuestion(BaseModel):
    id: str
    text: str
    category: str
    required: bool = True
    answer_type: str = "text"
    allow_file: bool = False
    file_required: bool = False
    file_hint: str | None = None
    placeholder: str | None = None


class DefaultQuestionsResponse(BaseModel):
    questions: list[PreanalysisQuestion]


class AnalysisResponse(BaseModel):
    functional_requirements: list[dict]
    nonfunctional_requirements: list[dict]
    tasks: list[dict]
    architecture_options: list[dict]
    sizing: dict
    team_options: list[dict]
    risks: list[dict]


class PresaleEstimateResponse(BaseModel):
    analysis: AnalysisResponse
    extracted_rates: list[dict]
    effort_budget: dict
    support_budget: dict
    warranty_budget: dict
    monthly_expenses: list[dict]
    source_documents: list[dict]
