from app.schemas import AnalysisResponse


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

