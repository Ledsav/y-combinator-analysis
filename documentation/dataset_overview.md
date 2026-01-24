# Y Combinator Dataset Overview

This document provides a high-level overview of the Y Combinator dataset, initial findings, and potential avenues for deeper analysis.

## 1. Dataset Content

The dataset is composed of 8 CSV files:

-   `companies.csv`: Main table with 4,844 companies. Contains company name, description, team size, YC batch, and operational status.
-   `founders.csv`: Information on 8,465 founders, linked to companies.
-   `industries.csv`: Company-to-industry mappings.
-   `badges.csv`: Special recognitions like "topCompany" or "highlightWomen".
-   `regions.csv`: Geographic information for each company.
-   `schools.csv`: Educational background of founders.
-   `tags.csv`: Descriptive tags for companies (e.g., "SaaS", "AI").
-   `prior_companies.csv`: Founders' previous work experience.

## 2. Initial Findings & Key Statistics

-   **Company Status**:
    -   **Active**: 71.0%
    -   **Inactive**: 16.6%
    -   **Acquired**: 12.0%
    -   **Public**: 0.4%
-   **Success Rate**: Only **1.88%** of companies have the `topCompany` badge, offering a strict definition of success. A broader definition could include `Acquired` and `Public` companies (12.4%).
-   **Team Size**: Public companies have a significantly larger median team size (600) compared to active (8), acquired (11), and inactive (2) companies. This suggests team growth is a strong indicator of reaching a large scale.
-   **Industries & Tags**: The most common industries are **B2B (26%)**, Consumer (9%), and Healthcare (7%). Popular tags include **SaaS**, **Fintech**, and **Artificial Intelligence**.
-   **Founder Background**:
    -   **Education**: Top feeder schools are Stanford, MIT, and UC Berkeley.
    -   **Experience**: Many founders previously worked at major tech companies like Google, Facebook, and Microsoft.
-   **Batch Vintage**: A stark contrast exists between early and recent batches.
    -   **Early (2005-2007)**: 52% of companies are now Inactive or Acquired.
    -   **Recent (2022-2024)**: 97% of companies are still Active, which is expected given their young age. This highlights the time it takes for outcomes to materialize.

## 3. Potential Analysis Paths

Here are some interesting questions you can explore with this dataset.

### a) Success & Failure Analysis (Predictive Modeling)

The primary goal here is to identify the key drivers of startup success.

-   **Define Success**:
    -   **Strict**: `badge` == 'topCompany'
    -   **Broad**: `status` in ['Acquired', 'Public']
-   **Features to Analyze**:
    -   **Founder DNA**: Does the founder's school (`schools.csv`) or prior employer (`prior_companies.csv`) correlate with success? Do "top company" founders produce more successful startups?
    -   **Team Composition**: Is there an optimal initial `teamSize`?
    -   **Industry & Niche**: Are certain `industries` or `tags` (like AI or Fintech) more prone to success or failure?
    -   **Geography**: Does the `region` or `country` impact a company's outcome?
-   **Complexity**: Medium. Requires merging multiple datasets and applying classification models (e.g., Logistic Regression, Random Forest).

### b) Company Clustering (Unsupervised Learning)

This analysis can help identify common startup archetypes.

-   **Clustering Features**:
    -   Combine `industries`, `tags`, and `longDescription`.
    -   Use NLP techniques (like TF-IDF or embeddings) on the text data to create numerical features.
-   **Goal**: To segment companies into groups like "Deep Tech B2B," "Consumer Marketplace," "Healthcare SaaS," etc. This can reveal which types of companies YC funds most often.
-   **Complexity**: Medium to High. Involves NLP and clustering algorithms (e.g., K-Means, DBSCAN).

### c) Statistical & Trend Analysis

-   **Batch Analysis**: How has the profile of a YC company changed over time? Compare the `industry`, `teamSize`, and `region` of companies from early batches versus recent ones.
-   **Geographic Hotspots**: Map the locations of successful vs. unsuccessful companies. Are there emerging startup hubs outside of the Bay Area?
-   **Founder Networks**: Analyze the prevalence of founders from the same schools or prior companies. Do "mafias" (e.g., the "PayPal Mafia") from certain universities or companies lead to more success?
-   **Complexity**: Low to Medium. Can be done with data aggregation and visualization.

### d) Company Complexity Index (New Analysis)

This involves creating a scoring system to quantify the "difficulty" of a startup's mission. This can be broken down into two components:

-   **Technical Complexity**: How hard is the technology the company is building?
    -   **Method**: Assign scores based on `tags` and `industries`. For example, "Generative AI," "Biotechnology," or "Robotics" would receive higher scores than "E-commerce" or "Social Media."
    -   **Advanced Method**: Use NLP on `longDescription` to detect keywords related to deep tech, scientific research, or patents.
    -   **Goal**: To see if technically ambitious companies have a higher failure rate but also produce more "topCompany" outcomes when they succeed.

-   **Practical (Market) Complexity**: How difficult is the market and operational environment?
    -   **Method**: Assign scores based on factors like:
        -   **Regulated Industries**: `Fintech` and `Healthcare` would get higher scores.
        -   **Market Type**: B2B companies might be considered more complex due to long sales cycles, while B2C is complex due to user acquisition challenges. This could be a nuanced factor.
        -   **Geography**: Operating in emerging markets (`regions`) might be assigned a higher practical complexity score due to logistical and regulatory hurdles.
    -   **Goal**: To understand if companies tackling difficult markets are more resilient or have different success patterns.

-   **Combined Index**: The technical and practical scores can be combined into a single complexity index. This could be used to cluster companies or as a feature in the predictive models for success.
-   **Complexity**: High. Requires careful feature engineering, scoring logic, and potentially advanced NLP.

## 4. Missing Data & Potential Integrations

-   **Missing Descriptions**: `longDescription` (6.9% missing) and `oneLiner` (3.1% missing).
    -   **Integration**: Scrape company `website` URLs to fetch up-to-date descriptions. (Complexity: **High**, requires web scraping and parsing).
-   **Missing Founder Info**: 381 companies lack founder data.
    -   **Integration**: Use external APIs (like LinkedIn or Clearbit) to find founder information based on the company name. (Complexity: **High**, requires API access and budget).
-   **Financial Data**: The dataset lacks funding rounds, valuation, and revenue.
    -   **Integration**: This is the most critical missing piece for a robust success analysis. You could attempt to link companies to external financial databases like Crunchbase or PitchBook. (Complexity: **Very High**, requires data subscription and fuzzy matching).
-   **Team Size**: 78 companies have no team size listed.
    -   **Integration**: Could be estimated from LinkedIn data or other professional network APIs. (Complexity: **High**).
