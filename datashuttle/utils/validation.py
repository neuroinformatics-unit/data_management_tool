from __future__ import annotations

import re
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union, overload

if TYPE_CHECKING:
    from datashuttle.configs.config_class import Configs
    from datashuttle.utils.custom_types import (
        DisplayMode,
        Prefix,
        TopLevelFolder,
    )

from datetime import datetime
from itertools import chain
from pathlib import Path

from datashuttle.configs import canonical_configs, canonical_folders
from datashuttle.utils import formatting, getters, utils
from datashuttle.utils.custom_exceptions import NeuroBlueprintError

# -----------------------------------------------------------------------------
# Formatted Error Messages
# -----------------------------------------------------------------------------


def get_bad_value_error(name, prefix, path_):
    return handle_path(
        f"BAD_VALUE: The value for prefix {prefix} in name {name} is not an integer.",
        path_,
    )


def get_duplicate_prefix_error(name, prefix, path_):
    return handle_path(
        f"DUPLICATE_PREFIX: The name: {name} of contains more than one instance of the prefix {prefix}.",
        path_,
    )


def get_name_error(name, prefix, path_):
    return handle_path(
        f"BAD_NAME: The name: {name} of type: {prefix} is not valid.", path_
    )


def get_special_char_error(name, path_):
    return handle_path(
        f"SPECIAL_CHAR: The name: {name}, contains characters which are not alphanumeric, dash or underscore.",
        path_,
    )


def get_name_format_error(name, path_):
    return handle_path(
        f"NAME_FORMAT: The name {name} does not consist of key-value pairs separated by underscores.",
        path_,
    )


def get_value_length_error(prefix):
    return f"VALUE_LENGTH: Inconsistent value lengths for the prefix: {prefix} were found in the project."


def get_datetime_error(key, name, strfmt, path_):
    return handle_path(
        f"DATETIME: Name {name} contains an invalid {key}. It should be ISO format: {strfmt}.",
        path_,
    )


def get_template_error(name, regexp, path_):
    return handle_path(
        f"TEMPLATE: The name: {name} does not match the template: {regexp}.",
        path_,
    )


def get_missing_top_level_folder_error(path_):
    return handle_path(
        "The local project must contain a 'rawdata' or 'derivatives' folder.",
        path_,
    )


def get_duplicate_name_error(new_name, exist_name, exist_path):
    return f"DUPLICATE_NAME: The prefix for {new_name} duplicates the name : {exist_name} at path: {exist_path}"


def get_datatype_error(datatype_name, path_):
    return handle_path(
        f"DATATYPE: {datatype_name} is not a valid datatype name.", path_
    )


def handle_path(message, path_):
    if path_:
        message += f" Path: {path_}"
    return message


# -----------------------------------------------------------------------------
# Checking a standalone list of names
# -----------------------------------------------------------------------------


