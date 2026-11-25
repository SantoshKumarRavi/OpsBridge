"""Validate the checked-in Keycloak demo realm's identity and OTP controls."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REALM_PATH = ROOT / "infra" / "keycloak" / "opsbridge-realm.json"


def main():
    realm = json.loads(REALM_PATH.read_text(encoding="utf-8"))
    assert realm.get("realm") == "opsbridge" and realm.get("enabled") is True
    assert realm.get("otpPolicyType") == "totp"
    assert realm.get("otpPolicyAlgorithm") == "HmacSHA1"
    assert realm.get("otpPolicyDigits") == 6
    assert realm.get("otpPolicyPeriod") == 30
    assert realm.get("otpPolicyLookAheadWindow") == 1
    assert realm.get("otpPolicyCodeReusable") is False

    required_actions = {action.get("alias"): action for action in realm.get("requiredActions", [])}
    configure_otp = required_actions.get("CONFIGURE_TOTP")
    assert configure_otp, "The realm must register the Configure OTP required action."
    assert configure_otp.get("enabled") is True
    assert configure_otp.get("defaultAction") is True

    public_clients = [client for client in realm.get("clients", []) if client.get("publicClient")]
    assert public_clients, "The realm should define its browser/mobile public clients."
    assert all(client.get("standardFlowEnabled") is True for client in public_clients)
    assert all(client.get("directAccessGrantsEnabled") is False for client in public_clients)
    assert all("roles" in client.get("defaultClientScopes", []) for client in public_clients)

    print(
        "Keycloak realm config passed: TOTP policy and default enrollment are enabled; "
        "public clients use browser authorization and disable direct grants."
    )


if __name__ == "__main__":
    main()
