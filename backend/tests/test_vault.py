import pytest
from app.core.vault import LocalCredentialVault


def test_credential_vault_encryption(tmp_path):
    vault = LocalCredentialVault(db_path=tmp_path / "test_vault.db")

    # Kontrollera att nyckel initialt saknas
    assert vault.has_key("SHODAN_API_KEY") is False
    assert vault.get_key("SHODAN_API_KEY") is None

    # Sätt nyckel och kryptera
    secret_token = "shodan_super_secret_token_12345"
    vault.set_key("SHODAN_API_KEY", secret_token, "Shodan Enterprise")

    assert vault.has_key("SHODAN_API_KEY") is True
    decrypted = vault.get_key("SHODAN_API_KEY")
    assert decrypted == secret_token

    # Kontrollera maskerad listning
    keys_list = vault.list_configured_keys()
    shodan_entry = next(k for k in keys_list if k["key_name"] == "SHODAN_API_KEY")
    assert shodan_entry["is_configured"] is True
    assert shodan_entry["masked_value"] == "sho...2345"
    assert secret_token not in shodan_entry["masked_value"]

    # Radering
    assert vault.delete_key("SHODAN_API_KEY") is True
    assert vault.has_key("SHODAN_API_KEY") is False
