from __future__ import annotations

import datetime
import re
from typing import TYPE_CHECKING, Dict, List, Optional, Union

if TYPE_CHECKING:
    from datashuttle.utils.custom_types import Prefix

from datashuttle.configs.canonical_folders import canonical_reserved_keywords
from datashuttle.configs.canonical_tags import tags
from datashuttle.utils import utils, validation

# -----------------------------------------------------------------------------
# Format Sub / Ses Names
# -----------------------------------------------------------------------------


def check_and_format_names(
    names: Union[list, str],
    prefix: Prefix,
    name_templates: Optional[Dict] = None,
    bypass_validation: bool = False,
) -> List[str]:
    """
    Format a list of subject or session names, e.g.
    by ensuring all have sub- or ses- prefix, checking
    for tags, that names do not include spaces and that
    there are not duplicates.

    Note that as we might have canonical keys e.g. "all_sub"
    or certain tags e.g. "@*@" we cannot perform validation on
    these keys as they intrinsically break the NeuroBlueprint rules.
    However, in practice this is not an issue because you won't make a
    folder with "@*@" in it anyway, this is strictly for searching
    during upload / download.
    see canonical_folders.canonical_reserved_keywords() for more information.

    Parameters
    ----------

    names : Union[list, str]
        str or list containing sub or ses names (e.g. to create folders)

    prefix : Prefix
        "sub" or "ses" - this defines the prefix checks.

    name_templates : Dict
        A dictionary of templates to validate subject and session name against.
        e.g. {"name_templates": {"on": False, "sub": None, "ses": None}}
        where the "sub" and "ses" may contain a regexp to validate against.

    bypass_validation : Dict
        If `True`, NeuroBlueprint validation will be performed
        on the passed names.
    """
    if isinstance(names, str):
        names = [names]

    names_to_format, reserved_keywords = [], []
    for name in names:
        if name in canonical_reserved_keywords() or tags("*") in name:
            reserved_keywords.append(name)
        else:
            names_to_format.append(name)

    formatted_names = format_names(names_to_format, prefix)

    if not bypass_validation:
        validation.validate_list_of_names(
            formatted_names,
            prefix,
            "error",
            name_templates=name_templates,
            log=True,
        )

    return formatted_names + reserved_keywords


def format_names(names: List, prefix: Prefix) -> List[str]:
    """
    Check a single or list of input session or subject names.

    First check the type is correct, next prepend the prefix
    sub- or ses- to entries that do not have the relevant prefix.
    Finally, check for duplicates and replace any tags
    with required inputs e.g. date, time

    Parameters
    -----------
    names: str or list containing sub or ses names (e.g. to make folders)

    prefix: "sub" or "ses" - this defines the prefix checks.
    """
    assert prefix in ["sub", "ses"], "`prefix` must be 'sub' or 'ses'."

    if not isinstance(names, List) or any(
        [not isinstance(ele, str) for ele in names]
    ):
        utils.log_and_raise_error(
            f"Ensure {prefix} names are a list of strings.", TypeError
        )

    prefixed_names = add_missing_prefixes_to_names(names, prefix)

    prefixed_names = update_names_with_range_to_flag(prefixed_names, prefix)

    update_names_with_datetime(prefixed_names)

    return prefixed_names


def update_names_with_range_to_flag(
    names: List[str], prefix: str
) -> List[str]:
    """
    Given a list of names, check if they contain the @TO@ keyword.
    If so, expand to a range of names. Names including the @TO@
    keyword must be in the form prefix-num1@num2. The maximum
    number of leading zeros are used to pad the output
    e.g.
    sub-01@003 becomes ["sub-001", "sub-002", "sub-003"]

    Input can also be a mixed list e.g.
    names = ["sub-01", "sub-02@TO@04", "sub-05@TO@10"]
    will output a list of ["sub-01", ..., "sub-10"]
    """
    new_names = []

    for i, name in enumerate(names):
        if tags("to") in name:
            check_name_with_to_tag_is_formatted_correctly(name, prefix)

            prefix_tag = re.search(f"{prefix}-[0-9]+{tags('to')}[0-9]+", name)[0]  # type: ignore
            tag_number = prefix_tag.split(f"{prefix}-")[1]

            name_start_str, name_end_str = name.split(tag_number)

            if tags("to") not in tag_number:
                utils.log_and_raise_error(
                    f"{tags('to')} flag must be between two "
                    f"numbers in the {prefix} tag.",
                    ValueError,
                )

            left_number, right_number = tag_number.split(tags("to"))

            if int(left_number) >= int(right_number):
                utils.log_and_raise_error(
                    f"Number of the {prefix} to the  left of {tags('to')} "
                    f"flag must be smaller than the number to the right.",
                    ValueError,
                )

            names_with_new_number_inserted = (
                make_list_of_zero_padded_names_across_range(
                    left_number, right_number, name_start_str, name_end_str
                )
            )
            new_names += names_with_new_number_inserted

        else:
            new_names.append(name)

    return new_names


