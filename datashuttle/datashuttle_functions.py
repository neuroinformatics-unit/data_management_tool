from __future__ import annotations

from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from datashuttle.utils.custom_types import DisplayMode, TopLevelFolder
from pathlib import Path
from typing import (
    Optional,
)

from datashuttle.configs import (
    canonical_configs,
)
from datashuttle.configs.config_class import Configs
from datashuttle.utils import (
    validation,
)


def quick_validate_project(
    project_path: str | Path,
    top_level_folder: Optional[TopLevelFolder] = None,
    display_mode: DisplayMode = "warn",
    name_templates: Optional[Dict] = None,
):
    """
    Perform validation on the project. This checks the subject
    and session level folders to ensure there are not
    NeuroBlueprint formatting issues.

    Parameters
    ----------

    project_path
        Path to the project to validate. Must include the project
        name, and hold a "rawdata" or "derivatives" folder.

    top_level_folder : TopLevelFolder
        The top-level folder ("rawdata" or "derivatives" to
        perform validation. If `None`, both are checked.

    display_mode : DisplayMode
        The validation issues are displayed as ``"error"`` (raise error)
        ``"warn"`` (show warning) or ``"print"``.

    name_templates : Dict
        A dictionary of templates for subject and session name
        to validate against. See ``DataShuttle.set_name_templates()``
        for details.
    """
    project_path = Path(project_path)

    # Check that the project file exists and contains
    # at least one top-level folder
    if not project_path.is_dir():
        raise FileNotFoundError(
            f"Cannot perform validation. No file or folder found at `project_path`: {project_path}"
        )
    if (
        not (project_path / "rawdata").is_dir()
        or not (project_path / "derivatives").is_dir()
    ):
        raise FileNotFoundError(
            "`project_path` must contain a 'rawdata' or 'derivatives' folder."
        )

    # Format the top-level folders into a list
    rawdata_and_derivatives = ["rawdata", "derivatives"]

    if top_level_folder is None:
        top_level_folders_to_validate = rawdata_and_derivatives
    else:
        if top_level_folder not in rawdata_and_derivatives:
            raise ValueError(
                f"`top_level_folder must be one of: {rawdata_and_derivatives}"
            )
        top_level_folders_to_validate = [top_level_folder]

    # Create some mock configs for the validation call,
    # then for each top-level folder, run the validation
    placeholder_configs = {
        key: None for key in canonical_configs.get_canonical_configs().keys()
    }
    placeholder_configs["local_path"] = Path(project_path)  # type: ignore

    cfg = Configs(
        project_name=project_path.name,
        file_path=None,  # type: ignore
        input_dict=placeholder_configs,
    )

    for folder in top_level_folders_to_validate:
        validation.validate_project(
            cfg=cfg,
            top_level_folder=folder,  # type: ignore
            local_only=True,
            display_mode=display_mode,
            name_templates=name_templates,
        )
