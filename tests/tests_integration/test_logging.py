import glob
import logging
import os
import re
from pathlib import Path

import pytest
import test_utils

from datashuttle import DataShuttle
from datashuttle.configs import canonical_configs
from datashuttle.configs.canonical_tags import tags
from datashuttle.utils import ds_logger
from datashuttle.utils.custom_exceptions import (
    ConfigError,
    NeuroBlueprintError,
)


class TestLogging:

    @pytest.fixture(scope="function")
    def teardown_logger(self):
        """
        Ensure the logger is deleted at the end of each test.
        """
        yield
        if "datashuttle" in logging.root.manager.loggerDict:
            logging.root.manager.loggerDict.pop("datashuttle")

    # -------------------------------------------------------------------------
    # Basic Functionality Tests
    # -------------------------------------------------------------------------

    def test_logger_name(self):
        """
        Check the canonical logger name.
        """
        assert ds_logger.get_logger_name() == "datashuttle"

    def test_start_logging(self, tmp_path, teardown_logger):
        """
        Test that the central `start` logging function
        starts the named logger with the expected handlers.
        """
        assert ds_logger.logging_is_active() is False

        ds_logger.start(tmp_path, "test-command", variables=[])

        # test logger exists and is as expected
        assert "datashuttle" in logging.root.manager.loggerDict
        assert ds_logger.logging_is_active() is True

        logger = logging.getLogger("datashuttle")
        assert logger.propagate is False
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.FileHandler)

    def test_shutdown_logger(self, tmp_path, teardown_logger):
        """
        Check the log handler remover indeed removes the handles.
        """
        assert ds_logger.logging_is_active() is False

        ds_logger.start(tmp_path, "test-command", variables=[])

        logger = logging.getLogger("datashuttle")

        ds_logger.close_log_filehandler()

        assert len(logger.handlers) == 0
        assert ds_logger.logging_is_active() is False

    def test_logging_an_error(self, project, teardown_logger):
        """
        Check that errors are caught and logged properly.
        """
        try:
            project.create_folders("rawdata", "sob-001")
        except:
            pass

        log = test_utils.read_log_file(project.cfg.logging_path)

        assert "ERROR" in log
        assert "Problem with name:" in log

    # -------------------------------------------------------------------------
    # Functional Tests
    # -------------------------------------------------------------------------

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
    def project(self, tmp_path, clean_project_name, request):
        """
        Set `up a project with default configs to use
        for testing. This fixture is distinct
        from the base.py fixture as requires
        additional logging setup / teardown.

        Switch on datashuttle logging as required for
        these tests, then turn back off during tear-down.
        """
        project_type = getattr(request, "param", "full")

        project, cwd = test_utils.setup_project_fixture(
            tmp_path, clean_project_name, project_type
        )

        test_utils.delete_log_files(project.cfg.logging_path)

        test_utils.set_datashuttle_loggers(disable=False)

        yield project

        test_utils.teardown_project(cwd, project)
        test_utils.set_datashuttle_loggers(disable=True)

    # ----------------------------------------------------------------------------------------------------------
    # Test Public API Logging
    # ----------------------------------------------------------------------------------------------------------

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
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

        log = test_utils.read_log_file(project.cfg.logging_path)

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

        log = test_utils.read_log_file(project.cfg.logging_path)

        assert "Starting logging for command update-config-file" in log
        assert (
            "\n\nVariablesState:\nlocals: {'kwargs': {'central_host_id':"
            in log
        )
        assert "Update successful. New config file:" in log
        assert """ "central_host_id": "test_id",\n """ in log

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_create_folders(self, project):
        subs = ["sub-111", f"sub-002{tags('to')}004"]

        ses = ["ses-123", "ses-101"]

        project.create_folders(
            "rawdata",
            subs,
            ses,
            datatype=canonical_configs.get_broad_datatypes(),
        )

        log = test_utils.read_log_file(project.cfg.logging_path)

        assert "Formatting Names..." in log

        assert (
            "VariablesState:\nlocals: {'top_level_folder': 'rawdata', 'sub_names': ['sub-111', 'sub-002@TO@004'],"
            in log
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

    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    @pytest.mark.parametrize(
        "transfer_method", ["entire_project", "top_level_folder", "custom"]
    )
    def test_logs_upload_and_download(
        self, project, upload_or_download, transfer_method
    ):
        """
        Set transfer verbosity and progress settings so
        maximum output is produced to test against.
        """
        subs = ["sub-11"]
        sessions = ["ses-123"]

        test_utils.make_and_check_local_project_folders(
            project,
            "rawdata",
            subs,
            sessions,
            canonical_configs.get_broad_datatypes(),
        )

        (
            transfer_function,
            base_path_to_check,
        ) = test_utils.handle_upload_or_download(
            project,
            upload_or_download,
            transfer_method,
            top_level_folder="rawdata",
        )
        test_utils.delete_log_files(project.cfg.logging_path)

        if transfer_method == "custom":
            transfer_function("rawdata", "all", "all", "all")
        else:
            transfer_function()

        log = test_utils.read_log_file(project.cfg.logging_path)

        if transfer_method == "entire_project":
            assert (
                f"Starting logging for command {upload_or_download}-entire-project"
                in log
            )
        elif transfer_method == "top_level_folder":
            assert (
                f"Starting logging for command {upload_or_download}-rawdata"
                in log
            )
        else:
            assert f"{upload_or_download}-custom" in log

        # 'remote' here is rclone terminology
        assert "Creating backend with remote" in log
        assert "Using config file from" in log
        assert "--include" in log
        assert "sub-11/ses-123/anat/**" in log
        assert "/central/test_project/rawdata" in log

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
            "rawdata",
            subs=["sub-001"],
            sessions=["ses-001"],
            datatype=canonical_configs.get_broad_datatypes(),
        )

        test_utils.handle_upload_or_download(
            project, upload_or_download, transfer_method=None
        )
        test_utils.delete_log_files(project.cfg.logging_path)

        if upload_or_download == "upload":
            project.upload_specific_folder_or_file(
                f"{project.cfg['local_path']}/rawdata/sub-001/ses-001"
            )
        else:
            project.download_specific_folder_or_file(
                f"{project.cfg['central_path']}/rawdata/sub-001/ses-001"
            )

        log = test_utils.read_log_file(project.cfg.logging_path)

        assert (
            f"Starting logging for command {upload_or_download}-specific-folder-or-file"
            in log
        )
        assert "sub-001/ses-001" in log
        assert "Elapsed time" in log

    # ----------------------------------------------------------------------------------
    # Test temporary logging path
    # ----------------------------------------------------------------------------------

    def test_temp_log_folder_moved_make_config_file(
        self, clean_project_name, tmp_path
    ):
        """
        Check that
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

        tmp_path_logs = list(glob.glob(str(project._temp_log_path / "*.log")))
        project_path_logs = list(glob.glob(local_path_search))

        assert len(tmp_path_logs) == 0
        assert len(project_path_logs) == 1
        assert "make-config-file" in project_path_logs[0]

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
        stored_logs = list(
            glob.glob((project._temp_log_path / "*.log").as_posix())
        )
        assert len(stored_logs) == 1

        project._clear_temp_log_path()

        stored_logs = list(
            glob.glob((project._temp_log_path / "*.log").as_posix())
        )
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

        log = test_utils.read_log_file(project.cfg.logging_path)

        assert (
            "'central_host_username' are required if 'connection_method' is 'ssh'"
            in log
        )
        assert (
            "VariablesState:\nlocals: {'kwargs': {'connection_method': 'ssh'"
            in log
        )

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_logs_bad_create_folders_error(self, project):
        """"""
        project.create_folders("rawdata", "sub-001", datatype="all")
        test_utils.delete_log_files(project.cfg.logging_path)

        with pytest.raises(NeuroBlueprintError):
            project.create_folders(
                "rawdata", "sub-001_datetime-123213T123122", datatype="all"
            )
        log = test_utils.read_log_file(project.cfg.logging_path)

        assert (
            "A sub already exists with the same "
            "sub id as sub-001_datetime-123213T123122. "
            "The existing folder is sub-001" in log
        )

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_validate_project_logging(self, project):
        """
        Test that `validate_project` logs errors
        and warnings to file.
        """
        # Make conflicting subject folders
        project.create_folders("rawdata", ["sub-001", "sub-002"])
        for sub in ["sub-1", "sub-002_date-2023"]:
            os.makedirs(project.cfg["local_path"] / "rawdata" / sub)

        test_utils.delete_log_files(project.cfg.logging_path)

        # Check a validation error is logged.
        with pytest.raises(BaseException) as e:
            project.validate_project("rawdata", error_or_warn="error")

        log = test_utils.read_log_file(project.cfg.logging_path)
        assert "ERROR" in log
        assert str(e.value) in log

        test_utils.delete_log_files(project.cfg.logging_path)

        # Check that validation warnings are logged.
        with pytest.warns(UserWarning) as w:
            project.validate_project("rawdata", error_or_warn="warn")

        log = test_utils.read_log_file(project.cfg.logging_path)

        assert "WARNING" in log

        for idx in range(len(w)):
            assert str(w[idx].message) in log

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_validate_names_against_project_logging(self, project):
        """
        Implicitly test `validate_names_against_project` called when
        `make_project_folders` is called, that it logs errors
        to file. Warnings are not tested.
        """
        project.create_folders("rawdata", "sub-001")
        test_utils.delete_log_files(project.cfg.logging_path)  #

        with pytest.raises(BaseException) as e:
            project.create_folders("rawdata", "sub-001_id-a")

        log = test_utils.read_log_file(project.cfg.logging_path)

        assert "ERROR" in log
        assert str(e.value) in log
