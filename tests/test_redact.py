from app.redact import redact


def test_redacts_pii_but_keeps_policy_and_amount():
    t = "Policy No: POL/0123456789 Amount: NGN 450,000 call +234 703 0835 693 or 08030835693, a@b.com, Account number: 0123456789, BVN: 12345678901"
    clean, found = redact(t)
    assert "POL/0123456789" in clean and "450,000" in clean
    assert "0835" not in clean and "a@b.com" not in clean and "12345678901" not in clean
    assert found == {"email": 1, "phone": 2, "account": 1, "bvn": 1}


def test_kenyan_number():
    clean, found = redact("reach me on +254 719 784 120")
    assert "[PHONE]" in clean and found["phone"] == 1
