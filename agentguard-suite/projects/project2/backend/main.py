import os
import sys
from collections import Counter, deque, defaultdict
from pathlib import Path
from typing import Optional
import random
import uuid

# Ensure backend directory is in sys.path for direct execution or submodule import
BACKEND_DIR = str(Path(__file__).resolve().parent)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.types import Txn, now, Account, OUTCOME_META, TYPOLOGIES
from app.agents.orchestrator import Orchestrator
from app.db.memory import MemoryStore
from app.db.sqlite import Db
from app.graph.memgraph import Graph
from app.policy.engine import PolicyEngine
from app.chase.engine import ChaseEngine
from app.ledger.chain import Ledger
from app.holds.engine import HoldEngine

STATIC = Path(__file__).parent / "static"


class DummyHub:
    def publish(self, topic, payload): pass


class DummyMetrics:
    def record_decision(self, d, txn): pass


class DummyCases:
    def create(self, txn, d, status):
        class CaseMock:
            case_id = "C-" + txn.txn_id[:8]
            def to_dict(self): return {"case_id": self.case_id}
        return CaseMock()


class Services:
    def __init__(self):
        self.db = Db(":memory:")
        self.store = MemoryStore()
        self.graph = Graph()
        self.policy = PolicyEngine(self.db)
        self.policy.load_default()
        self.chase = ChaseEngine(self)
        self.ledger = Ledger(self.db)
        self.holds = HoldEngine(self)
        self.cases = DummyCases()
        self.hub = DummyHub()
        self.metrics = DummyMetrics()


