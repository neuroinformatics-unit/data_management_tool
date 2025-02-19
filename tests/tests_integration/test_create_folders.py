import datetime
import os
import re
import shutil
from os.path import join

import pytest
import test_utils
from base import BaseTest

from datashuttle.configs import canonical_configs, canonical_folders
from datashuttle.configs.canonical_tags import tags


class TestCreateFolders(BaseTest):

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_generate_folders_default_ses(self, project):
        """
        Make a subject folders with full tree. Don't specify
        session name (it will default to no sessions).

        Check that the folder tree is created correctly. Pass
        a dict that indicates if each subfolder is used (to avoid
        circular testing from the project itself).
        """
        subs = ["00011", "sub-00002", "30303"]

        project.create_folders("rawdata", subs)

        test_utils.check_folder_tree_is_correct(
            base_folder=test_utils.get_top_level_folder_path(project),
            subs=["sub-00011", "sub-00002", "sub-30303"],
            sessions=[],
            folder_used=test_utils.get_all_broad_folders_used(),
        )

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_explicitly_session_list(self, project):
        """
        Perform an alternative test where the output is tested explicitly.
        This is some redundancy to ensure tests are working correctly and
        make explicit the expected folder tree.

        Note for new folders, this will have to be manually updated.
        This is highlighted in an assert in check_and_cd_folder()
        """
        subs = ["sub-001", "sub-002"]

        sessions = ["ses-00001", "50432"]

        project.create_folders(
            "rawdata", subs, sessions, self.broad_datatypes()
        )

        base_folder = test_utils.get_top_level_folder_path(project)

        for sub in subs:
            for ses in ["ses-00001", "ses-50432"]:
                test_utils.check_and_cd_folder(
                    join(base_folder, sub, ses, "ephys")
                )
                test_utils.check_and_cd_folder(
                    join(
                        base_folder,
                        sub,
                        ses,
                        "behav",
                    )
                )
                test_utils.check_and_cd_folder(
                    join(base_folder, sub, ses, "funcimg")
                )
                test_utils.check_and_cd_folder(
                    join(base_folder, sub, ses, "anat")
                )

    @pytest.mark.parametrize("behav", [True, False])
    @pytest.mark.parametrize("ephys", [True, False])
    @pytest.mark.parametrize("funcimg", [True, False])
    @pytest.mark.parametrize("anat", [True, False])
    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_every_broad_datatype_passed(
        self, project, behav, ephys, funcimg, anat
    ):
        """
        Check every combination of data type used and ensure only the
        correct ones are made.

        NOTE: This test could be refactored to reduce code reuse.
        """
        datatypes_to_make = []
        if behav:
            datatypes_to_make.append("behav")
        if ephys:
            datatypes_to_make.append("ephys")
        if funcimg:
            datatypes_to_make.append("funcimg")
        if anat:
            datatypes_to_make.append("anat")

        # Make folder tree
        subs = ["sub-001", "sub-002"]
        sessions = ["ses-001", "ses-002"]

        created_folder_dict = project.create_folders(
            "rawdata", subs, sessions, datatypes_to_make
        )
        folders_used = test_utils.get_all_broad_folders_used()
        folders_used.update(
            {"behav": behav, "ephys": ephys, "funcimg": funcimg, "anat": anat}
        )
        # Check folder tree is not made but all others are
        test_utils.check_folder_tree_is_correct(
            base_folder=test_utils.get_top_level_folder_path(project),
            subs=subs,
            sessions=sessions,
            folder_used=folders_used,
            created_folder_dict=created_folder_dict,
        )

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_custom_folder_names(self, project, monkeypatch):
        """
        Change folder names to custom (non-default) and
        ensure they are made correctly.
        """
        new_name_datafolders = canonical_folders.get_datatype_folders()
        new_name_datafolders["ephys"].name = "change_ephys"
        new_name_datafolders["behav"].name = "change_behav"
        new_name_datafolders["anat"].name = "change_anat"
        new_name_datafolders["funcimg"].name = "change_funcimg"

        def new_name_func():
            return new_name_datafolders

        monkeypatch.setattr(
            "datashuttle.configs.canonical_folders.get_datatype_folders",
            new_name_func,
        )

        # Make the folders
        sub = "sub-001"
        ses = "ses-001"

        project.create_folders("rawdata", sub, ses, self.broad_datatypes())

        # Check the correct folder names were made
        base_folder = test_utils.get_top_level_folder_path(project)

        test_utils.check_and_cd_folder(
            join(
                base_folder,
                sub,
                ses,
                "change_ephys",
            )
        )
        test_utils.check_and_cd_folder(
            join(base_folder, sub, ses, "change_behav")
        )
        test_utils.check_and_cd_folder(
            join(base_folder, sub, ses, "change_funcimg")
        )
        test_utils.check_and_cd_folder(
            join(base_folder, sub, ses, "change_anat")
        )

    @pytest.mark.parametrize(
        "files_to_test",
        [
            ["ephys", "behav"],
            ["ephys", "behav", "anat"],
            ["ephys", "behav", "anat", "funcimg"],
            ["funcimg", "ephys"],
            ["funcimg"],
        ],
    )
    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_datatypes_subsection(self, project, files_to_test):
        """
        Check that combinations of datatypes passed to make file folder
        make the correct combination of datatypes.

        Note this will fail when new top level folders are added, and should be
        updated.
        """
        sub = "sub-001"
        ses = "ses-001"
        project.create_folders("rawdata", sub, ses, files_to_test)

        base_folder = test_utils.get_top_level_folder_path(project)

        # Check at the subject level
        test_utils.glob_basenames(
            join(base_folder, sub, "*"),
            exclude=ses,
        )

        # Check at the session level
        ses_file_names = test_utils.glob_basenames(
            join(base_folder, sub, ses, "*"),
            exclude=ses,
        )

        assert ses_file_names == sorted(files_to_test)

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_date_flags_in_session(self, project):
        """
        Check that @DATE@ is converted into current date
        in generated folder names
        """
        date, time_ = self.get_formatted_date_and_time()

        project.create_folders(
            "rawdata",
            ["sub-001", "sub-002"],
            [f"ses-001_{tags('date')}", f"002_{tags('date')}"],
            "ephys",
        )

        ses_names = test_utils.glob_basenames(
            join(test_utils.get_top_level_folder_path(project), "**", "ses-*"),
            recursive=True,
        )

        assert all([date in name for name in ses_names])
        assert all([tags("date") not in name for name in ses_names])

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_datetime_flag_in_session(self, project):
        """
        Check that @DATETIME@ is converted to datetime
        in generated folder names
        """
        date, time_ = self.get_formatted_date_and_time()

        project.create_folders(
            "rawdata",
            ["sub-001", "sub-002"],
            [f"ses-001_{tags('datetime')}", f"002_{tags('datetime')}"],
            "ephys",
        )

        ses_names = test_utils.glob_basenames(
            join(test_utils.get_top_level_folder_path(project), "**", "ses-*"),
            recursive=True,
        )

        # Convert the minutes to regexp as could change during test runtime
        regexp_time = r"\d{6}"
        datetime_regexp = f"datetime-{date}T{regexp_time}"

        assert all([re.search(datetime_regexp, name) for name in ses_names])
        assert all([tags("time") not in name for name in ses_names])

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_created_paths_dict_sub_or_ses_only(self, project):
        """
        Test that the `created_folders` dictionary returned by
        `create_folders` correctly splits paths when only
        subject or session is passed. The `datatype` case is
        tested in `test_utils.check_folder_tree_is_correct()`.
        """
        created_path_sub = project.create_folders("rawdata", "sub-001")

        assert len(created_path_sub) == 2
        assert created_path_sub["ses"] == []
        assert (
            created_path_sub["sub"][0]
            == project.get_local_path() / "rawdata" / "sub-001"
        )

        created_path_ses = project.create_folders(
            "rawdata", "sub-002", "ses-001"
        )

        assert len(created_path_ses) == 2
        assert created_path_ses["sub"] == []
        assert (
            created_path_ses["ses"][0]
            == project.get_local_path() / "rawdata" / "sub-002" / "ses-001"
        )

    # ----------------------------------------------------------------------------------------------------------
    # Test Make Folders in Different Top Level Folders
    # ----------------------------------------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "top_level_folder", canonical_folders.get_top_level_folders()
    )
    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_all_top_level_folders(self, project, top_level_folder):
        """
        Check that when switching the top level folder (e.g. rawdata, derivatives)
        new folders are made in the correct folder.
        """
        subs = ["sub-001", "sub-002"]
        sessions = ["ses-001", "ses-003"]

        project.create_folders(
            top_level_folder, subs, sessions, self.broad_datatypes()
        )

        # Check folder tree is made in the desired top level folder
        test_utils.check_working_top_level_folder_only_exists(
            top_level_folder,
            project.cfg["local_path"] / top_level_folder,
            subs,
            sessions,
            folders_used=test_utils.get_all_broad_folders_used(),
        )

    # ----------------------------------------------------------------------------------------------------------
    # Test get next subject / session numbers
    # ----------------------------------------------------------------------------------

    @pytest.mark.parametrize("top_level_folder", ["rawdata", "derivatives"])
    @pytest.mark.parametrize("return_with_prefix", [True, False])
    def test_get_next_sub(self, project, return_with_prefix, top_level_folder):
        """
        Test that the next subject number is suggested correctly.
        This takes the union of subjects available in the local and
        central repository. As such test the case where either are
        empty, or when they have different subjects in.
        """
        # Create local folders, central is empty
        test_utils.make_local_folders_with_files_in(
            project, top_level_folder, ["001", "002", "003"]
        )

        new_num = project.get_next_sub(top_level_folder, return_with_prefix)

        assert new_num == "sub-004" if return_with_prefix else "004"

        # Upload to central, now local and central folders match
        (
            project.upload_rawdata()
            if top_level_folder == "rawdata"
            else project.upload_derivatives()
        )

        shutil.rmtree(project.cfg["local_path"] / top_level_folder)

        new_num = project.get_next_sub(top_level_folder, return_with_prefix)
        assert new_num == "sub-004" if return_with_prefix else "004"

        # Add large-sub num folders to local and check all are detected.
        project.create_folders(top_level_folder, ["004", "005"])

        new_num = project.get_next_sub(top_level_folder, return_with_prefix)
        assert new_num == "sub-006" if return_with_prefix else "006"

        # check `local_path` option
        os.makedirs(project.cfg["central_path"] / top_level_folder / "sub-006")
        new_num = project.get_next_sub(
            top_level_folder, return_with_prefix, local_only=False
        )
        assert new_num == "sub-007" if return_with_prefix else "007"

        new_num = project.get_next_sub(
            top_level_folder, return_with_prefix, local_only=True
        )
        assert new_num == "sub-006" if return_with_prefix else "006"

    @pytest.mark.parametrize("top_level_folder", ["rawdata", "derivatives"])
    @pytest.mark.parametrize("return_with_prefix", [True, False])
    def test_get_next_ses(self, project, return_with_prefix, top_level_folder):
        """
        Almost identical to test_get_next_sub() but with calls
        for searching sessions. This could be combined with
        above but reduces readability, so leave with some duplication.

        Note the main underlying function is tested in
        `test_get_max_sub_or_ses_num_and_value_length()`.
        """
        sub = "sub-09"

        test_utils.make_local_folders_with_files_in(
            project, top_level_folder, sub, ["001", "002", "003"]
        )

        # Test the next sub and ses number are correct
        new_num = project.get_next_sub(top_level_folder, return_with_prefix)
        assert new_num == "sub-10" if return_with_prefix else "10"

        new_num = project.get_next_ses(
            top_level_folder, sub, return_with_prefix
        )
        assert new_num == "ses-004" if return_with_prefix else "004"

        # Now upload the data, delete locally, and check the
        # suggested values are correct based on the `central` path.
        (
            project.upload_rawdata()
            if top_level_folder == "rawdata"
            else project.upload_derivatives()
        )

        shutil.rmtree(project.cfg["local_path"] / top_level_folder)

        new_num = project.get_next_sub(top_level_folder, return_with_prefix)
        assert new_num == "sub-10" if return_with_prefix else "10"

        new_num = project.get_next_ses(
            top_level_folder, sub, return_with_prefix
        )
        assert new_num == "ses-004" if return_with_prefix else "004"

        # Now make a couple more sessions locally, and check
        # the next session is updated accordingly.
        project.create_folders(top_level_folder, sub, ["004", "005"])

        new_num = project.get_next_ses(
            top_level_folder, sub, return_with_prefix
        )
        assert new_num == "ses-006" if return_with_prefix else "006"

        # check `local_path` object
        os.makedirs(
            project.cfg["central_path"] / top_level_folder / sub / "ses-006"
        )
        new_num = project.get_next_ses(
            top_level_folder, sub, return_with_prefix, local_only=False
        )
        assert new_num == "ses-007" if return_with_prefix else "007"

        new_num = project.get_next_ses(
            top_level_folder, sub, return_with_prefix, local_only=True
        )
        assert new_num == "ses-006" if return_with_prefix else "006"

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_get_next_sub_and_ses_name_template(self, project):
        """
        In the case where a name template exists, these getters should use the
        number of digits on the template (even if these are different
        within the project!).
        """
        project.create_folders("rawdata", "sub-001", "ses-001")

        name_templates = {
            "on": True,
            "sub": r"sub-\d.?.?.?\d_key-value",  # 5 digits
            "ses": r"ses-\d_@DATE@",  # 2 digits
        }
        project.set_name_templates(name_templates)

        new_num = project.get_next_sub(
            "rawdata", return_with_prefix=False, local_only=True
        )
        assert new_num == "00002"

        new_num = project.get_next_ses(
            "rawdata", "sub-001", return_with_prefix=False, local_only=True
        )
        assert new_num == "2"

        # Quick test on two cases that should not use name template.
        # Test sub only as underlying code is the same. If name templates
        # is off, use the num_digits from the project, same if the sub
        # key value takes a length-unspecific wildcard (should never really happen).
        name_templates["on"] = False
        project.set_name_templates(name_templates)

        new_num = project.get_next_sub(
            "rawdata", return_with_prefix=False, local_only=True
        )
        assert new_num == "002"

        name_templates["on"] = True
        name_templates["sub"] = "sub-.*"
        project.set_name_templates(name_templates)

        new_num = project.get_next_sub(
            "rawdata", return_with_prefix=False, local_only=True
        )
        assert new_num == "002"

    # ----------------------------------------------------------------------------------
    # Test Helpers
    # ----------------------------------------------------------------------------------

    def get_formatted_date_and_time(self):
        date = str(datetime.datetime.now().date())
        date = date.replace("-", "")
        time_ = datetime.datetime.now().time().strftime("%Hh%Mm")
        return date, time_

    def broad_datatypes(self):
        return canonical_configs.get_broad_datatypes()
