import json, sys
from jsonschema import Draft202012Validator

SCHEMA = json.load(open("visor-asset.schema.json"))

def valid(rec):
    Draft202012Validator(SCHEMA).validate(rec)

def invalid(rec):
    errs = list(Draft202012Validator(SCHEMA).iter_errors(rec))
    assert errs, f"expected validation errors, got none for {rec}"

def base(**asset):
    return {"schema_version": "1.1.0", "asset": asset,
            "source": {"tool": "allium"}, "timestamp": "2026-05-30T00:00:00Z"}

def test_clearnet_ok():
    valid(base(ip="1.2.3.4", port=443))

def test_onion_ok():
    valid(base(onion_address="a" * 56 + ".onion",
               intro_points=["AAAA"]))

def test_ipv6_ok():
    valid(base(ip="2001:db8::1", port=443))

def test_no_identity_fails():
    invalid(base())

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
