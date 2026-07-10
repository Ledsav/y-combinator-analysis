# Phase 6 Feature Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `src/etl/features.py`, a Phase 6 feature engineering module that extracts 8 raw complexity signals (4 technical, 4 practical) per company from `data/processed/step3_enriched/`, and writes `data/processed/features/complexity_features.parquet`.

**Architecture:** Pure, independently-testable functions — one per feature — each taking the small subset of dataframes it needs and returning a `(key, feature_value)` frame; an orchestrator (`build_feature_table`) that merges them all onto the companies table; a `validate_features` assertion function; and a pipeline entry point (`run_feature_engineering_pipeline`), following the exact module pattern of `src/etl/impute.py` and `src/etl/enrich.py` (module-level functions, `if __name__ == "__main__"` entry point, print-based progress logging, injectable keyword/tag sets as default parameters so tests don't depend on the exact curated taxonomy).

**Tech Stack:** Python stdlib (`re`, `pathlib`) + `pandas` (already a dependency) + `pyarrow` (new dependency, required for `DataFrame.to_parquet`).

## Global Constraints

- This is feature *extraction* only — no weighting, scoring, or 0-100 index. That is Phase 7 (`documentation/plan_complexity_metric/roadmap.md` "Phase 7: Scoring Rubric"). Every feature column here is a raw count, 0/1 flag, or small ordinal score.
- Input: `data/processed/step3_enriched/*.csv` (Phase 5 output — already exists in this repo).
- Output: `data/processed/features/complexity_features.parquet`, one row per company (same row count and `id` set as `companies_enriched.csv`), columns: `id, slug, name, batch, status, deep_tech_tag_count, description_tech_score, founder_phd_count, research_company_experience, regulated_industry, market_type_score, international_operations, operational_intensity`.
- No missing feature values in the output — every feature column is filled with `0` where nothing matched (never `NaN`).
- Per `documentation/plan_complexity_metric/objectives_and_metrics.md` open question #3 ("Start simple (keyword), upgrade if needed"): all text/tag matching is explicit keyword/set matching — no external NLP libraries, no new heavy dependencies.
- All curated keyword/tag/label sets are module-level constants but every compute function accepts them as an overridable default parameter, so unit tests exercise the matching *logic* with small fixture sets independent of the exact curated taxonomy content.
- `founders_df.hnid`, `schools_df.hnid`, and `prior_companies_df.hnid` are all string-typed (confirmed: `hnid` values like `'110'`, `'__JW__'`) — joins must not coerce to numeric.

---

## Task 1: Test setup + tag/industry-based features

**Files:**
- Create: `tests/test_features.py`
- Create: `src/etl/features.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces:
  - `DEEP_TECH_TAGS: Set[str]`, `REGULATED_INDUSTRIES: Set[str]`, `B2B_LABELS: Set[str]`, `MARKETPLACE_LABELS: Set[str]`, `B2C_LABELS: Set[str]`, `OPERATIONAL_LABELS: Set[str]` (module constants)
  - `compute_deep_tech_tag_count(tags_df: pd.DataFrame, deep_tech_tags: Set[str] = DEEP_TECH_TAGS) -> pd.DataFrame` — columns `['id', 'deep_tech_tag_count']`, only rows with count > 0
  - `compute_regulated_industry(tags_df: pd.DataFrame, industries_df: pd.DataFrame, regulated_labels: Set[str] = REGULATED_INDUSTRIES) -> pd.DataFrame` — columns `['id', 'regulated_industry']`, only matched ids (value always 1)
  - `compute_market_type_score(tags_df, industries_df, b2b_labels=B2B_LABELS, marketplace_labels=MARKETPLACE_LABELS, b2c_labels=B2C_LABELS) -> pd.DataFrame` — columns `['id', 'market_type_score']`, only matched ids, value = max(3 if B2B, 2 if Marketplace, 1 if B2C)
  - `compute_operational_intensity(tags_df, industries_df, operational_labels: Set[str] = OPERATIONAL_LABELS) -> pd.DataFrame` — columns `['id', 'operational_intensity']`, only matched ids, value = count of **distinct** matching labels

- [ ] **Step 1: Add pyarrow to the venv and requirements.txt**

Run: `./.venv/Scripts/pip.exe install pyarrow`

Then edit `requirements.txt` to:
```
pandas
numpy
pytest
pyarrow
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_features.py`:

```python
import pandas as pd

from src.etl.features import (
    compute_deep_tech_tag_count,
    compute_market_type_score,
    compute_operational_intensity,
    compute_regulated_industry,
)


def test_compute_deep_tech_tag_count_counts_matches_per_company():
    tags_df = pd.DataFrame(
        {
            "id": [1, 1, 1, 2, 3],
            "tag": ["Artificial Intelligence", "SaaS", "Robotics", "B2B", "Biotech"],
        }
    )
    deep_tech_tags = {"Artificial Intelligence", "Robotics", "Biotech"}

    result = compute_deep_tech_tag_count(tags_df, deep_tech_tags=deep_tech_tags)

    counts = dict(zip(result["id"], result["deep_tech_tag_count"]))
    assert counts == {1: 2, 3: 1}


def test_compute_deep_tech_tag_count_excludes_companies_with_no_matches():
    tags_df = pd.DataFrame({"id": [1], "tag": ["SaaS"]})

    result = compute_deep_tech_tag_count(tags_df, deep_tech_tags={"AI"})

    assert result.empty


def test_compute_regulated_industry_flags_matching_companies():
    tags_df = pd.DataFrame({"id": [1, 2], "tag": ["Fintech", "SaaS"]})
    industries_df = pd.DataFrame({"id": [3], "industry": ["Healthcare"]})

    result = compute_regulated_industry(
        tags_df, industries_df, regulated_labels={"Fintech", "Healthcare"}
    )

    matched_ids = set(result["id"])
    assert matched_ids == {1, 3}
    assert (result["regulated_industry"] == 1).all()


def test_compute_market_type_score_takes_highest_matching_type():
    tags_df = pd.DataFrame(
        {"id": [1, 1, 2, 3], "tag": ["B2B", "Marketplace", "Marketplace", "Consumer"]}
    )
    industries_df = pd.DataFrame({"id": [4], "industry": ["Other"]})

    result = compute_market_type_score(
        tags_df,
        industries_df,
        b2b_labels={"B2B"},
        marketplace_labels={"Marketplace"},
        b2c_labels={"Consumer"},
    )

    scores = dict(zip(result["id"], result["market_type_score"]))
    assert scores == {1: 3, 2: 2, 3: 1}


def test_compute_operational_intensity_counts_distinct_label_matches():
    tags_df = pd.DataFrame(
        {"id": [1, 1, 1, 2], "tag": ["Logistics", "Logistics", "Hardware", "SaaS"]}
    )
    industries_df = pd.DataFrame({"id": [1], "industry": ["Manufacturing"]})

    result = compute_operational_intensity(
        tags_df,
        industries_df,
        operational_labels={"Logistics", "Hardware", "Manufacturing"},
    )

    counts = dict(zip(result["id"], result["operational_intensity"]))
    assert counts == {1: 3}  # Logistics, Hardware, Manufacturing (duplicate Logistics row deduped)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_features.py -v`
Expected: `ModuleNotFoundError: No module named 'src.etl.features'` (module doesn't exist yet) or collection error.

- [ ] **Step 4: Implement `src/etl/features.py` (tag/industry-based features)**

```python
"""
Feature Engineering Module for Y Combinator Analysis
Phase 6: Extract technical and practical complexity features per company.

Strategy:
- Technical complexity signals: deep-tech tag matches, R&D keyword density in
  longDescription, founder PhD count, founder prior research/academic experience.
- Practical complexity signals: regulated-industry flag, market-type score
  (B2B/Marketplace/B2C), country-mention count in longDescription, operational
  intensity (logistics/hardware/manufacturing tag matches).
- This module extracts raw features only (counts, 0/1 flags, small ordinal
  scores). Weighting into a 0-100 index is Phase 7, not here.
- All keyword/tag/label sets are simple, explicit, and overridable (no
  external NLP libraries), per the "start simple" decision in
  documentation/plan_complexity_metric/objectives_and_metrics.md.
"""

import re
from pathlib import Path
from typing import Iterable, List, Set

import pandas as pd


DEEP_TECH_TAGS: Set[str] = {
    # AI / ML
    "AI", "AI Assistant", "AI-Enhanced Learning", "AI-powered Drug Discovery",
    "AIOps", "Artificial Intelligence", "Computer Vision", "Conversational AI",
    "Deep Learning", "Deepfake Detection", "Generative AI", "Machine Learning",
    "ML", "NLP", "Reinforcement Learning", "Speech Recognition",
    # Biotech / hard science
    "Biotech", "Biotechnology", "CRISPR", "Cell Therapy", "Cellular Agriculture",
    "Cultivated Meat", "Cultured Meat", "Drug Delivery", "Drug discovery",
    "Gene Therapy", "Genetic Engineering", "Genomics", "Lab-on-a-chip",
    "Medical Devices", "Medical Robotics", "Microfluidics", "Nanomedicine",
    "Neurotechnology", "Synthetic Biology",
    # Robotics / hardware / space
    "Robotics", "Food Service Robots & Machines", "Swarm Robotics",
    "Robotic Surgery", "Drones", "Autonomous Delivery", "Autonomous Trucking",
    "Self-Driving Vehicles", "Unmanned Vehicle", "Hardware", "Hard Tech",
    "Semiconductors", "Edge Computing Semiconductors", "Advanced Materials",
    "3D Printing", "Lidar", "Radar", "Satellites", "Rocketry",
    "Space Exploration", "Commercial Space Launch", "Air Taxis",
    "Fusion Energy", "Small Modular Reactors", "Quantum Computing",
    "Nanotechnology", "Nanosensors", "Batteryless IoT Sensors",
}

REGULATED_INDUSTRIES: Set[str] = {
    "Fintech", "Healthcare", "Healthcare IT", "Health Insurance", "Insurance",
    "Banking as a Service", "Banking and Exchange", "Credit and Lending",
    "Consumer Finance", "Finance and Accounting", "Asset Management", "Legal",
    "LegalTech", "Government", "GovTech", "Therapeutics", "Diagnostics",
    "Drug Discovery and Delivery", "Medical Devices", "Regtech",
    "Cyber Insurance", "Microinsurance",
}

B2B_LABELS: Set[str] = {"B2B"}
MARKETPLACE_LABELS: Set[str] = {"Marketplace"}
B2C_LABELS: Set[str] = {"Consumer"}

OPERATIONAL_LABELS: Set[str] = {
    "Logistics", "Supply Chain", "Supply Chain and Logistics", "Manufacturing",
    "Manufacturing and Robotics", "Hardware", "Construction",
    "Real Estate and Construction", "Housing and Real Estate", "Automotive",
    "Aerospace", "Aviation and Space", "Agriculture", "Sustainable Agriculture",
    "Vertical Farming", "Energy", "Mining", "Maritime", "Transportation",
    "Transportation Services", "Warehouse Management Tech", "Industrial",
    "Industrial Workplace Safety", "Industrials", "Food Service Robots & Machines",
    "Drones", "Delivery", "Autonomous Trucking", "Digital Freight Brokerage",
}


def _combined_labels(tags_df: pd.DataFrame, industries_df: pd.DataFrame) -> pd.DataFrame:
    """Concatenate tags and industries into a single (id, label) frame."""
    tags = tags_df.rename(columns={"tag": "label"})[["id", "label"]]
    industries = industries_df.rename(columns={"industry": "label"})[["id", "label"]]
    return pd.concat([tags, industries], ignore_index=True)


def compute_deep_tech_tag_count(
    tags_df: pd.DataFrame, deep_tech_tags: Set[str] = DEEP_TECH_TAGS
) -> pd.DataFrame:
    """
    Count deep-tech tag matches (AI/ML, biotech, robotics, hardware, space,
    quantum, etc.) per company.

    Args:
        tags_df: Long-format (id, tag) dataframe, one row per tag assignment.
        deep_tech_tags: Set of tag strings considered deep-tech.

    Returns:
        DataFrame with columns ['id', 'deep_tech_tag_count']. Companies with
        zero matches are absent (caller left-merges and fills 0).
    """
    matched = tags_df[tags_df["tag"].isin(deep_tech_tags)]
    return matched.groupby("id").size().reset_index(name="deep_tech_tag_count")


def compute_regulated_industry(
    tags_df: pd.DataFrame,
    industries_df: pd.DataFrame,
    regulated_labels: Set[str] = REGULATED_INDUSTRIES,
) -> pd.DataFrame:
    """
    Flag companies operating in a regulated industry (fintech, healthcare,
    insurance, legal, government, etc.), from either tags or industries.

    Args:
        tags_df: Long-format (id, tag) dataframe.
        industries_df: Long-format (id, industry) dataframe.
        regulated_labels: Set of tag/industry strings considered regulated.

    Returns:
        DataFrame with columns ['id', 'regulated_industry'] (always 1).
        Non-matching companies are absent (caller left-merges and fills 0).
    """
    labels = _combined_labels(tags_df, industries_df)
    matched_ids = labels.loc[labels["label"].isin(regulated_labels), "id"].unique()
    return pd.DataFrame({"id": matched_ids, "regulated_industry": 1})


def compute_market_type_score(
    tags_df: pd.DataFrame,
    industries_df: pd.DataFrame,
    b2b_labels: Set[str] = B2B_LABELS,
    marketplace_labels: Set[str] = MARKETPLACE_LABELS,
    b2c_labels: Set[str] = B2C_LABELS,
) -> pd.DataFrame:
    """
    Score each company's market-type complexity: B2B=3 (long sales cycles),
    Marketplace=2 (chicken-egg), B2C=1 (high CAC). A company matching
    multiple types takes the highest applicable score.

    Args:
        tags_df: Long-format (id, tag) dataframe.
        industries_df: Long-format (id, industry) dataframe.
        b2b_labels, marketplace_labels, b2c_labels: Label sets per type.

    Returns:
        DataFrame with columns ['id', 'market_type_score']. Non-matching
        companies are absent (caller left-merges and fills 0).
    """
    labels = _combined_labels(tags_df, industries_df).copy()

    def _label_score(label: str) -> int:
        if label in b2b_labels:
            return 3
        if label in marketplace_labels:
            return 2
        if label in b2c_labels:
            return 1
        return 0

    labels["_score"] = labels["label"].apply(_label_score)
    matched = labels[labels["_score"] > 0]
    return matched.groupby("id")["_score"].max().reset_index(name="market_type_score")


def compute_operational_intensity(
    tags_df: pd.DataFrame,
    industries_df: pd.DataFrame,
    operational_labels: Set[str] = OPERATIONAL_LABELS,
) -> pd.DataFrame:
    """
    Count distinct operational/logistics/hardware/manufacturing tag or
    industry matches per company (real-world operational intensity).

    Args:
        tags_df: Long-format (id, tag) dataframe.
        industries_df: Long-format (id, industry) dataframe.
        operational_labels: Set of tag/industry strings considered operational.

    Returns:
        DataFrame with columns ['id', 'operational_intensity']. Non-matching
        companies are absent (caller left-merges and fills 0).
    """
    labels = _combined_labels(tags_df, industries_df)
    matched = labels[labels["label"].isin(operational_labels)].drop_duplicates(
        ["id", "label"]
    )
    return matched.groupby("id").size().reset_index(name="operational_intensity")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_features.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add tests/test_features.py src/etl/features.py requirements.txt
git commit -m "feat: add tag/industry-based complexity features"
```

---

## Task 2: Text-based features (description NLP score + country mentions)

**Files:**
- Modify: `src/etl/features.py`
- Modify: `tests/test_features.py`

**Interfaces:**
- Produces:
  - `TECH_KEYWORD_PATTERNS: List[str]` (module constant, lowercase regex patterns)
  - `score_description_tech(text, keyword_patterns: List[str] = TECH_KEYWORD_PATTERNS) -> int`
  - `normalize_country_names(countries: Iterable[str]) -> List[str]`
  - `count_countries_mentioned(text, country_names: Iterable[str]) -> int`
  - `compute_international_operations(companies_df: pd.DataFrame, regions_df: pd.DataFrame) -> pd.DataFrame` — columns `['id', 'international_operations']`, one row per company in `companies_df`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_features.py`:

```python
from src.etl.features import (
    compute_international_operations,
    count_countries_mentioned,
    normalize_country_names,
    score_description_tech,
)


def test_score_description_tech_counts_keyword_matches():
    text = "Our proprietary machine learning algorithm uses a novel neural network."
    patterns = [
        r"\bproprietary\b", r"\bmachine learning\b", r"\balgorithms?\b",
        r"\bnovel\b", r"\bneural networks?\b",
    ]

    score = score_description_tech(text, keyword_patterns=patterns)

    assert score == 5


def test_score_description_tech_returns_zero_for_missing_text():
    assert score_description_tech(None) == 0
    assert score_description_tech(float("nan")) == 0
    assert score_description_tech("") == 0


def test_normalize_country_names_maps_and_dedupes():
    result = normalize_country_names(
        ["United States of America", "India", "Remote", "India", None]
    )
    assert result == ["India", "United States"]


def test_count_countries_mentioned_counts_distinct_whole_word_matches():
    text = "We started in India and expanded to Kenya, then to Indiana."
    countries = ["India", "Kenya", "Nigeria"]

    count = count_countries_mentioned(text, countries)

    assert count == 2  # India and Kenya; "Indiana" must not match "India"


def test_count_countries_mentioned_returns_zero_for_missing_text():
    assert count_countries_mentioned(None, ["India"]) == 0


def test_compute_international_operations_counts_per_company():
    companies_df = pd.DataFrame(
        {
            "id": [1, 2],
            "longDescription": [
                "We operate in India and Kenya.",
                "A local bakery in Ohio.",
            ],
        }
    )
    regions_df = pd.DataFrame(
        {"id": [10, 11, 12], "country": ["United States of America", "India", "Kenya"]}
    )

    result = compute_international_operations(companies_df, regions_df)

    counts = dict(zip(result["id"], result["international_operations"]))
    assert counts == {1: 2, 2: 0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_features.py -v`
Expected: `ImportError: cannot import name 'score_description_tech'`

- [ ] **Step 3: Implement the text-based feature functions**

Add to `src/etl/features.py` (add `Iterable, List` to the `typing` import — already imports `List, Set`, so just add `Iterable`):

```python
TECH_KEYWORD_PATTERNS: List[str] = [
    r"\bresearch(?:ers?)?\b", r"\bpatents?\b", r"\bpatented\b", r"\bnovel\b",
    r"\balgorithms?\b", r"\bproprietary\b", r"\bbreakthroughs?\b",
    r"\blaborator(?:y|ies)\b", r"\bclinical trials?\b", r"\bpeer[- ]reviewed\b",
    r"\bprototypes?\b", r"\bneural networks?\b", r"\bdeep learning\b",
    r"\bmachine learning\b", r"\bartificial intelligence\b", r"\bquantum\b",
    r"\bsemiconductors?\b", r"\bgenomes?\b", r"\bproteins?\b", r"\bmolecules?\b",
    r"\bbiotechnology\b", r"\bautonomous\b", r"\brobotics?\b",
]


def score_description_tech(
    text, keyword_patterns: List[str] = TECH_KEYWORD_PATTERNS
) -> int:
    """
    Count technical-vocabulary keyword occurrences in a company description
    (R&D intensity signal: research, patents, novel algorithms, etc.).

    Args:
        text: The longDescription value (may be None/NaN/non-string).
        keyword_patterns: Lowercase regex patterns to search for.

    Returns:
        Total keyword match count (sum across all patterns). 0 for
        missing/empty text.
    """
    if not isinstance(text, str) or not text.strip():
        return 0
    text_lower = text.lower()
    return sum(len(re.findall(pattern, text_lower)) for pattern in keyword_patterns)


def normalize_country_names(countries: Iterable[str]) -> List[str]:
    """
    Map raw region-country values to name forms more likely to appear in
    prose (e.g. "United States of America" -> "United States"), dropping
    non-country placeholder values and nulls.

    Args:
        countries: Raw country values (e.g. from regions_df["country"]).

    Returns:
        Sorted list of unique, normalized country names.
    """
    overrides = {"United States of America": "United States"}
    excluded = {"Remote"}
    result = []
    for country in countries:
        if pd.isna(country) or country in excluded:
            continue
        result.append(overrides.get(country, country))
    return sorted(set(result))


def count_countries_mentioned(text, country_names: Iterable[str]) -> int:
    """
    Count distinct countries (by name) mentioned in text — a proxy for
    geographic/international operational complexity.

    Args:
        text: The longDescription value (may be None/NaN/non-string).
        country_names: Country name strings to search for (whole-word,
            case-insensitive).

    Returns:
        Count of distinct country names found. 0 for missing/empty text.
    """
    if not isinstance(text, str) or not text.strip():
        return 0
    text_lower = text.lower()
    count = 0
    for name in country_names:
        pattern = r"\b" + re.escape(name.lower()) + r"\b"
        if re.search(pattern, text_lower):
            count += 1
    return count


def compute_international_operations(
    companies_df: pd.DataFrame, regions_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Count distinct countries mentioned in each company's longDescription,
    using the observed set of HQ countries (from regions_df) as the
    matching vocabulary.

    Args:
        companies_df: Companies dataframe with 'id' and 'longDescription'.
        regions_df: Regions dataframe with a 'country' column.

    Returns:
        DataFrame with columns ['id', 'international_operations'], one row
        per company in companies_df.
    """
    country_names = normalize_country_names(regions_df["country"].unique())
    result = companies_df[["id", "longDescription"]].copy()
    result["international_operations"] = result["longDescription"].apply(
        lambda text: count_countries_mentioned(text, country_names)
    )
    return result[["id", "international_operations"]]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_features.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/features.py tests/test_features.py
git commit -m "feat: add description-NLP and country-mention complexity features"
```

---

## Task 3: Founder-based features (PhD count + research-institution experience)

**Files:**
- Modify: `src/etl/features.py`
- Modify: `tests/test_features.py`

**Interfaces:**
- Produces:
  - `PHD_PATTERN: str`, `RESEARCH_PATTERN: str` (module constants, lowercase-oriented regex strings for `str.contains(..., case=False, regex=True)`)
  - `compute_founder_phd_count(founders_df: pd.DataFrame, schools_df: pd.DataFrame, phd_pattern: str = PHD_PATTERN) -> pd.DataFrame` — columns `['company_slug', 'founder_phd_count']`
  - `compute_research_company_experience(founders_df: pd.DataFrame, prior_companies_df: pd.DataFrame, research_pattern: str = RESEARCH_PATTERN) -> pd.DataFrame` — columns `['company_slug', 'research_company_experience']`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_features.py`:

```python
from src.etl.features import (
    compute_founder_phd_count,
    compute_research_company_experience,
)


def test_compute_founder_phd_count_counts_distinct_founders_with_phd():
    founders_df = pd.DataFrame(
        {
            "hnid": ["a", "b", "c", "d"],
            "company_slug": ["acme", "acme", "beta", "beta"],
        }
    )
    schools_df = pd.DataFrame(
        {
            "hnid": ["a", "a", "b", "c"],
            "field_of_study": [
                "Doctor Of Philosophy", "Computer Science", "Economics", "Phd",
            ],
        }
    )

    result = compute_founder_phd_count(founders_df, schools_df)

    counts = dict(zip(result["company_slug"], result["founder_phd_count"]))
    assert counts == {"acme": 1, "beta": 1}


def test_compute_founder_phd_count_deduplicates_multiple_phd_school_rows():
    founders_df = pd.DataFrame({"hnid": ["a"], "company_slug": ["acme"]})
    schools_df = pd.DataFrame(
        {"hnid": ["a", "a"], "field_of_study": ["Doctor Of Philosophy", "Ph.D."]}
    )

    result = compute_founder_phd_count(founders_df, schools_df)

    counts = dict(zip(result["company_slug"], result["founder_phd_count"]))
    assert counts == {"acme": 1}


def test_compute_research_company_experience_counts_distinct_founders():
    founders_df = pd.DataFrame(
        {"hnid": ["a", "b", "c"], "company_slug": ["acme", "acme", "beta"]}
    )
    prior_companies_df = pd.DataFrame(
        {
            "hnid": ["a", "b", "c"],
            "company": ["MIT Media Lab", "Acme Corp", "Stanford University"],
        }
    )

    result = compute_research_company_experience(founders_df, prior_companies_df)

    counts = dict(zip(result["company_slug"], result["research_company_experience"]))
    assert counts == {"acme": 1, "beta": 1}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_features.py -v`
Expected: `ImportError: cannot import name 'compute_founder_phd_count'`

- [ ] **Step 3: Implement the founder-based feature functions**

Add to `src/etl/features.py`:

```python
PHD_PATTERN: str = r"\bdoctor of philosophy\b|\bphd\b|\bph\.\s?d\.?"

RESEARCH_PATTERN: str = (
    r"\buniversit(?:y|ies)\b|\binstitute\b|\blaborator(?:y|ies)\b|\blabs?\b"
    r"|\bresearch\b|\bnasa\b|\bjpl\b|\bcern\b"
)


def compute_founder_phd_count(
    founders_df: pd.DataFrame, schools_df: pd.DataFrame, phd_pattern: str = PHD_PATTERN
) -> pd.DataFrame:
    """
    Count distinct founders per company with a PhD-like field_of_study
    (technical founder pedigree signal).

    Args:
        founders_df: Founders dataframe with 'hnid' and 'company_slug'.
        schools_df: Schools dataframe with 'hnid' and 'field_of_study'.
        phd_pattern: Case-insensitive regex identifying PhD field_of_study values.

    Returns:
        DataFrame with columns ['company_slug', 'founder_phd_count'].
        Companies with zero matches are absent (caller left-merges and fills 0).
    """
    schools = schools_df.dropna(subset=["field_of_study"])
    is_phd = schools["field_of_study"].str.contains(phd_pattern, case=False, regex=True)
    phd_hnids = set(schools.loc[is_phd, "hnid"])

    founders = founders_df[founders_df["hnid"].isin(phd_hnids)]
    matched = founders.drop_duplicates(["company_slug", "hnid"])
    return matched.groupby("company_slug").size().reset_index(name="founder_phd_count")


def compute_research_company_experience(
    founders_df: pd.DataFrame,
    prior_companies_df: pd.DataFrame,
    research_pattern: str = RESEARCH_PATTERN,
) -> pd.DataFrame:
    """
    Count distinct founders per company with prior experience at a
    university, research lab, or similar research institution.

    Args:
        founders_df: Founders dataframe with 'hnid' and 'company_slug'.
        prior_companies_df: Prior-companies dataframe with 'hnid' and 'company'.
        research_pattern: Case-insensitive regex identifying research-institution names.

    Returns:
        DataFrame with columns ['company_slug', 'research_company_experience'].
        Companies with zero matches are absent (caller left-merges and fills 0).
    """
    prior = prior_companies_df.dropna(subset=["company"])
    is_research = prior["company"].str.contains(research_pattern, case=False, regex=True)
    research_hnids = set(prior.loc[is_research, "hnid"])

    founders = founders_df[founders_df["hnid"].isin(research_hnids)]
    matched = founders.drop_duplicates(["company_slug", "hnid"])
    return matched.groupby("company_slug").size().reset_index(
        name="research_company_experience"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_features.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/features.py tests/test_features.py
git commit -m "feat: add founder PhD and research-institution experience features"
```

---

## Task 4: Feature table orchestrator + validation

**Files:**
- Modify: `src/etl/features.py`
- Modify: `tests/test_features.py`

**Interfaces:**
- Consumes: all `compute_*` functions from Tasks 1-3
- Produces:
  - `FEATURE_COLUMNS: List[str]` (module constant, the 8 feature column names)
  - `build_feature_table(companies_df, tags_df, industries_df, regions_df, founders_df, schools_df, prior_companies_df) -> pd.DataFrame` — columns `['id', 'slug', 'name', 'batch', 'status'] + FEATURE_COLUMNS`, one row per company in `companies_df`, no NaNs in feature columns
  - `validate_features(companies_df: pd.DataFrame, features_df: pd.DataFrame) -> None` — raises `AssertionError` on row-count/id-set mismatch, missing values, or out-of-range values; prints a success message otherwise

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_features.py`:

```python
import pytest

from src.etl.features import build_feature_table, validate_features


def _minimal_inputs():
    companies_df = pd.DataFrame(
        {
            "id": [1, 2],
            "slug": ["acme", "beta"],
            "name": ["Acme", "Beta"],
            "batch": ["W24", "S23"],
            "status": ["Active", "Active"],
            "longDescription": [
                "Acme builds a proprietary machine learning platform for India and Kenya.",
                "Beta is a local bakery.",
            ],
        }
    )
    tags_df = pd.DataFrame(
        {"id": [1, 1, 2], "tag": ["Artificial Intelligence", "B2B", "SaaS"]}
    )
    industries_df = pd.DataFrame({"id": [1], "industry": ["Fintech"]})
    regions_df = pd.DataFrame(
        {"id": [1, 2], "country": ["India", "United States of America"]}
    )
    founders_df = pd.DataFrame(
        {"hnid": ["a", "b"], "company_slug": ["acme", "beta"]}
    )
    schools_df = pd.DataFrame(
        {"hnid": ["a"], "field_of_study": ["Doctor Of Philosophy"]}
    )
    prior_companies_df = pd.DataFrame({"hnid": ["b"], "company": ["Acme Corp"]})
    return (
        companies_df, tags_df, industries_df, regions_df,
        founders_df, schools_df, prior_companies_df,
    )


def test_build_feature_table_has_one_row_per_company_and_no_missing_values():
    inputs = _minimal_inputs()

    features_df = build_feature_table(*inputs)

    assert len(features_df) == 2
    assert set(features_df["id"]) == {1, 2}
    feature_cols = [
        "deep_tech_tag_count", "description_tech_score", "founder_phd_count",
        "research_company_experience", "regulated_industry", "market_type_score",
        "international_operations", "operational_intensity",
    ]
    for col in feature_cols:
        assert features_df[col].notna().all()


def test_build_feature_table_computes_expected_values_for_acme():
    inputs = _minimal_inputs()

    features_df = build_feature_table(*inputs)

    acme = features_df[features_df["slug"] == "acme"].iloc[0]
    assert acme["deep_tech_tag_count"] == 1  # Artificial Intelligence
    assert acme["market_type_score"] == 3  # B2B
    assert acme["regulated_industry"] == 1  # Fintech
    assert acme["founder_phd_count"] == 1  # founder 'a' has a PhD
    assert acme["international_operations"] == 1  # "India" mentioned

    beta = features_df[features_df["slug"] == "beta"].iloc[0]
    assert beta["deep_tech_tag_count"] == 0
    assert beta["research_company_experience"] == 0  # "Acme Corp" isn't a research institution


def test_validate_features_passes_on_valid_table():
    inputs = _minimal_inputs()
    companies_df = inputs[0]
    features_df = build_feature_table(*inputs)

    validate_features(companies_df, features_df)  # should not raise


def test_validate_features_raises_on_row_count_mismatch():
    companies_df = pd.DataFrame({"id": [1, 2]})
    features_df = pd.DataFrame(
        {
            "id": [1],
            "deep_tech_tag_count": [0], "description_tech_score": [0],
            "founder_phd_count": [0], "research_company_experience": [0],
            "regulated_industry": [0], "market_type_score": [0],
            "international_operations": [0], "operational_intensity": [0],
        }
    )

    with pytest.raises(AssertionError, match="Row count"):
        validate_features(companies_df, features_df)


def test_validate_features_raises_on_missing_feature_values():
    companies_df = pd.DataFrame({"id": [1]})
    features_df = pd.DataFrame(
        {
            "id": [1],
            "deep_tech_tag_count": [None], "description_tech_score": [0],
            "founder_phd_count": [0], "research_company_experience": [0],
            "regulated_industry": [0], "market_type_score": [0],
            "international_operations": [0], "operational_intensity": [0],
        }
    )

    with pytest.raises(AssertionError, match="deep_tech_tag_count"):
        validate_features(companies_df, features_df)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_features.py -v`
Expected: `ImportError: cannot import name 'build_feature_table'`

- [ ] **Step 3: Implement `build_feature_table` and `validate_features`**

Add to `src/etl/features.py`:

```python
FEATURE_COLUMNS: List[str] = [
    "deep_tech_tag_count",
    "description_tech_score",
    "founder_phd_count",
    "research_company_experience",
    "regulated_industry",
    "market_type_score",
    "international_operations",
    "operational_intensity",
]


def build_feature_table(
    companies_df: pd.DataFrame,
    tags_df: pd.DataFrame,
    industries_df: pd.DataFrame,
    regions_df: pd.DataFrame,
    founders_df: pd.DataFrame,
    schools_df: pd.DataFrame,
    prior_companies_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build the full per-company Phase 6 feature table by computing each raw
    feature independently and left-merging them all onto the companies
    identity columns.

    Args:
        companies_df: Enriched companies dataframe (id, slug, name, batch,
            status, longDescription, ...).
        tags_df, industries_df, regions_df: Long-format per-company dataframes.
        founders_df: Founders dataframe (hnid, company_slug, ...).
        schools_df, prior_companies_df: Long-format per-founder dataframes.

    Returns:
        DataFrame with columns ['id', 'slug', 'name', 'batch', 'status'] +
        FEATURE_COLUMNS, one row per company in companies_df, no NaNs in
        feature columns.
    """
    features = companies_df[["id", "slug", "name", "batch", "status"]].copy()

    deep_tech = compute_deep_tech_tag_count(tags_df)
    regulated = compute_regulated_industry(tags_df, industries_df)
    market_type = compute_market_type_score(tags_df, industries_df)
    op_intensity = compute_operational_intensity(tags_df, industries_df)
    intl_ops = compute_international_operations(companies_df, regions_df)
    phd = compute_founder_phd_count(founders_df, schools_df)
    research_exp = compute_research_company_experience(founders_df, prior_companies_df)

    tech_score = companies_df[["id", "longDescription"]].copy()
    tech_score["description_tech_score"] = tech_score["longDescription"].apply(
        score_description_tech
    )

    features = features.merge(deep_tech, on="id", how="left")
    features = features.merge(tech_score[["id", "description_tech_score"]], on="id", how="left")
    features = features.merge(regulated, on="id", how="left")
    features = features.merge(market_type, on="id", how="left")
    features = features.merge(intl_ops, on="id", how="left")
    features = features.merge(op_intensity, on="id", how="left")
    features = features.merge(
        phd, left_on="slug", right_on="company_slug", how="left"
    ).drop(columns=["company_slug"])
    features = features.merge(
        research_exp, left_on="slug", right_on="company_slug", how="left"
    ).drop(columns=["company_slug"])

    for col in FEATURE_COLUMNS:
        features[col] = features[col].fillna(0).astype(int)

    return features


def validate_features(companies_df: pd.DataFrame, features_df: pd.DataFrame) -> None:
    """
    Validate the feature table before writing output.

    Args:
        companies_df: The source companies dataframe (post-enrichment).
        features_df: The built feature table.
    """
    assert len(companies_df) == len(features_df), "Row count changed during feature engineering!"
    assert set(companies_df["id"]) == set(features_df["id"]), "Company id set changed!"

    for col in FEATURE_COLUMNS:
        assert features_df[col].notna().all(), f"Missing values found in {col}!"
        assert (features_df[col] >= 0).all(), f"Negative values found in {col}!"

    assert features_df["regulated_industry"].isin([0, 1]).all(), (
        "regulated_industry must be 0 or 1!"
    )
    assert features_df["market_type_score"].isin([0, 1, 2, 3]).all(), (
        "market_type_score must be 0-3!"
    )

    print("Validation passed: No data corruption detected")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_features.py -v`
Expected: 19 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/features.py tests/test_features.py
git commit -m "feat: add feature table orchestrator and validation"
```

---

## Task 5: Pipeline orchestrator + real run + roadmap updates

**Files:**
- Modify: `src/etl/features.py`
- Modify: `tests/test_features.py`
- Modify: `documentation/plan_complexity_metric/roadmap.md`
- Modify: `documentation/plan/roadmap_todo.md`
- Create (generated by running the pipeline, not hand-written): `data/processed/features/complexity_features.parquet`

**Interfaces:**
- Consumes: `build_feature_table`, `validate_features` (Task 4)
- Produces: `run_feature_engineering_pipeline(input_dir: Path = None, output_dir: Path = None) -> None`

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_features.py`:

```python
from src.etl.features import run_feature_engineering_pipeline


def test_run_feature_engineering_pipeline_end_to_end(tmp_path):
    input_dir = tmp_path / "step3_enriched"
    output_dir = tmp_path / "features"
    input_dir.mkdir()

    companies = pd.DataFrame(
        [
            {
                "id": 1, "slug": "acme", "name": "Acme", "batch": "W24",
                "status": "Active",
                "longDescription": "Acme builds a proprietary machine learning platform.",
            },
            {
                "id": 2, "slug": "beta", "name": "Beta", "batch": "S23",
                "status": "Active", "longDescription": "Beta is a local bakery.",
            },
        ]
    )
    tags = pd.DataFrame({"id": [1], "tag": ["Artificial Intelligence"]})
    industries = pd.DataFrame({"id": [1], "industry": ["Fintech"]})
    regions = pd.DataFrame({"id": [1, 2], "country": ["United States of America", "India"]})
    founders = pd.DataFrame({"hnid": ["a"], "company_slug": ["acme"]})
    schools = pd.DataFrame({"hnid": ["a"], "field_of_study": ["Doctor Of Philosophy"]})
    prior_companies = pd.DataFrame({"hnid": [], "company": []})

    companies.to_csv(input_dir / "companies_enriched.csv", index=False)
    tags.to_csv(input_dir / "tags_enriched.csv", index=False)
    industries.to_csv(input_dir / "industries_enriched.csv", index=False)
    regions.to_csv(input_dir / "regions_enriched.csv", index=False)
    founders.to_csv(input_dir / "founders_enriched.csv", index=False)
    schools.to_csv(input_dir / "schools_enriched.csv", index=False)
    prior_companies.to_csv(input_dir / "prior_companies_enriched.csv", index=False)

    run_feature_engineering_pipeline(input_dir=input_dir, output_dir=output_dir)

    features_df = pd.read_parquet(output_dir / "complexity_features.parquet")
    assert len(features_df) == 2
    acme = features_df[features_df["slug"] == "acme"].iloc[0]
    assert acme["deep_tech_tag_count"] == 1
    assert acme["regulated_industry"] == 1
    assert acme["founder_phd_count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_features.py -v`
Expected: `ImportError: cannot import name 'run_feature_engineering_pipeline'`

- [ ] **Step 3: Implement `run_feature_engineering_pipeline`**

Add to `src/etl/features.py` (add `from pathlib import Path` — already imported at top):

```python
def run_feature_engineering_pipeline(input_dir: Path = None, output_dir: Path = None) -> None:
    """
    Main feature engineering pipeline orchestrator.

    Args:
        input_dir: Path to step3_enriched/ directory.
        output_dir: Path to features/ directory.
    """
    if input_dir is None:
        input_dir = (
            Path(__file__).resolve().parents[2] / "data" / "processed" / "step3_enriched"
        )
    if output_dir is None:
        output_dir = Path(__file__).resolve().parents[2] / "data" / "processed" / "features"

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("PHASE 6: FEATURE ENGINEERING")
    print("=" * 60)

    print("\n[1/4] Loading enriched data...")
    companies_df = pd.read_csv(input_dir / "companies_enriched.csv")
    tags_df = pd.read_csv(input_dir / "tags_enriched.csv")
    industries_df = pd.read_csv(input_dir / "industries_enriched.csv")
    regions_df = pd.read_csv(input_dir / "regions_enriched.csv")
    founders_df = pd.read_csv(input_dir / "founders_enriched.csv")
    schools_df = pd.read_csv(input_dir / "schools_enriched.csv")
    prior_companies_df = pd.read_csv(input_dir / "prior_companies_enriched.csv")

    print("\n[2/4] Building feature table...")
    features_df = build_feature_table(
        companies_df, tags_df, industries_df, regions_df,
        founders_df, schools_df, prior_companies_df,
    )

    print("\n[3/4] Validating features...")
    validate_features(companies_df, features_df)

    print("\n[4/4] Saving feature table...")
    output_path = output_dir / "complexity_features.parquet"
    features_df.to_parquet(output_path, index=False)
    print(f"  ✓ {output_path}")

    print("\n" + "=" * 60)
    print("PHASE 6 COMPLETE")
    print("=" * 60)
    print(f"Companies: {len(features_df)}")
    for col in FEATURE_COLUMNS:
        nonzero = int((features_df[col] > 0).sum())
        print(f"  {col}: {nonzero}/{len(features_df)} companies with value > 0")


if __name__ == "__main__":
    run_feature_engineering_pipeline()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_features.py -v`
Expected: 20 passed

- [ ] **Step 5: Commit**

```bash
git add src/etl/features.py tests/test_features.py
git commit -m "feat: add Phase 6 feature engineering pipeline orchestrator"
```

- [ ] **Step 6: Run the full test suite once more before the real run**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: all tests pass (Phase 5 `test_enrich.py` + Phase 6 `test_features.py`)

- [ ] **Step 7: Run the pipeline for real**

Run: `./.venv/Scripts/python.exe -m src.etl.features`

Expected: Console output showing `PHASE 6: FEATURE ENGINEERING`, then `PHASE 6 COMPLETE` with per-feature nonzero counts for all 4,844 companies.

- [ ] **Step 8: Sanity-check the output**

Run:
```bash
./.venv/Scripts/python.exe -c "
import pandas as pd
df = pd.read_parquet('data/processed/features/complexity_features.parquet')
print(df.shape)
print(df.isna().sum())
print(df[['deep_tech_tag_count','description_tech_score','founder_phd_count','research_company_experience','regulated_industry','market_type_score','international_operations','operational_intensity']].describe())
print(df.sort_values('deep_tech_tag_count', ascending=False)[['name','deep_tech_tag_count']].head(10))
"
```

Confirm: 4,844 rows, zero NaNs in any column, and the top `deep_tech_tag_count` companies are recognizably deep-tech (AI/biotech/robotics) by name.

- [ ] **Step 9: Update `documentation/plan_complexity_metric/roadmap.md`**

Change the checklist item 6 block:
```markdown
- [x] **6. Feature engineering**
  - [x] Extract technical complexity features
  - [x] Extract practical complexity features
  - [x] Combine with founder/school/prior company data
  - [x] Output: `data/processed/features/complexity_features.parquet`
```

Update the timeline table row:
```markdown
| 6. Features | 2-3 days | ✅ Complete |
```
and the total-complete percentage to `60% complete`.

Update "Next Immediate Actions":
```markdown
## Next Immediate Actions

**Current Focus:** Phase 7 - Scoring Rubric Design

**Next Steps:**
1. Design the interpretable weighted rubric per the Phase 7 spec above, using `data/processed/features/complexity_features.parquet` as input
2. Calibrate weights with example companies (biotech should score high technical, fintech high practical)
3. Run sensitivity analysis
4. Output: `notebooks/score_design.ipynb`
5. Update checklist item #7 accordingly

**To continue:** Mark this task complete and proceed to implementation.
```

- [ ] **Step 10: Update `documentation/plan/roadmap_todo.md`**

```markdown
- [x] 6. Feature engineering
```

- [ ] **Step 11: Commit**

```bash
git add documentation/plan_complexity_metric/roadmap.md documentation/plan/roadmap_todo.md docs/superpowers/plans/2026-07-10-phase6-feature-engineering.md
git add data/processed/features/complexity_features.parquet
git commit -m "feat: complete Phase 6 - extract complexity features for all companies"
```

---

## Self-Review Notes

- **Spec coverage:** All 4 technical features (`deep_tech_tag_count`, `description_tech_score`, `founder_phd_count`, `research_company_experience`) and all 4 practical features (`regulated_industry`, `market_type_score`, `international_operations`, `operational_intensity`) from the roadmap's Phase 6 spec are implemented (Tasks 1-3), combined and validated (Task 4), and written to the exact spec'd output path (Task 5).
- **Type consistency:** `compute_*` functions all return frames keyed by `id` (tag/industry/text-based) or `company_slug` (founder-based, since `founders_df` only carries `company_slug`, not `id`) — `build_feature_table` (Task 4) merges the `id`-keyed frames with `on="id"` and the `company_slug`-keyed frames with `left_on="slug", right_on="company_slug"`, consistent across Task 4's implementation and the integration test in Task 5.
- **No placeholders:** all steps contain complete, runnable code; all curated tag/label sets (`DEEP_TECH_TAGS`, `REGULATED_INDUSTRIES`, `OPERATIONAL_LABELS`) were cross-checked against the actual unique `tag`/`industry` values present in `data/processed/step3_enriched/tags_enriched.csv` and `industries_enriched.csv` to avoid dead entries that would silently never match.
- **hnid dtype:** confirmed `founders_df.hnid`, `schools_df.hnid`, `prior_companies_df.hnid` are all `str`-typed in the real data (values like `'110'`, `'__JW__'`) — the `isin()`/`set` joins in Task 3 rely on this and will not silently fail on type mismatch.
