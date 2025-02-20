import copy
import glob
import logging
import os
import pathlib
import shutil
import warnings
from os.path import join
from pathlib import Path

import yaml
from file_conflicts_pathtable import get_pathtable

from datashuttle import DataShuttle
from datashuttle.configs import canonical_configs, canonical_folders
from datashuttle.utils import ds_logger, rclone

# -----------------------------------------------------------------------------
# Setup and Teardown Test Project
# -----------------------------------------------------------------------------


def setup_project_default_configs(
    project_name,
    tmp_path,
    local_path=False,
    central_path=False,
):
    """
    Set up a fresh project to test on

    local_path / central_path: provide the config paths to set
    """
    delete_project_if_it_exists(project_name)

    warnings.filterwarnings("ignore")

    project = DataShuttle(project_name)

    default_configs = get_test_config_arguments_dict(
        tmp_path, project_name, set_as_defaults=True
    )

    #  make_project_paths(default_configs)

    project.make_config_file(**default_configs)

    rclone.setup_rclone_config_for_ssh(
        project.cfg,
        project.cfg.get_rclone_config_name("ssh"),
        project.cfg.ssh_key_path,
    )

    warnings.filterwarnings("default")

    if local_path:
        os.makedirs(local_path, exist_ok=True)
        project.update_config_file(local_path=local_path)

        delete_all_folders_in_local_path(project)
        project.cfg.make_and_get_logging_path()

    if central_path:
        os.makedirs(central_path, exist_ok=True)
        project.update_config_file(central_path=central_path)
        delete_all_folders_in_project_path(project, "central")
        project.cfg.make_and_get_logging_path()

    return project


def make_project_paths(config_dict):
    for path_name in ["local_path", "central_path"]:
        os.makedirs(config_dict[path_name], exist_ok=True)


def glob_basenames(search_path, recursive=False, exclude=None):
    """
    Use glob to search but strip the full path, including
    only the base name (lowest level).
    """
    paths_ = glob.glob(search_path, recursive=recursive)
    basenames = [os.path.basename(path_) for path_ in paths_]

    if exclude:
        basenames = [name for name in basenames if name not in exclude]

    return sorted(basenames)


def teardown_project(
    cwd, project
):  # 99% sure these are unnecessary with pytest tmp_path but keep until SSH testing.
    """"""
    os.chdir(cwd)
    delete_all_folders_in_project_path(project, "central")
    delete_all_folders_in_project_path(project, "local")
    delete_project_if_it_exists(project.project_name)


def delete_all_folders_in_local_path(project):
    ds_logger.close_log_filehandler()
    if project.cfg["local_path"].is_dir():
        shutil.rmtree(project.cfg["local_path"])


def delete_all_folders_in_project_path(project, local_or_central):
    """"""
    folder = f"{local_or_central}_path"

    if folder == "central_path" and project.cfg[folder] is None:
        return

    ds_logger.close_log_filehandler()
    if project.cfg[folder].is_dir() and project.cfg[folder].stem in [
        "local",
        "central",
    ]:
        shutil.rmtree(project.cfg[folder])


def delete_project_if_it_exists(project_name):
    """"""
    config_path, _ = canonical_folders.get_project_datashuttle_path(
        project_name
    )
    if config_path.is_dir():
        ds_logger.close_log_filehandler()
        shutil.rmtree(config_path)


def setup_project_fixture(tmp_path, test_project_name, project_type="full"):
    """
    Set up a project, either in full mode or local-only mode. This is
    very similar to the `BaseTest` fixture but is designed for
    use in other fixtures that require additional boilerplate e.g. logging.
    """
    if project_type == "full":
        project = setup_project_default_configs(
            test_project_name,
            tmp_path,
            local_path=make_test_path(tmp_path, "local", test_project_name),
            central_path=make_test_path(
                tmp_path, "central", test_project_name
            ),
        )
    elif project_type == "local":
        project = DataShuttle(test_project_name)
        project.make_config_file(
            local_path=make_test_path(tmp_path, "local", test_project_name)
        )

    cwd = os.getcwd()

    return project, cwd


def make_test_path(base_path, local_or_central, test_project_name):
    return Path(base_path) / local_or_central / test_project_name


def create_all_pathtable_files(pathtable):
    """ """
    for i in range(pathtable.shape[0]):
        filepath = pathtable["base_folder"][i] / pathtable["path"][i]
        filepath.parents[0].mkdir(parents=True, exist_ok=True)
        write_file(filepath, contents="test_entry")


def quick_create_project(base_path):
    pathtable = get_pathtable(base_path)
    create_all_pathtable_files(pathtable)


# -----------------------------------------------------------------------------
# Test Configs
# -----------------------------------------------------------------------------


