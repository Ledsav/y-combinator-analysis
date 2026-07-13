"""
Data cleaning module for Y Combinator dataset.

This module normalizes and standardizes all 8 raw CSV files:
- Standardizes text fields (lowercase, strip whitespace)
- Normalizes identifiers and categorical values
- Handles missing values consistently
- Validates data types

Output: Cleaned CSVs in data/processed/step1_cleaned/
"""

from pathlib import Path
import pandas as pd
import numpy as np
from typing import Dict, Tuple
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Path configuration
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
CLEANED_DIR = PROJECT_ROOT / "data" / "processed" / "step1_cleaned"


def standardize_text(text: str) -> str:
    """
    Standardize text field: strip whitespace, handle None.

    Args:
        text: Input text string

    Returns:
        Cleaned text or None
    """
    if pd.isna(text):
        return None
    return str(text).strip()


def clean_companies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean companies.csv dataset.

    Transformations:
    - Remove 'Unnamed: 0' column
    - Ensure 'id' is integer primary key
    - Standardize text fields (name, slug, oneLiner, longDescription)
    - Normalize batch format (uppercase, e.g., S05, W06)
    - Standardize status categories
    - Parse teamSize as numeric (preserve NaN)

    Args:
        df: Raw companies dataframe

    Returns:
        Cleaned companies dataframe
    """
    logger.info("Cleaning companies dataset...")
    df_clean = df.copy()

    # Remove index column
    if "Unnamed: 0" in df_clean.columns:
        df_clean = df_clean.drop(columns=["Unnamed: 0"])

    # Ensure id is integer and unique
    df_clean["id"] = df_clean["id"].astype(int)
    assert df_clean["id"].is_unique, "Company IDs must be unique"

    # Standardize text fields
    for col in ["name", "slug", "oneLiner", "longDescription", "website", "url"]:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(standardize_text)

    # Normalize batch format (ensure uppercase)
    df_clean["batch"] = df_clean["batch"].str.upper().str.strip()

    # Standardize status (title case)
    df_clean["status"] = df_clean["status"].str.strip()

    # teamSize: ensure numeric, preserve NaN
    df_clean["teamSize"] = pd.to_numeric(df_clean["teamSize"], errors="coerce")

    logger.info(
        f"Companies cleaned: {len(df_clean)} rows, {len(df_clean.columns)} columns"
    )
    return df_clean


def clean_founders(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean founders.csv dataset.

    Transformations:
    - Standardize name fields
    - Normalize hnid (primary key)
    - Standardize company_slug for joining
    - Clean title and company fields

    Args:
        df: Raw founders dataframe

    Returns:
        Cleaned founders dataframe
    """
    logger.info("Cleaning founders dataset...")
    df_clean = df.copy()

    # Standardize text fields
    for col in [
        "first_name",
        "last_name",
        "hnid",
        "current_company",
        "current_title",
        "company_slug",
    ]:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(standardize_text)

    # Ensure hnid is string (it's an identifier, not numeric)
    df_clean["hnid"] = df_clean["hnid"].astype(str)

    # top_company is already boolean

    logger.info(
        f"Founders cleaned: {len(df_clean)} rows, {len(df_clean.columns)} columns"
    )
    return df_clean