def validate_list_of_names(
    path_or_name_list: List[Path] | List[str],
    prefix: Prefix,
    display_mode: DisplayMode = "error",
    name_templates: Optional[Dict] = None,
    log: bool = True,
) -> List[str]:
    """
    Validate a list of subject or session names, ensuring
    they are formatted as per NeuroBlueprint.

    Parameters
    ----------

    path_or_name_list : List[Path]
        A list of pathlib.Path to NeuroBlueprint-formatted folders to validate

    prefix: Prefix
        Whether these are subject (sub) or session (ses) level names

    display_mode: DisplayMode
        If an invalid case is found, whether to raise error or warning

    check_duplicates : bool
        The function `duplicated_prefix_values()` performs a quick check
        for duplicate sub / ses values in the names. However, this will
        raise on any duplicate, see `new_name_duplicates_existing()`
        for a more flexible function used during new folder creation.

    log: bool
        If `True`, output will also be logged to "datashuttle" logger.

    Notes
    ------
    Each subfunction called in this function loops over the entire
    list of names. This is done in this way so each subfunction
    is modular. However for large projects this may become slow.
    """
    if len(path_or_name_list) == 0:
        return []

    error_messages = []

    for path_or_name in path_or_name_list:

        path_, name = get_path_and_name(path_or_name)

        def prefix_is_duplicate_or_has_bad_values(name, prefix, path_):
            """ """
            value = utils.get_value_from_key_regexp(name, prefix)

            if len(value) == 0:
                return ["NO VALUE ERROR"]

            if len(value) > 1:
                return [get_duplicate_prefix_error(name, prefix, path_)]

            try:
                int(value[0])
                return []
            except ValueError:
                return [get_bad_value_error(name, prefix, path_)]

        error_messages += prefix_is_duplicate_or_has_bad_values(
            name, prefix, path_
        )
        error_messages += name_begins_with_bad_key(name, prefix, path_)
        error_messages += names_include_special_characters(name, path_)
        error_messages += dashes_and_underscore_alternate_incorrectly(
            name, path_
        )
        error_messages += datetime_are_iso_format(name, path_)
        error_messages + names_dont_match_templates(
            name, path_, prefix, name_templates
        )

    # both of these are O(n^2)
    stripped_path_or_names_list = strip_invalid_names(
        path_or_name_list, prefix
    )  # TODO

    for path_or_name in stripped_path_or_names_list:

        path_, name = get_path_and_name(path_or_name)

        error_messages += new_name_duplicates_existing(
            name, stripped_path_or_names_list, prefix
        )

        error_messages += value_lengths_are_inconsistent(
            stripped_path_or_names_list, prefix
        )

    """
    # new_name_duplicates_existing
    # value_lengths_are_inconsistent

    tests_to_run = [
        lambda: name_begins_with_bad_key(path_or_name_list, prefix),
        lambda: names_include_special_characters(path_or_name_list),
        lambda: dashes_and_underscore_alternate_incorrectly(path_or_name_list),
        lambda: datetime_are_iso_format(path_or_name_list),
        lambda: names_dont_match_templates(
            path_or_name_list, prefix, name_templates
        ),
        lambda: value_lengths_are_inconsistent(path_or_name_list, prefix),
    ]
    if check_duplicates:
        tests_to_run += [
            lambda: duplicated_prefix_values(path_or_name_list, prefix)
        ]

    all_error_messages = []

    for test in tests_to_run:

        error_messages = test()

        for message in error_messages:
            raise_display_mode(
                message, display_mode, log
            )  # check logging here, will log error per file?

        all_error_messages += error_messages

    """

    return error_messages


def new_name_duplicates_existing(
    new_name: str,
    existing_path_or_name_list: List[Path] | List[str],
    prefix: Prefix,
) -> List[str]:
    """
    Check that a subject or session does not already exist
    that shares a sub / ses id with the new_name.

    When creating new subject or session files, if the
    sub or ses id already exists, the full subject or session
    name should match exactly.

    For example, if "sub-001" exists, we can pass
    "sub-001" as a valid subject name (for example, when making sessions).
    However, if "sub-001_another-tag" exists, we should throw an
    error, because this shares the same subject id but refers to
    a different subject.
    """
    # Make a list of matches between `new_name` and any in `existing_names`
    new_name_id = utils.get_values_from_bids_formatted_name(
        [new_name], prefix, return_as_int=True
    )[0]

    error_messages = []
    for exist_path_or_name in existing_path_or_name_list:

        exist_path, exist_name = get_path_and_name(exist_path_or_name)

        exist_name_id = utils.get_values_from_bids_formatted_name(
            [exist_name], prefix, return_as_int=True
        )[0]

        if exist_name_id == new_name_id:
            if new_name != exist_name:
                message = get_duplicate_name_error(
                    new_name, exist_name, exist_path
                )
                error_messages.append(message)

    return error_messages


def names_dont_match_templates(
    name: str,
    path_: Path | None,
    prefix: Prefix,
    name_templates: Optional[Dict] = None,
) -> List[str]:
    """
    Test a list of subject or session names against
    the respective `name_templates`, a regexp template.

    If checking `name_templates` is on, an invalid result will be given if the
    name does not re.fullmatch the regexp.
    """
    if name_templates is None:
        return []

    if name_templates["on"] is False:
        return []

    regexp = name_templates[prefix]

    if regexp is None:
        return []

    regexp = replace_tags_in_regexp(regexp)

    if not re.fullmatch(regexp, name):
        return [get_template_error(name, regexp, path_)]
    else:
        return []