def check_name_with_to_tag_is_formatted_correctly(
    name: str, prefix: str
) -> None:
    """
    Check the input string is formatted with the @TO@ key
    as expected.
    """
    first_key_value_pair = name.split("_")[0]
    expected_format = re.compile(f"{prefix}-[0-9]+{tags('to')}[0-9]+")

    if not re.fullmatch(expected_format, first_key_value_pair):
        utils.log_and_raise_error(
            f"The name: {name} is not in required format "
            f"for {tags('to')} keyword. "
            f"The start must be  be {prefix}-<NUMBER>{tags('to')}<NUMBER>).",
            ValueError,
        )


def make_list_of_zero_padded_names_across_range(
    left_number: str, right_number: str, name_start_str: str, name_end_str: str
) -> List[str]:
    """
    Numbers formatted with the @TO@ keyword need to have
    standardised leading zeros on the output. Here we take
    the maximum number of leading zeros and apply for
    all numbers in the range. Note int() will strip
    all leading zeros.

    Parameters
    ----------

    left_number : left (start) number from the range, e.g. "001"

    right_number : right (end) number from the range, e.g. "005"

    name_start_str : part of the name before the flag, usually "sub-"

    name_end_str : rest of the name after the flag, i.e. all other
        key-value pairs.
    """
    max_leading_zeros = max(
        utils.num_leading_zeros(left_number),
        utils.num_leading_zeros(right_number),
    )

    all_numbers = [*range(int(left_number), int(right_number) + 1)]

    all_numbers_with_leading_zero = [
        str(number).zfill(max_leading_zeros + 1) for number in all_numbers
    ]

    names_with_new_number_inserted = [
        f"{name_start_str}{number}{name_end_str}"
        for number in all_numbers_with_leading_zero
    ]

    return names_with_new_number_inserted


# Handle @DATE@, @DATETIME@, @TIME@ flags -------------------------------------


def update_names_with_datetime(names: List[str]) -> None:
    """
    Replace @DATE@ and @DATETIME@ flag with date and datetime respectively.

    Format using key-value pair for bids, i.e. date-20221223_time-
    """
    date = str(datetime.datetime.now().date().strftime("%Y%m%d"))
    date_with_key = format_date(date)

    time_ = datetime.datetime.now().time().strftime("%H%M%S")
    time_with_key = format_time(time_)

    datetime_with_key = format_datetime(date, time_)

    replace_date_time_tags_in_name(
        names, datetime_with_key, date_with_key, time_with_key
    )


def replace_date_time_tags_in_name(
    names: List[str],
    datetime_with_key: str,
    date_with_key: str,
    time_with_key: str,
):
    """
    For all names in the list, do the replacement of tags
    with their final values.
    """
    for i, name in enumerate(names):
        # datetime conditional must come first.
        if tags("datetime") in name:
            name = add_underscore_before_after_if_not_there(
                name, tags("datetime")
            )
            names[i] = name.replace(tags("datetime"), datetime_with_key)

        elif tags("date") in name:
            name = add_underscore_before_after_if_not_there(name, tags("date"))
            names[i] = name.replace(tags("date"), date_with_key)

        elif tags("time") in name:
            name = add_underscore_before_after_if_not_there(name, tags("time"))
            names[i] = name.replace(tags("time"), time_with_key)


def format_date(date: str) -> str:
    return f"date-{date}"


def format_time(time_: str) -> str:
    return f"time-{time_}"


def format_datetime(date: str, time_: str) -> str:
    return f"datetime-{date}T{time_}"


def add_underscore_before_after_if_not_there(string: str, key: str) -> str:
    """
    If names are passed with @DATE@, @TIME@, or @DATETIME@
    but not surrounded by underscores, check and insert
    if required. e.g. sub-001@DATE@ becomes sub-001_@DATE@
    or sub-001@DATEid-101 becomes sub-001_@DATE_id-101
    """
    key_len = len(key)
    key_start_idx = string.index(key)

    # Handle left edge
    if string[key_start_idx - 1] != "_":
        string_split = string.split(key)  # assumes key only in string once
        assert (
            len(string_split) == 2
        ), f"{key} must not appear in string more than once."

        string = f"{string_split[0]}_{key}{string_split[1]}"

    updated_key_start_idx = string.index(key)
    key_end_idx = updated_key_start_idx + key_len

    if key_end_idx != len(string) and string[key_end_idx] != "_":
        string = f"{string[:key_end_idx]}_{string[key_end_idx:]}"

    return string


def add_missing_prefixes_to_names(
    all_names: Union[List[str], str], prefix: str
) -> List[str]:
    """
    Make sure all elements in the list of names are
    prefixed with the prefix, typically "sub-" or "ses-"

    Use expanded list for readability
    """
    prefix = prefix + "-"
    n_chars = len(prefix)

    new_names = []
    for name in all_names:
        if name[:n_chars] != prefix:
            new_names.append(prefix + name)
        else:
            new_names.append(name)

    return new_names
