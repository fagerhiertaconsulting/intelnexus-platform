import os
import pytest
from unittest.mock import patch, MagicMock
from app.config import is_mock_osint
from app.models.entity import Entity, EntityType
from app.models.relationship import RelationshipType
from app.transforms.social_footprint_transform import SocialFootprintTransform, validate_probe_response


@pytest.mark.asyncio
async def test_social_footprint_mock_mode():
    """Verifierar att SocialFootprintTransform genererar deterministisk mock-data i testmiljö."""
    transform = SocialFootprintTransform()
    seed = Entity(type=EntityType.PERSON, name="Sophia Miller", case_id="test_case_mock")

    # konftest sätter automatiskt MOCK_OSINT=true
    assert is_mock_osint() is True

    res = await transform.execute(seed)
    assert res.success is True
    assert len(res.entities) == 2
    assert len(res.relationships) == 2
    assert len(res.evidence_items) == 3  # 2 bevisfiler för prober + 1 sammanfattning

    platforms = [e.attributes.get("platform") for e in res.entities]
    assert "GitHub" in platforms
    assert "GitLab" in platforms

    for r in res.relationships:
        assert r.relation_type == RelationshipType.HAS_ALIAS
        assert r.source_id == seed.id

    for ev in res.evidence_items:
        assert ev.sha256 is not None
        assert len(ev.sha256) == 64


@pytest.mark.asyncio
async def test_social_footprint_invalid_username():
    """Validerar felhantering vid tomt eller ogiltigt användarnamn."""
    transform = SocialFootprintTransform()
    seed = Entity(type=EntityType.USERNAME, name="   ", case_id="test_case_mock")

    res = await transform.execute(seed)
    assert res.success is False
    assert "Ogiltigt" in res.error_message


def test_validate_probe_response_whatsmyname():
    """Validerar WhatsMyName-reglerna för att undvika falska positiva."""
    # 1. GitHub
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"login": "torvalds"}
    mock_resp.text = '{"login": "torvalds"}'
    assert validate_probe_response("GitHub", "torvalds", mock_resp) is True

    mock_resp.json.return_value = {"message": "Not Found"}
    assert validate_probe_response("GitHub", "unknown_user", mock_resp) is False

    # 2. Steam falsk positiv (200 men 'The specified profile could not be found.')
    steam_fail = MagicMock()
    steam_fail.status_code = 200
    steam_fail.text = "<h3>The specified profile could not be found.</h3>"
    assert validate_probe_response("Steam", "nobody", steam_fail) is False

    steam_ok = MagicMock()
    steam_ok.status_code = 200
    steam_ok.text = '<div class="actual_persona_name">GamerPro</div>'
    assert validate_probe_response("Steam", "gamerpro", steam_ok) is True

    # 3. Telegram falsk positiv (200 men utan registrerad profil)
    tg_fail = MagicMock()
    tg_fail.status_code = 200
    tg_fail.text = '<div class="tgme_page_icon"></div>If you have Telegram, you can contact @nobody'
    assert validate_probe_response("Telegram", "nobody", tg_fail) is False

    tg_ok = MagicMock()
    tg_ok.status_code = 200
    tg_ok.text = '<div class="tgme_page_title">Security Channel</div><div class="tgme_page_extra">@secchan</div>'
    assert validate_probe_response("Telegram", "secchan", tg_ok) is True

    # 4. PyPI
    pypi_fail = MagicMock()
    pypi_fail.status_code = 404
    assert validate_probe_response("PyPI", "nobody", pypi_fail) is False

    pypi_ok = MagicMock()
    pypi_ok.status_code = 200
    pypi_ok.text = '<div class="user-profile">Packages by dev</div>'
    assert validate_probe_response("PyPI", "dev", pypi_ok) is True

    # 5. GitLab
    gl_ok = MagicMock()
    gl_ok.status_code = 200
    gl_ok.json.return_value = [{"username": "dev"}]
    gl_ok.text = '[{"username": "dev"}]'
    assert validate_probe_response("GitLab", "dev", gl_ok) is True

    gl_fail = MagicMock()
    gl_fail.status_code = 200
    gl_fail.json.side_effect = ValueError("Invalid JSON")
    gl_fail.text = "page not found"
    assert validate_probe_response("GitLab", "dev", gl_fail) is False

    # 6. HackerNews & Keybase & Reddit
    hn_ok = MagicMock()
    hn_ok.status_code = 200
    hn_ok.json.return_value = {"id": "dev", "created": 123}
    hn_ok.text = '{"id": "dev"}'
    assert validate_probe_response("HackerNews", "dev", hn_ok) is True

    hn_fail = MagicMock()
    hn_fail.status_code = 200
    hn_fail.json.return_value = None
    assert validate_probe_response("HackerNews", "dev", hn_fail) is False

    kb_ok = MagicMock()
    kb_ok.status_code = 200
    kb_ok.json.return_value = {"status": {"code": 0}, "them": [{"id": "abc"}]}
    kb_ok.text = "{}"
    assert validate_probe_response("Keybase", "dev", kb_ok) is True

    kb_fail = MagicMock()
    kb_fail.status_code = 200
    kb_fail.json.return_value = {"status": {"code": 1}, "them": []}
    assert validate_probe_response("Keybase", "dev", kb_fail) is False

    rd_ok = MagicMock()
    rd_ok.status_code = 200
    rd_ok.json.return_value = {"kind": "t2", "data": {"name": "dev"}}
    rd_ok.text = "{}"
    assert validate_probe_response("Reddit", "dev", rd_ok) is True

    rd_fail = MagicMock()
    rd_fail.status_code = 200
    rd_fail.json.return_value = {"error": 404}
    assert validate_probe_response("Reddit", "dev", rd_fail) is False

    # 7. DevTo, DockerHub, Codeberg, Wikipedia, MastodonSocial
    for p in ["DevTo", "DockerHub", "Codeberg", "MastodonSocial"]:
        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"username": "dev"}
        resp_ok.text = "{}"
        assert validate_probe_response(p, "dev", resp_ok) is True

        resp_fail = MagicMock()
        resp_fail.status_code = 200
        resp_fail.json.return_value = {"username": "other"}
        assert validate_probe_response(p, "dev", resp_fail) is False

    wiki_ok = MagicMock()
    wiki_ok.status_code = 200
    wiki_ok.json.return_value = {"query": {"users": [{"userid": 123, "name": "dev"}]}}
    wiki_ok.text = "{}"
    assert validate_probe_response("Wikipedia", "dev", wiki_ok) is True

    wiki_fail = MagicMock()
    wiki_fail.status_code = 200
    wiki_fail.json.return_value = {"query": {"users": [{"name": "dev", "missing": ""}]}}
    assert validate_probe_response("Wikipedia", "dev", wiki_fail) is False

    # 8. Pinterest & Kaggle
    pin_ok = MagicMock()
    pin_ok.status_code = 200
    pin_ok.text = '<script id="__PWS_DATA__">{"username":"dev"}</script>'
    assert validate_probe_response("Pinterest", "dev", pin_ok) is True

    pin_fail = MagicMock()
    pin_fail.status_code = 200
    pin_fail.text = "User not found on Pinterest"
    assert validate_probe_response("Pinterest", "dev", pin_fail) is False

    kaggle_ok = MagicMock()
    kaggle_ok.status_code = 200
    kaggle_ok.text = '<div class="profile">Dev profile</div>'
    assert validate_probe_response("Kaggle", "dev", kaggle_ok) is True

    kaggle_fail = MagicMock()
    kaggle_fail.status_code = 200
    kaggle_fail.text = "page not found"
    assert validate_probe_response("Kaggle", "dev", kaggle_fail) is False

    # 9. Generisk profil
    gen_ok = MagicMock()
    gen_ok.status_code = 200
    gen_ok.text = "Welcome to dev page"
    assert validate_probe_response("SoundCloud", "dev", gen_ok) is True

    gen_fail = MagicMock()
    gen_fail.status_code = 200
    gen_fail.text = "We couldn't find that page"
    assert validate_probe_response("SoundCloud", "dev", gen_fail) is False


