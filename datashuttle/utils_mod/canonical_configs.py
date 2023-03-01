"""
This module contains all information for the required
format of the configs class. This is clearly defined
as configs can be provided from file or input dynamically
and so careful checks must be done.

If adding a new config, first add the key to
get_canonical_config_dict( and type to
get_canonical_config_required_types()
"""

from pathlib import Path
from typing import Union, get_args

from datashuttle.utils_mod import canonical_configs, utils


def get_canonical_config_dict():
    """
    The only permitted keys in the
    DataShuttle config.
    """
    config_dict = {
        "local_path": None,
        "remote_path": None,
        "connection_method": None,
        "remote_host_id": None,
        "remote_host_username": None,
        "use_ephys": None,
        "use_behav": None,
        "use_imaging": None,
        "use_histology": None,
    }
    return config_dict


def get_experiment_types():
    return ["use_ephys", "use_behav", "use_imaging", "use_histology"]


def get_canonical_config_required_types():
    """
    The only permitted types for DataShuttle
    config values.
    """
    required_types = {
        "local_path": Union[str, Path],
        "remote_path": Union[str, Path],
        "connection_method": str,
        "remote_host_id": Union[str, None],
        "remote_host_username": Union[str, None],
        "use_ephys": bool,
        "use_behav": bool,
        "use_imaging": bool,
        "use_histology": bool,
    }

    assert (
        required_types.keys() == get_canonical_config_dict().keys()
    ), "update get_canonical_config_required_types with required types."

    return required_types


def check_dict_values_and_inform_user(config_dict):
    """
    Central function for performing checks on a
    DataShuttle Configs UserDict class. This should
    be run after any change to the configs (e.g.
    make_config_file, update_config, supply_config_file).

    This will raise assert if condition is not met.
    """
    canonical_dict = get_canonical_config_dict()

    for key in canonical_dict.keys():
        if key not in config_dict.keys():
            utils.raise_error(
                f"Loading Failed. The key {key} was not "
                f"found in the supplied config. "
                f"Config file was not updated."
            )

    for key in config_dict.keys():
        if key not in canonical_dict.keys():
            utils.raise_error(
                f"The supplied config contains an invalid key: {key}. "
                f"Config file was not updated."
            )

    check_config_types(config_dict)

    if list(config_dict.keys()) != list(canonical_dict.keys()):
        utils.raise_error(
            f"New config keys are in the wrong order. The"
            f" order should be: {canonical_dict.keys()}"
        )

    if config_dict["connection_method"] not in ["ssh", "local_filesystem"]:
        utils.raise_error("connection method must be ssh or local")

    if config_dict["remote_path"].as_posix()[0] == "~":
        utils.raise_error(
            "remote_path must contain the full directory path "
            "with no ~ syntax"
        )

    if not any([config_dict[key] for key in get_experiment_types()]):
        utils.raise_error(
            f"At least one experiment_type must be True in "
            f"configs, from: {' '.join(get_experiment_types())}"
        )

    # Check SSH settings
    if config_dict["connection_method"] == "ssh" and (
        not config_dict["remote_host_id"]
        or not config_dict["remote_host_username"]
    ):
        utils.raise_error(
            "remote_host_id and remote_host_username are "
            "required if connection_method is ssh."
        )


def handle_cli_or_supplied_config_bools(dict_):
    """
    For supplied configs for CLI input args,
    in some instances bools will as string type.
    Handle this case here to cast to correct type.
    """
    for key in dict_.keys():
        dict_[key] = canonical_configs.handle_bool(key, dict_[key])
    return dict_


def handle_bool(key, value):
    """ """
    if key in [
        "use_ephys",
        "use_behav",
        "use_imaging",
        "use_histology",
    ]:

        if value in ["None", "none", None]:
            value = False

        if isinstance(value, str):
            if value not in ["True", "False", "true", "false"]:
                utils.raise_error(
                    f"Input value for {key} " f"must be True or False"
                )

            value = value in ["True", "true"]

    elif value in ["None", "none"]:
        value = None

    return value


def check_config_types(config_dict):
    """
    Check the type of passed configs matched canonical types.
    This is a little awkward as testing types against
    Union is not neat. To do this you can use
    isinstance(type, get_args(Union[types])).
    But get_args() will be empty if there is only
    one type in union. So we need to test the
    two cases explicitly.
    """
    required_types = get_canonical_config_required_types()
    fail_type = False

    for key in config_dict.keys():
        if len(get_args(required_types[key])) == 0:
            if not isinstance(config_dict[key], required_types[key]):
                fail_type = required_types[key]
        else:
            if not isinstance(config_dict[key], get_args(required_types[key])):
                fail_type = get_args(required_types[key])

        if fail_type:
            utils.raise_error(
                f"The type of the value at {key} is incorrect, "
                f"it must be {fail_type}. "
                f"Config file was not updated."
            )