def get_path_and_name(path_or_name) -> Tuple[Optional[Path], str]:
    """ """
    if isinstance(path_or_name, Path):
        return path_or_name, path_or_name.name
    else:
        return None, path_or_name


def replace_tags_in_regexp(regexp: str) -> str:
    """
    Before validation, all tags in the names are converted to
    their final values (e.g. @DATE@ -> _date-<date>). We also want to
    allow template to be formatted like `sub-\d\d_@DATE@` as it
    is convenient for auto-completion in the TUI.

    Therefore we must replace the tags in the regexp with their
    actual regexp equivalent before comparison.
    Note `replace_date_time_tags_in_name()` operates in place on a list.
    """
    regexp_list = [regexp]
    date_regexp = "\d\d\d\d\d\d\d\d"
    time_regexp = "\d\d\d\d\d\d"
    formatting.replace_date_time_tags_in_name(
        regexp_list,
        datetime_with_key=formatting.format_datetime(date_regexp, time_regexp),
        date_with_key=formatting.format_date(date_regexp),
        time_with_key=formatting.format_time(time_regexp),
    )
    return regexp_list[0]


def get_names_format(bad_names):
    """
    A convenience function to properly format error messages
    depending on whether there is just 1, or multiple bad names.
    """
    assert len(bad_names) != 0, "`bad_names` should not be empty."
    if len(bad_names) == 1:
        name_str_format = "name"
        bad_names_format = bad_names[0]
    else:
        name_str_format = "names"
        bad_names_format = bad_names

    return f"{name_str_format}: {bad_names_format}"


def name_begins_with_bad_key(
    name: str, prefix: Prefix, path_: Path | None
) -> List[str]:
    """
    Check that a list of NeuroBlueprint names begin
    with the required subject or session.

    Returns `True` if an invalid name was found, along
     with a message detailing the error.
    """
    if name[:4] != f"{prefix}-":
        return [get_name_error(name, prefix, path_)]
    else:
        return []


def names_include_special_characters(
    name: str, path_: Path | None
) -> List[str]:
    """
    Check that a list of NeuroBlueprint formatted
    names do not contain special characters (i.e. characters
    that are not integers, letters, dash or underscore).

    Returns `True` if an invalid name was found, along
    with a message detailing the error.
    """
    if name_has_special_character(name):
        return [get_special_char_error(name, path_)]
    else:
        return []


def name_has_special_character(name: str) -> bool:
    return not re.match("^[A-Za-z0-9_-]*$", name)


def dashes_and_underscore_alternate_incorrectly(
    name: str, path_: Path | None
) -> List[str]:
    """
    Check a list of NeuroBlueprint formatted names
    have the "-" and "-" ordered correctly. Names should be
    key-value pairs separated by underscores e.g.
    sub-001_ses-001.

    Returns `True` if an invalid name was found, along
    with a message detailing the error.
    """
    discrim = {"-": 1, "_": -1}

    dashes_underscores = [discrim[ele] for ele in name if ele in ["-", "_"]]

    underscore_dash_not_interleaved = any(
        [ele == 0 for ele in utils.diff(dashes_underscores)]
    )

    if (
        (dashes_underscores[0] != 1)
        or underscore_dash_not_interleaved
        or (name[-1] in discrim.keys())
    ):
        return [get_name_format_error(name, path_)]
    else:
        return []


def value_lengths_are_inconsistent(
    path_or_names_list: List[Path] | List[str] | List[Path | str],
    prefix: Prefix,
) -> List[str]:
    """
    Given a list of NeuroBlueprint-formatted subject or session
    names, determine if there are inconsistent value lengths for
    the sub or ses key.

    Returns `True` if an invalid name was found, along
    with a message detailing the error.
    """
    # TODO: this is all getting insane...
    names_list = [
        path_or_name if isinstance(path_or_name, str) else path_or_name.name
        for path_or_name in path_or_names_list
    ]

    prefix_values = utils.get_values_from_bids_formatted_name(
        names_list, prefix, return_as_int=False
    )

    value_len = [len(value) for value in prefix_values]

    inconsistent_value_len = value_len != [] and not utils.all_identical(
        value_len
    )

    error_messages = []
    if inconsistent_value_len:
        message = get_value_length_error(prefix)
        error_messages.append(message)

    return error_messages


