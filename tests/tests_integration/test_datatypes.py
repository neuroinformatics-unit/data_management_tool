import os

import pytest
import test_utils
from base import BaseTest

from datashuttle.configs import canonical_configs


class TestDatatypes(BaseTest):
    """
    Tests for creating folders and transfer (very similar to other tests)
    however which test the creation and transfer of narrow datatypes.
    Other tests used broad datatypes.
    """

    def test_create_narrow_datatypes(self, project):
        """
        Create all narrow datatype folders and check
        they are created as expected.
        """
        # Make folder tree including all narrow datatypes
        subs = ["sub-001", "sub-002"]
        sessions = ["ses-001", "ses-002"]
        narrow_datatypes = canonical_configs.quick_get_narrow_datatypes()

        created_folder_dict = project.create_folders(
            "rawdata",
            subs,
            sessions,
            narrow_datatypes,
        )

        # Check all narrow datatypes (and no broad) are made
        test_utils.check_folder_tree_is_correct(
            base_folder=test_utils.get_top_level_folder_path(project),
            subs=subs,
            sessions=sessions,
            folder_used=self.get_narrow_only_datatypes_used(),
            created_folder_dict=created_folder_dict,
        )

    def get_narrow_only_datatypes_used(self, used=True):
        """
        This is similar to test_utils.get_all_broad_folders_used
        but for narrow datatypes.
        """
        return {
            key: used for key in canonical_configs.quick_get_narrow_datatypes()
        } | {key: False for key in canonical_configs.get_broad_datatypes()}

    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    def test_transfer_datatypes(
        self,
        project,
        upload_or_download,
    ):
        """
        Create a project with narrow datatypes and check these
        folders are transferred as expected.
        """
        subs, sessions = test_utils.get_default_sub_sessions_to_test()

        # Unfortunately on Windows we are encountering 'The command line is too long'
        # and so cannot test against all datatypes here.
        some_narrow_datatypes = canonical_configs.quick_get_narrow_datatypes()[
            :10
        ]

        datatypes_used = self.get_narrow_only_datatypes_used(used=False)
        for key in some_narrow_datatypes:
            datatypes_used[key] = True

        test_utils.make_and_check_local_project_folders(
            project,
            "rawdata",
            subs,
            sessions,
            some_narrow_datatypes,
            datatypes_used,
        )

        (
            transfer_function,
            base_path_to_check,
        ) = test_utils.handle_upload_or_download(
            project, upload_or_download, "custom", "rawdata"
        )

        transfer_function("rawdata", "all", "all", some_narrow_datatypes)

        test_utils.check_folder_tree_is_correct(
            os.path.join(base_path_to_check, "rawdata"),
            subs,
            sessions,
            datatypes_used,
        )
