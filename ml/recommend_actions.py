def get_risk_tier(probability):
    """
    Convert churn probability into InsightFlow risk tier.
    """

    if probability < 0.15:
        return "LOW"

    elif probability < 0.33:
        return "MEDIUM"

    elif probability < 0.60:
        return "HIGH"

    return "CRITICAL"


def get_recommendations(customer, risk_tier):
    """
    Generate rule-based Customer Success actions.

    These are decision-support recommendations,
    not causal claims.
    """

    actions = []

    # -------------------------------------------------
    # Contract
    # -------------------------------------------------

    if customer.get("Contract") == "Month-to-month":
        actions.append(
            "Explore annual contract conversion "
            "or loyalty incentive."
        )

    # -------------------------------------------------
    # Tech support
    # -------------------------------------------------

    if customer.get("TechSupport") == "No":
        actions.append(
            "Review support needs and consider "
            "proactive technical assistance."
        )

    # -------------------------------------------------
    # Online security
    # -------------------------------------------------

    if customer.get("OnlineSecurity") == "No":
        actions.append(
            "Discuss security-service adoption "
            "where relevant to the customer."
        )

    # -------------------------------------------------
    # Payment method
    # -------------------------------------------------

    if customer.get("PaymentMethod") == "Electronic check":
        actions.append(
            "Review payment experience and consider "
            "automatic-payment options."
        )

    # -------------------------------------------------
    # Tenure
    # -------------------------------------------------

    tenure = customer.get("tenure")

    if tenure is not None and tenure < 12:
        actions.append(
            "Prioritize early-lifecycle engagement "
            "and onboarding follow-up."
        )

    # -------------------------------------------------
    # Risk escalation
    # -------------------------------------------------

    if risk_tier == "CRITICAL":
        actions.insert(
            0,
            "Immediate CSM retention outreach recommended."
        )

    elif risk_tier == "HIGH":
        actions.insert(
            0,
            "Add customer to proactive retention queue."
        )

    elif risk_tier == "MEDIUM":
        actions.insert(
            0,
            "Monitor account and schedule proactive check-in."
        )

    else:
        actions.insert(
            0,
            "Maintain standard engagement cadence."
        )

    return actions[:5]