def datetime_are_iso_format(
    name: str,
    path_: Path | None,
):  # TODO: check all typing, add docs
    """ """
    formats = {
        "datetime": "%Y%m%dT%H%M%S",
        "time": "%H%M%S",
        "date": "%Y%m%d",
    }

    key = next((key for key in formats if key in name), None)

    if not key:
        error_message = []

    else:
        try:
            format_to_check = utils.get_values_from_bids_formatted_name(
                [name], key, return_as_int=False
            )[0]
        except:
            return []

        strfmt = formats[key]

        try:
            datetime.strptime(format_to_check, strfmt)
            error_message = []
        except ValueError:
            error_message = [get_datetime_error(key, name, strfmt, path_)]

    return error_message


def duplicated_prefix_values(
    path_or_names_list: List[Path] | List[str], prefix: Prefix
) -> List[str]:
    """
    Check a list of subject or session names for duplicate
    ids (e.g. not allowing ["sub-001", "sub-001_@DATE@"])

    This is a quick function however it will raise if two
    exact duplicates are in the list (e.g. ["sub-001", "sub-001"]).
    This may happen (e.g. if the same subject is on local and
    central). See `new_name_duplicates_existing()` for a
    function that permits exact matches.

    Returns `True` if an invalid name was found, along
    with a message detailing the error.
    """
    names_list: List[str]
    if isinstance(path_or_names_list[0], Path):
        names_list = [path_.name for path_ in path_or_names_list]  # type: ignore
    else:
        names_list = path_or_names_list  # type: ignore

    int_values = utils.get_values_from_bids_formatted_name(
        names_list, prefix, return_as_int=True
    )

    has_duplicate_ids = not utils.all_unique(int_values)

    error_message = []
    if (
        has_duplicate_ids
    ):  # TODO: this is an edge case that is only relevant for a passed list of names. Maybe we can remove this...
        error_message.append(
            f"{prefix} names must all have unique integer ids"
            f" after the {prefix} prefix."
        )
    return error_message


def raise_display_mode(
    message: str, display_mode: DisplayMode, log: bool
) -> None:
    """
    Given an error message, raise an error or warning, and log or
    do not log, depending on the passed arguments.
    """
    if display_mode == "error":
        utils.log_and_raise_error(message, NeuroBlueprintError)

    elif display_mode == "warn":
        utils.warn(message, log=log)

    elif display_mode == "print":
        if log:
            utils.log_and_message(message)
        else:
            utils.print_message_to_user(message)
    else:
        raise ValueError(
            "`display_mode` must be either 'error', 'warn' or 'print'."
        )


# -----------------------------------------------------------------------------
# Validate Entire Project
# -----------------------------------------------------------------------------