def clean_industries(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean industries.csv dataset.

    Transformations:
    - Remove 'Unnamed: 0' column
    - Ensure id is integer (links to companies)
    - Standardize industry names

    Args:
        df: Raw industries dataframe

    Returns:
        Cleaned industries dataframe
    """
    logger.info("Cleaning industries dataset...")
    df_clean = df.copy()

    # Remove index column
    if "Unnamed: 0" in df_clean.columns:
        df_clean = df_clean.drop(columns=["Unnamed: 0"])

    # Ensure id is integer
    df_clean["id"] = df_clean["id"].astype(int)

    # Standardize industry names
    df_clean["industry"] = df_clean["industry"].apply(standardize_text)

    logger.info(
        f"Industries cleaned: {len(df_clean)} rows, {len(df_clean.columns)} columns"
    )
    return df_clean


def clean_tags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean tags.csv dataset.

    Transformations:
    - Remove 'Unnamed: 0' column
    - Ensure id is integer (links to companies)
    - Standardize tag names

    Args:
        df: Raw tags dataframe

    Returns:
        Cleaned tags dataframe
    """
    logger.info("Cleaning tags dataset...")
    df_clean = df.copy()

    # Remove index column
    if "Unnamed: 0" in df_clean.columns:
        df_clean = df_clean.drop(columns=["Unnamed: 0"])

    # Ensure id is integer
    df_clean["id"] = df_clean["id"].astype(int)

    # Standardize tag names
    df_clean["tag"] = df_clean["tag"].apply(standardize_text)

    logger.info(f"Tags cleaned: {len(df_clean)} rows, {len(df_clean.columns)} columns")
    return df_clean


def clean_regions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean regions.csv dataset.

    Transformations:
    - Remove 'Unnamed: 0' column
    - Ensure id is integer (links to companies)
    - Standardize region, country, address fields

    Args:
        df: Raw regions dataframe

    Returns:
        Cleaned regions dataframe
    """
    logger.info("Cleaning regions dataset...")
    df_clean = df.copy()

    # Remove index column
    if "Unnamed: 0" in df_clean.columns:
        df_clean = df_clean.drop(columns=["Unnamed: 0"])

    # Ensure id is integer
    df_clean["id"] = df_clean["id"].astype(int)

    # Standardize location fields
    for col in ["region", "country", "address"]:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(standardize_text)

    logger.info(
        f"Regions cleaned: {len(df_clean)} rows, {len(df_clean.columns)} columns"
    )
    return df_clean


def clean_schools(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean schools.csv dataset.

    Transformations:
    - Normalize hnid (links to founders)
    - Standardize school and field_of_study fields
    - Ensure year is integer

    Args:
        df: Raw schools dataframe

    Returns:
        Cleaned schools dataframe
    """
    logger.info("Cleaning schools dataset...")
    df_clean = df.copy()

    # Ensure hnid is string
    df_clean["hnid"] = df_clean["hnid"].astype(str)

    # Standardize text fields
    for col in ["school", "field_of_study"]:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(standardize_text)

    # Ensure year is integer
    df_clean["year"] = df_clean["year"].astype(int)

    logger.info(
        f"Schools cleaned: {len(df_clean)} rows, {len(df_clean.columns)} columns"
    )
    return df_clean


def clean_prior_companies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean prior_companies.csv dataset.

    Transformations:
    - Normalize hnid (links to founders)
    - Standardize company names

    Args:
        df: Raw prior_companies dataframe

    Returns:
        Cleaned prior_companies dataframe
    """
    logger.info("Cleaning prior_companies dataset...")
    df_clean = df.copy()

    # Ensure hnid is string
    df_clean["hnid"] = df_clean["hnid"].astype(str)

    # Standardize company names
    df_clean["company"] = df_clean["company"].apply(standardize_text)

    logger.info(
        f"Prior companies cleaned: {len(df_clean)} rows, {len(df_clean.columns)} columns"
    )
    return df_clean


def clean_badges(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean badges.csv dataset.

    Transformations:
    - Remove 'Unnamed: 0' column
    - Ensure id is integer (links to companies)
    - Standardize badge names

    Args:
        df: Raw badges dataframe

    Returns:
        Cleaned badges dataframe
    """
    logger.info("Cleaning badges dataset...")
    df_clean = df.copy()

    # Remove index column
    if "Unnamed: 0" in df_clean.columns:
        df_clean = df_clean.drop(columns=["Unnamed: 0"])

    # Ensure id is integer
    df_clean["id"] = df_clean["id"].astype(int)

    # Standardize badge names
    df_clean["badge"] = df_clean["badge"].apply(standardize_text)

    logger.info(
        f"Badges cleaned: {len(df_clean)} rows, {len(df_clean.columns)} columns"
    )
    return df_clean


def validate_cleaning(
    original_counts: Dict[str, int], cleaned_counts: Dict[str, int]
) -> bool:
    """
    Validate that cleaning preserved row counts and didn't introduce errors.

    Args:
        original_counts: Dict of filename -> row count from raw data
        cleaned_counts: Dict of filename -> row count from cleaned data

    Returns:
        True if validation passes, False otherwise
    """
    logger.info("Validating cleaned data...")

    all_valid = True
    for filename, original_count in original_counts.items():
        cleaned_count = cleaned_counts.get(filename, 0)
        if original_count != cleaned_count:
            logger.error(
                f"Row count mismatch for {filename}: {original_count} -> {cleaned_count}"
            )
            all_valid = False
        else:
            logger.info(f"✓ {filename}: {cleaned_count} rows preserved")

    return all_valid


def run_cleaning_pipeline(
    input_dir: Path = None, output_dir: Path = None
) -> Tuple[bool, str]:
    """
    Execute the complete data cleaning pipeline.

    Reads all raw CSVs, applies cleaning functions, validates, and saves.

    Args:
        input_dir: Path to raw CSVs directory. Defaults to RAW_DIR.
        output_dir: Path to write cleaned CSVs. Defaults to CLEANED_DIR.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if input_dir is None:
        input_dir = RAW_DIR
    if output_dir is None:
        output_dir = CLEANED_DIR

    logger.info("Starting data cleaning pipeline...")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define cleaning functions for each file
    cleaning_functions = {
        "companies.csv": clean_companies,
        "founders.csv": clean_founders,
        "industries.csv": clean_industries,
        "tags.csv": clean_tags,
        "regions.csv": clean_regions,
        "schools.csv": clean_schools,
        "prior_companies.csv": clean_prior_companies,
        "badges.csv": clean_badges,
    }

    original_counts = {}
    cleaned_counts = {}

    try:
        # Process each file
        for filename, clean_func in cleaning_functions.items():
            input_path = input_dir / filename
            output_path = output_dir / filename.replace(".csv", "_cleaned.csv")

            logger.info(f"\nProcessing {filename}...")

            # Read raw data
            df_raw = pd.read_csv(input_path)
            original_counts[filename] = len(df_raw)

            # Clean data
            df_clean = clean_func(df_raw)
            cleaned_counts[filename] = len(df_clean)

            # Save cleaned data
            df_clean.to_csv(output_path, index=False)
            logger.info(f"Saved to {output_path}")

        # Validate results
        if validate_cleaning(original_counts, cleaned_counts):
            logger.info("\n✓ Data cleaning pipeline completed successfully!")
            return True, "All 8 CSV files cleaned and validated"
        else:
            logger.error("\n✗ Validation failed - row count mismatches detected")
            return False, "Validation failed"

    except Exception as e:
        logger.error(f"\n✗ Pipeline failed with error: {str(e)}")
        return False, str(e)


if __name__ == "__main__":
    success, message = run_cleaning_pipeline()
    if success:
        print(f"\n{'='*60}")
        print(f"SUCCESS: {message}")
        print(f"{'='*60}")
        print(f"\nCleaned files saved to:")
        print(f"  {CLEANED_DIR.relative_to(PROJECT_ROOT)}")
    else:
        print(f"\n{'='*60}")
        print(f"FAILED: {message}")
        print(f"{'='*60}")
        exit(1)
