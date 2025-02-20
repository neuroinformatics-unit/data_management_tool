from __future__ import annotations

import copy
import glob
import json
import os
import shutil
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
)

if TYPE_CHECKING:
    from datashuttle.utils.custom_types import (
        DisplayMode,
        OverwriteExistingFiles,
        Prefix,
        TopLevelFolder,
    )

import paramiko
import yaml

from datashuttle.configs import (
    canonical_configs,
    canonical_folders,
    load_configs,
)
from datashuttle.configs.config_class import Configs
from datashuttle.utils import (
    ds_logger,
    folders,
    formatting,
    getters,
    rclone,
    ssh,
    utils,
    validation,
)
from datashuttle.utils.custom_exceptions import (
    ConfigError,
    NeuroBlueprintError,
)
from datashuttle.utils.data_transfer import TransferData
from datashuttle.utils.decorators import (  # noqa
    check_configs_set,
    requires_ssh_configs,
)

# -----------------------------------------------------------------------------
# Project Manager Class
# -----------------------------------------------------------------------------


class DataShuttle:
    """
    DataShuttle is a tool for convenient scientific
    project management and data transfer in BIDS format.

    The expected organisation is a central repository
    on a central machine  ('central') that contains all
    project data. This is connected to multiple local
    machines ('local'). These can each contain a subset of
    the full project (e.g. machine for electrophysiology
    collection, machine for behavioural collection).

    On first use on a new profile, show warning prompting
    to set configurations with the function make_config_file().

    Datashuttle will save logs to a .datashuttle folder
    in the main local project. These logs contain
    detailed information on folder creation / transfer.
    To get the path to datashuttle logs, use
    cfgs.make_and_get_logging_path().

    For transferring data between a central data storage
    with SSH, use setup setup_ssh_connection().
    This will allow you to check the server key, add host key to
    profile if accepted, and setup ssh key pair.

    Parameters
    ----------

    project_name : The project name to use the datashuttle
                   Folders containing all project files
                   and folders are specified in make_config_file().
                   Datashuttle-related files are stored in
                   a .datashuttle folder in the user home
                   folder. Use get_datashuttle_path() to
                   see the path to this folder.

    print_startup_message : If `True`, a start-up message displaying the
                            current state of the program (e.g. persistent
                            settings such as the 'top-level folder') is shown.
    """

    def __init__(self, project_name: str, print_startup_message: bool = True):

        self._error_on_base_project_name(project_name)
        self.project_name = project_name
        (
            self._datashuttle_path,
            self._temp_log_path,
        ) = canonical_folders.get_project_datashuttle_path(self.project_name)

        folders.create_folders([self._datashuttle_path, self._temp_log_path])

        self._config_path = self._datashuttle_path / "config.yaml"

        self._persistent_settings_path = (
            self._datashuttle_path / "persistent_settings.yaml"
        )
        self.cfg: Any = None

        self.cfg = load_configs.attempt_load_configs(
            self.project_name, self._config_path, verbose=print_startup_message
        )

        if self.cfg:
            self._set_attributes_after_config_load()
        else:
            rclone.prompt_rclone_download_if_does_not_exist()

    def _set_attributes_after_config_load(self) -> None:
        """
        Once config file is loaded, update all private attributes
        according to config contents.
        """
        self.cfg.init_paths()

        self._make_project_metadata_if_does_not_exist()

    # -------------------------------------------------------------------------
    # Public Folder Makers
    # -------------------------------------------------------------------------

    @check_configs_set
    def create_folders(
        self,
        top_level_folder: TopLevelFolder,
        sub_names: Union[str, List[str]],
        ses_names: Optional[Union[str, List[str]]] = None,
        datatype: Union[str, List[str]] = "",
        bypass_validation: bool = False,
        log: bool = True,
    ) -> Dict[str, List[Path]]:
        """
        Create a subject / session folder tree in the project
        folder. The passed subject / session names are
        formatted and validated. If this succeeds, fully
        validation against all subject / session folders in
        the local project is performed before making the
        folders.

        Parameters
        ----------

        top_level_folder : TopLevelFolder
                Whether to make the folders in `rawdata` or
                `derivatives`.

        sub_names : Union[str, List[str]]
                subject name / list of subject names to make
                within the top-level project folder
                (if not already, these will be prefixed with
                "sub-")

        ses_names : Optional[Union[str, List[str]]]
                (Optional). session name / list of session names.
                (if not already, these will be prefixed with
                "ses-"). If no session is provided, no session-level
                folders are made.

        datatype : Union[str, List[str]]
                The datatype to make in the sub / ses folders.
                (e.g. "ephys", "behav", "anat"). If "all"
                is selected, all datatypes permitted in
                NeuroBlueprint will be created. If "" is passed
                no datatype will be created.

        bypass_validation : bool
            If `True`, folders will be created even if they are not
            valid to NeuroBlueprint style.

        log : bool
            If `True`, details of folder creation will be logged.

        Returns
        -------
        created_paths :
            A dictionary of the full filepaths made during folder creation,
            where the keys are the type of folder made and the values are a
            list of created folder paths (Path objects). If datatype were
            created, the dict keys will separate created folders by datatype
            name. Similarly, if only subject or session level folders were
            created, these are separated by "sub" and "ses" keys.

        Notes
        -----

        sub_names or ses_names may contain formatting tags

            @TO@ :
                used to make a range of subjects / sessions.
                Boundaries of the range must be either side of the tag
                e.g. sub-001@TO@003 will generate
                 ["sub-001", "sub-002", "sub-003"]

            @DATE@, @TIME@ @DATETIME@ :
                will add date-<value>, time-<value> or
                date-<value>_time-<value> keys respectively. Only one per-name
                is permitted.
                e.g. sub-001_@DATE@ will generate sub-001_date-20220101
                (on the 1st january, 2022).

        Examples
        --------
        project.create_folders("rawdata", "sub-001", datatype="all")

        project.create_folders("rawdata",
                             "sub-002@TO@005",
                             ["ses-001", "ses-002"],
                             ["ephys", "behav"])
        """
        if log:
            self._start_log("create-folders", local_vars=locals())

        self._check_top_level_folder(top_level_folder)

        if ses_names is None and datatype != "":
            datatype = ""
            utils.log_and_message(
                "`datatype` passed without `ses_names`, no datatype "
                "folders will be created."
            )

        utils.log("\nFormatting Names...")
        ds_logger.log_names(["sub_names", "ses_names"], [sub_names, ses_names])

        name_templates = self.get_name_templates()

        format_sub, format_ses = self._format_and_validate_names(
            top_level_folder,
            sub_names,
            ses_names,
            name_templates,
            bypass_validation,
            log=True,
        )

        ds_logger.log_names(
            ["formatted_sub_names", "formatted_ses_names"],
            [format_sub, format_ses],
        )

        utils.log("\nMaking folders...")
        created_paths = folders.create_folder_trees(
            self.cfg,
            top_level_folder,
            format_sub,
            format_ses,
            datatype,
            log=True,
        )

        utils.print_message_to_user("Finished making folders.")

        if log:
            utils.print_message_to_user(
                f"For log of all created folders, "
                f"please see {self.cfg.logging_path}"
            )
            ds_logger.close_log_filehandler()

        return created_paths

    def _format_and_validate_names(
        self,
        top_level_folder: TopLevelFolder,
        sub_names: Union[str, List[str]],
        ses_names: Optional[Union[str, List[str]]],
        name_templates: Dict,
        bypass_validation: bool,
        log: bool = True,
    ) -> Tuple[List[str], List[str]]:
        """
        A central method for the formatting and validation of subject / session
        names for folder creation. This is called by both DataShuttle and
        during TUI validation.
        """
        format_sub = formatting.check_and_format_names(
            sub_names, "sub", name_templates, bypass_validation
        )

        if ses_names is not None:
            format_ses = formatting.check_and_format_names(
                ses_names, "ses", name_templates, bypass_validation
            )
        else:
            format_ses = []

        if not bypass_validation:
            validation.validate_names_against_project(
                self.cfg,
                top_level_folder,
                format_sub,
                format_ses,
                local_only=True,
                display_mode="error",
                log=log,
                name_templates=name_templates,
            )

        return format_sub, format_ses

    # -------------------------------------------------------------------------
    # Public File Transfer
    # -------------------------------------------------------------------------

    @check_configs_set
    def upload_custom(
        self,
        top_level_folder: TopLevelFolder,
        sub_names: Union[str, list],
        ses_names: Union[str, list],
        datatype: Union[List[str], str] = "all",
        overwrite_existing_files: OverwriteExistingFiles = "never",
        dry_run: bool = False,
        init_log: bool = True,
    ) -> None:
        """
        Upload data from a local project to the central project
        folder. In the case that a file / folder exists on
        the central and local, the central will not be overwritten
        even if the central file is an older version. Data
        transfer logs are saved to the logging folder).

        Parameters
        ----------

        top_level_folder :
            The top-level folder (e.g. `rawdata`) to transfer files
            and folders within.

        sub_names :
            a subject name / list of subject names. These must
            be prefixed with "sub-", or the prefix will be
            automatically added. "@*@" can be used as a wildcard.
            "all" will search for all sub-folders in the
            datatype folder to upload.

        ses_names :
            a session name / list of session names, similar to
            sub_names but requiring a "ses-" prefix.

        datatype :
            see create_folders()

        overwrite_existing_files :
            If `False`, files on central will never be overwritten
            by files transferred from local. If `True`, central files
            will be overwritten if there is any difference (date, size)
            between central and local files.

        dry_run :
            perform a dry-run of transfer. This will output as if file
            transfer was taking place, but no files will be moved. Useful
            to check which files will be moved on data transfer.

        init_log :
            (Optional). Whether to handle logging. This should
            always be True, unless logger is handled elsewhere
            (e.g. in a calling function).
        """
        if init_log:
            self._start_log("upload-custom", local_vars=locals())

        self._check_top_level_folder(top_level_folder)

        TransferData(
            self.cfg,
            "upload",
            top_level_folder,
            sub_names,
            ses_names,
            datatype,
            overwrite_existing_files,
            dry_run,
            log=True,
        )

        if init_log:
            ds_logger.close_log_filehandler()

    @check_configs_set
    def download_custom(
        self,
        top_level_folder: TopLevelFolder,
        sub_names: Union[str, list],
        ses_names: Union[str, list],
        datatype: Union[List[str], str] = "all",
        overwrite_existing_files: OverwriteExistingFiles = "never",
        dry_run: bool = False,
        init_log: bool = True,
    ) -> None:
        """
        Download data from the central project folder to the
        local project folder.

        Parameters
        ----------

        top_level_folder :
            The top-level folder (e.g. `rawdata`) to transfer files
            and folders within.

        sub_names :
            a subject name / list of subject names. These must
            be prefixed with "sub-", or the prefix will be
            automatically added. "@*@" can be used as a wildcard.
            "all" will search for all sub-folders in the
            datatype folder to upload.

        ses_names :
            a session name / list of session names, similar to
            sub_names but requiring a "ses-" prefix.

        datatype :
            see create_folders()

        overwrite_existing_files :
            If "never" files on target will never be overwritten by source.
            If "always" files on target will be overwritten by source if
            there is any difference in date or size.
            If "if_source_newer" files on target will only be overwritten
            by files on source with newer creation / modification datetime.

        dry_run :
            perform a dry-run of transfer. This will output as if file
            transfer was taking place, but no files will be moved. Useful
            to check which files will be moved on data transfer.

        init_log :
            (Optional). Whether to handle logging. This should
            always be True, unless logger is handled elsewhere
            (e.g. in a calling function).
        """
        if init_log:
            self._start_log("download-custom", local_vars=locals())

        self._check_top_level_folder(top_level_folder)

        TransferData(
            self.cfg,
            "download",
            top_level_folder,
            sub_names,
            ses_names,
            datatype,
            overwrite_existing_files,
            dry_run,
            log=True,
        )

        if init_log:
            ds_logger.close_log_filehandler()

    # Specific top-level folder
    # ----------------------------------------------------------------------------------
    # A set of convenience functions are provided to abstract
    # away the 'top_level_folder' concept.

    @check_configs_set
    def upload_rawdata(
        self,
        overwrite_existing_files: OverwriteExistingFiles = "never",
        dry_run: bool = False,
    ):
        """
        Upload files in the `rawdata` top level folder.

        Parameters
        ----------

        overwrite_existing_files :
            If "never" files on target will never be overwritten by source.
            If "always" files on target will be overwritten by source if
            there is any difference in date or size.
            If "if_source_newer" files on target will only be overwritten
            by files on source with newer creation / modification datetime.

        dry_run :
            perform a dry-run of transfer. This will output as if file
            transfer was taking place, but no files will be moved. Useful
            to check which files will be moved on data transfer.
        """
        self._transfer_top_level_folder(
            "upload",
            "rawdata",
            overwrite_existing_files=overwrite_existing_files,
            dry_run=dry_run,
        )

    @check_configs_set
    def upload_derivatives(
        self,
        overwrite_existing_files: OverwriteExistingFiles = "never",
        dry_run: bool = False,
    ):
        """
        Upload files in the `derivatives` top level folder.

        Parameters
        ----------

        overwrite_existing_files :
            If "never" files on target will never be overwritten by source.
            If "always" files on target will be overwritten by source if
            there is any difference in date or size.
            If "if_source_newer" files on target will only be overwritten
            by files on source with newer creation / modification datetime.

        dry_run :
            perform a dry-run of transfer. This will output as if file
            transfer was taking place, but no files will be moved. Useful
            to check which files will be moved on data transfer.
        """
        self._transfer_top_level_folder(
            "upload",
            "derivatives",
            overwrite_existing_files=overwrite_existing_files,
            dry_run=dry_run,
        )

    @check_configs_set
    def download_rawdata(
        self,
        overwrite_existing_files: OverwriteExistingFiles = "never",
        dry_run: bool = False,
    ):
        """
        Download files in the `rawdata` top level folder.

        Parameters
        ----------

        overwrite_existing_files :
            If "never" files on target will never be overwritten by source.
            If "always" files on target will be overwritten by source if
            there is any difference in date or size.
            If "if_source_newer" files on target will only be overwritten
            by files on source with newer creation / modification datetime.

        dry_run :
            perform a dry-run of transfer. This will output as if file
            transfer was taking place, but no files will be moved. Useful
            to check which files will be moved on data transfer.
        """
        self._transfer_top_level_folder(
            "download",
            "rawdata",
            overwrite_existing_files=overwrite_existing_files,
            dry_run=dry_run,
        )

    @check_configs_set
    def download_derivatives(
        self,
        overwrite_existing_files: OverwriteExistingFiles = "never",
        dry_run: bool = False,
    ):
        """
        Download files in the `derivatives` top level folder.

        Parameters
        ----------

        overwrite_existing_files :
            If "never" files on target will never be overwritten by source.
            If "always" files on target will be overwritten by source if
            there is any difference in date or size.
            If "if_source_newer" files on target will only be overwritten
            by files on source with newer creation / modification datetime.

        dry_run :
            perform a dry-run of transfer. This will output as if file
            transfer was taking place, but no files will be moved. Useful
            to check which files will be moved on data transfer.
        """
        self._transfer_top_level_folder(
            "download",
            "derivatives",
            overwrite_existing_files=overwrite_existing_files,
            dry_run=dry_run,
        )

    @check_configs_set
    def upload_entire_project(
        self,
        overwrite_existing_files: OverwriteExistingFiles = "never",
        dry_run: bool = False,
    ) -> None:
        """
        Upload the entire project (from 'local' to 'central'),
        i.e. including every top level folder (e.g. 'rawdata',
        'derivatives', 'code', 'analysis').

        Parameters
        ----------

        overwrite_existing_files :
            If "never" files on target will never be overwritten by source.
            If "always" files on target will be overwritten by source if
            there is any difference in date or size.
            If "if_source_newer" files on target will only be overwritten
            by files on source with newer creation / modification datetime.

        dry_run :
            perform a dry-run of transfer. This will output as if file
            transfer was taking place, but no files will be moved. Useful
            to check which files will be moved on data transfer.
        """
        self._start_log("upload-entire-project", local_vars=locals())
        self._transfer_entire_project(
            "upload", overwrite_existing_files, dry_run
        )
        ds_logger.close_log_filehandler()

    @check_configs_set
    def download_entire_project(
        self,
        overwrite_existing_files: OverwriteExistingFiles = "never",
        dry_run: bool = False,
    ) -> None:
        """
        Download the entire project (from 'central' to 'local'),
        i.e. including every top level folder (e.g. 'rawdata',
        'derivatives', 'code', 'analysis').

        Parameters
        ----------

        overwrite_existing_files :
            If "never" files on target will never be overwritten by source.
            If "always" files on target will be overwritten by source if
            there is any difference in date or size.
            If "if_source_newer" files on target will only be overwritten
            by files on source with newer creation / modification datetime.

        dry_run :
            perform a dry-run of transfer. This will output as if file
            transfer was taking place, but no files will be moved. Useful
            to check which files will be moved on data transfer.
        """
        self._start_log("download-entire-project", local_vars=locals())
        self._transfer_entire_project(
            "download", overwrite_existing_files, dry_run
        )
        ds_logger.close_log_filehandler()

    @check_configs_set
    def upload_specific_folder_or_file(
        self,
        filepath: Union[str, Path],
        overwrite_existing_files: OverwriteExistingFiles = "never",
        dry_run: bool = False,
    ) -> None:
        """
        Upload a specific file or folder. If transferring
        a single file, the path including the filename is
        required (see 'filepath' input). If a folder,
        wildcards "*" or "**" must be used to transfer
        all files in the folder ("*") or all files
        and sub-folders ("**").

        Parameters
        ----------

        filepath :
            a string containing the full filepath.

        overwrite_existing_files :
            If "never" files on target will never be overwritten by source.
            If "always" files on target will be overwritten by source if
            there is any difference in date or size.
            If "if_source_newer" files on target will only be overwritten
            by files on source with newer creation / modification datetime.

        dry_run :
            perform a dry-run of transfer. This will output as if file
            transfer was taking place, but no files will be moved. Useful
            to check which files will be moved on data transfer.
        """
        self._start_log("upload-specific-folder-or-file", local_vars=locals())

        self._transfer_specific_file_or_folder(
            "upload", filepath, overwrite_existing_files, dry_run
        )

        ds_logger.close_log_filehandler()

    @check_configs_set
    def download_specific_folder_or_file(
        self,
        filepath: Union[str, Path],
        overwrite_existing_files: OverwriteExistingFiles = "never",
        dry_run: bool = False,
    ) -> None:
        """
        Download a specific file or folder. If transferring
        a single file, the path including the filename is
        required (see 'filepath' input). If a folder,
        wildcards "*" or "**" must be used to transfer
        all files in the folder ("*") or all files
        and sub-folders ("**").

        Parameters
        ----------

        filepath :
            a string containing the full filepath.

        overwrite_existing_files :
            If "never" files on target will never be overwritten by source.
            If "always" files on target will be overwritten by source if
            there is any difference in date or size.
            If "if_source_newer" files on target will only be overwritten
            by files on source with newer creation / modification datetime.

        dry_run :
            perform a dry-run of transfer. This will output as if file
            transfer was taking place, but no files will be moved. Useful
            to check which files will be moved on data transfer.
        """
        self._start_log(
            "download-specific-folder-or-file", local_vars=locals()
        )

        self._transfer_specific_file_or_folder(
            "download", filepath, overwrite_existing_files, dry_run
        )

        ds_logger.close_log_filehandler()

    def _transfer_top_level_folder(
        self,
        upload_or_download: Literal["upload", "download"],
        top_level_folder: TopLevelFolder,
        overwrite_existing_files: OverwriteExistingFiles = "never",
        dry_run: bool = False,
        init_log: bool = True,
    ):
        """
        Core function to upload / download files within a
        particular top-level-folder. e.g. `upload_rawdata().`
        """
        if init_log:
            self._start_log(
                f"{upload_or_download}-{top_level_folder}", local_vars=locals()
            )

        transfer_func = (
            self.upload_custom
            if upload_or_download == "upload"
            else self.download_custom
        )

        transfer_func(
            top_level_folder,
            "all",
            "all",
            "all",
            overwrite_existing_files=overwrite_existing_files,
            dry_run=dry_run,
            init_log=False,
        )

        if init_log:
            ds_logger.close_log_filehandler()

    def _transfer_specific_file_or_folder(
        self, upload_or_download, filepath, overwrite_existing_files, dry_run
    ):
        """
        Core function for upload/download_specific_folder_or_file().
        """
        if isinstance(filepath, str):
            filepath = Path(filepath)

        if upload_or_download == "upload":
            base_path = self.cfg["local_path"]
        else:
            base_path = self.cfg["central_path"]

        if not utils.path_starts_with_base_folder(base_path, filepath):
            utils.log_and_raise_error(
                "Transfer failed. "
                "Must pass the full filepath to file or folder to transfer.",
                ValueError,
            )

        processed_filepath = filepath.relative_to(base_path)

        top_level_folder = processed_filepath.parts[0]
        processed_filepath = Path(*processed_filepath.parts[1:])

        include_list = [f"--include /{processed_filepath.as_posix()}"]
        output = rclone.transfer_data(
            self.cfg,
            upload_or_download,
            top_level_folder,
            include_list,
            self.cfg.make_rclone_transfer_options(
                overwrite_existing_files, dry_run
            ),
        )

        utils.log(output.stderr.decode("utf-8"))

    # -------------------------------------------------------------------------
    # SSH
    # -------------------------------------------------------------------------

    @requires_ssh_configs
    def setup_ssh_connection(self) -> None:
        """
        Setup a connection to the central server using SSH.
        Assumes the central_host_id and central_host_username
        are set in configs (see make_config_file() and update_config_file())

        First, the server key will be displayed, requiring
        verification of the server ID. This will store the
        hostkey for all future use.

        Next, prompt to input their password for the central
        cluster. Once input, SSH private / public key pair
        will be setup.
        """
        self._start_log(
            "setup-ssh-connection-to-central-server", local_vars=locals()
        )

        verified = ssh.verify_ssh_central_host(
            self.cfg["central_host_id"],
            self.cfg.hostkeys_path,
            log=True,
        )

        if verified:
            ssh.setup_ssh_key(self.cfg, log=True)
            self._setup_rclone_central_ssh_config(log=True)

        ds_logger.close_log_filehandler()

    @requires_ssh_configs
    def write_public_key(self, filepath: str) -> None:
        """
        By default, the SSH private key only is stored, in
        the datashuttle configs folder. Use this function
        to save the public key.

        Parameters
        ----------

        filepath :
            full filepath (inc filename) to write the
            public key to.
        """
        key: paramiko.RSAKey
        key = paramiko.RSAKey.from_private_key_file(
            self.cfg.ssh_key_path.as_posix()
        )

        with open(filepath, "w") as public:
            public.write(key.get_base64())
        public.close()

    # -------------------------------------------------------------------------
    # Configs
    # -------------------------------------------------------------------------

    def make_config_file(
        self,
        local_path: str,
        central_path: str,
        connection_method: str,
        central_host_id: Optional[str] = None,
        central_host_username: Optional[str] = None,
    ) -> None:
        """
        Initialise the configurations for datashuttle to use on the
        local machine. Once initialised, these settings will be
        used each time the datashuttle is opened. This method
        can also be used to completely overwrite existing configs.

        These settings are stored in a config file on the
        datashuttle path (not in the project folder)
        on the local machine. Use get_config_path() to
        get the full path to the saved config file.

        Use update_config_file() to selectively update settings.

        Parameters
        ----------

        local_path :
            path to project folder on local machine

        central_path :
            Filepath to central project.
            If this is local (i.e. connection_method = "local_filesystem"),
            this is the full path on the local filesystem
            Otherwise, if this is via ssh (i.e. connection method = "ssh"),
            this is the path to the project folder on central machine.
            This should be a full path to central folder i.e. this cannot
            include ~ home folder syntax, must contain the full path
            (e.g. /nfs/nhome/live/jziminski)

        connection_method :
            The method used to connect to the central project filesystem,
            e.g. "local_filesystem" (e.g. mounted drive) or "ssh"

        central_host_id :
            server address for central host for ssh connection
            e.g. "ssh.swc.ucl.ac.uk"

        central_host_username :
            username for which to log in to central host.
            e.g. "jziminski"
        """
        self._start_log(
            "make-config-file",
            local_vars=locals(),
            store_in_temp_folder=True,
        )

        if self._config_path.is_file():
            utils.log_and_raise_error(
                "A config file already exists for this project. "
                "Use `update_config_file` to update settings.",
                RuntimeError,
            )

        cfg = Configs(
            self.project_name,
            self._config_path,
            {
                "local_path": local_path,
                "central_path": central_path,
                "connection_method": connection_method,
                "central_host_id": central_host_id,
                "central_host_username": central_host_username,
            },
        )

        cfg.setup_after_load()  # will raise error if fails
        self.cfg = cfg

        self.cfg.dump_to_file()

        self._set_attributes_after_config_load()

        # This is just a placeholder rclone config that will suffice
        # if ever central is a 'local filesystem'.
        self._setup_rclone_central_local_filesystem_config()

        utils.log_and_message(
            "Configuration file has been saved and "
            "options loaded into datashuttle."
        )
        self._log_successful_config_change()
        self._move_logs_from_temp_folder()

        ds_logger.close_log_filehandler()

    def update_config_file(self, **kwargs) -> None:
        """ """
        if not self.cfg:
            utils.log_and_raise_error(
                "Must have a config loaded before updating configs.",
                ConfigError,
            )

        self._start_log(
            "update-config-file",
            local_vars=locals(),
        )

        for option, value in kwargs.items():
            if option in self.cfg.keys_str_on_file_but_path_in_class:
                kwargs[option] = Path(value)

        new_cfg = copy.deepcopy(self.cfg)
        new_cfg.update(**kwargs)
        new_cfg.setup_after_load()  # Will raise on error

        self.cfg = new_cfg
        self._set_attributes_after_config_load()
        self.cfg.dump_to_file()
        self._log_successful_config_change(message=True)
        ds_logger.close_log_filehandler()

    # -------------------------------------------------------------------------
    # Getters
    # -------------------------------------------------------------------------

    @check_configs_set
    def get_local_path(self) -> Path:
        """
        Get the projects local path.
        """
        return self.cfg["local_path"]

    @check_configs_set
    def get_central_path(self) -> Path:
        """
        Get the project central path.
        """
        return self.cfg["central_path"]

    def get_datashuttle_path(self) -> Path:
        """
        Get the path to the local datashuttle
        folder where configs and other
        datashuttle files are stored.
        """
        return self._datashuttle_path

    @check_configs_set
    def get_config_path(self) -> Path:
        """
        Get the full path to the DataShuttle config file.
        """
        return self._config_path

    @check_configs_set
    def get_configs(self) -> Configs:
        return self.cfg

    @check_configs_set
    def get_logging_path(self) -> Path:
        """
        Get the path where datashuttle logs are written.
        """
        return self.cfg.logging_path

    @staticmethod
    def get_existing_projects() -> List[Path]:
        """
        Get a list of existing project names found on the local machine.
        This is based on project folders in the "home / .datashuttle" folder
        that contain valid config.yaml files.
        """
        return getters.get_existing_project_paths()

    @check_configs_set
    def get_next_sub(
        self,
        top_level_folder: TopLevelFolder,
        return_with_prefix: bool = True,
        local_only: bool = False,
    ) -> str:
        """
        Convenience function for get_next_sub_or_ses
        to find the next subject number.

        Parameters
        ----------

        return_with_prefix : bool
            If `True`, return with the "sub-" prefix.

        local_only : bool
            If `True, only get names from `local_path`, otherwise from
            `local_path` and `central_path`.
        """
        name_template = self.get_name_templates()
        name_template_regexp = (
            name_template["sub"] if name_template["on"] else None
        )

        return getters.get_next_sub_or_ses(
            self.cfg,
            top_level_folder,
            sub=None,
            local_only=local_only,
            return_with_prefix=return_with_prefix,
            search_str="sub-*",
            name_template_regexp=name_template_regexp,
        )

    @check_configs_set
    def get_next_ses(
        self,
        top_level_folder: TopLevelFolder,
        sub: str,
        return_with_prefix: bool = True,
        local_only: bool = False,
    ) -> str:
        """
        Convenience function for get_next_sub_or_ses
        to find the next session number.

        Parameters
        ----------

        top_level_folder:
            "rawdata" or "derivatives"

        sub: Optional[str]
            Name of the subject to find the next session of.

        return_with_prefix : bool
            If `True`, return with the "ses-" prefix.

        local_only : bool
            If `True, only get names from `local_path`, otherwise from
            `local_path` and `central_path`.
        """
        name_template = self.get_name_templates()
        name_template_regexp = (
            name_template["ses"] if name_template["on"] else None
        )

        return getters.get_next_sub_or_ses(
            self.cfg,
            top_level_folder,
            sub=sub,
            local_only=local_only,
            return_with_prefix=return_with_prefix,
            search_str="ses-*",
            name_template_regexp=name_template_regexp,
        )

    # Name Templates
    # -------------------------------------------------------------------------

    def get_name_templates(self) -> Dict:
        """
        Get the regexp templates used for validation. If
        the "on" key is set to `False`, template validation is not performed.

        Returns
        -------

        name_templates : Dict
            e.g. {"name_templates": {"on": False, "sub": None, "ses": None}}
        """
        settings = self._load_persistent_settings()
        return settings["name_templates"]

    def set_name_templates(self, new_name_templates: Dict) -> None:
        """
        Update the persistent settings with new name templates.

        Name templates are regexp for that, when name_templates["on"] is
        set to `True`, "sub" and "ses" names are validated against
        the regexp contained in the dict.

        Parameters
        ----------
        new_name_templates : Dict
            e.g. {"name_templates": {"on": False, "sub": None, "ses": None}}
            where "sub" or "ses" can be a regexp that subject and session
            names respectively are validated against.
        """
        self._update_persistent_setting("name_templates", new_name_templates)

    # -------------------------------------------------------------------------
    # Showers
    # -------------------------------------------------------------------------

    @check_configs_set
    def show_configs(self) -> None:
        """
        Print the current configs to the terminal.
        """
        utils.print_message_to_user(self._get_json_dumps_config())

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------

    @check_configs_set
    def validate_project(
        self,
        top_level_folder: TopLevelFolder,
        display_mode: DisplayMode,
        local_only: bool = False,
    ) -> None:
        """
        Perform validation on the project. This checks the subject
        and session level folders to ensure there are not
        NeuroBlueprint formatting issues.

        Parameters
        ----------

        display_mode : DisplayMode
            The validation issues are displayed as ``"error"`` (raise error)
            ``"warn"`` (show warning) or ``"print"``.

        local_only : bool
            If ``True``, only the local project is validated. Otherwise, both
            local and central projects are validated.
        """
        self._start_log(
            "validate-project",
            local_vars=locals(),
        )

        name_templates = self.get_name_templates()

        validation.validate_project(
            self.cfg,
            top_level_folder,
            local_only=local_only,
            display_mode=display_mode,
            name_templates=name_templates,
        )

        ds_logger.close_log_filehandler()

    @staticmethod
    def check_name_formatting(names: Union[str, list], prefix: Prefix) -> None:
        """
        Pass list of names to check how these will be auto-formatted,
        for example as when passed to create_folders() or upload_custom()
        or download()

        Useful for checking tags e.g. @TO@, @DATE@, @DATETIME@, @DATE@.
        This method will print the formatted list of names,

        Parameters
        ----------

        names :
            A string or list of subject or session names.
        prefix:
            The relevant subject or session prefix,
            e.g. "sub-" or "ses-"
        """
        if prefix not in ["sub", "ses"]:
            utils.log_and_raise_error(
                "'prefix' must be 'sub' or 'ses'.",
                NeuroBlueprintError,
            )

        if isinstance(names, str):
            names = [names]

        formatted_names = formatting.check_and_format_names(names, prefix)
        utils.print_message_to_user(formatted_names)

    # -------------------------------------------------------------------------
    # Private Functions
    # -------------------------------------------------------------------------

    def _transfer_entire_project(
        self,
        upload_or_download: Literal["upload", "download"],
        overwrite_existing_files: OverwriteExistingFiles,
        dry_run: bool,
    ) -> None:
        """
        Transfer (i.e. upload or download) the entire project (i.e.
        every 'top level folder' (e.g. 'rawdata', 'derivatives').

        Parameters
        ----------

        upload_or_download : direction to transfer the data, either "upload" (from
                    local to central) or "download" (from central to local).
        """
        for top_level_folder in canonical_folders.get_top_level_folders():

            utils.log_and_message(f"Transferring `{top_level_folder}`")

            self._transfer_top_level_folder(
                upload_or_download,
                top_level_folder,
                overwrite_existing_files=overwrite_existing_files,
                dry_run=dry_run,
                init_log=False,
            )

    def _start_log(
        self,
        command_name: str,
        local_vars: Optional[dict] = None,
        store_in_temp_folder: bool = False,
        verbose: bool = True,
    ) -> None:
        """
        Initialize the logger. This is typically called at
        the start of public methods to initialize logging
        for a specific function call.

        Parameters
        ----------

        command_name : name of the command, for the log output files.

        local_vars : local_vars are passed to fancylog variables argument.
                 see ds_logger.wrap_variables_for_fancylog for more info

        store_in_temp_folder :
            if `False`, existing logging path will be used
            (local project .datashuttle).
        """
        if local_vars is None:
            variables = None
        else:
            variables = ds_logger.wrap_variables_for_fancylog(
                local_vars, self.cfg
            )

        if store_in_temp_folder:
            path_to_save = self._temp_log_path
            self._clear_temp_log_path()
        else:
            path_to_save = self.cfg.logging_path

        ds_logger.start(path_to_save, command_name, variables, verbose)

    def _move_logs_from_temp_folder(self) -> None:
        """
        Logs are stored within the project folder. Although
        in some instances, when setting configs, we do not know what
        the project folder is. In this case, make the logs
        in a temp folder in the .datashuttle config folder,
        and move them to the project folder once set.
        """
        if not self.cfg or not self.cfg["local_path"].is_dir():
            utils.log_and_raise_error(
                "Project folder does not exist. Logs were not moved.",
                FileNotFoundError,
            )

        ds_logger.close_log_filehandler()

        log_files = glob.glob(str(self._temp_log_path / "*.log"))
        for file_path in log_files:
            file_name = os.path.basename(file_path)

            shutil.move(
                self._temp_log_path / file_name,
                self.cfg.logging_path / file_name,
            )

    def _clear_temp_log_path(self) -> None:
        """"""
        log_files = glob.glob(str(self._temp_log_path / "*.log"))
        for file in log_files:
            os.remove(file)

    def _error_on_base_project_name(self, project_name):
        if validation.name_has_special_character(project_name):
            utils.log_and_raise_error(
                "The project name must contain alphanumeric characters only.",
                ValueError,
            )

    def _log_successful_config_change(self, message: bool = False) -> None:
        """
        Log the entire config at the time of config change.
        If messaged, just message "update successful" rather than
        print the entire configs as it becomes confusing.
        """
        if message:
            utils.print_message_to_user("Update successful.")
        utils.log(
            f"Update successful. New config file: "
            f"\n {self._get_json_dumps_config()}"
        )

    def _get_json_dumps_config(self) -> str:
        """
        Get the config dictionary formatted as json.dumps()
        which allows well formatted printing.
        """
        copy_dict = copy.deepcopy(self.cfg.data)
        self.cfg.convert_str_and_pathlib_paths(copy_dict, "path_to_str")
        return json.dumps(copy_dict, indent=4)

    def _make_project_metadata_if_does_not_exist(self) -> None:
        """
        Within the project local_path is also a .datashuttle
        folder that contains additional information, e.g. logs.
        """
        folders.create_folders(self.cfg.project_metadata_path, log=False)

    def _setup_rclone_central_ssh_config(self, log: bool) -> None:
        rclone.setup_rclone_config_for_ssh(
            self.cfg,
            self.cfg.get_rclone_config_name("ssh"),
            self.cfg.ssh_key_path,
            log=log,
        )

    def _setup_rclone_central_local_filesystem_config(self) -> None:
        rclone.setup_rclone_config_for_local_filesystem(
            self.cfg.get_rclone_config_name("local_filesystem"),
        )

    # Persistent settings
    # -------------------------------------------------------------------------

    def _update_persistent_setting(
        self, setting_name: str, setting_value: Any
    ) -> None:
        """
        Load settings that are stored persistently across datashuttle
        sessions. These are stored in yaml dumped to dictionary.

        Parameters
        ----------
        setting_name : dictionary key of the persistent setting to change
        setting_value : value to change the persistent setting to
        """
        settings = self._load_persistent_settings()

        if setting_name not in settings:
            utils.log_and_raise_error(
                f"Setting key {setting_name} not found in "
                f"settings dictionary",
                KeyError,
            )

        settings[setting_name] = setting_value

        self._save_persistent_settings(settings)

    def _init_persistent_settings(self) -> None:
        """
        Initialise the default persistent settings
        and save to file.
        """
        settings = canonical_configs.get_persistent_settings_defaults()
        self._save_persistent_settings(settings)

    def _save_persistent_settings(self, settings: Dict) -> None:
        """
        Save the settings dict to file as .yaml
        """
        with open(self._persistent_settings_path, "w") as settings_file:
            yaml.dump(settings, settings_file, sort_keys=False)

    def _load_persistent_settings(self) -> Dict:
        """
        Load settings that are stored persistently across
        datashuttle sessions.
        """
        if not self._persistent_settings_path.is_file():
            self._init_persistent_settings()

        with open(self._persistent_settings_path, "r") as settings_file:
            settings = yaml.full_load(settings_file)

        self._update_settings_with_new_canonical_keys(settings)

        return settings

    def _update_settings_with_new_canonical_keys(self, settings: Dict):
        """
        Perform a check on the keys within persistent settings.
        If they do not exist, persistent settings is from older version
        and the new keys need adding.
        If changing keys within the top level (e.g. a dict entry in
        "tui") this method will need to be extended.

        Added keys:
            v0.4.0: tui "overwrite_existing_files" and "dry_run"
        """
        if "name_templates" not in settings:
            settings.update(canonical_configs.get_name_templates_defaults())

        canonical_tui_configs = canonical_configs.get_tui_config_defaults()

        if "tui" not in settings:
            settings.update(canonical_tui_configs)

        for key in ["overwrite_existing_files", "dry_run"]:
            if key not in settings["tui"]:
                settings["tui"][key] = canonical_tui_configs["tui"][key]

    def _check_top_level_folder(self, top_level_folder):
        """
        Raise an error if ``top_level_folder`` not correct.
        """
        canonical_top_level_folders = canonical_folders.get_top_level_folders()

        if top_level_folder not in canonical_top_level_folders:
            utils.log_and_raise_error(
                f"`top_level_folder` must be one of "
                f"{canonical_top_level_folders}",
                ValueError,
            )
