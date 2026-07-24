import os
import shutil
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import Mock, patch

from mackup.application import ApplicationProfile
from mackup.mackup import Mackup


class TestApplicationProfile(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock Mackup instance
        self.mock_mackup = Mock(spec=Mackup)
        self.mock_mackup.mackup_folder = tempfile.mkdtemp()

        # Create a temporary home directory
        self.temp_home = tempfile.mkdtemp()

        # Save original HOME and set it to temp directory
        self.original_home = os.environ.get("HOME")
        os.environ["HOME"] = self.temp_home

        # Define test files
        self.test_files = {".testfile", ".testfolder"}

        # Create the ApplicationProfile instance
        self.app_profile = ApplicationProfile(
            mackup=self.mock_mackup,
            files=self.test_files,
            dry_run=False,
            verbose=False,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        # Restore original HOME
        if self.original_home:
            os.environ["HOME"] = self.original_home
        else:
            del os.environ["HOME"]

        # Clean up temporary directories
        if os.path.exists(self.temp_home):
            shutil.rmtree(self.temp_home)
        if os.path.exists(self.mock_mackup.mackup_folder):
            shutil.rmtree(self.mock_mackup.mackup_folder)

    def test_copy_files_to_mackup_folder_permission_error(self):
        """Test PermissionError handling in copy_files_to_mackup_folder."""
        # Create a test file in the home directory
        test_file = ".testfile"
        home_filepath = os.path.join(self.temp_home, test_file)

        # Create the actual file
        with open(home_filepath, "w") as f:
            f.write("test content")

        # Patch utils.copy to raise PermissionError
        with patch("mackup.application.utils.copy") as mock_copy:
            mock_copy.side_effect = PermissionError("Permission denied")

            # The failure must be reported on stderr, not stdout, so a pipeline
            # can detect it.
            captured_err = StringIO()
            sys.stderr = captured_err
            try:
                failed = self.app_profile.copy_files_to_mackup_folder()
            finally:
                sys.stderr = sys.__stderr__

            # Verify that copy was called
            mock_copy.assert_called_once()

            # The error names the file on stderr...
            err = captured_err.getvalue()
            assert "Error: Unable to copy" in err
            assert home_filepath in err
            # ...and the path is returned so the caller can exit non-zero.
            assert failed == [home_filepath]

    def test_files_are_sorted_for_deterministic_processing(self):
        """Application files should always be processed in sorted order."""
        unsorted_files = {"z-last", "a-first", "m-middle"}
        app_profile = ApplicationProfile(
            mackup=self.mock_mackup,
            files=unsorted_files,
            dry_run=False,
            verbose=False,
        )
        assert app_profile.files == ["a-first", "m-middle", "z-last"]

    def test_copy_files_to_mackup_folder_permission_error_verbose(self):
        """Test PermissionError handling in copy_files_to_mackup_folder verbose."""
        # Create a verbose ApplicationProfile
        app_profile_verbose = ApplicationProfile(
            mackup=self.mock_mackup,
            files=self.test_files,
            dry_run=False,
            verbose=True,
        )

        # Create a test file in the home directory
        test_file = ".testfile"
        home_filepath = os.path.join(self.temp_home, test_file)

        # Create the actual file
        with open(home_filepath, "w") as f:
            f.write("test content")

        # Patch utils.copy to raise PermissionError
        with patch("mackup.application.utils.copy") as mock_copy:
            mock_copy.side_effect = PermissionError("Permission denied")

            # Progress goes to stdout; the error goes to stderr.
            captured_output = StringIO()
            captured_err = StringIO()
            sys.stdout = captured_output
            sys.stderr = captured_err
            try:
                failed = app_profile_verbose.copy_files_to_mackup_folder()
            finally:
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__

            # Verify that copy was called
            mock_copy.assert_called_once()

            # The verbose progress line is on stdout; the error is on stderr.
            assert "Backing up" in captured_output.getvalue()
            assert "Error: Unable to copy" in captured_err.getvalue()
            assert failed == [home_filepath]

    def test_copy_files_from_mackup_folder_permission_error(self):
        """Test PermissionError handling in copy_files_from_mackup_folder."""
        # Create a test file in the mackup directory
        test_file = ".testfile"
        mackup_filepath = os.path.join(self.mock_mackup.mackup_folder, test_file)

        # Create the actual file
        with open(mackup_filepath, "w") as f:
            f.write("test content")

        # Patch utils.copy to raise PermissionError
        with patch("mackup.application.utils.copy") as mock_copy:
            mock_copy.side_effect = PermissionError("Permission denied")

            # The failure must be reported on stderr, not stdout.
            captured_err = StringIO()
            sys.stderr = captured_err
            try:
                failed = self.app_profile.copy_files_from_mackup_folder()
            finally:
                sys.stderr = sys.__stderr__

            # Verify that copy was called
            mock_copy.assert_called_once()

            # The error names the file on stderr, and the path is returned.
            err = captured_err.getvalue()
            assert "Error: Unable to copy" in err
            assert mackup_filepath in err
            assert failed == [mackup_filepath]

    def test_copy_files_from_mackup_folder_permission_error_verbose(self):
        """Test PermissionError handling in copy_files_from_mackup_folder verbose."""
        # Create a verbose ApplicationProfile
        app_profile_verbose = ApplicationProfile(
            mackup=self.mock_mackup,
            files=self.test_files,
            dry_run=False,
            verbose=True,
        )

        # Create a test file in the mackup directory
        test_file = ".testfile"
        mackup_filepath = os.path.join(self.mock_mackup.mackup_folder, test_file)

        # Create the actual file
        with open(mackup_filepath, "w") as f:
            f.write("test content")

        # Patch utils.copy to raise PermissionError
        with patch("mackup.application.utils.copy") as mock_copy:
            mock_copy.side_effect = PermissionError("Permission denied")

            # Progress goes to stdout; the error goes to stderr.
            captured_output = StringIO()
            captured_err = StringIO()
            sys.stdout = captured_output
            sys.stderr = captured_err
            try:
                failed = app_profile_verbose.copy_files_from_mackup_folder()
            finally:
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__

            # Verify that copy was called
            mock_copy.assert_called_once()

            # The verbose progress line is on stdout; the error is on stderr.
            assert "Recovering" in captured_output.getvalue()
            assert "Error: Unable to copy" in captured_err.getvalue()
            assert failed == [mackup_filepath]

    def test_copy_files_to_mackup_folder_with_directory_permission_error(self):
        """Test PermissionError with a directory in copy_files_to_mackup_folder."""
        # Create a test directory in the home directory
        test_dir = ".testfolder"
        home_dirpath = os.path.join(self.temp_home, test_dir)
        os.makedirs(home_dirpath)

        # Create a file inside the directory
        with open(os.path.join(home_dirpath, "testfile.txt"), "w") as f:
            f.write("test content")

        # Patch utils.copy to raise PermissionError
        with patch("mackup.application.utils.copy") as mock_copy:
            mock_copy.side_effect = PermissionError("Permission denied for directory")

            # The failure must be reported on stderr, not stdout.
            captured_err = StringIO()
            sys.stderr = captured_err
            try:
                failed = self.app_profile.copy_files_to_mackup_folder()
            finally:
                sys.stderr = sys.__stderr__

            # Verify that copy was called
            mock_copy.assert_called_once()

            # The error names the folder on stderr, and the path is returned.
            err = captured_err.getvalue()
            assert "Error: Unable to copy" in err
            assert home_dirpath in err
            assert failed == [home_dirpath]

    def test_copy_files_from_mackup_folder_with_directory_permission_error(self):
        """Test PermissionError with a directory in copy_files_from_mackup_folder."""
        # Create a test directory in the mackup directory
        test_dir = ".testfolder"
        mackup_dirpath = os.path.join(self.mock_mackup.mackup_folder, test_dir)
        os.makedirs(mackup_dirpath)

        # Create a file inside the directory
        with open(os.path.join(mackup_dirpath, "testfile.txt"), "w") as f:
            f.write("test content")

        # Patch utils.copy to raise PermissionError
        with patch("mackup.application.utils.copy") as mock_copy:
            mock_copy.side_effect = PermissionError("Permission denied for directory")

            # The failure must be reported on stderr, not stdout.
            captured_err = StringIO()
            sys.stderr = captured_err
            try:
                failed = self.app_profile.copy_files_from_mackup_folder()
            finally:
                sys.stderr = sys.__stderr__

            # Verify that copy was called
            mock_copy.assert_called_once()

            # The error names the folder on stderr, and the path is returned.
            err = captured_err.getvalue()
            assert "Error: Unable to copy" in err
            assert mackup_dirpath in err
            assert failed == [mackup_dirpath]

    def test_copy_files_to_mackup_folder_non_permission_oserror(self):
        """A non-permission OSError (e.g. disk full) is handled like any other.

        Regression for the split behavior where only PermissionError was caught
        and every other OSError aborted the run with a raw traceback.
        """
        test_file = ".testfile"
        home_filepath = os.path.join(self.temp_home, test_file)
        with open(home_filepath, "w") as f:
            f.write("test content")

        with patch("mackup.application.utils.copy") as mock_copy:
            mock_copy.side_effect = OSError("No space left on device")

            captured_err = StringIO()
            sys.stderr = captured_err
            try:
                # No traceback escapes: the OSError is caught, not propagated.
                failed = self.app_profile.copy_files_to_mackup_folder()
            finally:
                sys.stderr = sys.__stderr__

            assert "Error: Unable to copy" in captured_err.getvalue()
            assert failed == [home_filepath]

    def test_copy_files_to_mackup_folder_one_failure_continues(self):
        """One failing file does not abort the rest; only it is returned."""
        # Both files are processed in sorted order: .testfile, then .testfolder.
        good_file = os.path.join(self.temp_home, ".testfile")
        failing_dir = os.path.join(self.temp_home, ".testfolder")
        with open(good_file, "w") as f:
            f.write("good")
        os.makedirs(failing_dir)

        def fake_copy(src, dst):
            if src == failing_dir:
                raise OSError("boom")

        with patch("mackup.application.utils.copy", side_effect=fake_copy) as mock_copy:
            captured_err = StringIO()
            sys.stderr = captured_err
            try:
                failed = self.app_profile.copy_files_to_mackup_folder()
            finally:
                sys.stderr = sys.__stderr__

        # Both files were attempted even though the first-attempted one failed.
        attempted = {call.args[0] for call in mock_copy.call_args_list}
        assert attempted == {good_file, failing_dir}
        # Only the failing path is reported and returned.
        assert failed == [failing_dir]
        assert failing_dir in captured_err.getvalue()
        assert good_file not in captured_err.getvalue()

    def test_copy_files_to_mackup_folder_success_returns_no_failures(self):
        """A fully successful backup returns an empty failure list."""
        with open(os.path.join(self.temp_home, ".testfile"), "w") as f:
            f.write("good")
        os.makedirs(os.path.join(self.temp_home, ".testfolder"))

        with patch("mackup.application.utils.copy"):
            failed = self.app_profile.copy_files_to_mackup_folder()

        assert failed == []

    def test_copy_files_to_mackup_folder_dry_run_no_permission_error(self):
        """Test dry_run mode doesn't trigger PermissionError in backup."""
        # Create a dry_run ApplicationProfile
        app_profile_dry = ApplicationProfile(
            mackup=self.mock_mackup,
            files=self.test_files,
            dry_run=True,
            verbose=False,
        )

        # Create a test file in the home directory
        test_file = ".testfile"
        home_filepath = os.path.join(self.temp_home, test_file)

        # Create the actual file
        with open(home_filepath, "w") as f:
            f.write("test content")

        # Patch utils.copy - it should NOT be called in dry_run mode
        with patch("mackup.application.utils.copy") as mock_copy:
            # Capture stdout
            captured_output = StringIO()
            sys.stdout = captured_output

            # Call the method
            app_profile_dry.copy_files_to_mackup_folder()

            # Restore stdout
            sys.stdout = sys.__stdout__

            # Verify that copy was NOT called (dry_run mode)
            mock_copy.assert_not_called()

            # Verify that the backing up message was printed
            output = captured_output.getvalue()
            assert "Backing up" in output

    def test_copy_files_from_mackup_folder_dry_run_no_permission_error(self):
        """Test dry_run mode doesn't trigger PermissionError in restore."""
        # Create a dry_run ApplicationProfile
        app_profile_dry = ApplicationProfile(
            mackup=self.mock_mackup,
            files=self.test_files,
            dry_run=True,
            verbose=False,
        )

        # Create a test file in the mackup directory
        test_file = ".testfile"
        mackup_filepath = os.path.join(self.mock_mackup.mackup_folder, test_file)

        # Create the actual file
        with open(mackup_filepath, "w") as f:
            f.write("test content")

        # Patch utils.copy - it should NOT be called in dry_run mode
        with patch("mackup.application.utils.copy") as mock_copy:
            # Capture stdout
            captured_output = StringIO()
            sys.stdout = captured_output

            # Call the method
            app_profile_dry.copy_files_from_mackup_folder()

            # Restore stdout
            sys.stdout = sys.__stdout__

            # Verify that copy was NOT called (dry_run mode)
            mock_copy.assert_not_called()

            # Verify that the recovering message was printed
            output = captured_output.getvalue()
            assert "Recovering" in output

    def test_copy_files_to_mackup_folder_decline_replace_skips_copy(self):
        """Test backup does not overwrite when user declines replacement."""
        test_file = ".testfile"
        home_filepath = os.path.join(self.temp_home, test_file)
        mackup_filepath = os.path.join(self.mock_mackup.mackup_folder, test_file)

        with open(home_filepath, "w") as f:
            f.write("home content")
        with open(mackup_filepath, "w") as f:
            f.write("existing backup")

        with patch("mackup.application.utils.confirm", return_value=False), \
             patch("mackup.application.utils.delete") as mock_delete, \
             patch("mackup.application.utils.copy") as mock_copy:
            self.app_profile.copy_files_to_mackup_folder()

            mock_delete.assert_not_called()
            mock_copy.assert_not_called()

        with open(mackup_filepath) as f:
            assert f.read() == "existing backup"

    def test_copy_files_from_mackup_folder_decline_replace_skips_copy(self):
        """Test restore does not overwrite when user declines replacement."""
        test_file = ".testfile"
        home_filepath = os.path.join(self.temp_home, test_file)
        mackup_filepath = os.path.join(self.mock_mackup.mackup_folder, test_file)

        with open(home_filepath, "w") as f:
            f.write("existing home")
        with open(mackup_filepath, "w") as f:
            f.write("backup content")

        with patch("mackup.application.utils.confirm", return_value=False), \
             patch("mackup.application.utils.delete") as mock_delete, \
             patch("mackup.application.utils.copy") as mock_copy:
            self.app_profile.copy_files_from_mackup_folder()

            mock_delete.assert_not_called()
            mock_copy.assert_not_called()

        with open(home_filepath) as f:
            assert f.read() == "existing home"

    def test_link_uninstall_mackup_not_a_link(self):
        """Test link_uninstall skips when home file is not a symbolic link."""
        # Create a test file in the mackup directory (regular file, not a link)
        test_file = ".testfile"
        mackup_filepath = os.path.join(self.mock_mackup.mackup_folder, test_file)
        home_filepath = os.path.join(self.temp_home, test_file)

        # Create the mackup file as a regular file
        with open(mackup_filepath, "w") as f:
            f.write("mackup content")

        # Create the home file as a regular file (not a link)
        with open(home_filepath, "w") as f:
            f.write("home content")

        # Patch utils.delete and utils.copy
        with patch("mackup.application.utils.delete") as mock_delete, \
             patch("mackup.application.utils.copy") as mock_copy:
            # Capture stdout
            captured_output = StringIO()
            sys.stdout = captured_output

            # Call the method
            self.app_profile.link_uninstall()

            # Restore stdout
            sys.stdout = sys.__stdout__

            # Verify that delete and copy were NOT called
            mock_delete.assert_not_called()
            mock_copy.assert_not_called()

            # Verify that the warning message was printed
            output = captured_output.getvalue()
            assert "Warning: the file in your home" in output
            assert "does not point to the original file" in output
            assert mackup_filepath in output
            assert home_filepath in output
            assert "skipping" in output

    def test_link_uninstall_mackup_points_to_wrong_target(self):
        """Test link_uninstall skips when home link points to wrong target."""
        # Create a test file
        test_file = ".testfile"
        mackup_filepath = os.path.join(self.mock_mackup.mackup_folder, test_file)
        home_filepath = os.path.join(self.temp_home, test_file)

        # Create the mackup file
        with open(mackup_filepath, "w") as f:
            f.write("mackup content")

        # Create a different target file
        wrong_target = os.path.join(self.temp_home, ".wrongtarget")
        with open(wrong_target, "w") as f:
            f.write("wrong target content")

        # Create the home file as a symbolic link pointing to the wrong target
        os.symlink(wrong_target, home_filepath)

        # Patch utils.delete and utils.copy
        with patch("mackup.application.utils.delete") as mock_delete, \
             patch("mackup.application.utils.copy") as mock_copy:
            # Capture stdout
            captured_output = StringIO()
            sys.stdout = captured_output

            # Call the method
            self.app_profile.link_uninstall()

            # Restore stdout
            sys.stdout = sys.__stdout__

            # Verify that delete and copy were NOT called
            mock_delete.assert_not_called()
            mock_copy.assert_not_called()

            # Verify that the warning message was printed
            output = captured_output.getvalue()
            assert "Warning: the file in your home" in output
            assert "does not point to the original file" in output
            assert mackup_filepath in output
            assert home_filepath in output
            assert "skipping" in output

    def test_link_uninstall_mackup_points_correctly(self):
        """Test link_uninstall proceeds when home link points to mackup file."""
        # Create a test file
        test_file = ".testfile"
        mackup_filepath = os.path.join(self.mock_mackup.mackup_folder, test_file)
        home_filepath = os.path.join(self.temp_home, test_file)

        # Create the mackup file first
        with open(mackup_filepath, "w") as f:
            f.write("mackup content")

        # Create the home file as a symbolic link pointing to the mackup file
        os.symlink(mackup_filepath, home_filepath)

        # Patch utils.delete and utils.copy
        with patch("mackup.application.utils.delete") as mock_delete, \
             patch("mackup.application.utils.copy") as mock_copy:
            # Capture stdout
            captured_output = StringIO()
            sys.stdout = captured_output

            # Call the method
            self.app_profile.link_uninstall()

            # Restore stdout
            sys.stdout = sys.__stdout__

            # Verify that delete and copy WERE called (normal operation)
            mock_delete.assert_called_once_with(home_filepath)
            mock_copy.assert_called_once_with(mackup_filepath, home_filepath)

            # Verify that the reverting message was printed (not warning)
            output = captured_output.getvalue()
            assert "Reverting" in output
            assert "Warning" not in output

    def test_copy_files_to_mackup_folder_skips_already_linked_files(self):
        """Test that backup skips files already linked from link install."""
        # Create a test file
        test_file = ".testfile"
        mackup_filepath = os.path.join(self.mock_mackup.mackup_folder, test_file)
        home_filepath = os.path.join(self.temp_home, test_file)

        # Create the mackup file first (simulating link install)
        with open(mackup_filepath, "w") as f:
            f.write("mackup content")

        # Create the home file as a symbolic link pointing to the mackup file
        # (simulating what link install does)
        os.symlink(mackup_filepath, home_filepath)

        # Patch utils.delete and utils.copy
        with patch("mackup.application.utils.delete") as mock_delete, \
             patch("mackup.application.utils.copy") as mock_copy:
            # Capture stdout
            captured_output = StringIO()
            sys.stdout = captured_output

            # Call the method
            self.app_profile.copy_files_to_mackup_folder()

            # Restore stdout
            sys.stdout = sys.__stdout__

            # Verify that delete and copy were NOT called (should skip)
            mock_delete.assert_not_called()
            mock_copy.assert_not_called()

            # Verify that the skipping message was NOT printed (non-verbose)
            output = captured_output.getvalue()
            assert "Backing up" not in output

        # Verify the symlink still exists and points to mackup file
        assert os.path.islink(home_filepath)
        assert os.path.samefile(home_filepath, mackup_filepath)

        # Verify the mackup file still exists with original content
        assert os.path.exists(mackup_filepath)
        with open(mackup_filepath) as f:
            assert f.read() == "mackup content"


    def test_copy_files_to_mackup_folder_skips_already_linked_files_verbose(self):
        """Test backup skips files already linked with verbose mode."""
        # Create a verbose ApplicationProfile
        app_profile_verbose = ApplicationProfile(
            mackup=self.mock_mackup,
            files=self.test_files,
            dry_run=False,
            verbose=True,
        )

        # Create a test file
        test_file = ".testfile"
        mackup_filepath = os.path.join(self.mock_mackup.mackup_folder, test_file)
        home_filepath = os.path.join(self.temp_home, test_file)

        # Create the mackup file first (simulating link install)
        with open(mackup_filepath, "w") as f:
            f.write("mackup content")

        # Create the home file as a symbolic link pointing to the mackup file
        # (simulating what link install does)
        os.symlink(mackup_filepath, home_filepath)

        # Patch utils.delete and utils.copy
        with patch("mackup.application.utils.delete") as mock_delete, \
             patch("mackup.application.utils.copy") as mock_copy:
            # Capture stdout
            captured_output = StringIO()
            sys.stdout = captured_output

            # Call the method
            app_profile_verbose.copy_files_to_mackup_folder()

            # Restore stdout
            sys.stdout = sys.__stdout__

            # Verify that delete and copy were NOT called (should skip)
            mock_delete.assert_not_called()
            mock_copy.assert_not_called()

            # Verify that the skipping message WAS printed (verbose mode)
            output = captured_output.getvalue()
            assert "Skipping" in output
            assert "already linked to" in output
            assert home_filepath in output
            assert mackup_filepath in output

        # Verify the symlink still exists and points to mackup file
        assert os.path.islink(home_filepath)
        assert os.path.samefile(home_filepath, mackup_filepath)

        # Verify the mackup file still exists with original content
        assert os.path.exists(mackup_filepath)
        with open(mackup_filepath) as f:
            assert f.read() == "mackup content"


    def test_copy_files_to_mackup_folder_backs_up_symlink_to_different_location(self):
        """Test that backup still works for symlinks pointing elsewhere (not mackup)."""
        # Create a test file
        test_file = ".testfile"
        mackup_filepath = os.path.join(self.mock_mackup.mackup_folder, test_file)
        home_filepath = os.path.join(self.temp_home, test_file)

        # Create a different target file (not in mackup folder)
        other_target = os.path.join(self.temp_home, ".otherlocation")
        with open(other_target, "w") as f:
            f.write("other content")

        # Create the home file as a symbolic link pointing to different location
        os.symlink(other_target, home_filepath)

        # Patch utils.copy (no mackup file exists, so confirm won't be called)
        with patch("mackup.application.utils.copy") as mock_copy:
            # Capture stdout
            captured_output = StringIO()
            sys.stdout = captured_output

            # Call the method
            self.app_profile.copy_files_to_mackup_folder()

            # Restore stdout
            sys.stdout = sys.__stdout__

            # Verify that copy WAS called (should backup symlinks to other locations)
            mock_copy.assert_called_once_with(home_filepath, mackup_filepath)

            # Verify that the backing up message was printed
            output = captured_output.getvalue()
            assert "Backing up" in output


if __name__ == "__main__":
    unittest.main()
