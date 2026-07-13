"""Tests for drift detection (utils.diff_paths) and the backup/restore skip."""

import os
import plistlib
from unittest.mock import Mock

from mackup import utils
from mackup.application import ApplicationProfile
from mackup.mackup import Mackup


def _write(path, data, mode="w"):
    with open(path, mode) as f:
        f.write(data)


def test_identical_text_files_report_identical(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    _write(a, "same\ncontent\n")
    _write(b, "same\ncontent\n")
    result = utils.diff_paths(str(a), str(b))
    assert result.identical is True
    assert result.detail == ""


def test_differing_text_files_show_a_diff(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    _write(a, "line one\nline two\n")
    _write(b, "line one\nline CHANGED\n")
    result = utils.diff_paths(str(a), str(b))
    assert result.identical is False
    assert "line CHANGED" in result.detail
    assert "line two" in result.detail


def test_plist_equivalent_but_byte_different_reports_identical(tmp_path):
    """The differentiator: same plist data in binary vs xml format is 'in sync'."""
    data = {"Greeting": "hi", "Count": 3, "Nested": {"on": True}}
    binary_plist = tmp_path / "a.plist"
    xml_plist = tmp_path / "b.plist"
    with open(binary_plist, "wb") as f:
        plistlib.dump(data, f, fmt=plistlib.FMT_BINARY)
    with open(xml_plist, "wb") as f:
        plistlib.dump(data, f, fmt=plistlib.FMT_XML)
    # Sanity: the bytes really do differ.
    assert binary_plist.read_bytes() != xml_plist.read_bytes()
    result = utils.diff_paths(str(binary_plist), str(xml_plist))
    assert result.identical is True


def test_plist_with_different_values_shows_a_diff(tmp_path):
    a = tmp_path / "a.plist"
    b = tmp_path / "b.plist"
    with open(a, "wb") as f:
        plistlib.dump({"Count": 3}, f, fmt=plistlib.FMT_BINARY)
    with open(b, "wb") as f:
        plistlib.dump({"Count": 4}, f, fmt=plistlib.FMT_BINARY)
    result = utils.diff_paths(str(a), str(b))
    assert result.identical is False
    assert result.detail != ""


def test_binary_files_differ_without_a_text_diff(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    _write(a, b"\x00\x01\x02\xff", mode="wb")
    _write(b, b"\x00\x09\x02\xff", mode="wb")
    result = utils.diff_paths(str(a), str(b))
    assert result.identical is False
    assert "binary" in result.detail.lower()


def test_directories_compared_by_content(tmp_path):
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    (d1 / "sub").mkdir(parents=True)
    (d2 / "sub").mkdir(parents=True)
    _write(d1 / "keep.txt", "x")
    _write(d2 / "keep.txt", "x")
    _write(d1 / "sub" / "changed.txt", "old")
    _write(d2 / "sub" / "changed.txt", "new")
    _write(d1 / "only_src.txt", "here")
    result = utils.diff_paths(str(d1), str(d2))
    assert result.identical is False
    assert "changed.txt" in result.detail
    assert "only_src.txt" in result.detail


def test_identical_directories_report_identical(tmp_path):
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    _write(d1 / "f.txt", "same")
    _write(d2 / "f.txt", "same")
    result = utils.diff_paths(str(d1), str(d2))
    assert result.identical is True


def test_symlink_is_not_content_comparable(tmp_path):
    real = tmp_path / "real.txt"
    link = tmp_path / "link.txt"
    _write(real, "hi")
    os.symlink(str(real), str(link))
    result = utils.diff_paths(str(link), str(real))
    assert result.identical is False
    assert result.detail == ""


def test_backup_skips_when_already_in_sync(tmp_path, monkeypatch):
    """An identical existing backup is left untouched (not deleted+recopied)."""
    home = tmp_path / "home"
    mackup_dir = tmp_path / "mackup"
    home.mkdir()
    mackup_dir.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _write(home / ".myrc", "config\n")
    _write(mackup_dir / ".myrc", "config\n")
    mackup_before = (mackup_dir / ".myrc").stat().st_ino

    mck = Mock(spec=Mackup)
    mck.mackup_folder = str(mackup_dir)
    profile = ApplicationProfile(mck, {".myrc"}, dry_run=False, verbose=False)
    utils.FORCE_YES = True
    try:
        profile.copy_files_to_mackup_folder()
    finally:
        utils.FORCE_YES = False

    # Same inode => the file was never deleted and recopied.
    assert (mackup_dir / ".myrc").stat().st_ino == mackup_before
    assert (mackup_dir / ".myrc").read_text() == "config\n"
