import pandas as pd

from src.etl.clean import run_cleaning_pipeline


def test_run_cleaning_pipeline_respects_input_and_output_dir(tmp_path):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "step1_cleaned"
    input_dir.mkdir()

    pd.DataFrame(
        {"id": [1], "batch": ["w24"], "status": ["Active"], "teamSize": [3]}
    ).to_csv(input_dir / "companies.csv", index=False)
    pd.DataFrame({"hnid": ["a"]}).to_csv(input_dir / "founders.csv", index=False)
    pd.DataFrame({"id": [1], "industry": ["Fintech"]}).to_csv(
        input_dir / "industries.csv", index=False
    )
    pd.DataFrame({"id": [1], "tag": ["AI"]}).to_csv(input_dir / "tags.csv", index=False)
    pd.DataFrame({"id": [1]}).to_csv(input_dir / "regions.csv", index=False)
    pd.DataFrame({"hnid": ["a"], "year": [2020]}).to_csv(
        input_dir / "schools.csv", index=False
    )
    pd.DataFrame({"hnid": ["a"], "company": ["Old Co"]}).to_csv(
        input_dir / "prior_companies.csv", index=False
    )
    pd.DataFrame({"id": [1], "badge": ["Top Company"]}).to_csv(
        input_dir / "badges.csv", index=False
    )

    success, message = run_cleaning_pipeline(input_dir=input_dir, output_dir=output_dir)

    assert success is True
    assert (output_dir / "companies_cleaned.csv").exists()
    cleaned = pd.read_csv(output_dir / "companies_cleaned.csv")
    assert cleaned.loc[0, "batch"] == "W24"


def test_run_cleaning_pipeline_defaults_still_work_with_no_args():
    # Uses the real RAW_DIR/CLEANED_DIR defaults — just confirms the
    # function signature still accepts a no-arg call after the change.
    import inspect

    from src.etl.clean import run_cleaning_pipeline as fn

    sig = inspect.signature(fn)
    assert list(sig.parameters) == ["input_dir", "output_dir"]
    assert sig.parameters["input_dir"].default is None
    assert sig.parameters["output_dir"].default is None
