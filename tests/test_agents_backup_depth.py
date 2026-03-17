# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_agents_backup_depth.py
# REM: Depth coverage for agents/backup_agent.py
# REM: Helper functions are pure. Filesystem tasks use tmp_path.

import tarfile
import tempfile
from pathlib import Path

import pytest

from agents.backup_agent import (
    AGENT_ID,
    CAPABILITIES,
    REQUIRES_APPROVAL_FOR,
    _calculate_checksum,
    _human_size,
    get_backup_schedule,
    get_status,
    list_backups,
    list_volumes,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestBackupAgentConstants:
    def test_agent_id(self):
        assert AGENT_ID == "backup_agent"

    def test_capabilities_is_list(self):
        assert isinstance(CAPABILITIES, list)
        assert len(CAPABILITIES) > 0

    def test_requires_approval_for(self):
        assert "delete_backup" in REQUIRES_APPROVAL_FOR
        assert "restore_backup" in REQUIRES_APPROVAL_FOR


# ═══════════════════════════════════════════════════════════════════════════════
# _human_size helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestHumanSize:
    def test_bytes(self):
        result = _human_size(512)
        assert "B" in result
        assert "512" in result

    def test_kilobytes(self):
        result = _human_size(1024)
        assert "KB" in result

    def test_megabytes(self):
        result = _human_size(1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self):
        result = _human_size(1024 ** 3)
        assert "GB" in result

    def test_terabytes(self):
        result = _human_size(1024 ** 4)
        assert "TB" in result

    def test_zero_bytes(self):
        result = _human_size(0)
        assert "B" in result

    def test_returns_string(self):
        assert isinstance(_human_size(100), str)

    def test_one_kb(self):
        result = _human_size(1024)
        assert "1.0 KB" == result

    def test_fractional(self):
        result = _human_size(1536)  # 1.5 KB
        assert "1.5 KB" == result


# ═══════════════════════════════════════════════════════════════════════════════
# _calculate_checksum helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateChecksum:
    def test_returns_hex_string(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        result = _calculate_checksum(f)
        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 hex length

    def test_consistent_for_same_content(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"same content")
        f2.write_bytes(b"same content")
        assert _calculate_checksum(f1) == _calculate_checksum(f2)

    def test_differs_for_different_content(self, tmp_path):
        f1 = tmp_path / "c.txt"
        f2 = tmp_path / "d.txt"
        f1.write_bytes(b"content A")
        f2.write_bytes(b"content B")
        assert _calculate_checksum(f1) != _calculate_checksum(f2)

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        result = _calculate_checksum(f)
        assert len(result) == 64

    def test_known_checksum(self, tmp_path):
        # SHA256 of b"" = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        result = _calculate_checksum(f)
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


# ═══════════════════════════════════════════════════════════════════════════════
# get_backup_schedule task — pure, returns hardcoded config
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetBackupSchedule:
    def test_returns_success(self):
        result = get_backup_schedule()
        assert result["status"] == "success"

    def test_has_schedules_list(self):
        result = get_backup_schedule()
        assert isinstance(result["schedules"], list)
        assert len(result["schedules"]) >= 2

    def test_daily_schedule_exists(self):
        result = get_backup_schedule()
        names = [s["name"] for s in result["schedules"]]
        assert "daily_backup" in names

    def test_weekly_schedule_exists(self):
        result = get_backup_schedule()
        names = [s["name"] for s in result["schedules"]]
        assert "weekly_backup" in names

    def test_schedule_has_cron(self):
        result = get_backup_schedule()
        for sched in result["schedules"]:
            assert "cron" in sched

    def test_qms_status(self):
        result = get_backup_schedule()
        assert result["qms_status"] == "Thank_You"


# ═══════════════════════════════════════════════════════════════════════════════
# get_status task — filesystem-safe (returns defaults when /app/backups absent)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetStatusTask:
    def test_returns_agent_id(self):
        result = get_status()
        assert result["agent_id"] == "backup_agent"

    def test_returns_healthy(self):
        result = get_status()
        assert result["status"] == "healthy"

    def test_has_stats(self):
        result = get_status()
        assert "stats" in result

    def test_stats_has_total_backups(self):
        result = get_status()
        assert "total_backups" in result["stats"]

    def test_stats_has_total_size(self):
        result = get_status()
        assert "total_size_bytes" in result["stats"]

    def test_qms_status(self):
        result = get_status()
        assert result["qms_status"] == "Thank_You"


# ═══════════════════════════════════════════════════════════════════════════════
# list_volumes task — returns empty list when /data doesn't exist
# ═══════════════════════════════════════════════════════════════════════════════

class TestListVolumesTask:
    def test_returns_success(self):
        result = list_volumes()
        assert result["status"] == "success"

    def test_volumes_is_list(self):
        result = list_volumes()
        assert isinstance(result["volumes"], list)

    def test_count_matches_volumes(self):
        result = list_volumes()
        assert result["count"] == len(result["volumes"])

    def test_qms_status(self):
        result = list_volumes()
        assert result["qms_status"] == "Thank_You"


# ═══════════════════════════════════════════════════════════════════════════════
# list_backups task — returns empty list when /app/backups doesn't exist
# ═══════════════════════════════════════════════════════════════════════════════

class TestListBackupsTask:
    def test_returns_success(self):
        result = list_backups()
        assert result["status"] == "success"

    def test_backups_is_list(self):
        result = list_backups()
        assert isinstance(result["backups"], list)

    def test_count_matches_backups(self):
        result = list_backups()
        assert result["count"] == len(result["backups"])

    def test_qms_status(self):
        result = list_backups()
        assert result["qms_status"] == "Thank_You"

    def test_with_backup_type_filter(self):
        # Even with a filter, returns success (just no results if dir doesn't exist)
        result = list_backups(backup_type="manual")
        assert result["status"] == "success"


# ═══════════════════════════════════════════════════════════════════════════════
# delete_backup task — path validation (outside /app/backups)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeleteBackupPathValidation:
    def test_path_outside_backup_dir_returns_error(self):
        from agents.backup_agent import delete_backup
        result = delete_backup("/etc/passwd")
        assert result["status"] == "error"
        assert "outside" in result["error"].lower()

    def test_path_traversal_outside_backup_dir(self):
        from agents.backup_agent import delete_backup
        result = delete_backup("/tmp/evil.tar.gz")
        assert result["status"] == "error"

    def test_valid_path_not_found_returns_error(self):
        from agents.backup_agent import delete_backup
        result = delete_backup("/app/backups/nonexistent_file.tar.gz")
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# restore_backup task — path validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestRestoreBackupPathValidation:
    def test_path_outside_backup_dir_returns_error(self):
        from agents.backup_agent import restore_backup
        result = restore_backup("/etc/passwd")
        assert result["status"] == "error"
        assert "outside" in result["error"].lower()

    def test_valid_path_not_found_returns_error(self):
        from agents.backup_agent import restore_backup
        result = restore_backup("/app/backups/nonexistent.tar.gz")
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# verify_backup task — file not found
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyBackupNotFound:
    def test_nonexistent_file_returns_error(self):
        from agents.backup_agent import verify_backup
        result = verify_backup("/app/backups/nonexistent.tar.gz")
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    def test_error_qms_status(self):
        from agents.backup_agent import verify_backup
        result = verify_backup("/tmp/does_not_exist_backup.tar.gz")
        assert result["qms_status"] == "Thank_You_But_No"


# ═══════════════════════════════════════════════════════════════════════════════
# verify_backup with real file
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyBackupWithRealFile:
    def test_calculates_checksum_without_expected(self, tmp_path):
        # Create a fake tar.gz
        backup_file = tmp_path / "test_backup.tar.gz"
        with tarfile.open(backup_file, "w:gz") as tar:
            info = tarfile.TarInfo(name="dummy")
            info.size = 0
            import io
            tar.addfile(info, io.BytesIO(b""))

        from agents.backup_agent import verify_backup
        result = verify_backup(str(backup_file))
        assert result["status"] == "calculated"
        assert "checksum_sha256" in result
        assert result["match"] is None

    def test_verify_matching_checksum(self, tmp_path):
        backup_file = tmp_path / "test_verify.tar.gz"
        with tarfile.open(backup_file, "w:gz") as tar:
            info = tarfile.TarInfo(name="dummy")
            info.size = 0
            import io
            tar.addfile(info, io.BytesIO(b""))

        expected = _calculate_checksum(backup_file)
        from agents.backup_agent import verify_backup
        result = verify_backup(str(backup_file), expected_checksum=expected)
        assert result["status"] == "valid"
        assert result["match"] is True
        assert result["qms_status"] == "Thank_You"

    def test_verify_wrong_checksum(self, tmp_path):
        backup_file = tmp_path / "test_corrupt.tar.gz"
        with tarfile.open(backup_file, "w:gz") as tar:
            info = tarfile.TarInfo(name="dummy")
            info.size = 0
            import io
            tar.addfile(info, io.BytesIO(b""))

        from agents.backup_agent import verify_backup
        result = verify_backup(str(backup_file), expected_checksum="a" * 64)
        assert result["status"] == "corrupted"
        assert result["match"] is False
        assert result["qms_status"] == "Thank_You_But_No"


# ═══════════════════════════════════════════════════════════════════════════════
# apply_retention_policy — no backup dir exists
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplyRetentionPolicyNoBakDir:
    def test_no_dir_returns_success_zero_deleted(self):
        from agents.backup_agent import apply_retention_policy
        result = apply_retention_policy(backup_type="nonexistent_type_xyz_abc")
        assert result["status"] == "success"
        assert result["deleted_count"] == 0

    def test_qms_status(self):
        from agents.backup_agent import apply_retention_policy
        result = apply_retention_policy(backup_type="nonexistent_type_xyz_abc2")
        assert result["qms_status"] == "Thank_You"
