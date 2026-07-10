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
