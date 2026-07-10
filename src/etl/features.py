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


TECH_KEYWORD_PATTERNS: List[str] = [
    r"\bresearch(?:ers?)?\b", r"\bpatents?\b", r"\bpatented\b", r"\bnovel\b",
    r"\balgorithms?\b", r"\bproprietary\b", r"\bbreakthroughs?\b",
    r"\blaborator(?:y|ies)\b", r"\bclinical trials?\b", r"\bpeer[- ]reviewed\b",
    r"\bprototypes?\b", r"\bneural networks?\b", r"\bdeep learning\b",
    r"\bmachine learning\b", r"\bartificial intelligence\b", r"\bquantum\b",
    r"\bsemiconductors?\b", r"\bgenomes?\b", r"\bproteins?\b", r"\bmolecules?\b",
    r"\bbiotechnology\b", r"\bautonomous\b", r"\brobotics?\b",
]

COUNTRY_NAME_OVERRIDES: dict = {"United States of America": "United States"}
EXCLUDED_COUNTRY_VALUES: Set[str] = {"Remote"}


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


def normalize_country_names(
    countries: Iterable[str],
    overrides: dict = COUNTRY_NAME_OVERRIDES,
    excluded: Set[str] = EXCLUDED_COUNTRY_VALUES,
) -> List[str]:
    """
    Map raw region-country values to name forms more likely to appear in
    prose (e.g. "United States of America" -> "United States"), dropping
    non-country placeholder values and nulls.

    Args:
        countries: Raw country values (e.g. from regions_df["country"]).
        overrides: Mapping of raw country name -> prose-friendly name.
        excluded: Non-country placeholder values to drop.

    Returns:
        Sorted list of unique, normalized country names.
    """
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