app = FastAPI(title="AgentGuard API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
svcs = Services()
orchestrator = Orchestrator(svcs)
history: deque = deque(maxlen=300)   # recent decisions for the dashboard


def ensure_account(aid: str, **kw) -> Account:
    acc = svcs.store.accounts.get(aid)
    if acc is None:
        acc = svcs.store.add_account(Account(id=aid, name=kw.pop("name", aid), persona=kw.pop("persona", "salaried"),
                                             vpa=f"{aid}@upi", phone="000", **kw))
        svcs.graph.add_node(aid, "Account", acc.name, persona=acc.persona)
    return acc


# Seed with some accounts for testing
ensure_account("acc_1", name="Payer", persona="gig")
ensure_account("acc_2", name="Payee", persona="biz")


class TxnRequest(BaseModel):
    payer: str
    payee: str
    amount: float
    channel: str = "p2p"
    device_fp: str = ""
    geo: str = ""
    on_call: bool = False
    call_minutes: float = 0.0
    screen_share: bool = False
    sim_changed_hrs_ago: Optional[float] = None
    pin_reset_hrs_ago: Optional[float] = None


def dump_model(m: BaseModel) -> dict:
    return m.model_dump() if hasattr(m, "model_dump") else m.dict()


async def process(req: TxnRequest, scenario: str = "manual") -> dict:
    ensure_account(req.payer)
    ensure_account(req.payee)
    data = dump_model(req)
    txn = Txn(txn_id=uuid.uuid4().hex, ts=now(), **data)
    decision = await orchestrator.score(txn)
    d = decision.to_dict()
    if d["outcome"] != "BLOCK":   # blocked money never moved
        svcs.graph.add_edge(txn.payer, txn.payee, "PAID", txn_id=txn.txn_id, ts=txn.ts, amount=txn.amount)
    if txn.device_fp:
        svcs.graph.add_node(txn.device_fp, "Device", txn.device_fp)
        svcs.graph.add_edge(txn.payer, txn.device_fp, "USED_DEVICE", ts=txn.ts)
        svcs.store.accounts[txn.payer].known_devices.add(txn.device_fp)
    svcs.graph.refresh_warm_properties(svcs.store)
    d["request"] = {**data, "scenario": scenario}
    history.appendleft(d)
    return d


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/analyze")
async def analyze(req: TxnRequest):
    return await process(req)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/meta")
def meta():
    return {"outcomes": OUTCOME_META, "typologies": TYPOLOGIES}


@app.get("/transactions")
def transactions(limit: int = 100):
    return list(history)[:limit]


@app.get("/stats")
def stats():
    h = list(history)
    lat = sorted(x["total_latency_ms"] for x in h)
    return {
        "total": len(h),
        "by_outcome": Counter(x["outcome"] for x in h),
        "by_typology": Counter(x["dominant"] for x in h if x["dominant"]),
        "avg_latency_ms": round(sum(lat) / len(lat), 1) if lat else 0,
        "p95_latency_ms": lat[int(len(lat) * 0.95)] if lat else 0,
    }


@app.get("/graph")
def graph():
    return svcs.graph.subgraph_for(list(svcs.graph.nodes), {"PAID", "USED_DEVICE"})


def format_display_name(aid: str, acc: Optional[Account] = None) -> str:
    if acc and acc.name and acc.name != aid and not acc.name.startswith("acc_"):
        return acc.name
    parts = aid.split("_")
    suffix = parts[-1] if len(parts) > 1 else aid[-5:]
    if acc and acc.persona:
        persona_map = {
            "elderly": "Elderly Account",
            "salaried": "Salaried Account",
            "gig": "Gig Worker",
            "student": "Student Account",
            "merchant": "Merchant Account",
            "biz": "Business Account",
            "mule": "Mule Beneficiary",
            "ring": "Syndicate Cashout",
        }
        prefix = persona_map.get(acc.persona, "Account")
        return f"{prefix} ending {suffix}"
    return f"Account ending {suffix}"


def compute_account_verdict(aid: str, acc: Optional[Account], recent_scores: list[float], shared_cnt: int) -> tuple[float, str, list[str]]:
    role = acc.persona if acc else "user"
    max_s = max(recent_scores, default=0.0)
    net_r = svcs.graph.network_risk.get(aid, 0.0)

    # Consistent risk level & score calculation
    if role in ("mule", "ring"):
        score = max(max_s, net_r, 86.0)
        lvl = "High risk"
    elif acc and acc.sanctioned:
        score = max(max_s, 95.0)
        lvl = "High risk"
    elif max_s >= 65 or net_r >= 65:
        score = max(max_s, net_r)
        lvl = "High risk"
    elif max_s >= 30 or net_r >= 30 or shared_cnt >= 2 or role in ("dormant",):
        score = max(max_s, net_r, 35.0 if shared_cnt >= 2 else 30.0)
        lvl = "Watch"
    else:
        score = max(max_s, net_r)
        lvl = "Safe"
    score = round(min(100.0, max(0.0, score)), 1)

    # 2-4 plain-English verdict reasons
    reasons = []
    if lvl == "High risk":
        if role in ("mule", "ring"):
            reasons.append("Identified as a high-velocity collector or syndicate cash-out mule account.")
        if shared_cnt >= 3:
            reasons.append(f"Shares phone device with {shared_cnt} other accounts, indicating a device farm.")
        flags_found = []
        for d in history:
            if d.get("request", {}).get("payer") == aid or d.get("request", {}).get("payee") == aid:
                req = d.get("request", {})
                if req.get("on_call"): flags_found.append("phone call coercion")
                if req.get("screen_share"): flags_found.append("remote screen-sharing")
                if req.get("sim_changed_hrs_ago"): flags_found.append("recent SIM swap")
        if flags_found:
            reasons.append(f"Suspicious activity flags recorded: {', '.join(set(flags_found))}.")
        if not reasons:
            reasons.append("Extreme transaction deviation detected compared to normal baselines.")
        reasons.append("Immediate fraud intervention or credit lien recommended to protect funds.")
    elif lvl == "Watch":
        if shared_cnt > 0:
            reasons.append(f"Phone or device linked to {shared_cnt} other account{'s' if shared_cnt != 1 else ''} in the network.")
        if max_s >= 30:
            reasons.append("Payment triggered moderate behavioral or timing divergence.")
        if not reasons:
            reasons.append("Uncharacteristic transfer pattern observed relative to customer history.")
        reasons.append("Proceed with caution and require secondary biometric confirmation if amount increases.")
    else:
        reasons.append("All transactions match regular customer spending, timing, and velocity profiles.")
        reasons.append("Payments executed from registered, verified personal device.")
        reasons.append("No linkages to known mule syndicates or reported entities.")

    return score, lvl, reasons


@app.get("/v1/accounts")
def v1_accounts():
    res = []
    for aid, a in svcs.store.accounts.items():
        res.append({
            "id": aid,
            "display_name": format_display_name(aid, a),
            "role": a.persona or "user",
        })
    return res


@app.get("/v1/graph/account/{account_id}")
def v1_account_money_map(account_id: str, hops: int = 1):
    acc = svcs.store.accounts.get(account_id)
    if acc is None:
        acc = ensure_account(account_id)

    inbound_by_sender = defaultdict(lambda: {"amount": 0.0, "count": 0, "status": "Completed", "ts_list": []})
    outbound_by_payee = defaultdict(lambda: {"amount": 0.0, "count": 0, "status": "Completed", "ts_list": []})

    seen_txns = set()
    my_scores = []

    for d in history:
        req = d.get("request", {})
        tx_id = d.get("txn_id")
        if tx_id:
            seen_txns.add(tx_id)
        amt = float(req.get("amount", 0))
        outc = d.get("outcome", "ALLOW")
        ts = d.get("ts", now())
        st = "Completed"
        if outc == "BLOCK":
            st = "Blocked"
        elif outc in ("HOLD_CREDIT", "COOLING_ROOM", "PAUSE"):
            st = "On Hold"

        if req.get("payee") == account_id:
            src = req.get("payer")
            if src:
                inbound_by_sender[src]["amount"] += amt
                inbound_by_sender[src]["count"] += 1
                inbound_by_sender[src]["ts_list"].append(ts)
                if st != "Completed":
                    inbound_by_sender[src]["status"] = st
            my_scores.append(float(d.get("score", 0)))

        if req.get("payer") == account_id:
            dst = req.get("payee")
            if dst:
                outbound_by_payee[dst]["amount"] += amt
                outbound_by_payee[dst]["count"] += 1
                outbound_by_payee[dst]["ts_list"].append(ts)
                if st != "Completed":
                    outbound_by_payee[dst]["status"] = st
            my_scores.append(float(d.get("score", 0)))

    # Check graph edges for any seeded connections
    for idx in svcs.graph._in.get(account_id, ()):
        e = svcs.graph.edges[idx]
        if e["type"] == "PAID" and e["props"].get("txn_id") not in seen_txns:
            src = e["src"]
            amt = float(e["props"].get("amount", 0))
            ts = float(e["props"].get("ts", now()))
            inbound_by_sender[src]["amount"] += amt
            inbound_by_sender[src]["count"] += 1
            inbound_by_sender[src]["ts_list"].append(ts)

    for idx in svcs.graph._out.get(account_id, ()):
        e = svcs.graph.edges[idx]
        if e["type"] == "PAID" and e["props"].get("txn_id") not in seen_txns:
            dst = e["dst"]
            amt = float(e["props"].get("amount", 0))
            ts = float(e["props"].get("ts", now()))
            outbound_by_payee[dst]["amount"] += amt
            outbound_by_payee[dst]["count"] += 1
            outbound_by_payee[dst]["ts_list"].append(ts)

    def peer_risk_level(peer_id: str) -> str:
        p_acc = svcs.store.accounts.get(peer_id)
        p_scores = [float(d["score"]) for d in history if d.get("request", {}).get("payer") == peer_id or d.get("request", {}).get("payee") == peer_id]
        p_shared = svcs.graph.shared_device_count(peer_id)
        _s, lvl, _r = compute_account_verdict(peer_id, p_acc, p_scores, p_shared)
        return lvl

    shared_dev_cnt = svcs.graph.shared_device_count(account_id)
    my_risk_score, my_risk_level, my_reasons = compute_account_verdict(account_id, acc, my_scores, shared_dev_cnt)

    senders = []
    for s_id, s_data in sorted(inbound_by_sender.items(), key=lambda kv: -kv[1]["amount"]):
        senders.append({
            "id": s_id,
            "display_name": format_display_name(s_id, svcs.store.accounts.get(s_id)),
            "amount": round(s_data["amount"], 2),
            "count": s_data["count"],
            "risk_level": peer_risk_level(s_id),
            "status": s_data["status"],
            "first_ts": min(s_data["ts_list"]) if s_data["ts_list"] else None,
            "last_ts": max(s_data["ts_list"]) if s_data["ts_list"] else None,
        })

    payees = []
    for p_id, p_data in sorted(outbound_by_payee.items(), key=lambda kv: -kv[1]["amount"]):
        payees.append({
            "id": p_id,
            "display_name": format_display_name(p_id, svcs.store.accounts.get(p_id)),
            "amount": round(p_data["amount"], 2),
            "count": p_data["count"],
            "risk_level": peer_risk_level(p_id),
            "status": p_data["status"],
            "first_ts": min(p_data["ts_list"]) if p_data["ts_list"] else None,
            "last_ts": max(p_data["ts_list"]) if p_data["ts_list"] else None,
        })

    # Shared devices
    shared_devices = []
    seen_devs = set()
    for idx in svcs.graph._out.get(account_id, ()):
        e = svcs.graph.edges[idx]
        if e["type"] == "USED_DEVICE":
            dev_id = e["dst"]
            if dev_id in seen_devs:
                continue
            seen_devs.add(dev_id)
            all_users = svcs.graph.accounts_on_device(dev_id)
            others = [u for u in all_users if u != account_id]
            dev_label = f"Device ending {dev_id[-5:]}" if len(dev_id) > 5 else f"Device ({dev_id})"
            shared_devices.append({
                "device_label": dev_label,
                "device_id": dev_id,
                "other_accounts": len(others),
                "other_account_ids": others,
                "other_account_names": [format_display_name(u, svcs.store.accounts.get(u)) for u in others],
            })

    # Held payments
    held_payments = []
    for hold in svcs.store.holds.values():
        if hold.status == "active" and (hold.payer == account_id or hold.beneficiary == account_id):
            mins_left = max(1, int(round((hold.release_at - now()) / 60.0)))
            held_payments.append({
                "to": hold.beneficiary,
                "amount": round(hold.amount, 2),
                "minutes_left": mins_left,
            })
    if not held_payments:
        for d in history:
            if d.get("request", {}).get("payer") == account_id and d.get("outcome") in ("HOLD_CREDIT", "COOLING_ROOM", "PAUSE"):
                held_payments.append({
                    "to": d["request"]["payee"],
                    "amount": round(float(d["request"]["amount"]), 2),
                    "minutes_left": d.get("hold_minutes") or 10,
                })
                break

    total_in = round(sum(s["amount"] for s in senders), 2)
    count_in = sum(s["count"] for s in senders)
    total_out = round(sum(p["amount"] for p in payees), 2)
    count_out = sum(p["count"] for p in payees)

    # summary_sentence
    sentence_parts = [
        f"Received ₹{total_in:,.0f} and sent ₹{total_out:,.0f} to {len(payees)} account{'s' if len(payees) != 1 else ''}."
    ]
    if shared_devices and shared_devices[0]["other_accounts"] > 0:
        c = shared_devices[0]["other_accounts"]
        sentence_parts.append(f"{c} account{'s' if c != 1 else ''} share its phone.")
    elif shared_dev_cnt > 0:
        sentence_parts.append(f"{shared_dev_cnt} accounts share its phone.")
    else:
        sentence_parts.append("No shared devices.")

    if held_payments:
        hc = len(held_payments)
        sentence_parts.append("One payment is on hold." if hc == 1 else f"{hc} payments are on hold.")

    summary_sentence = " ".join(sentence_parts)

    return {
        "account": {
            "id": account_id,
            "display_name": format_display_name(account_id, acc),
            "role": acc.persona or "user",
            "risk_score": my_risk_score,
            "risk_level": my_risk_level,
            "verdict_reasons": my_reasons,
        },
        "received": {
            "total_amount": total_in,
            "count": count_in,
            "senders": senders,
        },
        "sent": {
            "total_amount": total_out,
            "count": count_out,
            "payees": payees,
        },
        "shared_devices": shared_devices,
        "held_payments": held_payments,
        "summary_sentence": summary_sentence,
    }


@app.get("/ledger")
def ledger(limit: int = 30):
    return svcs.ledger.recent(limit)


@app.get("/ledger/verify")
def ledger_verify(mode: str = "live"):
    return svcs.ledger.verify(mode=mode)


@app.post("/ledger/tamper")
def ledger_tamper():
    return {"tamper": svcs.ledger.tamper(), "verify": svcs.ledger.verify(mode="sandbox")}


@app.post("/ledger/restore")
def ledger_restore():
    return svcs.ledger.restore()


# ---------- scenario simulator ----------
def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:5]}"


