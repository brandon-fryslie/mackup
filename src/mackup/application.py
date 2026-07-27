"""
Application Profile.

An Application Profile contains all the information about an application in
Mackup. Name, files, ...
"""

import os
from typing import NamedTuple

from . import colors, utils
from .mackup import Mackup


def _describe_path_type(path: str) -> str:
    """Describe an existing path as "file", "folder", or "link" for prompts."""
    if os.path.isfile(path):
        return "file"
    if os.path.isdir(path):
        return "folder"
    if os.path.islink(path):
        return "link"
    raise ValueError(f"Unsupported file: {path}")


class _CopyDirection(NamedTuple):
    """Everything that differs between backing up and recovering, as data.

    [LAW:one-type-per-behavior] backup and restore are one copy operation
    instantiated twice, not two mirrored implementations.
    """

    verb: str  # "Backing up" / "Recovering", for the progress message.
    diff_desc: str  # "home and Mackup" / "Mackup and home", for the drift message.
    dst_location: str  # where the destination lives, for the confirm prompt.
    confirm_force_hint: str  # confirm-prompt suffix; only backup mentions --force.
    home_is_src: bool  # which of (home, mackup) is the source for this direction.
    # Backup only: a home file that is already a symlink to its Mackup copy is
    # counted as backed up via link_install, with nothing left to copy. Restore
    # has no equivalent case, since the Mackup copy is always the real file.
    skip_if_src_linked_to_dst: bool


_BACKUP = _CopyDirection(
    verb="Backing up",
    diff_desc="home and Mackup",
    dst_location="the Mackup folder",
    confirm_force_hint=" (use --force to skip this prompt)",
    home_is_src=True,
    skip_if_src_linked_to_dst=True,
)

_RESTORE = _CopyDirection(
    verb="Recovering",
    diff_desc="Mackup and home",
    dst_location="your home folder",
    confirm_force_hint="",
    home_is_src=False,
    skip_if_src_linked_to_dst=False,
)


