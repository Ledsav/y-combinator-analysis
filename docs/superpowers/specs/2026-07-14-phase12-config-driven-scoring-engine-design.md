# Phase 12: Config-Driven, Method-Agnostic Scoring Engine

**Date:** 2026-07-14
**Status:** Design approved, not yet implemented

---

## 1. Motivation

The project's 11 phases are complete (per `documentation/plan_complexity_metric/roadmap.md`), producing a working Complexity Index. But `src/etl/score.py` hardcodes its scoring rubric: six named functions (`compute_deep_tech_score`, `compute_regulated_score`, etc.), each with the scaling formula (`raw.clip(upper=cap) / cap * points`) inlined, called explicitly from `build_score_table`, and their point budgets re-asserted by hand in `validate_scores` (`between(0, 30)`, `between(0, 70)`, `between(0, 100)`).

This makes two things harder than they should be:
1. **Plugging in a non-linear (or any other) scaling method** — there's no interface a new method implements; you'd edit `build_score_table` directly.
2. **Changing the rubric** — every past revision (e.g. Phase 9.5's 50/50 → 30/70 split) required a code change and a matching hand-edit of the hardcoded validation bounds, which is exactly the kind of two-places-to-update bug class that's easy to get out of sync.

This phase is **future-proofing only** — no new estimation method ships as part of it. The one existing method (linear-capped scaling) is preserved exactly; what changes is that it becomes the first of potentially many, selected and parameterized from external data rather than baked into code.

**Not in scope:** implementing a second scaling method (logistic, percentile-rank, etc.); expressing raw-feature *combination* logic (e.g. founder-background's weighted sum) as config data rather than named code — combination logic stays as small named Python functions the config references by name, since it varies enough between buckets that generalizing it further is a bigger problem than this phase needs to solve.

---

## 2. Architecture

### 2.1 Rubric config files

One YAML file per output version, checked into `config/`:
- `config/rubric_v1.yaml` — reproduces Phase 7's original 50/50 split (for provenance/auditability of the frozen `complexity_index_v1.csv`; nothing forces it to be rerun).
- `config/rubric_v2.yaml` — reproduces Phase 9.5's current 30/70 split. This is what actually drives the live pipeline today.

A rubric declares a list of **buckets**. Each bucket has:

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | Unique bucket id. Output column is `<name>_score`. |
| `dimension` | yes | Which total this bucket rolls into (`technical`, `practical`, ...). Engine creates `<dimension>_score` per distinct value seen — not hardcoded to exactly two, though today's rubrics only use two. |
| `raw_feature` | one of `raw_feature` / `combine` | Single source column in the Phase 6 feature table. Mutually exclusive with `combine`. |
| `combine` + `combine_params` | one of `raw_feature` / `combine` | Name of a registered combine function (`src/etl/combine.py`) plus its params, for buckets built from multiple raw features. |
| `method` | yes | Name of a registered scaling function (`src/etl/scaling.py`). |
| `params` | yes | Kwargs for the scaling method. **Must include `points`** — the bucket's max output, and the unit `validate_scores` uses to derive dimension bounds. |

Example bucket entries (full `rubric_v2.yaml` mirrors all 7 buckets — see §2.4 for why there are 7, not 6):

```yaml
version: v2
description: "Phase 9.5 rubric — 30/70 technical/practical split"
buckets:
  - name: deep_tech
    dimension: technical
    raw_feature: deep_tech_tag_count
    method: linear_capped
    params: {cap: 2, points: 12}

  - name: description
    dimension: technical
    raw_feature: description_tech_score
    method: linear_capped
    params: {cap: 2, points: 9}

  - name: founder_background
    dimension: technical
    combine: weighted_sum
    combine_params:
      features: {founder_phd_count: 2, research_company_experience: 1}
    method: linear_capped
    params: {cap: 2, points: 9}

  - name: regulated
    dimension: practical
    raw_feature: regulated_industry
    method: linear_capped
    params: {cap: 1, points: 21}

  - name: market_type
    dimension: practical
    raw_feature: market_type_score
    method: linear_capped
    params: {cap: 3, points: 21}

  - name: international_operations
    dimension: practical
    raw_feature: international_operations
    method: linear_capped
    params: {cap: 1, points: 14}

  - name: operational_intensity
    dimension: practical
    raw_feature: operational_intensity
    method: linear_capped
    params: {cap: 1, points: 14}
```

`config/rubric_v1.yaml` follows the same shape with Phase 7's original 50/50-split point values (exact values pulled from `docs/superpowers/specs/2026-07-10-phase7-scoring-rubric-design.md` during implementation).

**Format:** YAML, adding `pyyaml` to `requirements.txt`. Chosen over JSON specifically so each bucket's cap/points can carry an inline comment explaining its rationale — every current value in `score.py` already has one, and losing that would be a real documentation regression.

### 2.2 `src/etl/scaling.py` — scaling-method registry

```python
def linear_capped(raw: pd.Series, cap: float, points: float) -> pd.Series:
    return raw.clip(upper=cap) / cap * points

SCALING_METHODS: Dict[str, Callable] = {"linear_capped": linear_capped}
```

**Contract:** every scaling method takes a raw `pd.Series` plus its own kwargs (which must include `points`), and returns a `pd.Series` bounded `[0, points]`. This contract is what lets `validate_scores` (§2.5) compute correct bounds purely from config, for any method — including ones that don't exist yet. Adding a new method later means writing one function honoring this contract and registering it here; nothing else in the codebase changes.

### 2.3 `src/etl/combine.py` — combine-method registry

```python
def identity(features_df: pd.DataFrame, raw_feature: str) -> pd.Series:
    return features_df[raw_feature]

def weighted_sum(features_df: pd.DataFrame, features: Dict[str, float]) -> pd.Series:
    return sum(features_df[col] * weight for col, weight in features.items())

COMBINE_METHODS: Dict[str, Callable] = {"identity": identity, "weighted_sum": weighted_sum}
```

A bucket with `raw_feature` set uses `identity` implicitly (no `combine` key needed). Only `founder_background` needs `combine: weighted_sum` today.

### 2.4 Output schema change: `geo_ops_score` splits in two

Today, `compute_geo_ops_score` independently caps-and-scales `international_operations` and `operational_intensity` into two internal halves (14 points each) and sums them into one `geo_ops_score` column. That's structurally different from the other five buckets (one raw signal in, one score out), and doesn't fit the uniform bucket model cleanly.

Generalizing means treating it as **two ordinary buckets** (`international_operations`, `operational_intensity`, 14 points each, both `dimension: practical`) instead of one composite bucket with internal two-part logic. The dimension-total summing (§2.5) naturally recombines them — no special-case "combine-then-sum-independently" mode needed in the engine.

**Consequence:** `complexity_index_v3.csv` (or whatever the next regenerated version is called) will have `international_operations_score` and `operational_intensity_score` columns instead of `geo_ops_score`. `technical_score`, `practical_score`, and `complexity_score` totals are unaffected — this is a pure decomposition of one existing column into two, not a rubric change.

### 2.5 `src/etl/score.py` — generalized engine

```python
def build_score_table(features_df: pd.DataFrame, rubric: dict) -> pd.DataFrame:
    scores = features_df[["id", "slug", "name", "batch", "status"]].copy()
    dimension_cols: Dict[str, List[str]] = {}

    for bucket in rubric["buckets"]:
        raw = _resolve_raw(features_df, bucket)          # combine.py, or identity
        method_fn = SCALING_METHODS[bucket["method"]]
        col = f"{bucket['name']}_score"
        scores[col] = method_fn(raw, **bucket["params"])
        dimension_cols.setdefault(bucket["dimension"], []).append(col)

    dimension_totals = []
    for dimension, cols in dimension_cols.items():
        total_col = f"{dimension}_score"
        scores[total_col] = scores[cols].sum(axis=1).round(1)
        dimension_totals.append(total_col)

    scores["complexity_score"] = scores[dimension_totals].sum(axis=1).round(1)
    return scores
```

`_resolve_raw` dispatches on whether the bucket has `raw_feature` (→ `identity`) or `combine` (→ the named combine function with `combine_params`).

`validate_scores(features_df, scores_df, rubric)` computes bounds from the config instead of hardcoding them:

```python
def validate_scores(features_df, scores_df, rubric) -> None:
    ...
    dimension_budgets: Dict[str, float] = {}
    for bucket in rubric["buckets"]:
        dimension_budgets[bucket["dimension"]] = (
            dimension_budgets.get(bucket["dimension"], 0) + bucket["params"]["points"]
        )
    for dimension, budget in dimension_budgets.items():
        assert scores_df[f"{dimension}_score"].between(0, budget).all()
    total_budget = sum(dimension_budgets.values())
    assert scores_df["complexity_score"].between(0, total_budget).all()
```

### 2.6 `src/etl/rubric.py` — config loading & validation

`load_rubric(path: Path) -> dict` reads and validates a rubric YAML before it reaches the engine:
- every bucket has a unique `name`
- exactly one of `raw_feature` / `combine` is present (not both, not neither)
- `method` is a key in `SCALING_METHODS`; if present, `combine` is a key in `COMBINE_METHODS`
- `params` includes `points`

Fails fast with a clear error rather than letting a malformed config produce a confusing downstream KeyError.

---

## 3. Integration

### 3.1 Pipeline / CLI

- `scripts/run_complexity_pipeline.py` gets a `--rubric-config` flag, defaulting to `config/rubric_<output-version>.yaml`.
- `src/etl/pipeline.py`'s `_default_paths` resolves that default and threads `rubric_config_path` through to `run_scoring_pipeline`.
- `run_scoring_pipeline` loads the rubric via `rubric.load_rubric` and passes it to `build_score_table`/`validate_scores`.

### 3.2 Downstream consumers (dashboard, notebook)

`scripts/generate_dashboard.py` (`build_correlation_matrix`) and `scripts/generate_complexity_analysis_notebook.py` currently hardcode the 6 legacy bucket-column names (confirmed via grep — both list them literally, not via `SCORE_COLUMNS` import). Both change to discover bucket-score columns dynamically: any column in the scores CSV ending in `_score` other than `technical_score`/`practical_score`/`complexity_score`. Neither script needs to parse YAML — they introspect the CSV they already load.

`tests/test_generate_dashboard.py` fixtures updated to match.

---

## 4. Testing & Verification

1. **Unit tests**, isolated per module:
   - `scaling.linear_capped` — linear scaling + clipping behavior (migrate existing cases from `test_score.py`).
   - `combine.identity`, `combine.weighted_sum`.
   - `rubric.load_rubric` — valid config loads; each validation failure mode raises clearly.
2. **Engine tests** in `test_score.py`: `build_score_table`/`validate_scores` against a small synthetic rubric + feature fixture, independent of the real rubric files.
3. **Regression check (load-bearing)**: run the new engine against `config/rubric_v2.yaml` over the real feature table, and assert `technical_score`, `practical_score`, `complexity_score` match the currently-committed `complexity_index_v2.csv` exactly, row for row. This is the proof the refactor preserves behavior; it must pass before anything else is considered done.
4. Regenerate `complexity_index_v2.csv`, `notebooks/complexity_analysis.ipynb`, and `output/complexity_dashboard_v2.html` with the new engine and commit them — the schema changed (§2.4), so the old files are stale, not wrong. `complexity_index_v1.csv` stays frozen; `config/rubric_v1.yaml` makes it reproducible on demand but nothing forces a rerun.
5. Full `pytest` suite green, including updated `test_run_complexity_pipeline.py` for the new `--rubric-config` flag.

**Definition of done for "method agnostic":** adding a second scaling method (e.g. `logistic`) afterward should require: (a) write `logistic()` in `scaling.py` honoring the `[0, points]` contract, (b) register it, (c) change one bucket's `method:`/`params:` in a rubric YAML, (d) add a unit test for `logistic()` itself. Zero changes to `score.py`, `pipeline.py`, `rubric.py`, or any other bucket's config.

---

## 5. Out of scope (explicitly deferred)

- Any second scaling method (logistic, percentile-rank, ML-learned, etc.) — this phase builds the plug-in point only.
- Expressing combine logic as generic config data rather than named functions.
- Config schema validation via a formal schema library (jsonschema etc.) — hand-written checks in `rubric.py` are sufficient at this scale.
- Changing `data/raw/` availability or the Phase 8 `enrich`-ordering gap — unrelated pre-existing issues, both already documented in the README.
