"""Tests for durable recommendation state in GitHub Actions workflows."""

from pathlib import Path

import pytest


@pytest.mark.parametrize("workflow_name", ["main.yml", "test.yml"])
def test_email_workflows_restore_and_save_history_and_upload_funnel(workflow_name):
    workflow = (Path(__file__).parent.parent / ".github" / "workflows" / workflow_name).read_text(
        encoding="utf-8"
    )

    assert "Restore recommendation history" in workflow
    assert "actions/cache/restore@v4" in workflow
    assert "Save recommendation history" in workflow
    assert "actions/cache/save@v4" in workflow
    assert workflow.count(".cache/recommendation-history.json") >= 2
    assert "Upload recommendation funnel" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "outputs/recommendation-funnel.json" in workflow
    assert "if: always()" in workflow


def test_daily_email_schedule_runs_at_six_am_shanghai_time():
    workflow = (Path(__file__).parent.parent / ".github" / "workflows" / "main.yml").read_text(
        encoding="utf-8"
    )

    assert "cron: '0 22 * * *'" in workflow
    assert "06:00 Asia/Shanghai" in workflow
