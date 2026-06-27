"""Field validation: email / phone / PAN — valid and invalid cases."""
import pytest

from app.validation import normalize_phone, validate_email, validate_pan


@pytest.mark.parametrize("good", ["a@b.com", "Sandeep@SpsTechnosoft.com", "x.y+z@sub.domain.co"])
def test_email_valid(good):
    assert "@" in validate_email(good) and validate_email(good) == good.strip().lower()


@pytest.mark.parametrize("bad", ["", "noatsign.com", "no@domain", "no@domain.", "a b@c.com", "@b.com", "x@.com"])
def test_email_invalid(bad):
    with pytest.raises(ValueError):
        validate_email(bad)


@pytest.mark.parametrize("good,expected", [
    ("9876543210", "9876543210"), ("+91 98765 43210", "9876543210"),
    ("098765-43210", "9876543210"), ("(91)9876543210", "9876543210"),
])
def test_phone_valid(good, expected):
    assert normalize_phone(good) == expected


@pytest.mark.parametrize("bad", ["12345", "98765432101", "1234567890", "abcdefghij", "", "5876543210"])
def test_phone_invalid(bad):
    with pytest.raises(ValueError):
        normalize_phone(bad)


@pytest.mark.parametrize("good", ["ABCDE1234F", "abcde1234f"])
def test_pan_valid(good):
    assert validate_pan(good) == good.upper()


@pytest.mark.parametrize("bad", ["ABCD1234F", "ABCDE12345", "ABCDE1234", "12345ABCDF", "", "ABCDE-234F"])
def test_pan_invalid(bad):
    with pytest.raises(ValueError):
        validate_pan(bad)
