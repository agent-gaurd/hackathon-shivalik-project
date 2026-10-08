# AgentGuard — Project 3: Model Analytics & Decision Intelligence

Comprehensive comparative analytics dashboard evaluating all payment and fraud data seen across AI models.
Compares **Stepped-Up** (Friction / Verification) and **Blocked** (Hard Defense Interception) decisions directly against **Allowed** baselines.

## Features
- **Cross-Engine Model Telemetry**: Normalizes and ingests inference records across Project 1 (6-agent engine: XGBoost, Isolation Forest, Velocity, Graph Mule, AML, Explainer) and Project 2 (Money Map & Policy Console).
- **Direct Head-to-Head Comparative Matrix**: Side-by-side metrics contrasting Allowed vs Stepped-Up vs Blocked across volume, financial volume in ₹, average ticket sizes, score distributions, and customer friction.
- **Per-Model / Per-Agent Analytics**: Grouped breakdown of individual model scores (XGBoost, Isolation Forest, Velocity bursts, Graph mule centrality, AML structuring, Counsel policy).
- **Model Score Density & Threshold Boundaries**: 10-point histogram curves comparing score distributions with policy threshold boundaries.
- **Typology & Threat Vector Matrix**: Stacked outcome breakdowns for Digital Arrest, Account Takeover (SIM swap), Remote Screen-sharing, Mule Fan-in, Structuring, and Micro Probing.
- **Behavioral Flag Correlations**: Heatmap of contextual flags (active call, screen share, SIM swap <72h, PIN reset <24h, new device).
- **Deep Model Telemetry Modal**: Detailed inspection drawer displaying exact per-agent scores, features, signals, and routing rationale.
- **Live Sync & Real-Time Wave Simulator**: One-click ingestion from live backends or targeted scenario wave simulations.

## Port
- Assigned Port: `8003` (Internal)
- Gateway Route: `http://localhost:9000/p3/`
- API Proxy: `http://localhost:9000/p3/api/*`
