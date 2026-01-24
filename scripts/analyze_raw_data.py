#!/usr/bin/env python3
"""Analyze raw CSV files to generate data dictionary statistics."""
import pandas as pd
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def analyze_csv(filepath):
    """Analyze a single CSV file and return stats."""
    df = pd.read_csv(filepath)
    stats = {
        "file": filepath.name,
        "rows": len(df),
        "columns": len(df.columns),
        "column_details": [],
    }

    for col in df.columns:
        col_stats = {
            "name": col,
            "dtype": str(df[col].dtype),
            "null_count": int(df[col].isna().sum()),
            "null_pct": round(df[col].isna().sum() / len(df) * 100, 2),
            "unique_count": int(df[col].nunique()),
            "sample_values": df[col].dropna().head(3).tolist(),
        }
        stats["column_details"].append(col_stats)

    return stats


def main():
    """Analyze all CSV files in data/raw."""
    csv_files = sorted(RAW_DIR.glob("*.csv"))

    print("# Data Dictionary - Raw Dataset Analysis\n")
    print(f"**Analysis Date:** {pd.Timestamp.now().strftime('%Y-%m-%d')}\n")
    print(f"**Total Files:** {len(csv_files)}\n")

    for csv_file in csv_files:
        print(f"\n## {csv_file.stem}.csv\n")
        stats = analyze_csv(csv_file)

        print(f"**Rows:** {stats['rows']:,}")
        print(f"**Columns:** {stats['columns']}\n")
        print("| Column | Type | Null Count | Null % | Unique | Sample Values |")
        print("|--------|------|------------|--------|--------|---------------|")

        for col in stats["column_details"]:
            sample = (
                str(col["sample_values"])[:50] + "..."
                if len(str(col["sample_values"])) > 50
                else str(col["sample_values"])
            )
            print(
                f"| `{col['name']}` | {col['dtype']} | {col['null_count']:,} | {col['null_pct']}% | {col['unique_count']:,} | {sample} |"
            )

        print()


if __name__ == "__main__":
    main()
