# Y Combinator Company Analysis

A comprehensive data analysis project for analyzing Y Combinator company datasets.

## Project Overview

This project provides tools and analysis for exploring Y Combinator company data, including funding rounds, company performance, industry trends, and success patterns.

## Project Structure

```
y-combinator-analysis/
├── data/
│   ├── raw/              # Raw data files (original datasets)
│   └── processed/        # Cleaned and processed data
├── notebooks/            # Jupyter notebooks for exploratory analysis
├── src/                  # Source code for data processing and analysis
├── tests/                # Unit tests
├── output/               # Generated reports, visualizations, and results
├── requirements.txt      # Python dependencies
├── .gitignore           # Git ignore rules
└── README.md            # This file
```

## Setup

### Prerequisites
- Python 3.12 or higher
- pip (Python package manager)

### Installation

1. Clone this repository (or navigate to the project directory)
   ```bash
   cd y-combinator-analysis
   ```

2. Create a virtual environment
   ```bash
   python -m venv .venv
   ```

3. Activate the virtual environment
   - Windows:
     ```bash
     .venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source .venv/bin/activate
     ```

4. Install required packages
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Data Processing
Place your raw Y Combinator dataset files in the `data/raw/` directory.

### Running Analysis
1. Start with the exploratory notebooks in the `notebooks/` directory
2. Use the source code in `src/` for reproducible data processing
3. Results and visualizations will be saved to the `output/` directory

## Dependencies

- **pandas**: Data manipulation and analysis
- **numpy**: Numerical computing
- Additional packages may be added as needed

## Contributing

When adding new features:
1. Write clean, documented code
2. Add unit tests in the `tests/` directory
3. Update this README if needed

## License

This project is for educational and research purposes.

## Contact

For questions or suggestions, please open an issue in the project repository.
