"""Package used to manage the .mackup.cfg config file."""

import configparser
import os
import os.path
from pathlib import Path

from .constants import (
    CUSTOM_APPS_DIR,
    CUSTOM_APPS_DIR_XDG,
    MACKUP_BACKUP_PATH,
    MACKUP_CONFIG_FILE,
    Engine,
)
from .utils import (
    error,
    get_dropbox_folder_location,
    get_google_drive_folder_location,
    get_icloud_folder_location,
)


class Config:
    """The Mackup Config class."""

    def __init__(self, filename: str | None = None) -> None:
        """
        Create a Config instance.

        Args:
            filename (str): Optional filename of the config file. If empty,
                            defaults to MACKUP_CONFIG_FILE
        """
        assert isinstance(filename, str) or filename is None

        # Initialize the parser
        self._parser = self._setup_parser(filename)

        # Do we have an old config file?
        self._warn_on_old_config()

        # Get the storage engine
        self._engine = self._parse_engine()

        # Get the path where the Mackup folder is
        self._path = self._parse_path()

        # Get the directory replacing 'Mackup', if any
        self._directory = self._parse_directory()

        # Get the list of apps to ignore
        self._apps_to_ignore = self._parse_apps_to_ignore()

        # Get the list of apps to allow
        self._apps_to_sync = self._parse_apps_to_sync()

    @property
    def engine(self) -> str:
        """
        The engine used by the storage.

        One of Engine.DROPBOX, Engine.GOOGLE_DRIVE, Engine.ICLOUD or
        Engine.FILE_SYSTEM.

        Returns:
            str
        """
        return self._engine.value

    @property
    def path(self) -> str:
        """
        Path to the Mackup configuration files.

        The path to the directory where Mackup is gonna create and store his
        directory.

        Returns:
            str
        """
        return str(self._path)

    @property
    def directory(self) -> str:
        """
        The name of the Mackup directory, named Mackup by default.

        Returns:
            str
        """
        return str(self._directory)

    @property
    def fullpath(self) -> str:
        """
        Full path to the Mackup configuration files.

        The full path to the directory when Mackup is storing the configuration
        files.

        Returns:
            str
        """
        return str(os.path.join(self.path, self.directory))

    @property
    def apps_to_ignore(self) -> set[str]:
        """
        Get the list of applications ignored in the config file.

        Returns:
            set. Set of application names to ignore, lowercase
        """
        return set(self._apps_to_ignore)

    @property
    def apps_to_sync(self) -> set[str]:
        """
        Get the list of applications allowed in the config file.

        Returns:
            set. Set of application names to allow, lowercase
        """
        return set(self._apps_to_sync)

    def _setup_parser(
        self, filename: str | None = None,
    ) -> configparser.ConfigParser:
        """
        Configure the ConfigParser instance the way we want it.

        Args:
            filename (str) or None

        Returns:
            ConfigParser
        """
        assert isinstance(filename, str) or filename is None

        parser = configparser.ConfigParser(
            allow_no_value=True, inline_comment_prefixes=(";", "#"),
        )
        parser.read(self._best_config_path(filename))

        return parser

    def _best_config_path(self, filename: str | None = None) -> str:
        """
        If no filename is provided, we try to find one in according to the following
        order, note that we will always check the original default of `~/.mackup.cfg`
        first before checking the other options:

        - ~/.mackup.cfg
        - $MACKUP_CONFIG
        - $XDG_CONFIG_HOME/mackup/mackup.cfg
        - ~/.config/mackup/mackup.cfg

        if none of these files exist, we create ~/.mackup.cfg

        Args:
            filename (str or None, optional): Optional override for the config
                file path. Can be absolute or relative to home directory.
                Defaults to None.

        Returns:
            str: the absolute path to the config file
        """
        assert isinstance(filename, str) or filename is None

        # If we are not overriding the config filename
        config_path: Path
        if not filename:
            default = Path.home() / MACKUP_CONFIG_FILE
            search_paths = [
                # 1. the default config file is ~/.mackup.cfg
                default,
                # 2. check for the MACKUP_CONFIG envvar
                Path(os.environ.get("MACKUP_CONFIG", "")).expanduser(),
                # 3. check for a config file in the XDG_CONFIG_HOME directory
                (
                    Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
                    / "mackup"
                    / MACKUP_CONFIG_FILE.lstrip(".")
                ),
            ]
            config_path = next((p for p in search_paths if p.is_file()), default)
        else:
            # Support both absolute and relative paths
            config_path = Path(filename).expanduser()
            if not config_path.is_absolute():
                config_path = Path.home() / filename

            # When explicitly specified, check that the file exists
            if not config_path.is_file():
                error(
                    f"The config file '{config_path}' does not exist. Aborting.",
                )

        try:
            # Make sure the config file is in the home directory
            config_path.relative_to(Path.home())
        except ValueError:
            error(
                f"The config file '{config_path}' is not in your home "
                "directory. Aborting.",
            )

        # return the absolute path to the config file
        return str(config_path.absolute())

    def _warn_on_old_config(self) -> None:
        """Warn the user if an old config format is detected."""
        # Is an old section in the config file?
        old_sections = ["Allowed Applications", "Ignored Applications"]
        for old_section in old_sections:
            if self._parser.has_section(old_section):
                error(
                    "Old config file detected. Aborting.\n"
                    "\n"
                    "An old section (e.g. [Allowed Applications]"
                    " or [Ignored Applications] has been detected"
                    f" in your {MACKUP_CONFIG_FILE} file.\n"
                    "I'd rather do nothing than do something you"
                    " do not want me to do.\n"
                    "\n"
                    "Please read the up to date documentation on"
                    " <https://github.com/lra/mackup> and migrate"
                    " your configuration file.",
                )

    def _parse_engine(self) -> Engine:
        """
        Parse the storage engine in the config.

        Returns:
            Engine
        """
        if self._parser.has_option("storage", "engine"):
            engine_str = self._parser.get("storage", "engine")
        else:
            engine_str = Engine.DROPBOX.value

        try:
            return Engine(engine_str)
        except ValueError:
            raise ConfigError(f"Unknown storage engine: {engine_str}") from None

    def _parse_path(self) -> str:
        """
        Parse the storage path in the config.

        Returns:
            str
        """
        # [LAW:types-are-the-program] Engine is a closed set of four; the final
        # `else` can only fire if a member is added here without a case below,
        # so it fails loudly instead of leaving `path` silently unbound.
        if self._engine == Engine.DROPBOX:
            path = get_dropbox_folder_location()
        elif self._engine == Engine.GOOGLE_DRIVE:
            path = get_google_drive_folder_location()
        elif self._engine == Engine.ICLOUD:
            path = get_icloud_folder_location()
        elif self._engine == Engine.FILE_SYSTEM:
            if self._parser.has_option("storage", "path"):
                cfg_path = self._parser.get("storage", "path")
                path = os.path.join(os.environ["HOME"], cfg_path)
            else:
                raise ConfigError(
                    "The required 'path' can't be found while"
                    " the 'file_system' engine is used.",
                )
        else:
            raise AssertionError(
                f"Unreachable: unhandled storage engine {self._engine!r}",
            )

        return str(path)

    def _parse_directory(self) -> str:
        """
        Parse the storage directory in the config.

        Returns:
            str
        """
        if self._parser.has_option("storage", "directory"):
            directory = self._parser.get("storage", "directory")
            # Don't allow CUSTOM_APPS_DIR or XDG custom apps dir as a storage directory
            if directory == CUSTOM_APPS_DIR:
                raise ConfigError(
                    f"{CUSTOM_APPS_DIR} cannot be used as a storage directory.",
                )
            xdg_custom_apps_dir = os.path.join(".config", CUSTOM_APPS_DIR_XDG)
            in_xdg_dir = directory in (CUSTOM_APPS_DIR_XDG, xdg_custom_apps_dir)
            if in_xdg_dir or directory.endswith("/" + xdg_custom_apps_dir):
                raise ConfigError(
                    f"{CUSTOM_APPS_DIR_XDG} cannot be used as a storage directory.",
                )
        else:
            directory = MACKUP_BACKUP_PATH

        return str(directory)

    def _parse_apps_to_ignore(self) -> set[str]:
        """
        Parse the applications to ignore in the config.

        Returns:
            set
        """
        # We ignore nothing by default
        apps_to_ignore = set()

        # Is the "[applications_to_ignore]" in the cfg file?
        section_title = "applications_to_ignore"
        if self._parser.has_section(section_title):
            apps_to_ignore = set(self._parser.options(section_title))

        return apps_to_ignore

    def _parse_apps_to_sync(self) -> set[str]:
        """
        Parse the applications to backup in the config.

        Returns:
            set
        """
        # We allow nothing by default
        apps_to_sync = set()

        # Is the "[applications_to_sync]" section in the cfg file?
        section_title = "applications_to_sync"
        if self._parser.has_section(section_title):
            apps_to_sync = set(self._parser.options(section_title))

        return apps_to_sync


class ConfigError(Exception):
    """Exception used for handle errors in the configuration."""
