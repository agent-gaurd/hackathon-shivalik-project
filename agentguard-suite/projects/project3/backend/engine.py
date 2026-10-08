"""Project 3 Analytics Engine.
Ingests, normalizes, simulates, and aggregates model inference telemetry.
Provides head-to-head comparative analytics: Stepped-Up and Blocked vs Allowed.
"""
import time
import math
import random
import uuid
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import httpx

# Decision Normalization Constants
CATEGORY_ALLOWED = "ALLOWED"
CATEGORY_STEPPED_UP = "STEPPED_UP"
CATEGORY_BLOCKED = "BLOCKED"

ALLOWED_DECISIONS = {"ALLOW", "ALLOW_NUDGE", "SUCCESS", "COMPLETED", "ALLOWED"}
STEPPED_UP_DECISIONS = {"STEP_UP", "VERIFY", "AWAITING_OTP", "COOLING_ROOM", "HOLD_CREDIT", "PAUSE", "IN_REVIEW", "CHALLENGED"}
BLOCKED_DECISIONS = {"BLOCK", "BLOCKED", "REJECTED"}

TYPOLOGY_NAMES = {
    "T1": "Digital arrest / authority impersonation",
    "T2": "Investment / task scam",
    "T3": "Account takeover (SIM swap)",
    "T4": "Remote-access / screen-share",
    "T5": "QR code swap at merchant",
    "T6": "Fake refund / collect abuse",
    "T7": "Micro-payment probing",
    "T8": "Mule account: fan-in collector",
    "T9": "Mule chain / layering",
    "T10": "Round-tripping",
    "T11": "Structuring (smurfing)",
    "T12": "Rented accounts (mule farm)",
    "T0": "Normal peer-to-peer / merchant payment",
}


def normalize_category(raw_decision: str) -> str:
    raw = str(raw_decision or "").upper().strip()
    if raw in BLOCKED_DECISIONS:
        return CATEGORY_BLOCKED
    if raw in STEPPED_UP_DECISIONS:
        return CATEGORY_STEPPED_UP
    return CATEGORY_ALLOWED