def validate_project(
    cfg: Configs,
    top_level_folder: TopLevelFolder,
    local_only: bool = False,
    display_mode: DisplayMode = "error",
    log: bool = True,
    name_templates: Optional[Dict] = None,
    strict_mode: bool = False,
) -> List[str]:
    """
    Validate all subject and session folders within a project.

    A list of all subjects and sessions per-subject is retrieved from
    the project. We want to check all names at a certain level (e.g.
    all subject filenames contain the same number of "sub-" value digits).
    For duplicate checks, exact duplicates are allowed (for example
    subjects will be duplicated across `local_path` and `central_path`)
    but subject / sessions that share the same value but are otherwise
    different are not allowed.

    Parameters
    -----------

    cfg : Configs
        datashuttle Configs class.

    top_level_folder:  TopLevelFolder
        The top level folder to validate.

    local_only : bool
        If `True`, only project folders in the `local_path` will
        be validated. Otherwise, project folders in both the `local_path`
        and `central_path` will be validated.

    display_mode : DisplayMode
        Determine whether error or warning is raised.

    log : bool
        If `True`, errors or warnings are logged to "datashuttle" logger.
    """
    error_messages = []

    error_messages += check_high_level_project_structure(
        cfg, local_only, display_mode, log
    )

    if strict_mode:
        error_messages += check_strict_mode(
            cfg, top_level_folder, local_only, display_mode, log
        )

    folder_names = getters.get_all_sub_and_ses_names(
        cfg,
        top_level_folder,
        local_only,
    )

    # Check subjects
    #   all_sub_paths = folder_names["sub"]

    #   all_sub_paths, error_messages = strip_invalid_names(
    #       all_sub_paths, "sub", display_mode, log
    #   )
    # # all_error_messages += error_messages

    error_messages += validate_list_of_names(
        folder_names["sub"],
        prefix="sub",
        display_mode=display_mode,
        log=log,
        name_templates=name_templates,
    )

    #   for sub_path in all_sub_paths:
    #
    #       error_messages = new_name_duplicates_existing(
    #           sub_path.name, all_sub_paths, "sub"
    #       )
    #       for message in error_messages:
    #           raise_display_mode(message, display_mode, log)
    #       all_error_messages += error_messages

    # Check sessions
    all_ses_paths = list(chain(*folder_names["ses"].values()))

    #    all_ses_paths, error_messages = strip_invalid_names(
    #        all_ses_paths, "ses", display_mode, log
    #    )
    #    all_error_messages += error_messages

    error_messages += validate_list_of_names(
        all_ses_paths,
        "ses",
        display_mode=display_mode,
        log=log,
    )

    #    for ses_paths in folder_names["ses"].values():
    #        for path_ in ses_paths:
    #            error_messages = new_name_duplicates_existing(
    #                path_.name, ses_paths, "ses"
    #            )
    #            for message in error_messages:
    #                raise_display_mode(message, display_mode, log)
    #            all_error_messages += error_messages

    for message in error_messages:
        raise_display_mode(message, display_mode, log)

    return error_messages


def validate_names_against_project(
    cfg: Configs,
    top_level_folder: TopLevelFolder,
    sub_names: List[str],
    ses_names: Optional[List[str]] = None,
    local_only: bool = False,
    display_mode: DisplayMode = "error",
    log: bool = True,
    name_templates: Optional[Dict] = None,
) -> None:
    """
    Given a list of subject and (optionally) session names,
    check that these names are formatted consistently with the
    rest of the project. Unfortunately this function has become
    quite complex due to the need to only validate the passed
    list of subject / session names while ignoring validation errors
    that may already exist in the project.

    The passed list of names is first validated in `validate_list_of_names()`
    without reference to the existing project.

    Next, checks for inconsistent length of sub or ses values are checked.
    This cannot be run if there are inconsistent values within the project
    itself, which will throw an error in this case. Only valid sub / ses
    names within the project are checked.

    Finally, checks for duplicate subjects / sessions are performed. For subjects,
    duplicates are checked for project-wide. For sessions, duplicates are
    checked for within the corresponding folders. This assumes that
    the passed `ses_names` will be created in all passed `sub_names`.

    Parameters
    ----------

    cfg : Configs
        datashuttle Configs class.

    top_level_folder :  TopLevelFolder
        The top level folder to validate

    sub_names : List[str]
        A list of subject-level names to validate against the
        subject names that exist in the project.

    ses_names : List[str]
        A list of session-level names to validate against the
        session names that exist in the project. Note that
        duplicate checks will only be performed for sessions within
        the passed `sub_names`.

    local_only : bool
        If `True`, only project folders in the `local_path` will
        be validated against. Otherwise, project folders in both the
        `local_path` and `central_path` will be validated against.

    display_mode : DisplayMode
        Determine whether error or warning is raised.

    log : bool
        If `True`, errors or warnings are logged to "datashuttle" logger.

    TODO
    ----
    This function is now quite confusing, and in general the validation
    needs optimisation are there are frequent looping over the same
    list under different circumstances. See issue #355
    """
    error_messages = []

    folder_names = getters.get_all_sub_and_ses_names(
        cfg, top_level_folder, local_only
    )
    # TODO: THESE ARE FOLDER PATHS
    #    try:
    #        error_messages += duplicated_prefix_values(sub_names, prefix="sub")
    #    except:
    #        breakpoint()

    # Check subjects
    error_messages += validate_list_of_names(
        sub_names,
        prefix="sub",
        display_mode=display_mode,
        name_templates=name_templates,
    )

    if folder_names["sub"]:

        valid_sub_in_project = strip_invalid_names(folder_names["sub"], "sub")

        error_messages += (
            check_sub_names_value_length_are_consistent_with_project(
                sub_names, valid_sub_in_project, display_mode, log
            )
        )

        for new_sub in sub_names:
            error_messages += new_name_duplicates_existing(
                new_sub, valid_sub_in_project, "sub"
            )

    # Check sessions
    if ses_names is not None and any(ses_names):

        #      try:
        #          error_messages += duplicated_prefix_values(ses_names, prefix="ses")  maybe we dont care about checking duplicaes in the passed name
        #      except:
        #          breakpoint()

        error_messages += validate_list_of_names(
            ses_names,
            "ses",
            display_mode=display_mode,
        )

        if folder_names["sub"]:
            # For all the subjects, check that the ses_names are valid
            # for all sessions currently within those subjects.
            for new_sub in sub_names:
                if new_sub in folder_names["ses"]:

                    valid_ses_in_sub = (
                        strip_invalid_names(  # strip_uncheckable_names?
                            folder_names["ses"][new_sub],
                            "ses",
                        )
                    )
                    error_messages += check_ses_names_value_length_are_consistent_with_project(
                        ses_names, valid_ses_in_sub, new_sub, display_mode, log
                    )
                    for new_ses in ses_names:
                        error_messages += new_name_duplicates_existing(
                            new_ses, valid_ses_in_sub, "ses"
                        )

    for message in error_messages:
        raise_display_mode(message, display_mode, log)

    return error_messages