def get_test_config_arguments_dict(
    tmp_path,
    project_name,
    set_as_defaults=False,
    required_arguments_only=False,
):
    """
    Retrieve configs, either the required configs
    (for project.make_config_file()), all configs (default)
    or non-default configs. Note that default configs here
    are the expected default arguments in project.make_config_file().

    Include spaces in path so this case is always checked
    """
    tmp_path = Path(tmp_path).as_posix()

    dict_ = {
        "local_path": f"{tmp_path}/not/a/re al/local/folder/{project_name}",
        "central_path": f"{tmp_path}/a/re al/central_ local/folder/{project_name}",
        "connection_method": "local_filesystem",
    }
    make_project_paths(dict_)

    if required_arguments_only:
        return dict_

    if set_as_defaults:
        dict_.update(
            {
                "central_host_id": None,
                "central_host_username": None,
            }
        )
    else:
        dict_.update(
            {
                "local_path": f"{tmp_path}/test/test_ local/test_edit/{project_name}",
                "central_path": f"{tmp_path}/nfs/test folder/test_edit2/{project_name}",
                "connection_method": "ssh",
                "central_host_id": "test_central_host_id",
                "central_host_username": "test_central_host_username",
            }
        )
        make_project_paths(dict_)

    return dict_


def get_all_broad_folders_used(value=True):
    """
    The `folders_used` construct tells the tests which
    folders were used (e.g. created or transferred) and
    which are not. This means the expected datatypes
    can be checked.

    When we want to get the broad folders used, we set all
    broad datatypes to `True` and all narrow datatype names to `False`.
    """
    broad_datatypes = {
        name: value for name in canonical_configs.get_broad_datatypes()
    }
    narrow_datatypes_off = {
        name: False for name in canonical_configs.quick_get_narrow_datatypes()
    }
    return broad_datatypes | narrow_datatypes_off


# -----------------------------------------------------------------------------
# Folder Checkers
# -----------------------------------------------------------------------------


def check_folder_tree_is_correct(
    base_folder, subs, sessions, folder_used, created_folder_dict=None
):
    """
    Automated test that folders are made based
    on the structure specified on project itself.

    Cycle through all datatypes (defined in
    canonical_folders.get_datatype_folders(), sub, sessions and check that
    the expected file exists. For  subfolders, recursively
    check all exist.

    The folder_used variable must be passed so we don't
    rely on project settings itself, as this doesn't explicitly test this.

    `created_folder_dict` is used to test the output of `create_folders`.
    """
    if created_folder_dict is None:
        created_folder_dict = {}

    for sub in subs:
        path_to_sub_folder = join(base_folder, sub)
        check_and_cd_folder(path_to_sub_folder)

        for ses in sessions:
            path_to_ses_folder = join(base_folder, sub, ses)
            check_and_cd_folder(path_to_ses_folder)

            for (
                key,
                folder,
            ) in canonical_folders.get_datatype_folders().items():
                assert key in folder_used.keys(), (
                    "Key not found in folder_used. "
                    "Update folder used and hard-coded tests: "
                    "test_custom_folder_names(), test_explicitly_session_list()"
                )

                assert folder.level in ["sub", "ses"]

                if folder.level == "sub":
                    datatype_path = join(path_to_sub_folder, folder.name)
                elif folder.level == "ses":
                    datatype_path = join(path_to_ses_folder, folder.name)

                if folder_used[key]:
                    check_and_cd_folder(datatype_path)

                    # Check the created path is found only in the expected
                    # dict entry.
                    for (
                        datatype_name,
                        all_datatype_paths,
                    ) in created_folder_dict.items():
                        if datatype_name == key:
                            assert Path(datatype_path) in all_datatype_paths
                        else:
                            assert (
                                Path(datatype_path) not in all_datatype_paths
                            )
                else:
                    assert not os.path.isdir(datatype_path)
                    assert key not in created_folder_dict


def check_and_cd_folder(path_):
    """
    Check a folder exists and CD to it if it does.

    Use the pytest -s flag to print all tested paths
    """
    assert os.path.isdir(path_)
    os.chdir(path_)


