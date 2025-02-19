import os
import re
import time
from pathlib import Path

import pytest
import test_utils
from base import BaseTest

from datashuttle.configs import canonical_folders
from datashuttle.configs.canonical_configs import get_broad_datatypes
from datashuttle.configs.canonical_tags import tags


class TestFileTransfer(BaseTest):

    @pytest.mark.parametrize(
        "top_level_folder", canonical_folders.get_top_level_folders()
    )
    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    @pytest.mark.parametrize(
        "transfer_method", ["entire_project", "top_level_folder", "custom"]
    )
    def test_transfer_empty_folder_structure(
        self,
        project,
        top_level_folder,
        upload_or_download,
        transfer_method,
    ):
        """
        First make a project (folders only) locally.
        Next upload this to the central path
        and check all folders are uploaded correctly.
        """
        subs, sessions = test_utils.get_default_sub_sessions_to_test()

        test_utils.make_and_check_local_project_folders(
            project, top_level_folder, subs, sessions, get_broad_datatypes()
        )

        (
            transfer_function,
            base_path_to_check,
        ) = test_utils.handle_upload_or_download(
            project, upload_or_download, transfer_method, top_level_folder
        )

        if transfer_method == "custom":
            transfer_function(top_level_folder, "all", "all", "all")
        else:
            transfer_function()

        test_utils.check_folder_tree_is_correct(
            os.path.join(base_path_to_check, top_level_folder),
            subs,
            sessions,
            test_utils.get_all_broad_folders_used(),
        )

    def test_empty_folder_is_not_transferred(self, project):
        project.create_folders("rawdata", "sub-001")
        project.upload_rawdata()
        assert not (
            project.cfg["central_path"] / "rawdata" / "sub-001"
        ).is_dir()

    @pytest.mark.parametrize(
        "top_level_folder_to_transfer",
        canonical_folders.get_top_level_folders(),
    )
    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    @pytest.mark.parametrize("transfer_method", ["top_level_folder", "custom"])
    def test_transfer_across_top_level_folders(
        self,
        project,
        top_level_folder_to_transfer,  # Do not change this name, see doc
        upload_or_download,
        transfer_method,
    ):
        """
        For each possible top level folder (e.g. rawdata, derivatives)
        (parametrized) create a folder tree in every top-level folder,
        then transfer using upload / download and
        upload_rawdata() / download_rawdata() that only the working top-level folder
        is transferred.

        Do not change the name of variable `top_level_folder_to_transfer`.
        It is very tempting to change it to `top_level_folder`. In this test
        they are not the same thing!
        """
        subs, sessions = test_utils.get_default_sub_sessions_to_test()

        for top_level_folder in canonical_folders.get_top_level_folders():
            test_utils.make_and_check_local_project_folders(
                project,
                top_level_folder,
                subs,
                sessions,
                get_broad_datatypes(),
            )

        (
            transfer_function,
            base_path_to_check,
        ) = test_utils.handle_upload_or_download(
            project,
            upload_or_download,
            transfer_method,
            top_level_folder_to_transfer,
        )

        if transfer_method == "custom":
            transfer_function(
                top_level_folder_to_transfer, "all", "all", "all"
            )
        else:
            transfer_function()

        full_base_path_to_check = (
            base_path_to_check / top_level_folder_to_transfer
        )

        test_utils.check_working_top_level_folder_only_exists(
            top_level_folder_to_transfer,
            full_base_path_to_check,
            subs,
            sessions,
        )

    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    def test_transfer_all_top_level_folders(self, project, upload_or_download):
        """ """
        subs, sessions = test_utils.get_default_sub_sessions_to_test()

        for top_level_folder in canonical_folders.get_top_level_folders():
            test_utils.make_and_check_local_project_folders(
                project,
                top_level_folder,
                subs,
                sessions,
                get_broad_datatypes(),
            )
        (
            transfer_function,
            base_path_to_check,
        ) = test_utils.handle_upload_or_download(
            project, upload_or_download, transfer_method="entire_project"
        )

        transfer_function()

        for top_level_folder in canonical_folders.get_top_level_folders():

            test_utils.check_folder_tree_is_correct(
                os.path.join(base_path_to_check, top_level_folder),
                subs,
                sessions,
                test_utils.get_all_broad_folders_used(),
            )

    @pytest.mark.parametrize(
        "datatype_to_transfer",
        [
            ["behav"],
            ["ephys"],
            ["funcimg"],
            ["anat"],
            ["behav", "ephys"],
            ["ephys", "anat"],
            ["behav", "ephys", "anat"],
            ["funcimg", "anat", "behav"],
            ["behav", "ephys", "funcimg", "anat"],
        ],
    )
    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    def test_transfer_empty_folder_specific_data(
        self, project, upload_or_download, datatype_to_transfer
    ):
        """
        For the combination of datatype folders, make a folder
        tree with all datatype folders then upload select ones,
        checking only the selected ones are uploaded.
        """
        subs, sessions = test_utils.get_default_sub_sessions_to_test()
        test_utils.make_and_check_local_project_folders(
            project, "rawdata", subs, sessions, get_broad_datatypes()
        )

        (
            transfer_function,
            base_path_to_check,
        ) = test_utils.handle_upload_or_download(
            project, upload_or_download, transfer_method="custom"
        )

        transfer_function("rawdata", subs, sessions, datatype_to_transfer)

        test_utils.check_datatype_sub_ses_uploaded_correctly(
            os.path.join(base_path_to_check, "rawdata"),
            datatype_to_transfer,
            subs,
            sessions,
        )

    @pytest.mark.parametrize(
        "sub_idx_to_upload", [[0], [1], [2], [0, 1], [1, 2], [0, 2], [0, 1, 2]]
    )
    @pytest.mark.parametrize(
        "datatype_to_transfer",
        [
            ["anat"],
            ["behav", "ephys"],
            ["funcimg", "anat", "behav"],
            ["behav", "ephys", "funcimg", "anat"],
        ],
    )
    @pytest.mark.parametrize("upload_or_download", ["upload" "download"])
    def test_transfer_empty_folder_specific_subs(
        self,
        project,
        upload_or_download,
        datatype_to_transfer,
        sub_idx_to_upload,
    ):
        """
        Create a project folder tree with a set of subs, then
        take a subset of these subs and upload them. Check only the
        selected subs were uploaded.
        """
        subs, sessions = test_utils.get_default_sub_sessions_to_test()
        test_utils.make_and_check_local_project_folders(
            project, "rawdata", subs, sessions, get_broad_datatypes()
        )

        (
            transfer_function,
            base_path_to_check,
        ) = test_utils.handle_upload_or_download(
            project, upload_or_download, transfer_method="custom"
        )

        subs_to_upload = [subs[i] for i in sub_idx_to_upload]
        transfer_function(
            "rawdata", subs_to_upload, sessions, datatype_to_transfer
        )

        test_utils.check_datatype_sub_ses_uploaded_correctly(
            os.path.join(base_path_to_check, "rawdata"),
            datatype_to_transfer,
            subs_to_upload,
        )

    @pytest.mark.parametrize(
        "ses_idx_to_upload", [[0], [1], [2], [0, 1], [1, 2], [0, 2], [0, 1, 2]]
    )
    @pytest.mark.parametrize("sub_idx_to_upload", [[0], [1, 2], [0, 1, 2]])
    @pytest.mark.parametrize(
        "datatype_to_transfer",
        [["ephys"], ["funcimg", "anat", "behav"]],
    )
    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    def test_transfer_empty_folder_specific_ses(
        self,
        project,
        upload_or_download,
        datatype_to_transfer,
        sub_idx_to_upload,
        ses_idx_to_upload,
    ):
        """
        Make a project with set subs and sessions. Then select a subset of the
        sessions to upload. Check only the selected sessions were uploaded.
        """
        subs, sessions = test_utils.get_default_sub_sessions_to_test()

        test_utils.make_and_check_local_project_folders(
            project, "rawdata", subs, sessions, get_broad_datatypes()
        )

        (
            transfer_function,
            base_path_to_check,
        ) = test_utils.handle_upload_or_download(
            project, upload_or_download, transfer_method="custom"
        )

        subs_to_upload = [subs[i] for i in sub_idx_to_upload]
        ses_to_upload = [sessions[i] for i in ses_idx_to_upload]

        transfer_function(
            "rawdata", subs_to_upload, ses_to_upload, datatype_to_transfer
        )

        test_utils.check_datatype_sub_ses_uploaded_correctly(
            os.path.join(base_path_to_check, "rawdata"),
            datatype_to_transfer,
            subs_to_upload,
            ses_to_upload,
        )

    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    def test_transfer_with_keyword_parameters(
        self, project, upload_or_download
    ):
        """
        Test the @TO@ keyword is accepted properly when making a session and
        transferring it. First pass @TO@-formatted sub and sessions to
        create_folders. Then transfer the files (upload or download).

        Finally, check the expected formatting on the subject and session
        is observed on the created and transferred file paths.
        """
        subs = ["001", f"02{tags('to')}003"]
        sessions = [f"ses-01{tags('to')}003_{tags('datetime')}"]

        test_utils.make_local_folders_with_files_in(
            project, "rawdata", subs, sessions, get_broad_datatypes()
        )

        (
            transfer_function,
            base_path_to_check,
        ) = test_utils.handle_upload_or_download(
            project, upload_or_download, transfer_method="custom"
        )

        transfer_function("rawdata", subs, "all", "all")

        for base_local in [
            project.cfg["local_path"],
            project.cfg["central_path"],
        ]:
            for sub in ["sub-001", "sub-002", "sub-003"]:
                sessions_in_path = test_utils.glob_basenames(
                    (base_local / "rawdata" / sub / "ses*").as_posix()
                )

                datetime_regexp = "datetime-\d{8}T\d{6}"

                assert re.fullmatch(
                    "ses-001_" + datetime_regexp, sessions_in_path[0]
                )
                assert re.fullmatch(
                    "ses-002_" + datetime_regexp, sessions_in_path[1]
                )
                assert re.fullmatch(
                    "ses-003_" + datetime_regexp, sessions_in_path[2]
                )

    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    def test_wildcard_transfer(self, project, upload_or_download):
        """
        Transfer a subset of define subject and session
        and check only the expected folders are there.
        """
        subs = ["sub-389", "sub-989", "sub-445"]
        sessions = [
            "001_date-20220501",
            "002_date-20220516",
            "003_date-20220601",
        ]

        test_utils.make_local_folders_with_files_in(
            project, "rawdata", subs, sessions, get_broad_datatypes()
        )

        (
            transfer_function,
            base_path_to_check,
        ) = test_utils.handle_upload_or_download(
            project, upload_or_download, transfer_method="custom"
        )

        transfer_function(
            "rawdata",
            f"sub-{tags('*')}89",
            f"ses-{tags('*')}_date-202205{tags('*')}",
            ["ephys", "behav", "funcimg"],
        )

        transferred_subs = test_utils.glob_basenames(
            (base_path_to_check / "rawdata" / "*").as_posix()
        )
        expected_subs = ["sub-389", "sub-989"]
        assert transferred_subs == expected_subs

        for sub in expected_subs:
            transferred_ses = test_utils.glob_basenames(
                (base_path_to_check / "rawdata" / sub / "*").as_posix()
            )
            assert transferred_ses == [
                "ses-001_date-20220501",
                "ses-002_date-20220516",
            ]

    def test_deep_folder_structure(self, project):
        """
        Just a quick test as all other tests only test files directly in the
        datatyp directly. Check that rlcone is setup to transfer
        multiple levels down from the datatype level.
        """
        make_base_path = (
            lambda root: root / "rawdata" / "sub-001" / "ses-001" / "behav"
        )
        local = make_base_path(project.cfg["local_path"])
        test_file_path = (
            Path("level_1") / "level_2" / "level 3" / "deep_test_file"
        )

        test_utils.write_file(local / test_file_path, "hello world")

        project.upload_entire_project()

        assert (
            make_base_path(project.cfg["central_path"]) / test_file_path
        ).is_file()

    @pytest.mark.parametrize(
        "overwrite_existing_files", ["never", "always", "if_source_newer"]
    )
    @pytest.mark.parametrize("dry_run", [True, False])
    def test_rclone_options(
        self,
        project,
        overwrite_existing_files,
        dry_run,
        capsys,
    ):
        """
        When verbosity is --vv, rclone itself will output
        a list of all called arguments. Use this to check
        rclone is called with the arguments set in configs
        as expected. verbosity itself is tested in another method.
        """
        test_utils.make_local_folders_with_files_in(
            project, "rawdata", ["sub-001"], ["ses-002"], ["behav"]
        )

        test_utils.clear_capsys(capsys)
        project.upload_rawdata(
            overwrite_existing_files=overwrite_existing_files, dry_run=dry_run
        )

        log = capsys.readouterr().out

        if overwrite_existing_files == "never":
            assert "--ignore-existing" in log
        elif overwrite_existing_files == "always":
            assert "--ignore-existing" not in log
            assert "--update" not in log
        elif overwrite_existing_files == "if_source_newer":
            assert "--update" in log

        assert "--progress" in log

        if dry_run:
            assert "--dry-run" in log
        else:
            assert "--dry-run" not in log

    @pytest.mark.parametrize(
        "overwrite_existing_files", ["never", "always", "if_source_newer"]
    )
    @pytest.mark.parametrize(
        "transfer_method", ["entire_project", "custom", "top_level_folder"]
    )
    @pytest.mark.parametrize("top_level_folder", ["rawdata", "derivatives"])
    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    def test_overwrite_same_size_earlier_to_later(
        self,
        project,
        overwrite_existing_files,
        transfer_method,
        top_level_folder,
        upload_or_download,
    ):
        """
        Main test to check every parameterization for overwrite settings.
        It is such an important setting it is tested for all top level folder,
        transfer method, even though it makes for quite a confusing function.

        Check that the `overwrite_existing_files` setting performs as
        expected when transferring two files of the same size, the
        one that is older onto the one that is newer.

        "never" : files will never be overwritten
        "always" : files will be overwritten wherever there is a date difference
                   (both cases)
        "if_source_newer" : only overwrite when the source file is
                            newer than the target (only in `later_to_earlier`
                            parameter)

        Two files are written with 'earlier' and 'later' times. The
        exact location of these files is abstracted as will change
        depending on uploading or downloading. Transfer the 'earlier'
        onto the 'later' - it should be transferred only in the
        'always' case.
        """
        path_earlier, path_later = self.setup_overwrite_file_tests(
            upload_or_download, top_level_folder, project
        )

        assert os.path.getsize(path_earlier) == os.path.getsize(path_later)

        transfer_func = test_utils.get_transfer_func(
            project, upload_or_download, transfer_method, top_level_folder
        )

        if transfer_method == "custom":
            transfer_func(
                top_level_folder,
                "all",
                "all",
                "all",
                overwrite_existing_files=overwrite_existing_files,
            )
        else:
            transfer_func(overwrite_existing_files=overwrite_existing_files)

        if overwrite_existing_files in ["never", "if_source_newer"]:
            # The newer file is not transferred
            assert test_utils.read_file(path_later) == ["file laterxx"]
        elif overwrite_existing_files == "always":
            # The newer file is transferred
            assert test_utils.read_file(path_later) == ["file earlier"]

    @pytest.mark.parametrize(
        "overwrite_existing_files", ["never", "always", "if_source_newer"]
    )
    @pytest.mark.parametrize(
        "transfer_method", ["entire_project", "custom", "top_level_folder"]
    )
    @pytest.mark.parametrize("top_level_folder", ["rawdata", "derivatives"])
    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    def test_overwrite_same_size_later_to_earlier(
        self,
        project,
        overwrite_existing_files,
        transfer_method,
        top_level_folder,
        upload_or_download,
    ):
        """
        This functions is extremely similar to
        `test_overwrite_same_size_later_to_earlier()` but it is much
        easier to understand individually when they are split.

        Again test overwrite setting for every possible combination,
        but this time swap the transfer function direction such that
        the later file is transferred onto the earlier file. This
        should transfer both in the 'if_source_newer' and 'always' case.
        """
        path_earlier, path_later = self.setup_overwrite_file_tests(
            upload_or_download, top_level_folder, project
        )

        assert os.path.getsize(path_earlier) == os.path.getsize(path_later)

        swapped_direction = (
            "download" if upload_or_download == "upload" else "upload"
        )
        transfer_func = test_utils.get_transfer_func(
            project, swapped_direction, transfer_method, top_level_folder
        )

        if transfer_method == "custom":
            transfer_func(
                top_level_folder,
                "all",
                "all",
                "all",
                overwrite_existing_files=overwrite_existing_files,
            )
        else:
            transfer_func(overwrite_existing_files=overwrite_existing_files)

        if overwrite_existing_files == "never":
            # The newer file is not transferred
            assert test_utils.read_file(path_earlier) == ["file earlier"]
        elif overwrite_existing_files in ["if_source_newer", "always"]:
            # The newer file is transferred
            assert test_utils.read_file(path_earlier) == ["file laterxx"]

    @pytest.mark.parametrize(
        "overwrite_existing_files", ["never", "always", "if_source_newer"]
    )
    def test_overwrite_different_size_different_times(
        self, project, overwrite_existing_files
    ):
        """
        Quick additional test to confirm that "if_source_newer" will still
        not transfer even if the older file is larger. This is the expected
        behaviour from rclone, this is confidence check on understanding.
        """
        local_file_path, central_file_path = (
            self.get_paths_to_a_local_and_central_file(project, "rawdata")
        )

        # Write a local file and transfer
        test_utils.write_file(local_file_path, contents="file earlier")
        time.sleep(1)
        test_utils.write_file(
            central_file_path, contents="file laterxx bigger"
        )

        assert os.path.getsize(local_file_path) < os.path.getsize(
            central_file_path
        )
        assert os.path.getmtime(local_file_path) < os.path.getmtime(
            central_file_path
        )

        project.upload_rawdata(
            overwrite_existing_files=overwrite_existing_files
        )
        if overwrite_existing_files in ["never", "if_source_newer"]:
            # so they are different in size, but `if_source_newer` will still not transfer.
            assert test_utils.read_file(central_file_path) == [
                "file laterxx bigger"
            ]
        elif overwrite_existing_files == "always":
            assert test_utils.read_file(central_file_path) == ["file earlier"]

    def get_paths_to_a_local_and_central_file(self, project, top_level_folder):
        path_to_test_file = (
            Path(top_level_folder)
            / "sub-001"
            / "ses-001"
            / "anat"
            / "test_file.txt"
        )

        local_file_path = project.cfg["local_path"] / path_to_test_file
        central_file_path = project.cfg["central_path"] / path_to_test_file

        return local_file_path, central_file_path

    def setup_overwrite_file_tests(
        self, upload_or_download, top_level_folder, project
    ):
        """"""
        local_file_path, central_file_path = (
            self.get_paths_to_a_local_and_central_file(
                project, top_level_folder
            )
        )

        # Write a local file and transfer
        if upload_or_download == "upload":
            path_earlier = local_file_path
            path_later = central_file_path
        else:
            path_earlier = central_file_path
            path_later = local_file_path

        test_utils.write_file(path_earlier, contents="file earlier")
        time.sleep(1)
        test_utils.write_file(path_later, contents="file laterxx")

        assert os.path.getmtime(path_earlier) < os.path.getmtime(path_later)

        return path_earlier, path_later

    @pytest.mark.parametrize("top_level_folder", ["rawdata", "derivatives"])
    @pytest.mark.parametrize(
        "transfer_method", ["entire_project", "top_level_folder", "custom"]
    )
    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    def test_dry_run(
        self, project, top_level_folder, transfer_method, upload_or_download
    ):
        """
        Just do a quick functional test on dry-run that indeed nothing
        is transferred across all top-level-folder / upload-download
        methods.
        """
        local_file_path, _ = self.get_paths_to_a_local_and_central_file(
            project, "rawdata"
        )

        test_utils.write_file(local_file_path, contents="test contents")

        project.upload_rawdata(dry_run=True)

        transfer_func = test_utils.get_transfer_func(
            project, upload_or_download, transfer_method, top_level_folder
        )

        if transfer_method == "custom":
            transfer_func(top_level_folder, "all", "all", "all", dry_run=True)
        else:
            transfer_func(dry_run=True)

        assert len(list(project.cfg["central_path"].glob("*"))) == 0

    @pytest.mark.parametrize("top_level_folder", ["rawdata", "derivatives"])
    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    @pytest.mark.parametrize("transfer_file", [True, False])
    def test_specific_file_or_folder(
        self,
        project,
        top_level_folder,
        transfer_file,
        upload_or_download,
    ):
        """
        Test upload_specific_folder_or_file() and download_specific_folder_or_file().

        Make a project with two different files (just to
        ensure non-target files are not transferred). Transfer
        a single file or the folder containing the file. Check that
        the transferred folders and no others were transferred.
        """
        (
            path_to_test_file_behav,
            path_to_test_file_ephys,
        ) = self.setup_specific_file_or_folder_files(project, top_level_folder)

        if upload_or_download == "upload":
            transfer_function = project.upload_specific_folder_or_file
            transfer_from = "local_path"
            transfer_to = "central_path"
        else:
            transfer_function = project.download_specific_folder_or_file
            transfer_from = "central_path"
            transfer_to = "local_path"
            test_utils.swap_local_and_central_paths(project)

        if transfer_file:
            to_transfer = path_to_test_file_behav
            formatted_to_transfer = to_transfer
        else:
            to_transfer = path_to_test_file_ephys
            formatted_to_transfer = to_transfer.parents[0] / "**"

        transfer_function(project.cfg[transfer_from] / formatted_to_transfer)

        transferred_files = [
            path_
            for path_ in project.cfg[transfer_to].glob("**/*")
            if ".datashuttle" not in str(path_)
        ]
        to_test_against = [
            project.cfg[transfer_to] / path_
            for path_ in reversed(to_transfer.parents)
        ][1:] + [project.cfg[transfer_to] / to_transfer]

        assert transferred_files == to_test_against

    def setup_specific_file_or_folder_files(self, project, top_level_folder):
        """ """
        project.create_folders(
            top_level_folder,
            ["sub-001", "sub-002"],
            "ses-003",
            ["behav", "ephys"],
        )

        path_to_test_file_behav = (
            Path(top_level_folder)
            / "sub-002"
            / "ses-003"
            / "behav"
            / "behav_test_file.txt"
        )

        path_to_test_file_ephys = (
            Path(top_level_folder)
            / "sub-002"
            / "ses-003"
            / "ephys"
            / "ephys_test_file.txt"
        )

        test_utils.write_file(
            project.cfg["local_path"] / path_to_test_file_behav
        )
        test_utils.write_file(
            project.cfg["local_path"] / path_to_test_file_ephys
        )

        return path_to_test_file_behav, path_to_test_file_ephys
