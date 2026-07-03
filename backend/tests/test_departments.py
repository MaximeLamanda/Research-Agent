from app.agent.llm_extractor import SYSTEM_PROMPT, system_prompt_for_country
from app.agent.schemas import ProjectExtraction
from app.data.departments import ensure_department, format_department, infer_country_from_department, normalize_department


def test_format_department_from_code():
    assert format_department("69") == "69 - Rhône"
    assert format_department("38") == "38 - Isère"


def test_department_name_from_code():
    from app.data.departments import department_name

    assert department_name("69") == "Rhône"
    assert department_name("38") == "Isère"


def test_normalize_department_from_name():
    assert normalize_department("Rhône") == "69 - Rhône"
    assert normalize_department("rhone") == "69 - Rhône"


def test_normalize_department_from_code():
    assert normalize_department("69") == "69 - Rhône"


def test_normalize_department_from_formatted_value():
    assert normalize_department("69 - Rhône") == "69 - Rhône"
    assert normalize_department("69 — Rhône") == "69 - Rhône"


def test_format_department_from_code_de():
    assert format_department("BY", "DE") == "BY - Bayern"
    assert format_department("NW", "DE") == "NW - Nordrhein-Westfalen"


def test_normalize_department_from_german_name():
    assert normalize_department("Bayern", "DE") == "BY - Bayern"
    assert normalize_department("Nordrhein-Westfalen", "DE") == "NW - Nordrhein-Westfalen"


def test_ensure_department_uses_fallback_code():
    assert ensure_department(None, "69") == "69 - Rhône"
    assert ensure_department("Rhône", "38") == "69 - Rhône"


def test_ensure_department_uses_fallback_code_de():
    assert ensure_department(None, "BY", "DE") == "BY - Bayern"


def test_project_extraction_normalizes_department():
    extraction = ProjectExtraction(name="Projet test", department="Rhône", is_relevant=True)
    assert extraction.department == "69 - Rhône"


def test_project_extraction_normalizes_german_department():
    extraction = ProjectExtraction.model_validate(
        {"name": "Projekt test", "department": "Bayern", "is_relevant": True},
        context={"country": "DE"},
    )
    assert extraction.department == "BY - Bayern"


def test_project_extraction_irrelevant_defaults():
    extraction = ProjectExtraction(is_relevant=False)
    assert extraction.is_relevant is False
    assert extraction.name == ""


def test_llm_prompt_requires_department_format():
    assert '"69 - Rhône"' in SYSTEM_PROMPT
    assert "code - nom" in SYSTEM_PROMPT


def test_llm_prompt_german_department_format():
    prompt = system_prompt_for_country("DE")
    assert '"BY - Bayern"' in prompt
    assert "Bundesland" in prompt


def test_infer_country_from_department():
    assert infer_country_from_department("69 - Rhône") == "FR"
    assert infer_country_from_department("BY - Bayern") == "DE"
    assert infer_country_from_department(None) is None


def test_llm_prompt_requires_relevance_filter():
    assert "is_relevant" in SYSTEM_PROMPT
    assert "aménagement routier" in SYSTEM_PROMPT
    assert "NOUVELLE construction" in SYSTEM_PROMPT


def test_llm_prompt_requires_english_output():
    assert "EN ANGLAIS" in SYSTEM_PROMPT
    assert "traduire" in SYSTEM_PROMPT.lower()
    assert "lead_pitch" in SYSTEM_PROMPT
    assert "EN ANGLAIS" in SYSTEM_PROMPT.split("lead_pitch")[1]