def check_high_level_project_structure(cfg, local_only, display_mode, log):
    """
    DOC
    """
    # TODO: it should be impossible to have non-valid name but check anyways
    # actually this will raise correctly for the quick valid.ate TEst!
    error_messages = []
    error_messages += names_include_special_characters(
        cfg["local_path"].name, cfg["local_path"]
    )

    if cfg["central_path"]:
        error_messages += names_include_special_characters(
            cfg["central_path"].name, cfg["central_path"]
        )

    if (
        not (cfg["local_path"] / "rawdata").is_dir()
        and not (cfg["local_path"] / "derivatives").is_dir()
    ):
        message = get_missing_top_level_folder_error(cfg["local_path"])
        error_messages.append(message)

    if local_only:
        return error_messages

    # TODO: temporary workaround for circular imports
    from datashuttle.utils.folders import search_for_folders

    # TODO: must test this with SSH!
    all_folder_names, all_filenames = search_for_folders(
        cfg,
        cfg["central_path"],
        "central",
        "*",
        verbose=False,
        return_full_path=False,
    )

    if ("rawdata" not in all_folder_names) and (
        "derivatives" not in all_folder_names
    ):
        message = get_missing_top_level_folder_error(cfg["central_path"])
        error_messages.append(message)

    return error_messages


def check_strict_mode(cfg, top_level_folder, local_only, display_mode, log):
    """ """
    if not local_only:
        raise ValueError(
            "`strict_mode` is currently only available for `local_only=True`."
        )
    # TODO: temporary workaround for circular imports
    from datashuttle.utils import folders

    error_messages = []

    sub_level_folder_paths = folders.search_project_for_sub_or_ses_names(
        cfg,
        top_level_folder,
        None,
        "*",
        local_only=True,
        return_full_path=True,
    )

    for sub_level_path in sub_level_folder_paths["local"]:

        sub_level_name = sub_level_path.name

        if sub_level_name[:4] != "sub-":
            message = get_name_error(sub_level_name, "sub-", sub_level_path)
            error_messages.append(message)
            continue

        ses_level_folder_paths = folders.search_project_for_sub_or_ses_names(
            cfg,
            top_level_folder,
            sub_level_name,
            "*",
            local_only=True,
            return_full_path=True,
        )

        for ses_level_path in ses_level_folder_paths["local"]:

            ses_level_name = ses_level_path.name

            if ses_level_name[:4] != "ses-":
                message = get_name_error(
                    ses_level_name, "ses-", ses_level_path
                )
                error_messages.append(message)

            base_folder = cfg.get_base_folder("local", top_level_folder)

            search_results = folders.search_sub_or_ses_level(
                cfg,
                base_folder,
                "local",
                sub_level_name,
                ses_level_name,
                return_full_path=True,
            )[0]

            canonical_datatypes = canonical_configs.get_datatypes()
            for datatype_level_path in search_results:

                datatype_level_name = datatype_level_path.name

                if datatype_level_name not in canonical_datatypes:
                    message = get_datatype_error(
                        datatype_level_name, datatype_level_path
                    )
                    error_messages.append(message)

    return error_messages


