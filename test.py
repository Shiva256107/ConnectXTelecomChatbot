from app import check_scope, ACCOUNT


def test_account_data():
    assert ACCOUNT["plan"] == "ConnectX Pro — 150 Mbps"
    assert ACCOUNT["monthly_charge"] == "₹999"


def test_competitor_pricing_is_out_of_scope():
    result = check_scope(
        "How does ConnectX compare to Airtel's pricing?", []
    )
    assert result is not None


def test_landlord_request_is_out_of_scope():
    result = check_scope(
        "Can you help me write an email to my landlord?", []
    )
    assert result is not None


def test_weather_is_out_of_scope():
    result = check_scope(
        "What's the weather like in Mumbai today?", []
    )
    assert result is not None


def test_plan_question_is_in_scope():
    result = check_scope("What is my current plan?", [])
    assert result is None