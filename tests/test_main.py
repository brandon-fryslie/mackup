import os
import shutil
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import Mock, patch

from mackup import main
from mackup.appsdb import ApplicationsDatabase
from mackup.mackup import Mackup


class TestMain(unittest.TestCase):
    def test_main_header(self):
        assert main.header("blah") == "\033[34mblah\033[0m"

    def test_main_bold(self):
        assert main.bold("blah") == "\033[1mblah\033[0m"


class TestBackupCopyFailureExit(unittest.TestCase):
    """A copy failure during backup must exit non-zero and name the file.

    Regression for the bug where a file that failed to copy was reported but
    the run still exited 0, making a partial backup indistinguishable from a
    complete one.
    """

    def setUp(self):
        self.mackup_folder = tempfile.mkdtemp()
        self.temp_home = tempfile.mkdtemp()
        self.original_home = os.environ.get("HOME")
        os.environ["HOME"] = self.temp_home

        # One app with two config files, both present in the home folder.
        self.good_path = os.path.join(self.temp_home, ".good")
        self.bad_path = os.path.join(self.temp_home, ".bad")
        for path in (self.good_path, self.bad_path):
            with open(path, "w") as f:
                f.write("content")

        mckp = Mock(spec=Mackup)
        mckp.mackup_folder = self.mackup_folder
        mckp.get_apps_to_backup.return_value = {"testapp"}
        mckp.check_for_usable_backup_env = Mock()

        app_db = Mock(spec=ApplicationsDatabase)
        app_db.get_files.return_value = {".good", ".bad"}

        self.ctx = main._Context(
            config_file=None,
            mckp=mckp,
            app_db=app_db,
            dry_run=False,
            verbose=False,
        )

    def tearDown(self):
        if self.original_home:
            os.environ["HOME"] = self.original_home
        else:
            del os.environ["HOME"]
        shutil.rmtree(self.temp_home, ignore_errors=True)
        shutil.rmtree(self.mackup_folder, ignore_errors=True)

    def test_backup_with_failing_file_exits_nonzero_and_names_it(self):
        args = {"<application>": None}

        def fake_copy(src, dst):
            # Only the .bad file fails to copy; the .good one succeeds.
            if src == self.bad_path:
                raise OSError("boom")

        exit_code = None
        captured_err = StringIO()
        sys.stderr = captured_err
        try:
            with patch(
                "mackup.application.utils.copy", side_effect=fake_copy,
            ) as mock_copy:
                try:
                    main._cmd_backup(args, self.ctx)
                except SystemExit as exc:
                    exit_code = exc.code
        finally:
            sys.stderr = sys.__stderr__

        # Exits non-zero so a pipeline sees the partial backup as a failure.
        assert exit_code not in (0, None)

        # Both files were attempted -- one bad file did not abort the run.
        attempted = {call.args[0] for call in mock_copy.call_args_list}
        assert attempted == {self.good_path, self.bad_path}

        # The failing file is named on stderr; the good one is not flagged.
        err = captured_err.getvalue()
        assert self.bad_path in err
        assert self.good_path not in err

    def test_backup_with_all_files_ok_does_not_exit(self):
        args = {"<application>": None}

        with patch("mackup.application.utils.copy"):
            # A clean run returns normally -- no SystemExit, exit code stays 0.
            main._cmd_backup(args, self.ctx)
