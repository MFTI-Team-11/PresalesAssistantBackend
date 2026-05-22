from pydantic import BaseModel, Field


class QuestionsRequest(BaseModel):
    text: str = ""


class QuestionsResponse(BaseModel):
    questions: list[str]


class ChatRequest(BaseModel):
    messages: list[dict]


class ChatResponse(BaseModel):
    message: str


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
    functional_requirements: list[dict] = Field(default_factory=list)
    nonfunctional_requirements: list[dict] = Field(default_factory=list)
    tasks: list[dict] = Field(default_factory=list)
    architecture_options: list[dict] = Field(default_factory=list)
    sizing: dict = Field(default_factory=dict)
    team_options: list[dict] = Field(default_factory=list)
    risks: list[dict] = Field(default_factory=list)


class PresaleEstimateResponse(BaseModel):
    analysis: AnalysisResponse
    extracted_rates: list[dict]
    effort_budget: dict
    support_budget: dict
    warranty_budget: dict
    monthly_expenses: list[dict]
    source_documents: list[dict]
