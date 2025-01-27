import os
import platform
import subprocess
import warnings

import pytest
import ssh_test_utils
import test_utils

from datashuttle.datashuttle import DataShuttle

TEST_PROJECT_NAME = "test_project"


class BaseTest:

    @pytest.fixture(scope="function")
    def no_cfg_project(test):
        """
        Fixture that creates an empty project. Ignore the
        warning that no configs are set up yet.
        """
        test_utils.delete_project_if_it_exists(TEST_PROJECT_NAME)

        warnings.filterwarnings("ignore")
        no_cfg_project = DataShuttle(TEST_PROJECT_NAME)
        warnings.filterwarnings("default")

        yield no_cfg_project

    @pytest.fixture(scope="function")
    def project(self, tmp_path):
        """
        Set up a project with default configs
        to use for testing.

        Note this fixture is a duplicate of project()
        in test_filesystem_transfer.py fixture
        """
        tmp_path = tmp_path / "test with space"

        project = test_utils.setup_project_default_configs(
            TEST_PROJECT_NAME,
            tmp_path,
            local_path=tmp_path / TEST_PROJECT_NAME,
        )

        cwd = os.getcwd()
        yield project
        test_utils.teardown_project(cwd, project)

    @pytest.fixture(scope="function")
    def clean_project_name(self):
        """
        Create an empty project, but ensure no
        configs already exists, and delete created
        configs after test.
        """
        project_name = TEST_PROJECT_NAME
        test_utils.delete_project_if_it_exists(project_name)
        yield project_name
        test_utils.delete_project_if_it_exists(project_name)

    @pytest.fixture(
        scope="class",
    )
    def setup_ssh_container(self):
        """
        Set up the Dockerfile container for SSH tests and
        delete it on teardown.
        """
        container_name = "datashuttle_ssh_tests"
        ssh_test_utils.setup_ssh_container(container_name)
        yield

        sudo = "sudo " if platform.system() == "Linux" else ""

        subprocess.run(f"{sudo}docker rm -f {container_name}", shell=True)
