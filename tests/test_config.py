from __future__ import annotations

from offrun.config import load_config, validate_config


def test_load_and_validate_config(temp_repo):
    config = load_config(temp_repo)

    assert config.project["project"]["name"] == "offrun"
    assert "descriptive market-liquidity evidence" in config.project["claim_boundary"][
        "required_report_phrases"
    ]
    messages = validate_config(temp_repo)
    assert "schemas ok" in messages