@pytest.mark.asyncio
async def test_social_footprint_sharp_mode_probe():
    """Verifierar att skarp probe (MOCK_OSINT=false) endast skapar noder för verifierade profiler."""
    transform = SocialFootprintTransform()
    seed = Entity(type=EntityType.PERSON, name="devuser", case_id="test_case_sharp")

    # Simulera svar från externa servrar
    async def fake_get(url, *args, **kwargs):
        mock_resp = MagicMock()
        url_str = str(url)

        if "api.github.com/users/devuser" in url_str:
            mock_resp.status_code = 200
            mock_resp.content = b'{"login": "devuser", "id": 555}'
            mock_resp.text = '{"login": "devuser", "id": 555}'
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.json.return_value = {"login": "devuser", "id": 555}
            return mock_resp

        if "steamcommunity.com" in url_str:
            # Falsk 200 (profil saknas)
            mock_resp.status_code = 200
            mock_resp.content = b"The specified profile could not be found."
            mock_resp.text = "The specified profile could not be found."
            mock_resp.headers = {"content-type": "text/html"}
            return mock_resp

        if "t.me" in url_str:
            # Falsk 200 Telegram
            mock_resp.status_code = 200
            mock_resp.content = b'<div class="tgme_page_icon"></div>Telegram: Contact @devuser'
            mock_resp.text = '<div class="tgme_page_icon"></div>Telegram: Contact @devuser'
            mock_resp.headers = {"content-type": "text/html"}
            return mock_resp

        # Övriga 404
        mock_resp.status_code = 404
        mock_resp.content = b"Not found"
        mock_resp.text = "Not found"
        mock_resp.headers = {"content-type": "text/plain"}
        return mock_resp

    with patch.dict(os.environ, {"MOCK_OSINT": "false"}), patch("httpx.AsyncClient.get", side_effect=fake_get):
        res = await transform.execute(seed)
        assert res.success is True
        # Endast GitHub ska bekräftas
        assert len(res.entities) == 1
        assert res.entities[0].attributes["platform"] == "GitHub"
        assert res.entities[0].attributes["verified"] is True
        assert res.entities[0].attributes["http_status"] == 200

        # Kontrollera att beviset sparades med korrekt sha256
        assert len(res.evidence_items) == 2  # 1 probe + 1 sammanfattning
        probe_ev = [e for e in res.evidence_items if "probe" in e.file_path][0]
        assert probe_ev.sha256 is not None
        assert len(probe_ev.sha256) == 64
