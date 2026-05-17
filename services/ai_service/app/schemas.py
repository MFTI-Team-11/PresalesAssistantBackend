from pydantic import BaseModel, Field


class QuestionsRequest(BaseModel):
    text: str = ""


class QuestionsResponse(BaseModel):
    questions: list[str]


class QuestionsTextResponse(BaseModel):
    text: str


class AnalysisRequest(BaseModel):
    text: str = ""
    answers: list[str] = Field(default_factory=list)
    desired_outputs: list[str] = Field(default_factory=list)


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
