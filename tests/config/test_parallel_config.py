import config.models as models
import config.parallel as parallel


def test_supported_locations_uses_gb_not_uk() -> None:
    assert "gb" in parallel.SUPPORTED_LOCATIONS
    assert "uk" not in parallel.SUPPORTED_LOCATIONS


def test_frequency_for_boundaries() -> None:
    assert parallel.frequency_for(61) == "1w"
    assert parallel.frequency_for(60) == "1d"
    assert parallel.frequency_for(8) == "1d"
    assert parallel.frequency_for(7) == "1h"
    assert parallel.frequency_for(1) == "1h"


def test_forbidden_task_processors() -> None:
    assert any(
        "ultra".startswith(p) or p.startswith("ultra")
        for p in parallel.FORBIDDEN_TASK_PROCESSOR_PREFIXES
    )


def test_jurisdictions_loaded_and_ng_has_no_parallel_location() -> None:
    assert "in" in parallel.JURISDICTIONS
    assert "gb" in parallel.JURISDICTIONS
    assert parallel.JURISDICTIONS["gb"]["parallel_location"] == "gb"
    assert "ng" in parallel.JURISDICTIONS
    assert "parallel_location" not in parallel.JURISDICTIONS["ng"]


def test_models_config() -> None:
    assert models.EXTRACTION_MODEL == "gemini-3.5-flash"
    assert models.REASONING_MODEL == "gemini-3.1-pro-preview"
    assert 0.0 < models.EXTRACTION_TEMPERATURE < models.REASONING_TEMPERATURE