class ApplicationProfile:
    """Instantiate this class with application specific data."""

    def __init__(
        self,
        mackup: Mackup,
        files: set[str],
        dry_run: bool,
        verbose: bool,
        run_policy: utils.RunPolicy = utils.DEFAULT_RUN_POLICY,
    ) -> None:
        """
        Create an ApplicationProfile instance.

        Args:
            mackup (Mackup)
            files (list)
        """
        assert isinstance(mackup, Mackup)
        assert isinstance(files, set)

        self.mackup: Mackup = mackup
        self.files: list[str] = sorted(files)
        self.dry_run: bool = dry_run
        self.verbose: bool = verbose
        self.run_policy: utils.RunPolicy = run_policy

    def get_filepaths(self, filename: str) -> tuple[str, str]:
        """
        Get home and mackup filepaths for given file

        Args:
            filename (str)

        Returns:
            home_filepath, mackup_filepath (str, str)
        """
        return (
            os.path.join(os.environ["HOME"], filename),
            os.path.join(self.mackup.mackup_folder, filename),
        )

    def copy_files_to_mackup_folder(self) -> list[str]:
        """
        Backup the application config files to the Mackup folder.

        Returns the home paths that could not be copied. The list is empty on a
        fully successful backup; a non-empty list is the caller's signal that
        the backup is partial and must not report success.
        """
        return self._copy_files(_BACKUP)

    def copy_files_from_mackup_folder(self) -> list[str]:
        """
        Recover the application config files from the Mackup folder.

        Returns the mackup paths that could not be copied back. The list is
        empty on a fully successful restore; a non-empty list is the caller's
        signal that the restore is partial and must not report success.
        """
        return self._copy_files(_RESTORE)

    def _copy_files(self, direction: _CopyDirection) -> list[str]:
        """
        Copy config files one way between home and the Mackup folder.

        Backup and restore are the same algorithm run in opposite directions;
        `direction` supplies everything that differs (wording and the one real
        asymmetry: only backup skips a file already linked to its Mackup copy).

        Algorithm:
            for config_file
                if config_file exists at the source and is a real file/folder
                    if applicable, skip when source is a symlink to destination
                    if exists at the destination
                        are you sure?
                        if sure
                            rm destination
                    cp source destination
        """
        # [LAW:dataflow-not-control-flow] failures flow up as data, not as a
        # traceback or a silent skip; the boundary turns them into a non-zero exit.
        failed_paths: list[str] = []
        for filename in self.files:
            (home_filepath, mackup_filepath) = self.get_filepaths(filename)
            (src_filepath, dst_filepath) = (
                (home_filepath, mackup_filepath)
                if direction.home_is_src
                else (mackup_filepath, home_filepath)
            )

            # If config_file exists at the source and is a real file/folder
            if os.path.isfile(src_filepath) or os.path.isdir(src_filepath):
                # Backup only: source is already a symlink to destination
                # (already backed up via link install)
                if (
                    direction.skip_if_src_linked_to_dst
                    and os.path.islink(src_filepath)
                    and os.path.exists(dst_filepath)
                    and os.path.samefile(src_filepath, dst_filepath)
                ):
                    colors.vlog(
                        f"Skipping {src_filepath}\n"
                        f"  already linked to\n  {dst_filepath}",
                        self.verbose,
                    )
                    continue

                # If a copy already exists at the destination, compare against
                # it. drift is None when there's nothing to compare.
                drift = (
                    utils.diff_paths(src_filepath, dst_filepath)
                    if os.path.lexists(dst_filepath)
                    else None
                )
                if drift is not None and drift.identical:
                    colors.vlog(f"{filename} already in sync, skipping", self.verbose)
                    continue

                if self.verbose:
                    colors.info_log(
                        f"{direction.verb}\n  {src_filepath}\n  to\n"
                        f"  {dst_filepath} ...",
                    )
                else:
                    colors.info_log(f"{direction.verb} {filename} ...")

                if self.dry_run:
                    continue

                # An existing destination differs: show what changed, then confirm.
                if drift is not None:
                    if drift.detail:
                        colors.warning_log(
                            f"{filename} differs between {direction.diff_desc}:",
                        )
                        print(drift.detail)
                    file_type = _describe_path_type(dst_filepath)
                    # Ask the user if he really wants to replace it
                    if utils.confirm(
                        f"A {file_type} named {dst_filepath} already exists in"
                        f" {direction.dst_location}.\nAre you sure that you want to"
                        f" replace it?{direction.confirm_force_hint}",
                        self.run_policy,
                    ):
                        # If confirmed, delete the file at the destination
                        utils.delete(dst_filepath)
                    else:
                        continue

                # Copy the file
                # [LAW:no-silent-failure] one failing file must not abort the run
                # or exit clean: report it loudly on stderr, record it, keep going.
                # [LAW:one-type-per-behavior] every copy failure (permission, disk
                # full, copytree's shutil.Error) is one OSError handled one way.
                try:
                    utils.copy(src_filepath, dst_filepath)
                except OSError as e:
                    colors.error_log(
                        f"Error: Unable to copy {src_filepath} to "
                        f"{dst_filepath}: {e}",
                    )
                    failed_paths.append(src_filepath)

        return failed_paths

    def link_install(self) -> None:
        """
        Create the application config file links.

        Algorithm:
            if exists home/file
              if home/file is a real file
                if exists mackup/file
                  are you sure?
                  if sure
                    rm mackup/file
                    mv home/file mackup/file
                    link mackup/file home/file
                else
                  mv home/file mackup/file
                  link mackup/file home/file
        """
        # For each file used by the application
        for filename in self.files:
            (home_filepath, mackup_filepath) = self.get_filepaths(filename)

            # If the file exists and is not already a link pointing to Mackup
            if (os.path.isfile(home_filepath) or os.path.isdir(home_filepath)) and not (
                os.path.islink(home_filepath)
                and (os.path.isfile(mackup_filepath) or os.path.isdir(mackup_filepath))
                and os.path.samefile(home_filepath, mackup_filepath)
            ):
                if self.verbose:
                    print(
                        f"Backing up\n  {home_filepath}\n  to\n  {mackup_filepath} ...",
                    )
                else:
                    print(f"Linking {filename} ...")

                if self.dry_run:
                    continue

                # Check if we already have a backup
                if os.path.exists(mackup_filepath):
                    file_type = _describe_path_type(mackup_filepath)

                    # Ask the user if he really wants to replace it
                    if utils.confirm(
                        f"A {file_type} named {mackup_filepath} already exists in the"
                        " backup.\nAre you sure that you want to"
                        " replace it?",
                        self.run_policy,
                    ):
                        # Delete the file in Mackup
                        utils.delete(mackup_filepath)
                        # Copy the file
                        utils.copy(home_filepath, mackup_filepath)
                        # Delete the file in the home
                        utils.delete(home_filepath)
                        # Link the backuped file to its original place
                        utils.link(mackup_filepath, home_filepath)
                else:
                    # Copy the file
                    utils.copy(home_filepath, mackup_filepath)
                    # Delete the file in the home
                    utils.delete(home_filepath)
                    # Link the backuped file to its original place
                    utils.link(mackup_filepath, home_filepath)
            elif self.verbose:
                if os.path.exists(home_filepath):
                    print(
                        f"Doing nothing\n  {home_filepath}\n  "
                        f"is already backed up to\n  {mackup_filepath}",
                    )
                elif os.path.islink(home_filepath):
                    print(
                        f"Doing nothing\n  {home_filepath}\n  "
                        "is a broken link, you might want to fix it.",
                    )
                else:
                    print(f"Doing nothing\n  {home_filepath}\n  does not exist")

    def link(self) -> None:
        """
        Link the application config files.

        Algorithm:
            if exists mackup/file
              if exists home/file
                are you sure?
                if sure
                  rm home/file
                  link mackup/file home/file
              else
                link mackup/file home/file
        """
        # For each file used by the application
        for filename in self.files:
            (home_filepath, mackup_filepath) = self.get_filepaths(filename)

            # If the file exists and is not already pointing to the mackup file
            # and the folder makes sense on the current platform (Don't sync
            # any subfolder of ~/Library on GNU/Linux)
            file_or_dir_exists: bool = os.path.isfile(mackup_filepath) or os.path.isdir(
                mackup_filepath,
            )
            pointing_to_mackup: bool = (
                os.path.islink(home_filepath)
                and os.path.exists(mackup_filepath)
                and os.path.samefile(mackup_filepath, home_filepath)
            )
            supported: bool = utils.can_file_be_synced_on_current_platform(filename)

            if file_or_dir_exists and not pointing_to_mackup and supported:
                if self.verbose:
                    print(
                        f"Restoring\n  linking {home_filepath}\n"
                        f"  to      {mackup_filepath} ...",
                    )
                else:
                    print(f"Restoring {filename} ...")

                if self.dry_run:
                    continue

                # Check if there is already a file in the home folder
                if os.path.exists(home_filepath):
                    file_type = _describe_path_type(home_filepath)

                    if utils.confirm(
                        f"You already have a {file_type} at {home_filepath}.\n"
                        "Do you want to replace it with your backup?",
                        self.run_policy,
                    ):
                        utils.delete(home_filepath)
                        utils.link(mackup_filepath, home_filepath)
                else:
                    utils.link(mackup_filepath, home_filepath)
            elif self.verbose:
                if os.path.exists(home_filepath):
                    print(
                        f"Doing nothing\n  {mackup_filepath}\n"
                        f"  already linked by\n  {home_filepath}",
                    )
                elif os.path.islink(home_filepath):
                    print(
                        f"Doing nothing\n  {home_filepath}\n  "
                        "is a broken link, you might want to fix it.",
                    )
                else:
                    print(
                        f"Doing nothing\n  {mackup_filepath}\n  does not exist",
                    )

    def link_uninstall(self) -> None:
        """
        Removes links and copy config files from the remote folder locally.

        Algorithm:
            for each file in config
                if mackup/file exists
                    if home/file exists
                        delete home/file
                    copy mackup/file home/file
        """
        # For each file used by the application
        for filename in self.files:
            (home_filepath, mackup_filepath) = self.get_filepaths(filename)

            # If the mackup file exists
            if os.path.isfile(mackup_filepath) or os.path.isdir(mackup_filepath):
                # Check if there is a corresponding file in the home folder
                if os.path.exists(home_filepath):
                    # If the home file is not a link or does not point to the
                    # mackup file, display a warning and skip it.
                    if not os.path.islink(home_filepath) or not os.path.samefile(
                        home_filepath, mackup_filepath,
                    ):
                        print(
                            f'Warning: the file in your home "{home_filepath}" '
                            f"does not point to the original file in Mackup "
                            f"{mackup_filepath}, skipping...",
                        )
                        continue
                    if self.verbose:
                        print(
                            f"Reverting {mackup_filepath}\n at {home_filepath} ...",
                        )
                    else:
                        print(f"Reverting {filename} ...")

                    if self.dry_run:
                        continue

                    # If there is, delete it as we are gonna copy the Dropbox
                    # one there
                    utils.delete(home_filepath)

                    # Copy the Dropbox file to the home folder
                    utils.copy(mackup_filepath, home_filepath)
            elif self.verbose:
                print(f"Doing nothing, {mackup_filepath} does not exist")
