"""
Data loading utilities for Y Combinator dataset analysis.

This module provides functions to load and validate Y Combinator company data.
"""

import pandas as pd
from pathlib import Path


def load_raw_data(filename: str) -> pd.DataFrame:
    """
    Load raw data from the data/raw directory.

    Parameters:
    -----------
    filename : str
        Name of the file to load (e.g., 'companies.csv')

    Returns:
    --------
    pd.DataFrame
        Loaded dataframe

    Examples:
    ---------
    >>> df = load_raw_data('yc_companies.csv')
    """
    data_path = Path(__file__).parent.parent / "data" / "raw" / filename

    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    # Determine file type and load accordingly
    if filename.endswith(".csv"):
        return pd.read_csv(data_path)
    elif filename.endswith(".json"):
        return pd.read_json(data_path)
    elif filename.endswith(".xlsx"):
        return pd.read_excel(data_path)
    else:
        raise ValueError(f"Unsupported file format: {filename}")


def save_processed_data(df: pd.DataFrame, filename: str) -> None:
    """
    Save processed data to the data/processed directory.

    Parameters:
    -----------
    df : pd.DataFrame
        Dataframe to save
    filename : str
        Name of the file to save (e.g., 'companies_cleaned.csv')

    Examples:
    ---------
    >>> save_processed_data(df, 'companies_cleaned.csv')
    """
    output_path = Path(__file__).parent.parent / "data" / "processed" / filename

    if filename.endswith(".csv"):
        df.to_csv(output_path, index=False)
    elif filename.endswith(".json"):
        df.to_json(output_path, orient="records", indent=2)
    elif filename.endswith(".parquet"):
        df.to_parquet(output_path, index=False)
    else:
        raise ValueError(f"Unsupported file format: {filename}")

    print(f"Data saved to: {output_path}")
