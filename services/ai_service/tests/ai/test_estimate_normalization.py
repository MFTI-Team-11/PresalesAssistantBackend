from app.schemas import AnalysisResponse
from app.service import AiService
import pytest


class FakeEstimateClient:
    async def chat_json(self, *args, **kwargs) -> str:
        return """
        {
          "analysis": {
            "tasks": [
              {"name": "API", "estimates": [{"role": "Backend Developer", "hours": 320}]}
            ]
          },
          "extracted_rates": [],
          "project_months": 2
        }
        """


def test_analysis_response_defaults_missing_sections() -> None:
    analysis = AnalysisResponse.model_validate(
        {
            "functional_requirements": [],
            "nonfunctional_requirements": [],
            "tasks": [],
            "architecture_options": [],
            "sizing": {},
            "team_options": [],
        }
    )

    assert analysis.risks == []


def test_rates_question_is_optional() -> None:
    items = AiService().default_question_items()
    rates_question = next(item for item in items if item["id"] == "rates_and_roles")

    assert rates_question["required"] is False
    assert rates_question["allow_file"] is True


def test_default_team_and_rates_when_rates_are_missing() -> None:
    service = AiService()
    tasks = [
        {
            "name": "Backend",
            "estimates": [
                {"role": "Backend Developer", "hours": 320},
                {"role": "QA Engineer", "hours": 120},
            ],
        }
    ]

    rates = service.default_rate_items(tasks)
    team_options = service.default_team_options(tasks, project_months=2)

    assert rates == [
        {
            "role": "Backend Developer",
            "grade": "middle",
            "hourly_rate": 3600,
            "source": "market_assumption",
        },
        {
            "role": "QA Engineer",
            "grade": "middle",
            "hourly_rate": 2600,
            "source": "market_assumption",
        },
    ]
    assert team_options[0]["without_idle_time"] is True
    assert "Backend Developer middle 1 FTE" in team_options[0]["roles"]


def test_filter_estimate_result_keeps_only_selected_outputs() -> None:
    result = {
        "analysis": {
            "functional_requirements": [{"code": "FR-001"}],
            "nonfunctional_requirements": [{"code": "NFR-001"}],
            "tasks": [{"name": "API"}],
            "architecture_options": [{"name": "Monolith"}],
            "sizing": {"summary": "Small"},
            "team_options": [{"name": "Team"}],
            "risks": [{"risk": "Scope"}],
        },
        "effort_budget": {"total_hours": 100},
        "support_budget": {"monthly_cost": 10},
        "warranty_budget": {"annual_cost": 20},
        "monthly_expenses": [{"month": 1}],
    }

    filtered = AiService().filter_estimate_result(result, ["architecture", "risks"])

    assert filtered["analysis"]["architecture_options"] == [{"name": "Monolith"}]
    assert filtered["analysis"]["risks"] == [{"risk": "Scope"}]
    assert filtered["analysis"]["tasks"] == []
    assert filtered["analysis"]["sizing"] == {}
    assert filtered["support_budget"] == {}


@pytest.mark.anyio
async def test_presale_estimate_fills_team_and_rates_without_uploaded_rates() -> None:
    result = await AiService(client=FakeEstimateClient()).presale_estimate(
        answers=[],
        desired_outputs=[],
        attachment_groups=[],
    )

    assert result["extracted_rates"][0]["role"] == "Backend Developer"
    assert result["analysis"]["team_options"][0]["without_idle_time"] is True
