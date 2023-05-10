import subprocess
from pathlib import Path
from subprocess import CompletedProcess

from datashuttle.configs.config_class import Configs
from datashuttle.utils import utils


def call_rclone(command: str, pipe_std: bool = False) -> CompletedProcess:
    """
    Call rclone with the specified command. Current mode is double-verbose.
    Return the completed process from subprocess.

    Parameters
    ----------
    command: Rclone command to be run

    pipe_std: if True, do not output anything to stdout.
    """
    command = "rclone " + command
    if pipe_std:
        output = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
    else:
        output = subprocess.run(command, shell=True)

    return output


def setup_remote_as_rclone_target(
    connection_method: str,
    cfg: Configs,
    rclone_config_name: str,
    ssh_key_path: Path,
    log: bool = True,
) -> None:
    """
    RClone sets remote targets in a config file. When
    copying to remote, use the syntax remote: to
    identify the remote to copy to.

    For local filesystem, this is just a placeholder and
    the config contains no further information.

    For SSH, this contains information for
    connecting to remote with SSH.

    Parameters
    ----------

    cfg : datashuttle configs UserDict

    rclone_config_name : rclone config name
        generated by datashuttle.cfg.get_rclone_config_name()

    ssh_key_path : path to the ssh key used for connecting to
        ssh remote filesystem, if config "connection_method" is "ssh"

    log : whether to log, if True logger must already be initialised.
    """
    if connection_method == "local_filesystem":
        call_rclone(f"config create {rclone_config_name} local", pipe_std=True)

    elif connection_method == "ssh":

        call_rclone(
            f"config create "
            f"{rclone_config_name} "
            f"sftp "
            f"host {cfg['remote_host_id']} "
            f"user {cfg['remote_host_username']} "
            f"port 22 "
            f"key_file {ssh_key_path.as_posix()}",
            pipe_std=True,
        )

    output = call_rclone("config file", pipe_std=True)

    if log:
        utils.log(
            f"Successfully created rclone config. "
            f"{output.stdout.decode('utf-8')}"
        )


def check_rclone_with_default_call() -> bool:
    """
    Check to see whether rclone is installed.
    """
    try:
        output = call_rclone("-h", pipe_std=True)
    except FileNotFoundError:
        return False
    return True if output.returncode == 0 else False


def prompt_rclone_download_if_does_not_exist() -> None:
    """
    Check that rclone is installed. If it does not
    (e.g. first time using datashuttle) then download.
    """
    if not check_rclone_with_default_call():
        raise BaseException(
            "RClone installation not found. Install by entering "
            "the following into your terminal:\n"
            " conda install -c conda-forge rclone"
        )


def transfer_data(
    cfg: Configs,
    upload_or_download: str,
    include_list: list,
    rclone_options: dict,
) -> subprocess.CompletedProcess:
    """ """
    local_filepath = cfg.get_base_folder("local").as_posix()
    remote_filepath = cfg.get_base_folder("remote").as_posix()

    extra_arguments = handle_rclone_arguments(
        rclone_options, include_list
    )  # TODO: fix this is not a list

    if upload_or_download == "upload":

        output = call_rclone(
            f"{rclone_args('copy')} "
            f'"{local_filepath}" "{cfg.get_rclone_config_name()}:{remote_filepath}" {extra_arguments}',
            pipe_std=True,
        )

    elif upload_or_download == "download":

        output = call_rclone(
            f"{rclone_args('copy')} "
            f'"{cfg.get_rclone_config_name()}:{remote_filepath}" "{local_filepath}"  {extra_arguments}',
            pipe_std=True,
        )

    return output


def handle_rclone_arguments(rclone_options, include_list):
    """
    Construct the extra arguments to pass to RClone based on the
    current configs.
    """
    extra_arguments_list = [rclone_args("create_empty_src_dirs")]

    extra_arguments_list += ["-" + rclone_options["transfer_verbosity"]]

    if not rclone_options["overwrite_old_files"]:
        extra_arguments_list += [rclone_args("ignore_existing")]

    if rclone_options["show_transfer_progress"]:
        extra_arguments_list += [rclone_args("progress")]

    if rclone_options["dry_run"]:
        extra_arguments_list += [rclone_args("dry_run")]

    extra_arguments_list += include_list

    extra_arguments = " ".join(extra_arguments_list)

    return extra_arguments


def rclone_args(name: str) -> str:
    """
    Central function to hold rclone commands
    """
    if name == "dry_run":
        arg = "--dry-run"

    if name == "create_empty_src_dirs":
        arg = "--create-empty-src-dirs"

    if name == "copy":
        arg = "copy"

    if name == "ignore_existing":
        arg = "--ignore-existing"

    if name == "progress":
        arg = "--progress"

    return arg
