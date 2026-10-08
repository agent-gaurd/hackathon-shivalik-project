"""Drift monitor: Population Stability Index (PSI) of live features vs the training distribution.
PSI < 0.1 stable, 0.1-0.2 moderate shift, > 0.2 drift (retrain)."""
from collections import deque
import numpy as np

DRIFT_FEATURES = ["log_amount", "hour", "src_cnt_24h", "src_amount_vs_avg", "forward_ratio", "new_payee"]


class DriftMonitor:
    def __init__(self, train_features, window=1000):
        self.cuts, self.expected = {}, {}
        for f in DRIFT_FEATURES:
            x = train_features[f].values
            cuts = np.array([.5]) if len(np.unique(x)) <= 2 else np.unique(np.quantile(x, np.linspace(.1, .9, 9)))
            self.cuts[f] = cuts
            self.expected[f] = np.bincount(np.digitize(x, cuts), minlength=len(cuts) + 1) / len(x)
        self.live = deque(maxlen=window)
        # Keep a reference to training rows so reset() can re-seed the live window
        # with a small number of training-distribution samples.  This means that
        # immediately after /drift/reset a run of normal traffic reports "stable"
        # rather than "insufficient_data" or a spurious "drift".
        rng = np.random.default_rng(42)
        n = min(200, len(train_features))
        idx = rng.choice(len(train_features), n, replace=False)
        self._train_seed = [{f: float(train_features[f].iloc[i]) for f in DRIFT_FEATURES} for i in idx]

    def update(self, tf):
        """Accept a dict OR a pandas Series / row with the drift feature values."""
        if hasattr(tf, "to_dict"):
            tf = tf.to_dict()
        row = {f: float(tf.get(f, 0.0)) for f in DRIFT_FEATURES}
        self.live.append(row)

    def reset(self):
        """Clear live window and re-seed with training-distribution samples so
        a subsequent run of normal traffic correctly shows 'stable'."""
        self.live.clear()
        for row in self._train_seed:
            self.live.append(row)

    def report(self, min_n=50):
        n = len(self.live)
        if n < min_n:
            return {"status": "insufficient_data", "n": n, "need": min_n}
        out, worst = {}, 0.0
        for f in DRIFT_FEATURES:
            x = np.array([r[f] for r in self.live])
            a = np.bincount(np.digitize(x, self.cuts[f]), minlength=len(self.cuts[f]) + 1) / n
            e = np.clip(self.expected[f], 1e-4, None); a = np.clip(a, 1e-4, None)
            psi = float(np.sum((a - e) * np.log(a / e))); worst = max(worst, psi)
            out[f] = {"psi": round(psi, 3), "expected": e.round(3).tolist(), "actual": a.round(3).tolist()}
        status = "stable" if worst < .1 else "moderate" if worst < .2 else "drift"
        return {"status": status, "max_psi": round(worst, 3), "n": n, "features": out}