def check_datatype_sub_ses_uploaded_correctly(
    base_path_to_check,
    datatype_to_transfer,
    subs_to_upload=None,
    ses_to_upload=None,
):
    """
    Iterate through the project (datatype > ses > sub) and
    check that the folders at each level match those that are
    expected (passed in datatype / sub / ses to upload). Folders
    are searched with wildcard glob.

    Note: might be easier to flatten entire path with glob(**)
    then search...
    """
    if subs_to_upload:
        sub_names = glob_basenames(join(base_path_to_check, "*"))
        assert sub_names == sorted(subs_to_upload)

        # Check ses are all uploaded
        if ses_to_upload:
            for sub in subs_to_upload:
                ses_names = glob_basenames(
                    join(
                        base_path_to_check,
                        sub,
                        "*",
                    )
                )
                assert ses_names == sorted(ses_to_upload)

                # check datatype folders in session folder
                if datatype_to_transfer:
                    for ses in ses_names:
                        data_names = glob_basenames(
                            join(base_path_to_check, sub, ses, "*")
                        )
                        assert data_names == sorted(datatype_to_transfer)


def make_and_check_local_project_folders(
    project, top_level_folder, subs, sessions, datatype, datatypes_used=None
):
    """
    Make a local project folder tree with the specified datatype,
    subs, sessions and check it is made successfully.

    Since empty folders are not transferred, it is necessary
    to write a placeholder file in all bottom-level
    directories so ensure they are transferred.
    """
    if datatypes_used is None:
        datatypes_used = get_all_broad_folders_used()

    make_local_folders_with_files_in(
        project, top_level_folder, subs, sessions, datatype
    )

    check_folder_tree_is_correct(
        get_top_level_folder_path(project, "local", top_level_folder),
        subs,
        sessions,
        datatypes_used,
    )


def make_local_folders_with_files_in(
    project, top_level_folder, subs, sessions=None, datatype=""
):
    project.create_folders(top_level_folder, subs, sessions, datatype)
    for root, dirs, _ in os.walk(project.cfg["local_path"]):
        if not dirs:
            path_ = Path(root) / "placeholder_file.txt"
            write_file(path_, contents="placeholder")


# -----------------------------------------------------------------------------
# Config Checkers
# -----------------------------------------------------------------------------


def check_configs(project, kwargs, config_path=None):
    """"""
    if config_path is None:
        config_path = project._config_path

    if not config_path.is_file():
        raise FileNotFoundError("Config file not found.")

    check_project_configs(project, kwargs)
    check_config_file(config_path, kwargs)


def check_project_configs(
    project,
    *kwargs,
):
    """
    Core function for checking the config against
    provided configs (kwargs). Open the config.yaml file
    and check the config values stored there,
    and in project.cfg, against the provided configs.

    Paths are stored as pathlib in the cfg but str in the .yaml
    """
    for arg_name, value in kwargs[0].items():
        if arg_name in canonical_configs.keys_str_on_file_but_path_in_class():
            assert type(project.cfg[arg_name]) in [
                pathlib.PosixPath,
                pathlib.WindowsPath,
            ]
            assert value == project.cfg[arg_name].as_posix()

        else:
            assert value == project.cfg[arg_name], f"{arg_name}"


def check_config_file(config_path, *kwargs):
    """"""
    with open(config_path, "r") as config_file:
        config_yaml = yaml.full_load(config_file)

        for name, value in kwargs[0].items():
            assert value == config_yaml[name], f"{name}"


# -----------------------------------------------------------------------------
# Test Helpers
# -----------------------------------------------------------------------------


def get_top_level_folder_path(
    project, local_or_central="local", folder_name="rawdata"
):
    """"""

    assert (
        folder_name in canonical_folders.get_top_level_folders()
    ), "folder_name must be canonical e.g. rawdata"

    if local_or_central == "local":
        base_path = project.cfg["local_path"]
    else:
        base_path = project.cfg["central_path"]

    return base_path / folder_name


def handle_upload_or_download(
    project,
    upload_or_download,
    transfer_method,
    top_level_folder=None,
    swap_last_folder_only=False,
):
    """
    To keep things consistent and avoid the pain of writing
    files over SSH, to test download just swap the central
    and local server (so things are still transferred from
    local machine to central, but using the download function).

    Also returns the transfer method, if 'transfer_method="top_level_folder"`
    then the `top_level_folder` is used to determine the method,
    otherwise it is not used.
    """
    if upload_or_download == "download":
        central_path = swap_local_and_central_paths(
            project, swap_last_folder_only
        )
    else:
        central_path = project.cfg["central_path"]

    transfer_function = get_transfer_func(
        project, upload_or_download, transfer_method, top_level_folder
    )

    return transfer_function, central_path


