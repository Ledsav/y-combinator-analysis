from pathlib import Path

from scripts import run_complexity_pipeline as cli_module
from scripts.run_complexity_pipeline import build_arg_parser, main, parse_steps_arg


def test_parse_steps_arg_splits_and_strips_comma_list():
    assert parse_steps_arg("clean, impute,score") == ["clean", "impute", "score"]


def test_parse_steps_arg_handles_all():
    assert parse_steps_arg("all") == ["all"]


def test_build_arg_parser_defaults():
    parser = build_arg_parser()
    args = parser.parse_args([])
    assert args.steps == "all"
    assert args.output_version == "v1"
    assert args.rubric_config is None


def test_build_arg_parser_accepts_overrides():
    parser = build_arg_parser()
    args = parser.parse_args(
        [
            "--steps", "clean,impute",
            "--output-version", "v3",
            "--rubric-config", "config/custom.yaml",
        ]
    )
    assert args.steps == "clean,impute"
    assert args.output_version == "v3"
    assert args.rubric_config == "config/custom.yaml"


def test_main_calls_run_pipeline_with_parsed_args_and_returns_zero(monkeypatch):
    captured = {}

    def fake_run_pipeline(steps, output_version, rubric_config_path):
        captured["steps"] = steps
        captured["output_version"] = output_version
        captured["rubric_config_path"] = rubric_config_path

    monkeypatch.setattr(cli_module, "run_pipeline", fake_run_pipeline)

    exit_code = main(["--steps", "clean,impute", "--output-version", "v3"])

    assert exit_code == 0
    assert captured == {
        "steps": ["clean", "impute"],
        "output_version": "v3",
        "rubric_config_path": None,
    }


def test_main_passes_rubric_config_path_as_a_path(monkeypatch):
    captured = {}

    def fake_run_pipeline(steps, output_version, rubric_config_path):
        captured["rubric_config_path"] = rubric_config_path

    monkeypatch.setattr(cli_module, "run_pipeline", fake_run_pipeline)

    main(["--steps", "score", "--rubric-config", "config/custom.yaml"])

    assert captured["rubric_config_path"] == Path("config/custom.yaml")


def test_main_returns_one_and_prints_error_on_pipeline_failure(monkeypatch, capsys):
    def fake_run_pipeline(steps, output_version, rubric_config_path):
        raise FileNotFoundError("missing data/raw/companies.csv")

    monkeypatch.setattr(cli_module, "run_pipeline", fake_run_pipeline)

    exit_code = main(["--steps", "clean"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "FAILED" in captured.err
