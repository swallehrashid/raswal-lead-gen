import logging

import pytest

from pipeline.settings import Env, MissingSecrets, install_secret_redaction


def test_missing_secret_names_variable_and_checklist_section():
    env = Env()
    with pytest.raises(MissingSecrets) as e:
        env.require("GOOGLE_PLACES_API_KEY", "SUPABASE_SERVICE_ROLE_KEY")
    msg = str(e.value)
    assert "GOOGLE_PLACES_API_KEY" in msg and "SETUP_CHECKLIST.md §2" in msg
    assert "SUPABASE_SERVICE_ROLE_KEY" in msg and "SETUP_CHECKLIST.md §4" in msg
    assert "--offline" in msg


def test_present_secrets_pass():
    Env(google_places_api_key="x" * 20).require("GOOGLE_PLACES_API_KEY")


def test_secrets_are_redacted_from_logs(caplog):
    env = Env(psi_api_key="AIzaSECRETSECRETSECRET")
    logging.getLogger().addHandler(caplog.handler)
    install_secret_redaction(env)
    logging.getLogger("t").warning("GET https://x/runPagespeed?key=%s failed", "AIzaSECRETSECRETSECRET")
    assert "AIzaSECRET" not in caplog.text
    assert "key=***" in caplog.text
