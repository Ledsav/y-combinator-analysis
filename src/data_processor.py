"""
Data processing utilities for Y Combinator dataset analysis.

This module provides functions for cleaning and transforming Y Combinator data.
"""

import pandas as pd
import numpy as np


def clean_company_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and standardize Y Combinator company data.

    Parameters:
    -----------
    df : pd.DataFrame
        Raw dataframe to clean

    Returns:
    --------
    pd.DataFrame
        Cleaned dataframe
    """
    df_clean = df.copy()

    # Remove duplicates
    df_clean = df_clean.drop_duplicates()

    # Strip whitespace from string columns
    string_columns = df_clean.select_dtypes(include=["object"]).columns
    for col in string_columns:
        df_clean[col] = df_clean[col].str.strip()

    return df_clean


def extract_year(df: pd.DataFrame, date_column: str) -> pd.DataFrame:
    """
    Extract year from a date column.

    Parameters:
    -----------
    df : pd.DataFrame
        Dataframe containing date column
    date_column : str
        Name of the column containing dates

    Returns:
    --------
    pd.DataFrame
        Dataframe with added year column
    """
    df_copy = df.copy()
    df_copy[date_column] = pd.to_datetime(df_copy[date_column], errors="coerce")
    df_copy[f"{date_column}_year"] = df_copy[date_column].dt.year

    return df_copy


def categorize_funding(df: pd.DataFrame, funding_column: str) -> pd.DataFrame:
    """
    Categorize companies by funding amount.

    Parameters:
    -----------
    df : pd.DataFrame
        Dataframe containing funding information
    funding_column : str
        Name of the column containing funding amounts

    Returns:
    --------
    pd.DataFrame
        Dataframe with added funding category column
    """
    df_copy = df.copy()

    # Define funding categories (in millions)
    bins = [0, 1, 10, 50, 100, float("inf")]
    labels = ["<1M", "1M-10M", "10M-50M", "50M-100M", "100M+"]

    df_copy["funding_category"] = pd.cut(
        df_copy[funding_column], bins=bins, labels=labels
    )

    return df_copy
