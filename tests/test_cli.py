from pathlib import Path

import yaml

from cli import _plain_terminal_wizard, _run_config_set, _run_init, _run_logs, _run_status
from adiuvare.core.models import AdiuvareEvent
from adiuvare.state.audit_log import AuditLog


def test_plain_wizard_writes_yaml(tmp_path, monkeypatch):
    dest = tmp_path / "adiuvare.yaml"
    answers = iter(["fastapi", "single", "internal", "observe", "no", str(dest)])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    _plain_terminal_wizard(dest)
    loaded = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert loaded["runtime"]["observe_only"] is True
    assert loaded["runtime"]["audit_db_path"] == ".adiuvare/audit.db"
    assert loaded["runtime"]["state_db_path"] == ".adiuvare/state.db"
    assert loaded["ai"]["mode"] == "off"
    assert loaded["ai"]["model"] == "llama3"
    assert loaded["thresholds"]["flag"] == 0.25
    assert loaded["thresholds"]["throttle"] == 0.55
    assert loaded["weights"]["payload"] == 0.40
    assert loaded["meta"]["framework"] == "fastapi"
    assert loaded["meta"]["instances"] == "single"
    assert loaded["meta"]["strictness"] == "internal"


def test_run_config_set_patches_nested_value(tmp_path, monkeypatch):
    cfg = tmp_path / "adiuvare.yaml"
    cfg.write_text("thresholds:\n  block: 0.8\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    _run_config_set("thresholds.block", "0.73")
    loaded = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert loaded["thresholds"]["block"] == 0.73


def test_run_logs_prints_recent_rows(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "adiuvare.yaml"
    audit_path = tmp_path / "audit.db"
    cfg.write_text(
        yaml.safe_dump({"runtime": {"audit_db_path": str(audit_path), "state_db_path": str(tmp_path / "state.db")}}),
        encoding="utf-8",
    )
    audit = AuditLog(audit_path)
    audit.write(
        AdiuvareEvent(
            identity="user:1",
            endpoint="GET /health",
            score=0.0,
            verdict="allow",
            breakdown={},
        )
    )
    monkeypatch.chdir(tmp_path)
    _run_logs(5)
    out = capsys.readouterr().out
    assert "user:1" in out
    assert "GET /health" in out


def test_run_status_prints_framework_and_instances(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "adiuvare.yaml"
    cfg.write_text(
        yaml.safe_dump(
            {
                "runtime": {"audit_db_path": str(tmp_path / "audit.db"), "state_db_path": str(tmp_path / "state.db")},
                "meta": {"framework": "fastapi", "instances": "single"},
                "ai": {"mode": "assist"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    _run_status()
    out = capsys.readouterr().out
    assert "framework: fastapi" in out
    assert "instances: single" in out


def test_run_init_keeps_existing_file_when_user_declines(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "adiuvare.yaml"
    cfg.write_text("thresholds:\n  block: 0.8\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    _run_init(cfg, no_tui=True)
    assert cfg.read_text(encoding="utf-8") == "thresholds:\n  block: 0.8\n"
    assert "aborted" in capsys.readouterr().out