class AnalyticsEngine:
    def __init__(self, max_history: int = 15000):
        self.max_history = max_history
        self.transactions: deque = deque(maxlen=max_history)
        self.txn_map: Dict[str, dict] = {}
        self.lock = False
        self._seed_initial_data()

    def _seed_initial_data(self):
        """Generate realistic historical baseline data across normal and fraud vectors."""
        random.seed(42)
        base_time = time.time() - 86400 * 2  # past 48 hours

        personas = [
            ("acc_salaried_101", "acc_merchant_201", 1200, "T0"),
            ("acc_student_102", "acc_salaried_103", 450, "T0"),
            ("acc_biz_104", "acc_vendor_202", 45000, "T0"),
            ("acc_elderly_105", "acc_mule_801", 185000, "T1"),   # Digital arrest
            ("acc_gig_106", "acc_mule_802", 95000, "T3"),        # ATO / SIM swap
            ("acc_user_107", "acc_mule_803", 48500, "T11"),      # Structuring
            ("acc_student_108", "acc_mule_804", 62000, "T4"),    # Screen share
            ("acc_probe_109", "acc_target_203", 5, "T7"),        # Micro probing
            ("acc_mule_fan1", "acc_collector_888", 85000, "T8"),  # Mule fan-in
        ]

        # Generate 450 initial transactions with realistic distribution
        # ~74% Allowed, ~17% Stepped Up, ~9% Blocked
        for i in range(450):
            ts = base_time + (i * 380) + random.uniform(-60, 60)
            
            # 70% normal, 30% fraud vectors
            is_fraud = random.random() < 0.28
            
            if not is_fraud:
                payer = f"acc_user_{random.randint(100, 350)}"
                payee = f"acc_payee_{random.randint(400, 700)}"
                amount = round(random.lognormvariate(7.2, 0.9), 2)
                amount = min(max(amount, 50.0), 45000.0)
                typology = "T0"
                typology_name = "Normal Payment"
                
                # Normal agent scores: mostly 2-25
                txn_score = round(random.uniform(3, 22), 1)
                beh_score = round(random.uniform(2, 24), 1)
                vel_score = round(random.uniform(1, 20), 1)
                mule_score = round(random.uniform(0, 15), 1)
                aml_score = round(random.uniform(0, 12), 1)
                counsel_score = round(random.uniform(85, 98), 1)
                
                overall = round(txn_score * 0.22 + beh_score * 0.22 + vel_score * 0.16 + mule_score * 0.22 + aml_score * 0.18, 1)
                
                # Occasionally a normal payment triggers a step-up (e.g. slight velocity spike or new payee)
                if random.random() < 0.08:
                    raw_decision = "STEP_UP"
                    category = CATEGORY_STEPPED_UP
                    overall = max(overall, round(random.uniform(35, 48), 1))
                else:
                    raw_decision = "ALLOW"
                    category = CATEGORY_ALLOWED

                signals = {
                    "on_call": False,
                    "screen_share": False,
                    "sim_swap": False,
                    "pin_reset": False,
                    "new_device": random.random() < 0.05,
                    "off_hours": random.random() < 0.04,
                    "high_velocity": False,
                    "amount_z_high": False,
                    "mule_cluster_hop": False
                }
                reason = "Normal historical baseline and payee profile"
                source_engine = "Project 1 (6-Agent Core)" if i % 2 == 0 else "Project 2 (Policy Orchestrator)"

            else:
                # Fraud typologies
                t_choice = random.choice(["T1", "T3", "T4", "T7", "T8", "T11"])
                typology = t_choice
                typology_name = TYPOLOGY_NAMES.get(t_choice, "Suspicious Activity")
                
                payer = f"acc_victim_{random.randint(10, 60)}"
                payee = f"acc_mule_{random.randint(1, 15)}"
                
                signals = {
                    "on_call": False,
                    "screen_share": False,
                    "sim_swap": False,
                    "pin_reset": False,
                    "new_device": False,
                    "off_hours": random.random() < 0.25,
                    "high_velocity": False,
                    "amount_z_high": True,
                    "mule_cluster_hop": False
                }

                if t_choice == "T1":  # Digital arrest
                    amount = round(random.uniform(65000, 350000), 2)
                    signals["on_call"] = True
                    signals["off_hours"] = random.random() < 0.4
                    txn_score = round(random.uniform(78, 96), 1)
                    beh_score = round(random.uniform(85, 99), 1)
                    vel_score = round(random.uniform(40, 75), 1)
                    mule_score = round(random.uniform(65, 92), 1)
                    aml_score = round(random.uniform(55, 80), 1)
                    counsel_score = round(random.uniform(5, 25), 1)
                    reason = "Prolonged active call with high amount drain to unlinked beneficiary"

                elif t_choice == "T3":  # ATO / SIM swap
                    amount = round(random.uniform(25000, 120000), 2)
                    signals["sim_swap"] = True
                    signals["new_device"] = True
                    signals["pin_reset"] = random.random() < 0.6
                    txn_score = round(random.uniform(70, 92), 1)
                    beh_score = round(random.uniform(82, 98), 1)
                    vel_score = round(random.uniform(60, 85), 1)
                    mule_score = round(random.uniform(40, 70), 1)
                    aml_score = round(random.uniform(30, 60), 1)
                    counsel_score = round(random.uniform(10, 30), 1)
                    reason = "SIM swap detected within 24h alongside unfamiliar device fingerprint"

                elif t_choice == "T4":  # Screen share
                    amount = round(random.uniform(15000, 85000), 2)
                    signals["screen_share"] = True
                    signals["on_call"] = random.random() < 0.7
                    txn_score = round(random.uniform(68, 89), 1)
                    beh_score = round(random.uniform(75, 94), 1)
                    vel_score = round(random.uniform(45, 75), 1)
                    mule_score = round(random.uniform(50, 78), 1)
                    aml_score = round(random.uniform(20, 50), 1)
                    counsel_score = round(random.uniform(10, 35), 1)
                    reason = "Remote screen-sharing session active during credential input"

                elif t_choice == "T7":  # Micro probing
                    amount = round(random.uniform(1, 10), 2)
                    signals["high_velocity"] = True
                    signals["new_device"] = True
                    txn_score = round(random.uniform(45, 70), 1)
                    beh_score = round(random.uniform(50, 75), 1)
                    vel_score = round(random.uniform(85, 99), 1)
                    mule_score = round(random.uniform(30, 55), 1)
                    aml_score = round(random.uniform(20, 45), 1)
                    counsel_score = round(random.uniform(20, 40), 1)
                    reason = "Sub-rupee automated card/VPA probing frequency threshold exceeded"

                elif t_choice == "T8":  # Mule fan-in
                    amount = round(random.uniform(40000, 180000), 2)
                    signals["mule_cluster_hop"] = True
                    signals["high_velocity"] = True
                    txn_score = round(random.uniform(75, 94), 1)
                    beh_score = round(random.uniform(65, 88), 1)
                    vel_score = round(random.uniform(80, 96), 1)
                    mule_score = round(random.uniform(88, 100), 1)
                    aml_score = round(random.uniform(70, 92), 1)
                    counsel_score = round(random.uniform(2, 18), 1)
                    reason = "Graph anomaly: Beneficiary receiving dense fan-in transfers from multiple unlinked accounts"

                else:  # T11 Structuring
                    amount = round(random.uniform(48000, 49990), 2)
                    signals["high_velocity"] = random.random() < 0.6
                    txn_score = round(random.uniform(62, 85), 1)
                    beh_score = round(random.uniform(55, 78), 1)
                    vel_score = round(random.uniform(65, 88), 1)
                    mule_score = round(random.uniform(60, 82), 1)
                    aml_score = round(random.uniform(88, 99), 1)
                    counsel_score = round(random.uniform(10, 25), 1)
                    reason = "Smurfing pattern: Repetitive transactions just below mandatory reporting threshold"

                overall = round(txn_score * 0.22 + beh_score * 0.22 + vel_score * 0.16 + mule_score * 0.22 + aml_score * 0.18, 1)

                # Determine decision: Block or Step-Up
                if overall >= 78 or signals.get("on_call") or signals.get("mule_cluster_hop"):
                    raw_decision = "BLOCK"
                    category = CATEGORY_BLOCKED
                else:
                    raw_decision = "STEP_UP"
                    category = CATEGORY_STEPPED_UP

                source_engine = "Project 1 (6-Agent Core)" if i % 2 == 0 else "Project 2 (Policy Orchestrator)"

            record = {
                "txn_id": f"TXN-{10000 + i}",
                "timestamp": ts,
                "iso_time": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
                "payer": payer,
                "payee": payee,
                "amount": amount,
                "channel": "UPI" if random.random() < 0.85 else "NET_BANKING",
                "typology": typology,
                "typology_name": typology_name,
                "raw_decision": raw_decision,
                "category": category,
                "overall_score": overall,
                "agent_scores": {
                    "transaction": txn_score,
                    "behavior": beh_score,
                    "velocity": vel_score,
                    "mule": mule_score,
                    "aml": aml_score,
                    "counsel": counsel_score
                },
                "signals": signals,
                "source_engine": source_engine,
                "reason": reason,
                "latency_ms": round(random.uniform(45, 160), 1),
                "is_synthetic": True
            }
            self.transactions.append(record)
            self.txn_map[record["txn_id"]] = record

    def add_transaction(self, record: dict) -> dict:
        """Add a single transaction, ensuring normalized structure."""
        txn_id = record.get("txn_id") or f"TXN-{uuid.uuid4().hex[:8].upper()}"
        ts = record.get("timestamp") or time.time()
        
        raw_dec = record.get("raw_decision") or record.get("decision") or record.get("outcome") or "ALLOW"
        category = normalize_category(raw_dec)

        scores = record.get("agent_scores", {})
        if not scores and "agents" in record and isinstance(record["agents"], list):
            for a in record["agents"]:
                if isinstance(a, dict) and "agent" in a and "score" in a:
                    scores[a["agent"]] = float(a["score"])

        # Fallback scores if missing
        scores.setdefault("transaction", float(record.get("score", 15.0)))
        scores.setdefault("behavior", float(record.get("score", 15.0)))
        scores.setdefault("velocity", 12.0)
        scores.setdefault("mule", 10.0)
        scores.setdefault("aml", 8.0)
        scores.setdefault("counsel", 90.0 if category == CATEGORY_ALLOWED else 20.0)

        typology = record.get("typology") or "T0"
        typology_name = record.get("typology_name") or TYPOLOGY_NAMES.get(typology, "Standard Transfer")

        clean_rec = {
            "txn_id": txn_id,
            "timestamp": ts,
            "iso_time": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
            "payer": record.get("payer") or record.get("src") or "acc_unknown",
            "payee": record.get("payee") or record.get("dst") or "acc_unknown",
            "amount": float(record.get("amount", 1000.0)),
            "channel": record.get("channel", "UPI"),
            "typology": typology,
            "typology_name": typology_name,
            "raw_decision": raw_dec,
            "category": category,
            "overall_score": float(record.get("overall_score") or record.get("score", 18.0)),
            "agent_scores": scores,
            "signals": record.get("signals", {
                "on_call": False, "screen_share": False, "sim_swap": False,
                "pin_reset": False, "new_device": False, "off_hours": False,
                "high_velocity": False, "amount_z_high": False, "mule_cluster_hop": False
            }),
            "source_engine": record.get("source_engine", "External Stream"),
            "reason": record.get("reason") or record.get("top_reason") or record.get("routing_reason") or "Automated inference result",
            "latency_ms": float(record.get("latency_ms", 85.0)),
            "is_synthetic": record.get("is_synthetic", False)
        }

        self.transactions.append(clean_rec)
        self.txn_map[clean_rec["txn_id"]] = clean_rec
        return clean_rec

    async def sync_from_project1(self, p1_url: str = "http://127.0.0.1:8001") -> int:
        """Fetch transactions from Project 1 (6-agent Core Engine) and normalize."""
        count = 0
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(f"{p1_url}/transactions?limit=250")
                if res.status_code == 200:
                    txns = res.json()
                    for t in txns:
                        tid = t.get("txn_id")
                        if tid and tid not in self.txn_map:
                            dt = t.get("ts")
                            ts_val = time.time()
                            if isinstance(dt, str):
                                try:
                                    ts_val = datetime.fromisoformat(dt.replace("Z", "+00:00")).timestamp()
                                except Exception:
                                    pass
                            
                            self.add_transaction({
                                "txn_id": tid,
                                "timestamp": ts_val,
                                "payer": t.get("src", "unknown"),
                                "payee": t.get("dst", "unknown"),
                                "amount": t.get("amount", 0.0),
                                "channel": t.get("channel", "UPI"),
                                "raw_decision": t.get("decision", "SUCCESS"),
                                "overall_score": t.get("score", 0.0),
                                "agent_scores": t.get("agent_scores", {}),
                                "reason": t.get("top_reason", "Project 1 Evaluated"),
                                "source_engine": "Project 1 (6-Agent Core)",
                                "latency_ms": t.get("latency_ms", 95.0),
                                "is_synthetic": False
                            })
                            count += 1
        except Exception:
            pass
        return count

    async def sync_from_project2(self, p2_url: str = "http://127.0.0.1:8002") -> int:
        """Fetch transactions from Project 2 (Money Map & Policy Engine) and normalize."""
        count = 0
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(f"{p2_url}/transactions?limit=150")
                if res.status_code == 200:
                    txns = res.json()
                    for t in txns:
                        tid = t.get("txn_id")
                        if tid and tid not in self.txn_map:
                            req = t.get("request", {})
                            payer = req.get("payer", "acc_payer")
                            payee = req.get("payee", "acc_payee")
                            amount = req.get("amount", 0.0)
                            dom = t.get("dominant", "T0")
                            
                            agent_dict = {}
                            for a in t.get("agents", []):
                                if isinstance(a, dict):
                                    agent_dict[a.get("agent")] = a.get("score", 0.0)

                            self.add_transaction({
                                "txn_id": tid,
                                "timestamp": t.get("ts", time.time()),
                                "payer": payer,
                                "payee": payee,
                                "amount": amount,
                                "channel": req.get("channel", "UPI"),
                                "typology": dom,
                                "typology_name": TYPOLOGY_NAMES.get(dom, "Policy Case"),
                                "raw_decision": t.get("outcome", "ALLOW"),
                                "overall_score": t.get("score", 0.0),
                                "agent_scores": agent_dict,
                                "signals": {
                                    "on_call": req.get("on_call", False),
                                    "screen_share": req.get("screen_share", False),
                                    "sim_swap": (req.get("sim_changed_hrs_ago") or 999) < 72,
                                    "pin_reset": (req.get("pin_reset_hrs_ago") or 999) < 24,
                                    "new_device": bool(req.get("device_fp")),
                                    "off_hours": False,
                                    "high_velocity": False,
                                    "amount_z_high": amount > 50000,
                                    "mule_cluster_hop": False
                                },
                                "reason": t.get("routing_reason", "Project 2 Policy Decision"),
                                "source_engine": "Project 2 (Policy Orchestrator)",
                                "latency_ms": t.get("total_latency_ms", 45.0),
                                "is_synthetic": False
                            })
                            count += 1
        except Exception:
            pass
        return count

    def simulate_batch(self, scenario: str = "normal", count: int = 10) -> List[dict]:
        """Simulate a targeted batch of payments through the models."""
        created = []
        now_ts = time.time()
        for i in range(count):
            t_id = f"SIM-{uuid.uuid4().hex[:8].upper()}"
            ts = now_ts - (count - i) * 12
            
            if scenario == "normal":
                amount = round(random.uniform(150, 12500), 2)
                typology = "T0"
                txn_s = round(random.uniform(4, 22), 1)
                beh_s = round(random.uniform(3, 25), 1)
                vel_s = round(random.uniform(2, 20), 1)
                mule_s = round(random.uniform(0, 14), 1)
                aml_s = round(random.uniform(0, 10), 1)
                counsel_s = round(random.uniform(88, 98), 1)
                overall = round(txn_s * 0.22 + beh_s * 0.22 + vel_s * 0.16 + mule_s * 0.22 + aml_s * 0.18, 1)
                decision = "ALLOW"
                signals = {
                    "on_call": False, "screen_share": False, "sim_swap": False,
                    "pin_reset": False, "new_device": False, "off_hours": False,
                    "high_velocity": False, "amount_z_high": False, "mule_cluster_hop": False
                }
                reason = "Benign baseline transaction; high counsel legitimacy score"

            elif scenario == "digital_arrest":
                amount = round(random.uniform(90000, 420000), 2)
                typology = "T1"
                txn_s = round(random.uniform(82, 98), 1)
                beh_s = round(random.uniform(88, 99), 1)
                vel_s = round(random.uniform(50, 80), 1)
                mule_s = round(random.uniform(70, 95), 1)
                aml_s = round(random.uniform(60, 85), 1)
                counsel_s = round(random.uniform(2, 15), 1)
                overall = round(txn_s * 0.22 + beh_s * 0.22 + vel_s * 0.16 + mule_s * 0.22 + aml_s * 0.18, 1)
                decision = "BLOCK" if overall >= 78 else "STEP_UP"
                signals = {
                    "on_call": True, "screen_share": False, "sim_swap": False,
                    "pin_reset": False, "new_device": False, "off_hours": True,
                    "high_velocity": False, "amount_z_high": True, "mule_cluster_hop": False
                }
                reason = "Authority impersonation signature: Active phone call during anomalous lump-sum payment"

            elif scenario == "mule_fanin":
                amount = round(random.uniform(45000, 160000), 2)
                typology = "T8"
                txn_s = round(random.uniform(75, 92), 1)
                beh_s = round(random.uniform(65, 86), 1)
                vel_s = round(random.uniform(85, 98), 1)
                mule_s = round(random.uniform(92, 100), 1)
                aml_s = round(random.uniform(75, 94), 1)
                counsel_s = round(random.uniform(5, 18), 1)
                overall = round(txn_s * 0.22 + beh_s * 0.22 + vel_s * 0.16 + mule_s * 0.22 + aml_s * 0.18, 1)
                decision = "BLOCK"
                signals = {
                    "on_call": False, "screen_share": False, "sim_swap": False,
                    "pin_reset": False, "new_device": False, "off_hours": False,
                    "high_velocity": True, "amount_z_high": True, "mule_cluster_hop": True
                }
                reason = "Mule aggregation hub detected: Rapid fan-in velocity from disparate remitters"

            elif scenario == "ato":
                amount = round(random.uniform(30000, 95000), 2)
                typology = "T3"
                txn_s = round(random.uniform(72, 94), 1)
                beh_s = round(random.uniform(84, 98), 1)
                vel_s = round(random.uniform(65, 88), 1)
                mule_s = round(random.uniform(45, 75), 1)
                aml_s = round(random.uniform(40, 65), 1)
                counsel_s = round(random.uniform(8, 25), 1)
                overall = round(txn_s * 0.22 + beh_s * 0.22 + vel_s * 0.16 + mule_s * 0.22 + aml_s * 0.18, 1)
                decision = "STEP_UP" if random.random() < 0.65 else "BLOCK"
                signals = {
                    "on_call": False, "screen_share": False, "sim_swap": True,
                    "pin_reset": True, "new_device": True, "off_hours": False,
                    "high_velocity": False, "amount_z_high": True, "mule_cluster_hop": False
                }
                reason = "Account Takeover Indicators: SIM swap & PIN reset under unrecognized hardware fingerprint"

            elif scenario == "structuring":
                amount = round(random.uniform(48500, 49950), 2)
                typology = "T11"
                txn_s = round(random.uniform(65, 86), 1)
                beh_s = round(random.uniform(55, 80), 1)
                vel_s = round(random.uniform(70, 92), 1)
                mule_s = round(random.uniform(65, 88), 1)
                aml_s = round(random.uniform(92, 100), 1)
                counsel_s = round(random.uniform(10, 25), 1)
                overall = round(txn_s * 0.22 + beh_s * 0.22 + vel_s * 0.16 + mule_s * 0.22 + aml_s * 0.18, 1)
                decision = "STEP_UP" if overall < 80 else "BLOCK"
                signals = {
                    "on_call": False, "screen_share": False, "sim_swap": False,
                    "pin_reset": False, "new_device": False, "off_hours": False,
                    "high_velocity": True, "amount_z_high": True, "mule_cluster_hop": False
                }
                reason = "AML Threshold Evasion: Repetitive sub-50k structuring burst"

            elif scenario == "screen_share":
                amount = round(random.uniform(18000, 75000), 2)
                typology = "T4"
                txn_s = round(random.uniform(70, 90), 1)
                beh_s = round(random.uniform(78, 96), 1)
                vel_s = round(random.uniform(45, 75), 1)
                mule_s = round(random.uniform(55, 80), 1)
                aml_s = round(random.uniform(30, 55), 1)
                counsel_s = round(random.uniform(10, 30), 1)
                overall = round(txn_s * 0.22 + beh_s * 0.22 + vel_s * 0.16 + mule_s * 0.22 + aml_s * 0.18, 1)
                decision = "BLOCK" if overall >= 75 else "STEP_UP"
                signals = {
                    "on_call": True, "screen_share": True, "sim_swap": False,
                    "pin_reset": False, "new_device": False, "off_hours": False,
                    "high_velocity": False, "amount_z_high": True, "mule_cluster_hop": False
                }
                reason = "Remote screen control detected concurrently with interactive transaction session"

            else:
                # Default normal
                amount = round(random.uniform(500, 8000), 2)
                typology = "T0"
                txn_s = beh_s = vel_s = mule_s = aml_s = 15.0
                counsel_s = 92.0
                overall = 15.0
                decision = "ALLOW"
                signals = {
                    "on_call": False, "screen_share": False, "sim_swap": False,
                    "pin_reset": False, "new_device": False, "off_hours": False,
                    "high_velocity": False, "amount_z_high": False, "mule_cluster_hop": False
                }
                reason = "Synthetic baseline transaction"

            rec = self.add_transaction({
                "txn_id": t_id,
                "timestamp": ts,
                "payer": f"acc_sim_payer_{random.randint(10, 99)}",
                "payee": f"acc_sim_payee_{random.randint(10, 99)}",
                "amount": amount,
                "channel": "UPI",
                "typology": typology,
                "typology_name": TYPOLOGY_NAMES.get(typology, "Simulated Scenario"),
                "raw_decision": decision,
                "overall_score": overall,
                "agent_scores": {
                    "transaction": txn_s,
                    "behavior": beh_s,
                    "velocity": vel_s,
                    "mule": mule_s,
                    "aml": aml_s,
                    "counsel": counsel_s
                },
                "signals": signals,
                "source_engine": "Real-Time Scenario Simulator",
                "reason": reason,
                "latency_ms": round(random.uniform(50, 140), 1),
                "is_synthetic": True
            })
            created.append(rec)
        return created

    # --------------------------------------------------------------- Aggregations
    def get_stats(self, engine_filter: Optional[str] = None) -> dict:
        """Calculate macro comparative KPIs: Stepped-Up & Blocked vs Allowed."""
        txns = self._filter_by_engine(engine_filter)
        total = len(txns)
        if total == 0:
            return {"total": 0, "allowed": {}, "stepped_up": {}, "blocked": {}, "efficiency": {}}

        allowed_txns = [t for t in txns if t["category"] == CATEGORY_ALLOWED]
        stepped_txns = [t for t in txns if t["category"] == CATEGORY_STEPPED_UP]
        blocked_txns = [t for t in txns if t["category"] == CATEGORY_BLOCKED]

        total_amount = sum(t["amount"] for t in txns)
        allowed_amount = sum(t["amount"] for t in allowed_txns)
        stepped_amount = sum(t["amount"] for t in stepped_txns)
        blocked_amount = sum(t["amount"] for t in blocked_txns)

        def avg_score(subset):
            return round(sum(t["overall_score"] for t in subset) / max(len(subset), 1), 1)

        def avg_amount(subset):
            return round(sum(t["amount"] for t in subset) / max(len(subset), 1), 2)

        latencies = [t["latency_ms"] for t in txns]
        latencies.sort()
        mean_latency = round(sum(latencies) / len(latencies), 1)
        p95_latency = latencies[int(len(latencies) * 0.95)] if latencies else 0

        # Protection and efficiency metrics
        # Friction rate: % of transactions requiring step-up or review
        friction_pct = round((len(stepped_txns) / total) * 100, 1)
        # Block rate: % intercepted
        block_pct = round((len(blocked_txns) / total) * 100, 1)
        # Allow rate: % passed seamlessly
        allow_pct = round((len(allowed_txns) / total) * 100, 1)

        # Money protected ratio: blocked INR / (blocked + stepped INR)
        risk_money_total = blocked_amount + stepped_amount
        protected_money_ratio = round((blocked_amount / max(risk_money_total, 1)) * 100, 1) if risk_money_total > 0 else 0.0

        return {
            "total_count": total,
            "total_volume_inr": round(total_amount, 2),
            "latency": {
                "mean_ms": mean_latency,
                "p95_ms": p95_latency
            },
            "allowed": {
                "count": len(allowed_txns),
                "pct": allow_pct,
                "volume_inr": round(allowed_amount, 2),
                "volume_pct": round((allowed_amount / max(total_amount, 1)) * 100, 1),
                "avg_ticket_inr": avg_amount(allowed_txns),
                "avg_score": avg_score(allowed_txns),
                "label": "Allowed (Frictionless)"
            },
            "stepped_up": {
                "count": len(stepped_txns),
                "pct": friction_pct,
                "volume_inr": round(stepped_amount, 2),
                "volume_pct": round((stepped_amount / max(total_amount, 1)) * 100, 1),
                "avg_ticket_inr": avg_amount(stepped_txns),
                "avg_score": avg_score(stepped_txns),
                "label": "Stepped-Up (Challenged / In Review)"
            },
            "blocked": {
                "count": len(blocked_txns),
                "pct": block_pct,
                "volume_inr": round(blocked_amount, 2),
                "volume_pct": round((blocked_amount / max(total_amount, 1)) * 100, 1),
                "avg_ticket_inr": avg_amount(blocked_txns),
                "avg_score": avg_score(blocked_txns),
                "label": "Blocked (Interceptions)"
            },
            "comparison": {
                "friction_ratio_pct": friction_pct,
                "protection_ratio_pct": block_pct,
                "risk_intervention_total": len(stepped_txns) + len(blocked_txns),
                "risk_intervention_pct": round(((len(stepped_txns) + len(blocked_txns)) / total) * 100, 1),
                "money_intercepted_inr": round(blocked_amount, 2),
                "money_friction_inr": round(stepped_amount, 2),
                "protected_money_ratio_pct": protected_money_ratio,
                "score_delta_blocked_vs_allowed": round(avg_score(blocked_txns) - avg_score(allowed_txns), 1),
                "score_delta_stepped_vs_allowed": round(avg_score(stepped_txns) - avg_score(allowed_txns), 1)
            }
        }

    def get_models_analytics(self, engine_filter: Optional[str] = None) -> dict:
        """Detailed breakdown of how each AI model scored across Allowed, Stepped-Up, and Blocked."""
        txns = self._filter_by_engine(engine_filter)
        if not txns:
            return {}

        allowed_txns = [t for t in txns if t["category"] == CATEGORY_ALLOWED]
        stepped_txns = [t for t in txns if t["category"] == CATEGORY_STEPPED_UP]
        blocked_txns = [t for t in txns if t["category"] == CATEGORY_BLOCKED]

        agent_keys = ["transaction", "behavior", "velocity", "mule", "aml", "counsel"]
        agent_display_names = {
            "transaction": "Transaction Agent (XGBoost)",
            "behavior": "Behavior Agent (Isolation Forest)",
            "velocity": "Velocity Agent (Bursts & Spikes)",
            "mule": "Mule Agent (Graph PageRank)",
            "aml": "AML Agent (Structuring / Layering)",
            "counsel": "Counsel Agent (Policy & Legitimacy)"
        }

        result = {}
        for a in agent_keys:
            def avg_a(subset):
                vals = [t["agent_scores"].get(a, 0.0) for t in subset]
                return round(sum(vals) / max(len(vals), 1), 1)

            def high_trigger_pct(subset):
                vals = [t["agent_scores"].get(a, 0.0) for t in subset]
                high = sum(1 for v in vals if v >= 60.0)
                return round((high / max(len(vals), 1)) * 100, 1)

            all_vals = [t["agent_scores"].get(a, 0.0) for t in txns]
            all_avg = round(sum(all_vals) / max(len(all_vals), 1), 1)

            result[a] = {
                "name": agent_display_names[a],
                "overall_avg": all_avg,
                "allowed_avg": avg_a(allowed_txns),
                "stepped_up_avg": avg_a(stepped_txns),
                "blocked_avg": avg_a(blocked_txns),
                "allowed_high_trigger_pct": high_trigger_pct(allowed_txns),
                "stepped_up_high_trigger_pct": high_trigger_pct(stepped_txns),
                "blocked_high_trigger_pct": high_trigger_pct(blocked_txns),
                # Divergence power: difference between Blocked and Allowed score
                "discrimination_power": round(avg_a(blocked_txns) - avg_a(allowed_txns), 1)
            }

        return result

    def get_score_distribution(self, engine_filter: Optional[str] = None) -> dict:
        """Histograms of risk score (0-100 in 10-point bins) comparing the 3 categories."""
        txns = self._filter_by_engine(engine_filter)
        bins = [f"{i*10}-{(i+1)*10}" for i in range(10)]
        
        counts = {
            "bins": bins,
            CATEGORY_ALLOWED: [0] * 10,
            CATEGORY_STEPPED_UP: [0] * 10,
            CATEGORY_BLOCKED: [0] * 10
        }

        for t in txns:
            cat = t["category"]
            s = min(max(t["overall_score"], 0.0), 99.9)
            idx = int(s // 10)
            if 0 <= idx < 10:
                counts[cat][idx] += 1

        return counts

    def get_typology_breakdown(self, engine_filter: Optional[str] = None) -> List[dict]:
        """Matrix of how fraud typologies are distributed across Allowed, Stepped-Up, and Blocked."""
        txns = self._filter_by_engine(engine_filter)
        typology_groups = defaultdict(list)
        for t in txns:
            typology_groups[t["typology"]].append(t)

        rows = []
        for code, group in sorted(typology_groups.items(), key=lambda x: len(x[1]), reverse=True):
            tot = len(group)
            allwd = sum(1 for t in group if t["category"] == CATEGORY_ALLOWED)
            stepd = sum(1 for t in group if t["category"] == CATEGORY_STEPPED_UP)
            blckd = sum(1 for t in group if t["category"] == CATEGORY_BLOCKED)
            val = sum(t["amount"] for t in group)

            rows.append({
                "typology_code": code,
                "typology_name": TYPOLOGY_NAMES.get(code, group[0]["typology_name"]),
                "total_count": tot,
                "total_amount_inr": round(val, 2),
                "allowed_count": allwd,
                "allowed_pct": round((allwd / tot) * 100, 1),
                "stepped_up_count": stepd,
                "stepped_up_pct": round((stepd / tot) * 100, 1),
                "blocked_count": blckd,
                "blocked_pct": round((blckd / tot) * 100, 1),
                "avg_score": round(sum(t["overall_score"] for t in group) / tot, 1)
            })
        return rows

    def get_signals_analytics(self, engine_filter: Optional[str] = None) -> List[dict]:
        """Prevalence of behavioral risk signals in Allowed vs Stepped-Up vs Blocked."""
        txns = self._filter_by_engine(engine_filter)
        allowed_txns = [t for t in txns if t["category"] == CATEGORY_ALLOWED]
        stepped_txns = [t for t in txns if t["category"] == CATEGORY_STEPPED_UP]
        blocked_txns = [t for t in txns if t["category"] == CATEGORY_BLOCKED]

        signal_keys = [
            ("on_call", "Active Voice Call"),
            ("screen_share", "Remote Screen-Share Session"),
            ("sim_swap", "SIM Card Swapped (<72h)"),
            ("pin_reset", "Security PIN Reset (<24h)"),
            ("new_device", "Unrecognized Hardware Device"),
            ("off_hours", "Late Night / Unusual Hours"),
            ("high_velocity", "Rapid Velocity Burst"),
            ("amount_z_high", "Extreme Amount Deviation (Z-score)"),
            ("mule_cluster_hop", "Mule Graph Proximity / Fan-in")
        ]

        output = []
        for key, name in signal_keys:
            def pct(subset):
                cnt = sum(1 for t in subset if t.get("signals", {}).get(key, False))
                return round((cnt / max(len(subset), 1)) * 100, 1)

            cnt_total = sum(1 for t in txns if t.get("signals", {}).get(key, False))

            output.append({
                "key": key,
                "name": name,
                "total_hits": cnt_total,
                "allowed_pct": pct(allowed_txns),
                "stepped_up_pct": pct(stepped_txns),
                "blocked_pct": pct(blocked_txns),
            })
        return output

    def get_timeseries(self, engine_filter: Optional[str] = None, points: int = 24) -> dict:
        """Throughput time series comparing Allowed vs Stepped-Up vs Blocked trends."""
        txns = self._filter_by_engine(engine_filter)
        if not txns:
            return {"labels": [], CATEGORY_ALLOWED: [], CATEGORY_STEPPED_UP: [], CATEGORY_BLOCKED: []}

        # Divide into chronological intervals
        sorted_txns = sorted(txns, key=lambda x: x["timestamp"])
        min_ts = sorted_txns[0]["timestamp"]
        max_ts = sorted_txns[-1]["timestamp"]
        if max_ts == min_ts:
            max_ts += 1.0

        step = (max_ts - min_ts) / points
        labels = []
        allowed_series = [0] * points
        stepped_series = [0] * points
        blocked_series = [0] * points

        for i in range(points):
            bucket_time = min_ts + (i + 0.5) * step
            labels.append(datetime.fromtimestamp(bucket_time, timezone.utc).strftime("%H:%M"))

        for t in sorted_txns:
            bucket_idx = int((t["timestamp"] - min_ts) / step)
            bucket_idx = min(max(bucket_idx, 0), points - 1)
            cat = t["category"]
            if cat == CATEGORY_ALLOWED:
                allowed_series[bucket_idx] += 1
            elif cat == CATEGORY_STEPPED_UP:
                stepped_series[bucket_idx] += 1
            elif cat == CATEGORY_BLOCKED:
                blocked_series[bucket_idx] += 1

        return {
            "labels": labels,
            CATEGORY_ALLOWED: allowed_series,
            CATEGORY_STEPPED_UP: stepped_series,
            CATEGORY_BLOCKED: blocked_series
        }

    def get_transactions(
        self,
        category: Optional[str] = None,
        engine_filter: Optional[str] = None,
        typology: Optional[str] = None,
        search: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        limit: int = 100,
        offset: int = 0
    ) -> dict:
        """Queryable transaction list with rich filtering."""
        res = list(self.transactions)
        
        if engine_filter:
            res = [t for t in res if t.get("source_engine") == engine_filter or engine_filter == "ALL"]
        if category and category.upper() != "ALL":
            res = [t for t in res if t["category"] == category.upper()]
        if typology and typology.upper() != "ALL":
            res = [t for t in res if t["typology"] == typology.upper()]
        if min_score is not None:
            res = [t for t in res if t["overall_score"] >= min_score]
        if max_score is not None:
            res = [t for t in res if t["overall_score"] <= max_score]
        if search:
            q = search.lower()
            res = [t for t in res if q in t["txn_id"].lower() or q in t["payer"].lower() or q in t["payee"].lower() or q in t.get("reason", "").lower()]

        res.sort(key=lambda x: x["timestamp"], reverse=True)
        total_matched = len(res)
        paginated = res[offset: offset + limit]

        return {
            "total": total_matched,
            "limit": limit,
            "offset": offset,
            "items": paginated
        }

    def get_transaction_detail(self, txn_id: str) -> Optional[dict]:
        return self.txn_map.get(txn_id)

    def reset_dataset(self):
        self.transactions.clear()
        self.txn_map.clear()
        self._seed_initial_data()

    def _filter_by_engine(self, engine_filter: Optional[str]) -> List[dict]:
        if not engine_filter or engine_filter == "ALL":
            return list(self.transactions)
        return [t for t in self.transactions if t.get("source_engine") == engine_filter]


# Global engine instance
engine = AnalyticsEngine()