def check_sub_names_value_length_are_consistent_with_project(  # TODO: delete function
    sub_names: List[str],
    valid_sub_in_project: List[str] | List[Path],
    display_mode: DisplayMode,
    log: bool,
) -> List[str]:
    """
    Given a list of names we are validating, and a list of
    all the other names that current exist in the project, check
    the list of names has consistent value length with all the
    other names in the project.

    Note this will throw an error if the project odes not have
    consistent value length as this check will not be possible
    otherwise.
    """
    if any(value_lengths_are_inconsistent(valid_sub_in_project, "sub")):
        raise_display_mode(
            "Cannot check names for inconsistent value lengths "
            "because the subject value lengths are not consistent "
            "across the project.",
            display_mode,
            log,
        )
    else:
        error_message = value_lengths_are_inconsistent(
            sub_names + valid_sub_in_project, "sub"
        )
        if any(error_message):
            return error_message
        else:
            return []  # TODO


def check_ses_names_value_length_are_consistent_with_project(  # TODO: Delete function!
    ses_names: List[str],
    valid_ses_in_sub: List[str] | List[Path],
    sub_name: str,
    display_mode: DisplayMode,
    log: bool,
) -> List[str]:
    """
    See check_sub_names_value_length_are_consistent_with_project(),
    this performs the same function for session. Potential to merge
    with that function, just some minor annoying differences.
    """
    if any(value_lengths_are_inconsistent(valid_ses_in_sub, "ses")):
        raise_display_mode(
            f"Cannot check names for inconsistent value lengths "
            f"because the session value lengths for subject "
            f"{sub_name} are not consistent.",
            display_mode,
            log,
        )
    else:
        error_message = value_lengths_are_inconsistent(
            ses_names + valid_ses_in_sub, "ses"
        )
        return error_message


@overload
def strip_invalid_names(
    path_or_names_list: List[Path],
    prefix: Prefix,
) -> Tuple[List[Path], List[str]]: ...


@overload
def strip_invalid_names(
    path_or_names_list: List[str],
    prefix: Prefix,
) -> Tuple[List[str], List[str]]: ...


def strip_invalid_names(
    path_or_names_list: List[Path] | List[str],
    prefix: Prefix,
) -> Tuple[List[Path] | List[str], List[str]]:
    """ """
    new_list = []

    for path_or_name in path_or_names_list:

        path_, name = get_path_and_name(path_or_name)

        try:
            utils.get_values_from_bids_formatted_name(
                [name], prefix, return_as_int=True
            )[0]
        except BaseException:
            continue

        if path_:
            new_list.append(path_)
        else:
            new_list.append(name)  # type: ignore

    return new_list


# -----------------------------------------------------------------------------
# Data types
# -----------------------------------------------------------------------------


# TODO: move and refactor this...
def datatypes_are_invalid(
    datatype: Union[List[str], str], allow_all: bool = False
) -> Tuple[bool, str]:
    """
    Check a datatype of list of datatypes is a valid
    NeuroBlueprint datatype.

    Returns `True` if an invalid name was found, along
    with a message detailing the error.
    """
    datatype_folders = canonical_folders.get_datatype_folders()

    if isinstance(datatype, str):
        datatype = [datatype]

    valid_keys = list(datatype_folders.keys())
    if allow_all:
        valid_keys += ["all"]

    bad_datatypes = []
    for dt in datatype:
        if dt not in valid_keys:
            bad_datatypes.append(dt)

    if bad_datatypes:
        or_all = " or 'all'" if allow_all else ""
        message = (
            f"datatypes: '{bad_datatypes}' are not valid. Must be one of"
            f" {list(datatype_folders.keys())}{or_all}. "
            f"No folders were made."
        )
        return True, message

    return False, ""
