import logging
import re
import traceback
from pathlib import Path
from typing import List, Tuple, Union

from rich import print as rich_print

from . import directories

# --------------------------------------------------------------------------------------------------------------------
# General Utils
# --------------------------------------------------------------------------------------------------------------------


def log(message: str) -> None:
    logger = logging.getLogger("fancylog_")
    logger.info(message)


def log_and_message(message: str, use_rich: bool = False) -> None:
    log(message)
    message_user(message, use_rich)


def log_and_raise_error(message: str) -> None:
    logging.error(f"\n\n{' '.join(traceback.format_stack(limit=5))}")
    logging.error(message)
    raise_error(message)


def message_user(message: Union[str, list], use_rich=False) -> None:
    """
    Centralised way to send message.
    """
    if use_rich:
        rich_print(message)
    else:
        print(message)


def get_user_input(message: str) -> str:
    """
    Centralised way to get user input
    """
    input_ = input(message)
    return input_


def raise_error(message: str) -> None:
    """
    Temporary centralized way to raise and error
    """
    raise BaseException(message)


def get_appdir_path(project_name: str) -> Tuple[Path, Path]:
    """
    It is not possible to write to program files in windows
    from app without admin permissions. However, if admin
    permission given drag and drop don't work, and it is
    not good practice. Use appdirs module to get the
    AppData cross-platform and save / load all files form here .
    """
    base_path = Path.home() / ".datashuttle" / project_name
    temp_logs_path = base_path / "temp_logs"

    directories.make_dirs(base_path)
    directories.make_dirs(temp_logs_path)

    return base_path, temp_logs_path


def get_path_after_base_dir(base_dir: Path, path_: Path) -> Path:
    """"""
    if path_already_stars_with_base_dir(base_dir, path_):
        return path_.relative_to(base_dir)
    return path_


def path_already_stars_with_base_dir(base_dir: Path, path_: Path) -> bool:
    return path_.as_posix().startswith(base_dir.as_posix())


def log_and_raise_error_not_exists_or_not_yaml(path_to_config: Path) -> None:
    """"""
    if not path_to_config.exists():
        log_and_raise_error(f"No file found at: {path_to_config}")

    if path_to_config.suffix not in [".yaml", ".yml"]:
        log_and_raise_error("The config file must be a YAML file")


def get_first_sub_ses_keys(all_names: List[str]) -> List[str]:
    """
    Assumes sub / ses name is in standard form with sub/ses label
    in the second position e.g. sub-001_id-...

    Only look for folders / file with sub/ses in first key
    to ignore all other files
    """
    return [
        re.split("-|_", name)[1]
        for name in all_names
        if re.split("-|_", name)[0] in ["sub", "ses"]
    ]
