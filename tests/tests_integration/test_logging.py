import glob
import os
import platform
import re
from pathlib import Path

import pytest
import test_utils

from datashuttle import DataShuttle
from datashuttle.configs.canonical_tags import tags
from datashuttle.utils import ds_logger
from datashuttle.utils.custom_exceptions import (
    ConfigError,
    NeuroBlueprintError,
)

# a symbol that will create an error when trying to make a file with this name.
# this is only tested in windows as nearly any char is allowed for macos and linux
BAD_WINDOWS_FILECHAR = "?"
IS_WINDOWS = platform.system() == "Windows"


class TestLogging:
    @pytest.fixture(scope="function")
    def clean_project_name(self):
        """
        Create an empty project, but ensure no
        configs already exists, and delete created configs
        after test.

        Switch on datashuttle logging as required for
        these tests, then turn back off during tear-down.
        """
        project_name = "test_project"
        test_utils.delete_project_if_it_exists(project_name)
        test_utils.set_datashuttle_loggers(disable=False)

        yield project_name
        test_utils.delete_project_if_it_exists(project_name)
        test_utils.set_datashuttle_loggers(disable=True)

    @pytest.fixture(scope="function")
    def project(self, tmp_path, clean_project_name):
        """
        Setup a project with default configs to use
        for testing. This fixture is distinct
        from the base.py fixture as requires
        additional logging setup / teardown.

        Switch on datashuttle logging as required for
        these tests, then turn back off during tear-down.
        """
        project, cwd = test_utils.setup_project_fixture(
            tmp_path, clean_project_name
        )

        self.delete_log_files(project.cfg.logging_path)

        test_utils.set_datashuttle_loggers(disable=False)

        yield project

        test_utils.teardown_project(cwd, project)
        test_utils.set_datashuttle_loggers(disable=True)

    # ----------------------------------------------------------------------------------------------------------
    # Test Public API Logging
    # ----------------------------------------------------------------------------------------------------------

    def read_log_file(self, logging_path):
        log_filepath = glob.glob(str(logging_path / "*.log"))

        assert len(log_filepath) == 1, (
            f"there should only be one log "
            f"in log output path {logging_path}"
        )
        log_filepath = log_filepath[0]

        with open(log_filepath, "r") as file:
            log = file.read()

        return log

    def delete_log_files(self, logging_path):
        ds_logger.close_log_filehandler()
        logs = glob.glob((str(logging_path / "*.log")))
        for log in logs:
            os.remove(log)

    def test_log_filename(self, project):
        """
        Check the log filename is formatted correctly, for
        `update_config_file`, an arbitrary command
        """
        project.update_config_file(central_host_id="test_id")

        log_search = list(project.cfg.logging_path.glob("*.log"))
        assert (
            len(log_search) == 1
        ), "should only be 1 log in this test environment."
        log_filename = log_search[0].name

        regex = re.compile(r"\d{8}T\d{6}_update-config-file.log")
        assert re.search(regex, log_filename) is not None

    def test_logs_make_config_file(self, clean_project_name, tmp_path):
        """"""
        project = DataShuttle(clean_project_name)

        project.make_config_file(
            tmp_path / clean_project_name,
            clean_project_name,
            "local_filesystem",
        )

        log = self.read_log_file(project.cfg.logging_path)

        assert "Starting logging for command make-config-file" in log
        assert "\nVariablesState:\nlocals: {'local_path':" in log
        assert "Successfully created rclone config." in log
        assert (
            "Configuration file has been saved and options loaded into datashuttle."
            in log
        )
        assert "Update successful. New config file:" in log

    def test_logs_update_config_file(self, project):
        project.update_config_file(central_host_id="test_id")

        log = self.read_log_file(project.cfg.logging_path)

        assert "Starting logging for command update-config-file" in log
        assert (
            "\n\nVariablesState:\nlocals: {'kwargs': {'central_host_id':"
            in log
        )
        assert "Update successful. New config file:" in log
        assert """ "central_host_id": "test_id",\n """ in log

    def test_logs_supply_config(self, project, tmp_path):
        """"""
        new_configs_path, _ = test_utils.make_correct_supply_config_file(
            project, tmp_path
        )
        self.delete_log_files(project.cfg.logging_path)

        project.supply_config_file(new_configs_path, warn=False)

        log = self.read_log_file(
            project.cfg["local_path"] / ".datashuttle" / "logs"
        )

        assert "supply-config-file" in log
        assert "\n\nVariablesState:\nlocals: {'input_path_to_config':" in log
        assert "Update successful. New config file: " in log
        assert (
            f""" "local_path": "{project.cfg['local_path'].as_posix()}",\n """
            in log
        )

    def test_make_folders(self, project):
        subs = ["sub-111", f"sub-002{tags('to')}004"]

        ses = ["ses-123", "ses-101"]

        project.make_folders(subs, ses, datatype="all")

        log = self.read_log_file(project.cfg.logging_path)

        assert "Formatting Names..." in log

        assert (
            "\n\nVariablesState:\nlocals: {'sub_names': ['sub-111', "
            "'sub-002@TO@004'], 'ses_names': ['ses-123', 'ses-101'], "
            "'datatype': 'all'}\ncfg: {'local_path':" in log
        )

        assert f"sub_names: ['sub-111', 'sub-002{tags('to')}004']" in log
        assert "ses_names: ['ses-123', 'ses-101']" in log
        assert (
            "formatted_sub_names: ['sub-111', 'sub-002', 'sub-003', 'sub-004']"
            in log
        )
        assert "formatted_ses_names: ['ses-123', 'ses-101']" in log
        assert "Made folder at path:" in log

        assert (
            str(Path("local") / project.project_name / "rawdata" / "sub-111")
            in log
        )
        assert (
            str(
                Path(
                    "local",
                    project.project_name,
                    "rawdata",
                    "sub-002",
                    "ses-123",
                    "funcimg",
                )
            )
            in log
        )
        assert (
            str(
                Path(
                    "local",
                    project.project_name,
                    "rawdata",
                    "sub-004",
                    "ses-101",
                )
            )
            in log
        )
        assert "Finished file creation. Local folder tree is now:" in log

    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    @pytest.mark.parametrize("use_all_alias", [True, False])
    def test_logs_upload_and_download(
        self, project, upload_or_download, use_all_alias
    ):
        """
        Set transfer verbosity and progress settings so
        maximum output is produced to test against.
        """
        subs = ["sub-11"]
        sessions = ["ses-123"]

        test_utils.make_and_check_local_project_folders(
            project,
            subs,
            sessions,
            "all",
        )

        project.update_config_file(show_transfer_progress=False)
        project.update_config_file(transfer_verbosity="vv")

        (
            transfer_function,
            base_path_to_check,
        ) = test_utils.handle_upload_or_download(
            project,
            upload_or_download,
            use_all_alias,
        )
        self.delete_log_files(project.cfg.logging_path)

        transfer_function() if use_all_alias else transfer_function(
            "all", "all", "all"
        )

        log = self.read_log_file(project.cfg.logging_path)

        suffix = "-all" if use_all_alias else ""

        assert (
            f"Starting logging for command {upload_or_download}{suffix}" in log
        )

        if use_all_alias:
            assert (
                "VariablesState:\nlocals: {'dry_run': False}\ncfg: {'local_path':"
                in log
            )
        else:
            assert (
                "VariablesState:\nlocals: {'sub_names': 'all', 'ses_names': 'all', 'datatype': 'all', 'dry_run': False, 'init_log': True}\ncfg: {'local_path': "
                in log
            )

        # 'remote' here is rclone terminology
        assert "Creating backend with remote" in log

        assert "Using config file from" in log
        assert "Local file system at" in log
        assert "--include" in log
        assert "sub-11/ses-123/anat/**" in log
        assert "/central/test_project/rawdata" in log
        assert "Waiting for checks to finish" in log

    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    def test_logs_upload_and_download_folder_or_file(
        self, project, upload_or_download
    ):
        """
        Set transfer verbosity and progress settings so
        maximum output is produced to test against.
        """
        test_utils.make_and_check_local_project_folders(
            project,
            subs=["sub-001"],
            sessions=["ses-001"],
            datatype="all",
        )

        project.update_config_file(show_transfer_progress=False)
        project.update_config_file(transfer_verbosity="vv")

        test_utils.handle_upload_or_download(
            project,
            upload_or_download,
        )
        self.delete_log_files(project.cfg.logging_path)

        if upload_or_download == "upload":
            project.upload_specific_folder_or_file("sub-001/ses-001")
        else:
            project.download_specific_folder_or_file("sub-001/ses-001")

        log = self.read_log_file(project.cfg.logging_path)

        assert (
            f"Starting logging for command {upload_or_download}-specific-folder-or-file"
            in log
        )
        assert (
            "\n\nVariablesState:\nlocals: {'filepath': 'sub-001/ses-001', "
            "'dry_run': False}\ncfg: {'local_path':" in log
        )
        assert """sub-001/ses-001"]""" in log
        assert "Using config file from" in log
        assert "Waiting for checks to finish" in log

    # ----------------------------------------------------------------------------------
    # Test temporary logging path
    # ----------------------------------------------------------------------------------

    def test_temp_log_folder_moved_make_config_file(
        self, clean_project_name, tmp_path
    ):
        """
        Similar to `test_logs_new_supply_config()`, check that
        logs are moved to the passed `local_path` when
        `make_config_file()` is passed.
        """
        project = DataShuttle(clean_project_name)

        configs = test_utils.get_test_config_arguments_dict(
            tmp_path, clean_project_name
        )
        project.make_config_file(**configs)

        # After a config file is made, check that the logs are found in
        # the passed `local_path`.
        local_path_search = (
            project.cfg["local_path"] / ".datashuttle" / "logs" / "*.log"
        ).as_posix()

        tmp_path_logs = glob.glob(str(project._temp_log_path / "*.log"))
        project_path_logs = glob.glob(local_path_search)

        assert len(tmp_path_logs) == 0
        assert len(project_path_logs) == 1
        assert "make-config-file" in project_path_logs[0]

        # Make another local path, and re-call `make_config_file`, checking
        # the logs of the action are found in the new local path.
        new_local_path = (
            tmp_path / "new_path_for_log_tests" / clean_project_name
        ).as_posix()

        os.makedirs(new_local_path, exist_ok=True)

        configs["local_path"] = new_local_path

        project.make_config_file(**configs)

        tmp_path_logs = glob.glob(str(project._temp_log_path / "*.log"))
        project_path_logs = glob.glob(local_path_search)
        new_local_path_logs = glob.glob(
            f"{new_local_path}/.datashuttle/logs/*.log"
        )

        assert len(tmp_path_logs) == 0
        assert len(project_path_logs) == 1
        assert len(new_local_path_logs) == 1
        assert all("make-config-file" in log for log in project_path_logs)

    def test_logs_new_supply_config(self, clean_project_name, tmp_path):
        """
        Check that logs are stored in the correct place after
        supply_config_file() is used. Under the hood, logs are
        stored to a temporary folder then moved to the local_path
        passed in the folder.
        """
        project = DataShuttle(clean_project_name)

        new_configs_path, _ = test_utils.make_correct_supply_config_file(
            project,
            tmp_path,
        )
        project.supply_config_file(new_configs_path, warn=False)

        # Check that the logs for the `supply_config_file` command
        # are found in the `local_path` from the supplied config.
        local_path_log_search = str(
            project.cfg["local_path"] / ".datashuttle" / "logs" / "*.log"
        )
        local_path_logs = glob.glob(local_path_log_search)

        assert len(local_path_logs) == 1
        assert "supply-config-file" in local_path_logs[0]

        # Next, supply a new config file with a different
        # `local_path`, and check when this is passed logs
        # are created in the new `local_path`.
        new_local_path = (
            tmp_path / "new_path_for_log_tests" / clean_project_name
        ).as_posix()
        os.makedirs(new_local_path, exist_ok=True)

        new_configs_path, _ = test_utils.make_correct_supply_config_file(
            project,
            tmp_path,
            update_configs={"key": "local_path", "value": new_local_path},
        )
        project.supply_config_file(new_configs_path, warn=False)

        local_path_logs = glob.glob(local_path_log_search)
        new_path_logs = glob.glob(f"{new_local_path}/.datashuttle/logs/*.log")

        assert len(new_path_logs) == 1
        assert len(local_path_logs) == 1
        assert all("supply-config-file" in log for log in local_path_logs)

    def test_clear_logging_path(self, clean_project_name, tmp_path):
        """
        The temporary logging path holds logs which are all
        transferred to a new `local_path` when configs
        are updated. This should only ever be the most
        recent log action, and not others which may
        have accumulated due to raised errors. Therefore
        the `_temp_log_path` is cleared before logging
        begins, this test checks the `_temp_log_path`
        is cleared correctly.
        """
        project = DataShuttle(clean_project_name)

        configs = test_utils.get_test_config_arguments_dict(
            tmp_path, clean_project_name
        )

        configs["local_path"] = "~"

        with pytest.raises(BaseException):
            project.make_config_file(**configs)

        # Because an error was raised, the log will stay in the
        # temp log folder. We clear it and check it is deleted.
        stored_logs = glob.glob((project._temp_log_path / "*.log").as_posix())
        assert len(stored_logs) == 1

        project._clear_temp_log_path()

        stored_logs = glob.glob((project._temp_log_path / "*.log").as_posix())
        assert len(stored_logs) == 0

    # ----------------------------------------------------------------------------------
    # Check errors propagate
    # ----------------------------------------------------------------------------------

    def test_logs_check_update_config_error(self, project):
        """"""
        with pytest.raises(ConfigError):
            project.update_config_file(
                connection_method="ssh", central_host_username=None
            )

        log = self.read_log_file(project.cfg.logging_path)

        assert (
            "'central_host_username' are required if 'connection_method' is 'ssh'"
            in log
        )
        assert (
            "VariablesState:\nlocals: {'kwargs': {'connection_method': 'ssh'"
            in log
        )

    def test_logs_bad_make_folders_error(self, project):
        """"""
        project.make_folders("sub-001", datatype="all")
        self.delete_log_files(project.cfg.logging_path)

        with pytest.raises(NeuroBlueprintError):
            project.make_folders(
                "sub-001_datetime-123213T123122", datatype="all"
            )
        log = self.read_log_file(project.cfg.logging_path)

        assert (
            "A sub already exists with the same "
            "sub id as sub-001_datetime-123213T123122. "
            "The existing folder is sub-001" in log
        )

    def test_validate_project_logging(self, project):
        """
        Test that `validate_project` logs errors
        and warnings to file.
        """
        # Make conflicting subject folders
        project.make_folders(["sub-001", "sub-002"])
        for sub in ["sub-1", "sub-002_date-2023"]:
            os.makedirs(project.cfg["local_path"] / "rawdata" / sub)

        self.delete_log_files(project.cfg.logging_path)

        # Check a validation error is logged.
        with pytest.raises(BaseException) as e:
            project.validate_project(error_or_warn="error")

        log = self.read_log_file(project.cfg.logging_path)
        assert "ERROR" in log
        assert str(e.value) in log

        self.delete_log_files(project.cfg.logging_path)

        # Check that validation warnings are logged.
        with pytest.warns(UserWarning) as w:
            project.validate_project(error_or_warn="warn")

        log = self.read_log_file(project.cfg.logging_path)

        assert "WARNING" in log

        for idx in range(len(w)):
            assert str(w[idx].message) in log

    def test_validate_names_against_project_logging(self, project):
        """
        Implicitly test `validate_names_against_project` called when
        `make_project_folders` is called, that it logs errors
        to file. Warnings are not tested.
        """
        project.make_folders("sub-001")
        self.delete_log_files(project.cfg.logging_path)  #

        with pytest.raises(BaseException) as e:
            project.make_folders("sub-001_id-a")

        log = self.read_log_file(project.cfg.logging_path)

        assert "ERROR" in log
        assert str(e.value) in log
