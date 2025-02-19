from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    import paramiko

    from datashuttle.configs.config_class import Configs
    from datashuttle.tui.app import App
    from datashuttle.utils.custom_types import InterfaceOutput, TopLevelFolder

from datashuttle import DataShuttle
from datashuttle.configs import load_configs
from datashuttle.utils import ssh


class Interface:
    """
    An interface class between the TUI and datashuttle API. Takes input
    to all datashuttle functions as passed from the TUI, outputs
    success status (True or False) and optional data, in the case
    of False.

    `self.project` is initialised when project is loaded.

    Interface functions typically return an `InterfaceOutput` type
    is contains a boolean in the first entry and output in the second
    entry. The first entry is True if the API call ran successfully
    and False if it threw an error. The output will contain any
    relevant data if successful, otherwise it will contain an error message.
    """

    def __init__(self) -> None:

        self.project: App
        self.name_templates: Dict = {}
        self.tui_settings: Dict = {}

    def select_existing_project(self, project_name: str) -> InterfaceOutput:
        """
        Load an existing project into `self.project`.

        Parameters
        ----------

        project_name : str
            The name of the datashuttle project to load.
            Must already exist.
        """
        try:
            project = DataShuttle(project_name, print_startup_message=False)
            self.project = project
            return True, None

        except BaseException as e:
            return False, str(e)

    def setup_new_project(
        self, project_name: str, cfg_kwargs: Dict
    ) -> InterfaceOutput:
        """
        Set up a new project and load into `self.project`.

        Parameters
        ----------

        project_name : str
            Name of the project to set up.

        cfg_kwargs : Dict
            The configurations to set the new project to.
        """
        try:
            project = DataShuttle(project_name, print_startup_message=False)

            project.make_config_file(**cfg_kwargs)

            self.project = project

            return True, None

        except BaseException as e:
            return False, str(e)

    def set_configs_on_existing_project(
        self, cfg_kwargs: Dict
    ) -> InterfaceOutput:
        """
        Update the settings on an existing project. Only the settings
        passed in `cfg_kwargs` are updated.

        Parameters
        ----------

        cfg_kwargs : Dict
            The configs and new values to update.
        """
        try:
            self.project.update_config_file(**cfg_kwargs)
            return True, None

        except BaseException as e:
            return False, str(e)

    def create_folders(
        self,
        sub_names: List[str],
        ses_names: Optional[List[str]],
        datatype: List[str],
    ) -> InterfaceOutput:
        """
        Create folders through datashuttle.

        Parameters
        ----------

        sub_names : List[str]
            A list of un-formatted / unvalidated subject names to create.

        ses_names : List[str]
            A list of un-formatted / unvalidated session names to create.

        datatype : List[str]
            A list of canonical datatype names to create.
        """
        top_level_folder = self.tui_settings["top_level_folder_select"][
            "create_tab"
        ]
        bypass_validation = self.tui_settings["bypass_validation"]

        try:
            self.project.create_folders(
                top_level_folder,
                sub_names=sub_names,
                ses_names=ses_names,
                datatype=datatype,
                bypass_validation=bypass_validation,
            )
            return True, None

        except BaseException as e:
            return False, str(e)

    def validate_names(
        self, sub_names: List[str], ses_names: Optional[List[str]]
    ) -> InterfaceOutput:
        """
        Validate a list of subject / session names. This is used
        to populate the Input tooltips with validation errors.
        Uses a central `_format_and_validate_names()` that is also
        called during folder creation itself, to ensure these a
        results always match.

        Parameters
        ----------

        sub_names : List[str]
            List of subject names to format.

        ses_names : List[str]
            List of session names to format.
        """
        top_level_folder = self.tui_settings["top_level_folder_select"][
            "create_tab"
        ]

        try:
            format_sub, format_ses = self.project._format_and_validate_names(
                top_level_folder,
                sub_names,
                ses_names,
                self.get_name_templates(),
                bypass_validation=False,
            )

            return True, {
                "format_sub": format_sub,
                "format_ses": format_ses,
            }

        except BaseException as e:
            return False, str(e)

    # Transfer
    # ----------------------------------------------------------------------------------

    def transfer_entire_project(self, upload: bool) -> InterfaceOutput:
        """
        Transfer the entire project (all canonical top-level folders).

        Parameters
        ----------

        upload : bool
            Upload from local to central if `True`, otherwise download
            from central to remote.
        """
        try:
            if upload:
                transfer_func = self.project.upload_entire_project
            else:
                transfer_func = self.project.download_entire_project

            transfer_func(
                overwrite_existing_files=self.tui_settings[
                    "overwrite_existing_files"
                ],
                dry_run=self.tui_settings["dry_run"],
            )

            return True, None

        except BaseException as e:
            return False, str(e)

    def transfer_top_level_only(
        self, selected_top_level_folder: str, upload: bool
    ) -> InterfaceOutput:
        """
        Transfer all files within a selected top level folder.

        Parameters
        ----------

        selected_top_level_folder : str
            The top level folder selected in the TUI for this transfer window.

        upload : bool
            Upload from local to central if `True`, otherwise download
            from central to remote.

        """
        assert selected_top_level_folder in ["rawdata", "derivatives"]

        try:
            if selected_top_level_folder == "rawdata":
                transfer_func = (
                    self.project.upload_rawdata
                    if upload
                    else self.project.download_rawdata
                )
            elif selected_top_level_folder == "derivatives":
                transfer_func = (
                    self.project.upload_derivatives
                    if upload
                    else self.project.download_derivatives
                )

            transfer_func(
                overwrite_existing_files=self.tui_settings[
                    "overwrite_existing_files"
                ],
                dry_run=self.tui_settings["dry_run"],
            )

            return True, None

        except BaseException as e:
            return False, str(e)

    def transfer_custom_selection(
        self,
        selected_top_level_folder: TopLevelFolder,
        sub_names: List[str],
        ses_names: List[str],
        datatype: List[str],
        upload: bool,
    ) -> InterfaceOutput:
        """
        Transfer a custom selection of subjects / sessions / datatypes.

        Parameters
        ----------

        selected_top_level_folder : str
            The top level folder selected in the TUI for this transfer window.

        sub_names : List[str]
            Subject names or subject-level canonical transfer keys to transfer.

        ses_names : List[str]
            Session names or session-level canonical transfer keys to transfer.

        datatype : List[str]
            Datatypes or datatype-level canonical transfer keys to transfer.

        upload : bool
            Upload from local to central if `True`, otherwise download
            from central to remote.
        """
        try:
            if upload:
                transfer_func = self.project.upload_custom
            else:
                transfer_func = self.project.download_custom

            transfer_func(
                selected_top_level_folder,
                sub_names=sub_names,
                ses_names=ses_names,
                datatype=datatype,
                overwrite_existing_files=self.tui_settings[
                    "overwrite_existing_files"
                ],
                dry_run=self.tui_settings["dry_run"],
            )

            return True, None

        except BaseException as e:
            return False, str(e)

    # Setup SSH
    # ----------------------------------------------------------------------------------

    def get_name_templates(self) -> Dict:
        """
        Get the `name_templates` defining templates to validate
        against. These are stored in a variable to avoid constantly
        reading these values from disk where they are stored in
        `persistent_settings`. It is critical this variable
        and the file contetns are in sync, so when changed
        on the TUI side they are updated also, in `get_tui_settings`.
        """
        if not self.name_templates:
            self.name_templates = self.project.get_name_templates()

        return self.name_templates

    def set_name_templates(self, name_templates: Dict) -> InterfaceOutput:
        """
        Set the `name_templates` here and on disk. See `get_name_templates`
        for more information.
        """
        try:
            self.project.set_name_templates(name_templates)
            self.name_templates = name_templates
            return True, None

        except BaseException as e:
            return False, str(e)

    def get_tui_settings(self) -> Dict:
        """
        Get the "tui" field of `persistent_settings`. Similar to
        `get_name_templates`, there are held on the class to avoid
        constantly reading from disk.
        """
        if not self.tui_settings:
            self.tui_settings = self.project._load_persistent_settings()["tui"]

        return self.tui_settings

    def save_tui_settings(
        self, value: Any, key: str, key_2: Optional[str] = None
    ) -> None:
        """
        Update the "tui" field of the `persistent_settings` on disk.

        Parameters
        ----------

        value : Any
            Value to set the `persistent_settings` tui field to

        key_1 : str
            First key of the tui `persistent_settings` to update
            e.g. "top_level_folder_select"

        key_2 : str
            Optionals second level of the dictionary to update.
            e.g. "create_tab"
        """
        if key_2 is None:
            self.tui_settings[key] = value
        else:
            self.tui_settings[key][key_2] = value

        self.project._update_persistent_setting("tui", self.tui_settings)

    # Setup SSH
    # ----------------------------------------------------------------------------------

    def get_central_host_id(self) -> str:
        return self.project.cfg["central_host_id"]

    def get_configs(self) -> Configs:
        return self.project.cfg

    def get_textual_compatible_project_configs(self) -> Configs:
        """
        Datashuttle configs keeps paths saved as pathlib.Path
        objects. In some cases textual requires str representation.
        This method returns datashuttle configs with all paths that
        are Path converted to str.
        """
        cfg_to_load = copy.deepcopy(self.project.cfg)
        load_configs.convert_str_and_pathlib_paths(cfg_to_load, "path_to_str")
        return cfg_to_load

    def get_next_sub(
        self, top_level_folder: TopLevelFolder
    ) -> InterfaceOutput:
        try:
            next_sub = self.project.get_next_sub(
                top_level_folder, return_with_prefix=True, local_only=True
            )
            return True, next_sub
        except BaseException as e:
            return False, str(e)

    def get_next_ses(
        self, top_level_folder: TopLevelFolder, sub: str
    ) -> InterfaceOutput:

        try:
            next_ses = self.project.get_next_ses(
                top_level_folder, sub, return_with_prefix=True, local_only=True
            )
            return True, next_ses
        except BaseException as e:
            return False, str(e)

    def get_ssh_hostkey(self) -> InterfaceOutput:
        try:
            key = ssh.get_remote_server_key(
                self.project.cfg["central_host_id"]
            )
            return True, key
        except BaseException as e:
            return False, str(e)

    def save_hostkey_locally(self, key: paramiko.RSAKey) -> InterfaceOutput:
        try:
            ssh.save_hostkey_locally(
                key,
                self.project.cfg["central_host_id"],
                self.project.cfg.hostkeys_path,
            )
            return True, None

        except BaseException as e:
            return False, str(e)

    def setup_key_pair_and_rclone_config(
        self, password: str
    ) -> InterfaceOutput:
        try:
            ssh.add_public_key_to_central_authorized_keys(
                self.project.cfg, password, log=False
            )
            self.project._setup_rclone_central_ssh_config(log=False)

            return True, None

        except BaseException as e:
            return False, str(e)
