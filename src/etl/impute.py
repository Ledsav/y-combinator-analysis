"""
Data Imputation Module for Y Combinator Analysis
Phase 4: Missing data completion with conservative heuristics

Strategy:
- Extract oneLiner from first sentence of longDescription (text-only, no synthesis)
- Add founder_count column by aggregating founders.csv
- Leave numeric fields (teamSize) as NaN with enrichment flags
- Generate enrichment_priorities.csv for optional Phase 5 scraping
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
import re


def extract_first_sentence(text: str) -> str:
    """
    Extract the first sentence from text.
    Handles common sentence terminators: . ! ?

    Args:
        text: Input text (longDescription)

    Returns:
        First sentence, or empty string if text is invalid
    """
    if pd.isna(text) or not isinstance(text, str):
        return ""

    text = text.strip()
    if not text:
        return ""

    # Match first sentence ending with . ! or ?
    # Handle edge case: "Inc." "Ltd." etc.
    match = re.search(r"^(.*?[.!?])(?:\s|$)", text)

    if match:
        sentence = match.group(1).strip()
        # Validate it's not too short (likely abbreviation like "Inc.")
        if len(sentence) > 10:
            return sentence
        # If too short, try to get more context
        sentences = re.split(r"[.!?]\s+", text)
        return sentences[0].strip() if sentences else text[:100]

    # No sentence terminator found - take first 100 chars
    return text[:100].strip()


def impute_oneliner_from_description(
    companies_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    Impute missing oneLiner values from longDescription.
    Only extracts from existing text - no synthetic generation.

    Args:
        companies_df: Cleaned companies dataframe

    Returns:
        Tuple of (updated dataframe, imputation log records)
    """
    imputation_log = []
    companies_df = companies_df.copy()

    # Find companies missing oneLiner but with longDescription
    missing_mask = (
        companies_df["oneLiner"].isna() & companies_df["longDescription"].notna()
    )
    missing_count = missing_mask.sum()

    print(f"Attempting to impute {missing_count} missing oneLiners...")

    for idx in companies_df[missing_mask].index:
        long_desc = companies_df.loc[idx, "longDescription"]
        first_sentence = extract_first_sentence(long_desc)

        if first_sentence:
            companies_df.loc[idx, "oneLiner"] = first_sentence
            imputation_log.append(
                {
                    "company_id": companies_df.loc[idx, "id"],
                    "company_slug": companies_df.loc[idx, "slug"],
                    "field": "oneLiner",
                    "method": "first_sentence_extraction",
                    "success": True,
                    "original_value": None,
                    "imputed_value": (
                        first_sentence[:50] + "..."
                        if len(first_sentence) > 50
                        else first_sentence
                    ),
                }
            )
        else:
            imputation_log.append(
                {
                    "company_id": companies_df.loc[idx, "id"],
                    "company_slug": companies_df.loc[idx, "slug"],
                    "field": "oneLiner",
                    "method": "first_sentence_extraction",
                    "success": False,
                    "original_value": None,
                    "imputed_value": None,
                }
            )

    successful = sum(1 for log in imputation_log if log["success"])
    print(f"Successfully imputed {successful}/{missing_count} oneLiners")

    return companies_df, imputation_log


