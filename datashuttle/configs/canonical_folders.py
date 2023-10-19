from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from .config_class import Configs

from pathlib import Path

from datashuttle.utils import folders
from datashuttle.utils.folder_class import Folder


def get_datatype_folders(cfg: Configs) -> dict:
    """
    This function holds the canonical folders
    managed by datashuttle.

    Parameters
    ----------

    cfg : datashuttle configs dict

    Other Parameters
    ----------------

    When adding a new folder, the
    key should be the canonical key used to refer
    to the datatype in datashuttle and SWC-BIDs.

    The value is a Folder() class instance with
    the required fields

    name : The display name for the datatype, that will
        be used for making and transferring files in practice.
        This should always match the canonical name, but left as
        an option for rare cases in which advanced users want to change it.

    used : whether the folder is used or not (see make_config_file)
        if False, the folder will not be made in make_folders
        even if selected.

    level : "sub" or "ses", level to make the folder at.

    Notes
    ------

    In theory, adding a new  folder should only require
    adding an entry to this dictionary. However, this will not
    update configs e.g. use_xxx. This has not been
    directly tested yet, but if it does not work when attempted
    it should be configured to from then on.
    """
    return {
        "ephys": Folder(
            name="ephys",
            used=cfg["use_ephys"],
            level="ses",
        ),
        "behav": Folder(
            name="behav",
            used=cfg["use_behav"],
            level="ses",
        ),
        "funcimg": Folder(
            name="funcimg",
            used=cfg["use_funcimg"],
            level="ses",
        ),
        "histology": Folder(
            name="histology",
            used=cfg["use_histology"],
            level="sub",
        ),
    }


def get_non_sub_names():
    """
    Get all arguments that are not allowed at the
    subject level for data transfer, i.e. as sub_names
    """
    return [
        "all_ses",
        "all_non_ses",
        "all_datatype",
        "all_ses_level_non_datatype",
    ]


def get_non_ses_names():
    """
    Get all arguments that are not allowed at the
    session level for data transfer, i.e. as ses_names
    """
    return [
        "all_sub",
        "all_non_sub",
        "all_datatype",
        "all_ses_level_non_datatype",
    ]


def get_top_level_folders():
    return ["rawdata", "derivatives"]


def get_datashuttle_path():
    """
    Get the datashuttle path where all project
    configs are stored.
    """
    return Path.home() / ".datashuttle"


def get_project_datashuttle_path(project_name: str) -> Tuple[Path, Path]:
    """
    Get the datashuttle path for the project,
    where configuration files are stored.
    Also, return a temporary path in this for logging in
    some cases where local_path location is not clear.

    The datashuttle configuration path is stored in the user home
    folder.
    """
    base_path = get_datashuttle_path() / project_name
    temp_logs_path = base_path / "temp_logs"

    folders.make_folders(base_path)
    folders.make_folders(temp_logs_path)

    return base_path, temp_logs_path
