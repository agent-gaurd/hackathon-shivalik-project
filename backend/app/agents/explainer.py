"""Explainer — customer/analyst messages and the structured debate log.

Victim-side messages are explicit and protective; beneficiary-side messages are
generic and non-tipping (RBI KYC Master Direction / PMLA tipping-off rule).
Free-form LLM text is never shown to customers — narratives are templates.
"""
from __future__ import annotations

from ..core.types import AgentResult, Decision, TYPOLOGIES

# message keys -> text; the customer app resolves these against its language pack
CUSTOMER_MESSAGES = {
    "BLOCK": {
        "title": "payment_declined",
        "body": "This payment was declined for your safety. No police, CBI, RBI or court "
                "ever asks for money over UPI or a video call.",
    },
    "COOLING_ROOM": {
        "title": "cooling_room",
        "body": "This payment looks unusual for you. Let's pause for a moment and check "
                "a few things together.",
    },
    "HOLD_CREDIT": {
        "title": "payment_pending",
        "body": "Payment sent. The receiver's account is being verified — usually a few "
                "minutes. Your money stays protected until then.",
    },
    "STEP_UP": {
        "title": "verify_it_is_you",
        "body": "Before we send this, confirm it's really you with your phone's biometrics.",
    },
    "PAUSE": {
        "title": "under_review",
        "body": "This payment is under a quick review — usually under 10 minutes.",
    },
    "ALLOW_NUDGE": {
        "title": "heads_up",
        "body": "Payment sent. A quick note: this is your first payment to this payee.",
    },
    "ALLOW": {"title": "payment_sent", "body": "Payment sent."},
}

BENEFICIARY_GENERIC = "Credit is being processed. It may take slightly longer than usual."


def customer_message(outcome: str, hold_minutes: int | None = None) -> str:
    m = CUSTOMER_MESSAGES.get(outcome, CUSTOMER_MESSAGES["ALLOW"])
    parts = [f"{m['title']}: {m['body']}"]
    if outcome == "HOLD_CREDIT" and hold_minutes:
        parts.append(f"Expected release in about {hold_minutes} minutes.")
    return " ".join(parts)


def beneficiary_message(_decision: object = None) -> str:
    return BENEFICIARY_GENERIC  # never tips off, whatever the risk


def debate_log(agents: list[AgentResult], fused: float, typologies: list,
               routing_reason: str, counterfactual: dict | None = None) -> list[dict]:
    """The debate log is a structured transcript, not LLM chatter (PRD §6)."""
    lines = []
    for a in agents:
        if a.agent == "counsel":
            if a.score > 20:
                lines.append({"actor": "Counsel", "impact": -1, "value": a.score,
                              "text": f"legitimacy {a.score:.0f}/100 → bounded discount applied"})
            continue
        top = a.signals[0]["feature"] if a.signals else "no signals"
        val = a.signals[0]["value"] if a.signals else ""
        lines.append({
            "actor": a.agent.capitalize(), "impact": 1 if a.score >= 0 else 0,
            "value": a.score, "text": f"score {a.score:.0f} · top signal {top}={val}",
        })
    typ = " + ".join(f"{t['typology']} ({t['confidence']:.2f})" for t in typologies[:2]) or "none"
    lines.append({"actor": "Policy", "impact": 0, "value": fused,
                  "text": f"score {fused:.0f} · typology {typ} · {routing_reason}"})
    if counterfactual:
        lines.append({"actor": "Counterfactual", "impact": 0, "value": counterfactual.get("score_if"),
                      "text": counterfactual.get("text", "")})
    return lines


def analyst_narrative(decision: Decision, graph_facts: list[str]) -> str:
    typ = ", ".join(f"{t['typology']} {TYPOLOGIES.get(t['typology'], '')}"
                    for t in decision.typologies[:2]) or "no specific typology"
    top_agents = sorted((a for a in decision.agent_results if a.agent != "counsel"),
                        key=lambda a: -a.score)[:3]
    drivers = "; ".join(f"{a.agent} {a.score:.0f} ({a.signals[0]['feature'] if a.signals else '—'})"
                        for a in top_agents)
    narrative = (
        f"Deterministic template — not LLM. Txn {decision.txn_id} scored {decision.score:.0f} → "
        f"{decision.outcome}. Dominant pattern: {typ}. Main drivers: {drivers}. "
    )
    if graph_facts:
        narrative += "Graph evidence: " + "; ".join(graph_facts) + ". "
    narrative += f"Routing: {decision.routing_reason}. Hard rule: {decision.hard_rule or 'none'}."
    return narrative


