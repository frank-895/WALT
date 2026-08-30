from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from api.demo.models import DemoBrief
from api.demo.seed import generate_seed


def test_generate_seed_builds_tailored_atomic_data_without_credentials() -> None:
    brief = DemoBrief(
        company_name="Acme",
        visitor_name="Sam Lee",
        industry="technology",
        team_size="51-250",
        priorities=["pipeline-visibility", "follow-up"],
    )

    seed = generate_seed(brief, datetime(2026, 8, 30, 12, tzinfo=UTC))

    assert seed["companies"][0]["name"] == "Acme"
    assert seed["companies"][0]["sector"] == "information-technology"
    assert seed["companies"][0]["size"] == 250
    assert seed["contacts"][0]["first_name"] == "Sam"
    assert seed["deals"][0]["amount"] == 80_000
    assert "pipeline visibility" in seed["deals"][0]["description"]
    assert seed["sales"][0].get("password") is None


def test_demo_brief_exposes_and_enforces_small_enums() -> None:
    schema = DemoBrief.model_json_schema()

    assert schema["properties"]["priorities"]["minItems"] == 1
    assert schema["properties"]["priorities"]["maxItems"] == 3
    assert schema["properties"]["industry"]["enum"] == [
        "technology",
        "professional-services",
        "financial-services",
        "healthcare",
        "retail",
        "manufacturing",
        "other",
    ]
    with pytest.raises(ValidationError):
        DemoBrief.model_validate(
            {
                "company_name": "Acme",
                "priorities": ["unsupported"],
            }
        )