def add_founder_count(
    companies_df: pd.DataFrame, founders_df: pd.DataFrame
) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    Add founder_count column by aggregating founders.csv by company_slug.

    Args:
        companies_df: Cleaned companies dataframe
        founders_df: Cleaned founders dataframe

    Returns:
        Tuple of (updated dataframe, enrichment log records)
    """
    enrichment_log = []
    companies_df = companies_df.copy()

    # Aggregate founder counts by company_slug
    founder_counts = (
        founders_df.groupby("company_slug").size().reset_index(name="founder_count")
    )

    # Merge with companies (left join to preserve all companies)
    companies_df = companies_df.merge(
        founder_counts, left_on="slug", right_on="company_slug", how="left"
    )
    companies_df.drop(columns=["company_slug"], inplace=True)

    # Fill NaN founder_count with 0 (companies with no founder data)
    companies_with_founders = companies_df["founder_count"].notna().sum()
    companies_df["founder_count"] = companies_df["founder_count"].fillna(0).astype(int)

    print(
        f"Added founder_count: {companies_with_founders}/{len(companies_df)} companies have founder data"
    )

    # Log companies without founder data
    no_founders_mask = companies_df["founder_count"] == 0
    for idx in companies_df[no_founders_mask].index:
        enrichment_log.append(
            {
                "company_id": companies_df.loc[idx, "id"],
                "company_slug": companies_df.loc[idx, "slug"],
                "field": "founder_count",
                "method": "aggregation_from_founders_csv",
                "success": False,
                "original_value": 0,
                "imputed_value": 0,
            }
        )

    return companies_df, enrichment_log


def create_enrichment_priorities(companies_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate ranked priority list for optional Phase 5 enrichment.

    Prioritization factors:
    1. Active/Public status (higher priority than Inactive)
    2. Recent batches (W20-W24 > older batches)
    3. Missing critical fields (oneLiner, longDescription)
    4. No founder data

    Args:
        companies_df: Companies dataframe with imputed data

    Returns:
        Dataframe with enrichment priorities
    """
    priorities = companies_df.copy()

    # Initialize priority score (0-100)
    priorities["enrichment_score"] = 0

    # Factor 1: Status (Active=30, Public=25, Acquired=15, Inactive=0)
    status_scores = {"Active": 30, "Public": 25, "Acquired": 15, "Inactive": 0}
    priorities["enrichment_score"] += priorities["status"].map(status_scores).fillna(0)

    # Factor 2: Recent batch (extract year from batch, e.g., "W24" -> 2024)
    def extract_batch_year(batch: str) -> int:
        if pd.isna(batch):
            return 2000
        # Handle formats: W24, S23, etc.
        year_str = batch[-2:]
        try:
            year = int(year_str)
            # Convert 2-digit year: 24 -> 2024, 05 -> 2005
            return 2000 + year if year >= 0 else 2000
        except:
            return 2000

    priorities["batch_year"] = priorities["batch"].apply(extract_batch_year)
    # Recent batches (2020+) get 20 points, scale down for older
    priorities["enrichment_score"] += priorities["batch_year"].apply(
        lambda y: 20 if y >= 2020 else max(0, (y - 2000) * 1)
    )

    # Factor 3: Missing critical fields
    priorities["enrichment_score"] += priorities["oneLiner"].isna().astype(int) * 15
    priorities["enrichment_score"] += (
        priorities["longDescription"].isna().astype(int) * 20
    )
    priorities["enrichment_score"] += (priorities["founder_count"] == 0).astype(
        int
    ) * 10

    # Create flags for missing data
    priorities["missing_oneliner"] = priorities["oneLiner"].isna()
    priorities["missing_description"] = priorities["longDescription"].isna()
    priorities["missing_founders"] = priorities["founder_count"] == 0
    priorities["missing_teamsize"] = priorities["teamSize"].isna()

    # Generate YC company URL for potential scraping
    priorities["yc_url"] = "https://www.ycombinator.com/companies/" + priorities["slug"]

    # Select relevant columns and sort by priority
    enrichment_cols = [
        "id",
        "slug",
        "name",
        "status",
        "batch",
        "batch_year",
        "enrichment_score",
        "missing_oneliner",
        "missing_description",
        "missing_founders",
        "missing_teamsize",
        "yc_url",
    ]

    priorities = priorities[enrichment_cols].sort_values(
        "enrichment_score", ascending=False
    )

    print(f"\nEnrichment Priority Summary:")
    print(f"High priority (score ≥60): {(priorities['enrichment_score'] >= 60).sum()}")
    print(
        f"Medium priority (40-59): {((priorities['enrichment_score'] >= 40) & (priorities['enrichment_score'] < 60)).sum()}"
    )
    print(f"Low priority (<40): {(priorities['enrichment_score'] < 40).sum()}")

    return priorities