def case_summary(decision: Decision, ctx: object = None) -> dict:
    typ_obj = decision.typologies[0] if decision.typologies else {}
    dominant_code = decision.dominant or typ_obj.get("typology", "NONE")
    dominant_name = TYPOLOGIES.get(dominant_code, dominant_code)
    dominant_conf = typ_obj.get("confidence", 0.0) if typ_obj else 0.0

    amount = ctx.txn.amount if ctx and getattr(ctx, "txn", None) else 0.0
    payer_bal = None
    balance_pct = None
    payee_age = None
    distinct_senders = None
    pass_through = None
    payments_1h = None

    if ctx:
        if getattr(ctx, "payer", None) and ctx.payer.balance and ctx.payer.balance > 0:
            payer_bal = round(ctx.payer.balance, 2)
            balance_pct = round((amount / ctx.payer.balance) * 100, 1)
        if getattr(ctx, "payee", None):
            payee_age = getattr(ctx.payee, "age_days", None)

        for a in decision.agent_results:
            if a.agent == "mule":
                distinct_senders = a.features.get("distinct_sources_24h")
                pt = a.features.get("pass_through_24h")
                if pt is not None:
                    pass_through = round(pt * 100, 1)
                if payee_age is None:
                    payee_age = a.features.get("account_age_days")
            elif a.agent == "velocity":
                payments_1h = a.features.get("count_out_1h")

        if distinct_senders is None and getattr(ctx, "store", None) and getattr(ctx, "payee", None):
            io = ctx.store.inflow_outflow(ctx.payee.id, since=ctx.now_ts - 86400)
            distinct_senders = io.get("distinct_sources", 0)
            if pass_through is None and io.get("inflow", 0) > 0:
                pass_through = round((io.get("outflow", 0) / io["inflow"]) * 100, 1)

        if payments_1h is None and getattr(ctx, "store", None) and getattr(ctx, "txn", None):
            v = ctx.store.velocity(ctx.txn.payer)
            payments_1h = v.get("count_out_1h", 0)
    else:
        for a in decision.agent_results:
            if a.agent == "mule":
                distinct_senders = a.features.get("distinct_sources_24h")
                pt = a.features.get("pass_through_24h")
                if pt is not None:
                    pass_through = round(pt * 100, 1)
                payee_age = a.features.get("account_age_days")
            elif a.agent == "velocity":
                payments_1h = a.features.get("count_out_1h")

    # Top drivers
    all_signals = []
    for a in decision.agent_results:
        if a.agent == "counsel":
            continue
        for sig in a.signals:
            c = sig.get("contribution")
            if c is not None and float(c) > 0:
                all_signals.append({
                    "agent": a.agent,
                    "signal": sig.get("feature", "signal"),
                    "value": sig.get("value"),
                    "contribution": round(float(c), 1),
                })
    all_signals.sort(key=lambda s: -s["contribution"])
    top_drivers = all_signals[:5]

    # Recommended action in one line
    out = decision.outcome
    if out == "BLOCK":
        action = "Block payment immediately; advise customer on safe banking and flag payee."
    elif out == "HOLD_CREDIT":
        mins = decision.hold_minutes or 30
        action = f"Hold credit for {mins} minutes, review the payee."
    elif out == "COOLING_ROOM":
        action = "Hold in cooling room for 4 hours; delay execution and require explicit customer confirmation."
    elif out == "PAUSE":
        action = "Pause payment for fraud analyst review (SLA < 10 mins)."
    elif out == "STEP_UP":
        action = "Request biometric step-up authentication on primary registered device."
    elif out == "ALLOW_NUDGE":
        action = "Allow payment with protective nudge; advise customer of first-time payee."
    else:
        action = "Allow payment; transaction metrics remain within normal customer baseline."

    # 1-2 sentence numeric summary
    parts = []
    parts.append(f"₹{amount:,.0f}" if amount else "Payment")
    if payee_age is not None:
        parts.append(f"sent to a {payee_age}-day-old payee")
    else:
        parts.append("sent to payee")
    if balance_pct is not None:
        parts.append(f"({balance_pct}% of balance)")
    parts.append(f"— scored {decision.score:.0f}/100 ({out}).")
    headline = " ".join(parts)
    if top_drivers:
        d0 = top_drivers[0]
        headline += f" Primary trigger: {d0['signal']} in {d0['agent']} agent (+{d0['contribution']:.0f})."

    return {
        "outcome": decision.outcome,
        "score": round(decision.score, 1),
        "dominant": dominant_code,
        "dominant_name": dominant_name,
        "dominant_confidence": round(dominant_conf, 2),
        "amount": amount,
        "payer_balance": payer_bal,
        "balance_pct": balance_pct,
        "payee_age_days": payee_age,
        "distinct_senders_24h": distinct_senders if distinct_senders is not None else 0,
        "pass_through_pct": pass_through if pass_through is not None else 0.0,
        "payments_last_hour": payments_1h if payments_1h is not None else 0,
        "latency_ms": round(decision.total_latency_ms, 2) if decision.total_latency_ms else 0.0,
        "drivers": top_drivers,
        "recommended_action": action,
        "headline": headline,
    }

