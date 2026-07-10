# Data Directory

## Structure

- **raw/**: Store original, unmodified Y Combinator datasets here
  - Keep raw data immutable
  - Document data sources and download dates
  
- **processed/**: Store cleaned and transformed datasets
  - Save intermediate processing steps
  - Use consistent naming conventions (e.g., `companies_cleaned.csv`)

## Data Sources

- **Source URL**: [2024 YCombinator All Companies Dataset](https://www.kaggle.com/datasets/sashakorovkina/ycombinator-all-funded-companies-dataset) (Kaggle, sashakorovkina)
- **Download date**: Unknown — not recorded at the time of import.
- **Dataset description**: Y Combinator company directory data scraped from YC's public listings (companies, founders, industries, badges, regions, schools, tags, prior companies).
- **Data format**: CSV (8 files, raw in `data/raw/`, gitignored).

## Data Dictionary

Document the columns/fields in your datasets:
- Column name
- Data type
- Description
- Example values