def scenario_txns(name: str) -> list[TxnRequest]:
    R = TxnRequest
    if name == "normal":
        ppl = [ensure_account(_id("user"), avg_amt_90d=1500).id for _ in range(4)]
        return [R(payer=random.choice(ppl), payee=random.choice(ppl[1:] + ["acc_2"]),
                  amount=round(random.uniform(150, 2500)), device_fp="dev_home") for _ in range(6)]
    if name == "digital_arrest":   # T1: coerced victim on a call, screen shared, draining savings
        victim = ensure_account(_id("elder"), name="Elderly victim", persona="elderly", balance=400000).id
        fraud = ensure_account(_id("cbi"), name="'CBI officer'", persona="mule", age_days=4).id
        return [R(payer=victim, payee=fraud, amount=180000, on_call=True, call_minutes=55, screen_share=True)]
    if name == "account_takeover":  # T3: SIM swapped, new device, new city
        v = ensure_account(_id("user"), balance=90000).id
        thief = ensure_account(_id("ato"), persona="mule", age_days=2).id
        return [R(payer=v, payee=thief, amount=49999, sim_changed_hrs_ago=6, pin_reset_hrs_ago=2,
                  device_fp=_id("newdev"), geo="PATNA")]
    if name == "mule_fanin":       # T8/T9: many unrelated victims → young mule → forwards out
        mule = ensure_account(_id("mule"), name="Mule collector", persona="mule", age_days=3).id
        sink = ensure_account(_id("sink"), persona="ring", age_days=5).id
        txns = [R(payer=ensure_account(_id("victim"), cluster=_id("c")).id, payee=mule, amount=round(random.uniform(8000, 25000)))
                for _ in range(10)]
        return txns + [R(payer=mule, payee=sink, amount=150000)]
    if name == "structuring":      # T11: many just-under-threshold payments
        tgt = ensure_account(_id("collector"), persona="ring", age_days=20).id
        return [R(payer=ensure_account(_id("smurf"), cluster=_id("c")).id, payee=tgt,
                  amount=random.choice([9900, 9950, 9990, 49900, 49990])) for _ in range(8)]
    if name == "probing":          # T7: tiny payments to new IDs, then a big one
        p = ensure_account(_id("user"), balance=120000).id
        txns = [R(payer=p, payee=ensure_account(_id("probe")).id, amount=1) for _ in range(5)]
        return txns + [R(payer=p, payee=ensure_account(_id("probe"), persona="mule", age_days=1).id, amount=60000)]
    if name == "device_farm":      # T12: one phone driving many accounts
        dev = _id("farm_dev")
        dst = ensure_account(_id("cashout"), persona="ring", age_days=7).id
        return [R(payer=ensure_account(_id("rented"), persona="mule", age_days=10).id, payee=dst,
                  amount=round(random.uniform(5000, 15000)), device_fp=dev) for _ in range(6)]
    raise HTTPException(404, f"unknown scenario {name}")


SCENARIOS = ["normal", "digital_arrest", "account_takeover", "mule_fanin", "structuring", "probing", "device_farm"]


@app.get("/scenarios")
def scenarios():
    return SCENARIOS


@app.post("/simulate/{name}")
async def simulate(name: str):
    out = [await process(r, scenario=name) for r in scenario_txns(name)]
    return {"scenario": name, "count": len(out), "decisions": out}


@app.post("/reset")
def reset():
    global svcs, orchestrator
    svcs = Services()
    orchestrator = Orchestrator(svcs)
    history.clear()
    ensure_account("acc_1", name="Payer", persona="gig")
    ensure_account("acc_2", name="Payee", persona="biz")
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    print(f"\n   AgentGuard running at http://localhost:{port}   (Ctrl+C to stop)\n")
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=False)