def validate_imputation(original_df: pd.DataFrame, imputed_df: pd.DataFrame) -> None:
    """
    Validate that imputation didn't corrupt data.

    Args:
        original_df: Original companies dataframe
        imputed_df: Imputed companies dataframe
    """
    assert len(original_df) == len(imputed_df), "Row count changed during imputation!"

    # Check that we didn't overwrite existing oneLiners
    original_has_oneliner = original_df["oneLiner"].notna()
    assert (
        original_df.loc[original_has_oneliner, "oneLiner"]
        == imputed_df.loc[original_has_oneliner, "oneLiner"]
    ).all(), "Existing oneLiners were modified!"

    # Check that founder_count is non-negative
    assert (imputed_df["founder_count"] >= 0).all(), "Negative founder counts found!"

    print("✅ Validation passed: No data corruption detected")


def run_imputation_pipeline(input_dir: Path = None, output_dir: Path = None) -> None:
    """
    Main imputation pipeline orchestrator.

    Args:
        input_dir: Path to step1_cleaned/ directory
        output_dir: Path to step2_imputed/ directory
    """
    # Setup paths
    if input_dir is None:
        input_dir = (
            Path(__file__).resolve().parents[2] / "data" / "processed" / "step1_cleaned"
        )
    if output_dir is None:
        output_dir = (
            Path(__file__).resolve().parents[2] / "data" / "processed" / "step2_imputed"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("PHASE 4: MISSING DATA COMPLETION")
    print("=" * 60)

    # Load cleaned data
    print("\n[1/6] Loading cleaned data...")
    companies_df = pd.read_csv(input_dir / "companies_cleaned.csv")
    founders_df = pd.read_csv(input_dir / "founders_cleaned.csv")

    original_companies = companies_df.copy()

    # Step 1: Impute oneLiner from longDescription
    print("\n[2/6] Imputing missing oneLiners...")
    companies_df, oneliner_log = impute_oneliner_from_description(companies_df)

    # Step 2: Add founder_count
    print("\n[3/6] Adding founder counts...")
    companies_df, founder_log = add_founder_count(companies_df, founders_df)

    # Step 3: Validate
    print("\n[4/6] Validating imputation...")
    validate_imputation(original_companies, companies_df)

    # Step 4: Create enrichment priorities
    print("\n[5/6] Creating enrichment priority list...")
    enrichment_priorities = create_enrichment_priorities(companies_df)

    # Step 5: Save outputs
    print("\n[6/6] Saving imputed data...")

    # Save imputed companies
    companies_df.to_csv(output_dir / "companies_imputed.csv", index=False)
    print(f"  ✓ {output_dir / 'companies_imputed.csv'}")

    # Copy other cleaned files (no imputation needed for these)
    for filename in [
        "founders_cleaned.csv",
        "industries_cleaned.csv",
        "tags_cleaned.csv",
        "schools_cleaned.csv",
        "prior_companies_cleaned.csv",
        "regions_cleaned.csv",
        "badges_cleaned.csv",
    ]:
        src = input_dir / filename
        dst = output_dir / filename.replace("_cleaned", "_imputed")
        pd.read_csv(src).to_csv(dst, index=False)
        print(f"  ✓ {dst}")

    # Save imputation report
    imputation_report = pd.DataFrame(oneliner_log + founder_log)
    imputation_report.to_csv(output_dir / "imputation_report.csv", index=False)
    print(f"  ✓ {output_dir / 'imputation_report.csv'}")

    # Save enrichment priorities
    enrichment_priorities.to_csv(output_dir / "enrichment_priorities.csv", index=False)
    print(f"  ✓ {output_dir / 'enrichment_priorities.csv'}")

    print("\n" + "=" * 60)
    print("PHASE 4 COMPLETE")
    print("=" * 60)
    print(f"\nOutputs saved to: {output_dir}")
    print(f"Total companies: {len(companies_df)}")
    print(f"OneLiners imputed: {sum(1 for log in oneliner_log if log['success'])}")
    print(f"Companies with founders: {(companies_df['founder_count'] > 0).sum()}")
    print(
        f"Companies flagged for enrichment: {(enrichment_priorities['enrichment_score'] >= 40).sum()}"
    )


if __name__ == "__main__":
    run_imputation_pipeline()