def get_transfer_func(
    project, upload_or_download, transfer_method, top_level_folder=None
):
    """"""
    if transfer_method == "top_level_folder":
        assert top_level_folder is not None, "must pass top-level-folder"
    assert top_level_folder in [None, "rawdata", "derivatives"]

    if upload_or_download == "download":
        if transfer_method == "entire_project":
            transfer_function = project.download_entire_project
        elif transfer_method == "top_level_folder":
            if top_level_folder == "rawdata":
                transfer_function = project.download_rawdata
            else:
                transfer_function = project.download_derivatives
        else:
            transfer_function = project.download_custom
    else:
        if transfer_method == "entire_project":
            transfer_function = project.upload_entire_project
        elif transfer_method == "top_level_folder":
            if top_level_folder == "rawdata":
                transfer_function = project.upload_rawdata
            else:
                transfer_function = project.upload_derivatives
        else:
            transfer_function = project.upload_custom

    return transfer_function


def swap_local_and_central_paths(project, swap_last_folder_only=False):
    """
    When testing upload vs. download, the most convenient way
    to test download is to swap the paths. In this case, we 'download'
    from local to central. It much simplifies creating the folders
    to transfer (which are created locally), and is fully required
    in tests with session scope fixture, in which a local project
    is made only once and repeatedly transferred.

    Typically, this is as simple as swapping central and local.
    For SSH test however, we want to use SSH to search the 'central'
    filesystem to find the necsesary files / folders to transfer.
    As such, the 'local' (which we are downloading from) must be the SSH
    path. As such, in this case we only want to swap the last folder only
    (i.e. "local" and "central"). In this case, we download from
    cfg["central_path"] (which is ssh_path/local) to cfg["local_path"]
    (which is filesystem/central).
    """
    local_path = copy.deepcopy(project.cfg["local_path"])
    central_path = copy.deepcopy(project.cfg["central_path"])

    os.makedirs(central_path, exist_ok=True)

    if swap_last_folder_only:
        new_local_path = local_path.parent / central_path.name
        os.makedirs(new_local_path, exist_ok=True)

        project.update_config_file(local_path=new_local_path)
        project.update_config_file(
            central_path=central_path.parent / local_path.name
        )
    else:
        os.makedirs(local_path, exist_ok=True)
        os.makedirs(central_path, exist_ok=True)

        project.update_config_file(local_path=central_path)
        project.update_config_file(central_path=local_path)

    return central_path


def get_default_sub_sessions_to_test():
    """
    Canonical subs / sessions for these tests
    """
    subs = ["sub-001", "sub-002", "sub-003"]
    sessions = ["ses-001_datetime-20220516T135022", "ses-002", "ses-003"]
    return subs, sessions


def move_some_keys_to_end_of_dict(config):
    """
    Need to move connection method to the end
    so ssh opts are already set before it is changed.
    """
    config["connection_method"] = config.pop("connection_method")


def clear_capsys(capsys):
    """
    read from capsys clears it, so new
    print statements are clearer to read.
    """
    capsys.readouterr()


def write_file(path_, contents="", append=False):
    key = "a" if append else "w"

    if not path_.parent.is_dir():
        os.makedirs(path_.parent, exist_ok=True)

    with open(path_, key) as file:
        file.write(contents)


def read_file(path_):
    with open(path_, "r") as file:
        contents = file.readlines()
    return contents


def set_datashuttle_loggers(disable):
    """
    Turn off or on datashuttle logs, if these are
    on when testing with pytest they will be propagated
    to pytest's output, making it difficult to read.

    As such, these are turned off for all tests
    (in conftest.py)  and dynamically turned on in setup
    of test_logging.py and turned back off during
    tear-down.
    """
    for name in [ds_logger.get_logger_name(), "rich"]:
        logger = logging.getLogger(name)
        logger.disabled = disable


def check_working_top_level_folder_only_exists(
    folder_name, base_path_to_check, subs, sessions, folders_used=None
):
    """
    Check that the folder tree made in the 'folder_name'
    (e.g. 'rawdata') top level folder is correct. Additionally,
    check that no other top-level folders exist. This is to ensure
    that folders made / transferred from one top-level folder
    do not inadvertently transfer other top-level folders.
    """
    if folders_used is None:
        folders_used = get_all_broad_folders_used()

    check_folder_tree_is_correct(
        base_path_to_check,
        subs,
        sessions,
        folders_used,
    )

    # Check other top-level folders are not made
    unused_folders = canonical_folders.get_top_level_folders()
    unused_folders.remove(folder_name)

    for folder in unused_folders:
        assert not (base_path_to_check.parent / folder).is_dir()


def read_log_file(logging_path):
    log_filepath = list(glob.glob(str(logging_path / "*.log")))

    assert len(log_filepath) == 1, (
        f"there should only be one log " f"in log output path {logging_path}"
    )
    log_filepath = log_filepath[0]

    with open(log_filepath, "r") as file:
        log = file.read()

    return log


def delete_log_files(logging_path):
    ds_logger.close_log_filehandler()
    for log in glob.glob((str(logging_path / "*.log"))):
        os.remove(log)
