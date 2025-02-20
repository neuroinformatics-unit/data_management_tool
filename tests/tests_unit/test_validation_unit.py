import pytest

from datashuttle.utils import formatting, validation


class TestValidationUnit:
    @pytest.mark.parametrize("prefix", ["sub", "ses"])
    def test_more_than_one_instance(self, prefix):
        """
        Check that any duplicate sub or ses values are caught
        in `validate_list_of_names()`.
        """
        error_message = validation.validate_list_of_names(
            [f"{prefix}-001", f"{prefix}-99_date-20231214_{prefix}-98"], prefix
        )

        assert len(error_message) == 1
        assert (
            f"DUPLICATE_PREFIX: The name: {prefix}-99_date-20231214_{prefix}-98 of "
            f"contains more than one instance of the prefix {prefix}."
            == error_message[0]
        )

        # This test is on sub, just test twice.
        error_message = validation.validate_list_of_names(
            ["sub-001_ses-03_id_1232_date-20231214__id_1234"], "sub"
        )
        assert len(error_message) == 1

    @pytest.mark.parametrize(
        "prefix_and_names",
        [
            ["sub", ["sdfsdfsd"]],
            ["sub", ["sub-1000", "sob-1001"]],
            ["sub", ["s23-999", "sub_@DATE@"]],
        ],
    )
    def test_name_does_not_begin_with_prefix(self, prefix_and_names):
        """
        Check validation that names passed to `validate_list_of_names()`
        start with the prefix prefix (sub or ses).
        """
        prefix, names = prefix_and_names

        error_messages = validation.validate_list_of_names(names, prefix)

        assert f"MISSING_PREFIX: The prefix {prefix}" in error_messages[0]

    @pytest.mark.parametrize("prefix", ["sub", "ses"])
    def test_special_characters_in_format_names(self, prefix):
        """
        Check `validate_list_of_names()` catches
        spaces in passed names (not all names are bad
        """
        error_messages = validation.validate_list_of_names(
            [
                f"{prefix}-1992_date-20100909_id-12 32",
                f"{prefix}-1993_id-12!34",
                f"{prefix}-1994_id-12@34",
            ],
            prefix,
        )
        assert len(error_messages) == 3
        assert all(["SPECIAL_CHAR" for message in error_messages])

    @pytest.mark.parametrize(
        "prefix_and_names",
        [
            ["ses", ["ses-001!", "ses-00 2"]],
            ["ses", ["ses-#001", "ses-00 2"]],
            ["ses", ["ses-001!", "ses-00%2"]],
        ],
    )
    def test_prefix_is_not_an_integer(self, prefix_and_names):
        """ """
        prefix, names = prefix_and_names

        error_messages = validation.validate_list_of_names(names, prefix)

        # these names get double error because the value is bad
        # and they contain special chars.
        assert "BAD_VALUE" in error_messages[0]
        assert "SPECIAL_CHAR" in error_messages[1]
        assert "BAD_VALUE" in error_messages[2]
        assert "SPECIAL_CHAR" in error_messages[3]

    @pytest.mark.parametrize("prefix", ["sub", "ses"])
    def test_formatting_dashes_and_underscore_alternate_incorrectly(
        self, prefix
    ):
        """
        Check `validate_list_of_names()` catches "-" and "_" that
        are not in the correct order.
        """

        # Test a large range of bad names. Do not use
        # parametrize so we can use f"{prefix}".
        # There should always be two validation errors per list.
        for names in [
            [f"{prefix}-001_id-123-suffix", f"{prefix}-002_id-123_suffix"],
            [
                f"{prefix}-001_id_123",
                f"{prefix}-002",
                f"{prefix}-003_id-_123",
            ],
            [
                f"{prefix}-001_id-123",
                f"{prefix}-002_id-002-task-check",
                f"{prefix}-003_date_20200101",
            ],
            [
                f"{prefix}-01",
                f"{prefix}-02_id-002-",
                f"{prefix}-04_id-002_",
            ],
        ]:
            error_messages = validation.validate_list_of_names(
                names, f"{prefix}"
            )

            assert len(error_messages) == 2
            assert all(
                ["NAME_FORMAT" in message for message in error_messages]
            )

        # Test the edge case where a wrong dash or underscore raises two errors,
        # the underscore error as well as bad value (because anything after prefix-
        # and before _ is considered the value).
        for name in [
            [f"{prefix}-001-date_101010"],
            [f"{prefix}_001_date_101010"],
        ]:
            error_messages = validation.validate_list_of_names(
                name, f"{prefix}"
            )
            assert len(error_messages) > 1

        # check these don't raise
        all_names = [f"{prefix}-001_hello-world_one-hundred"]
        validation.validate_list_of_names(all_names, f"{prefix}")

        all_names = [f"{prefix}-001_hello-world_suffix"]
        validation.validate_list_of_names(all_names, f"{prefix}")

    @pytest.mark.parametrize("prefix", ["sub", "ses"])
    def test_inconsistent_value_lengths_in_list_of_names(self, prefix):
        """
        Ensure a list of sub / ses names that contain inconsistent
        leading zeros (e.g. ["sub-001", "sub-02"]) leads to an error.
        """
        for names in [
            [f"{prefix}-001", f"{prefix}-02", f"{prefix}-003"],
            [f"{prefix}-999", f"{prefix}-1000", f"{prefix}-1001"],
            [f"{prefix}-0099", f"{prefix}-100", f"{prefix}-0098"],
        ]:
            with pytest.raises(BaseException) as e:
                formatting.check_and_format_names(names, prefix)

            assert (
                f"VALUE_LENGTH: Inconsistent value lengths for the prefix: {prefix}"
                in str(e.value)
            )

    @pytest.mark.parametrize("prefix", ["sub", "ses"])
    def test_duplicate_ids_in_list_of_names(self, prefix):
        """
        Ensure a list of sub / ses names that contain duplicate sub / ses
        ids (e.g. ["sub-001", "sub-001_@DATE@"]) leads to an error.
        """
        names = [f"{prefix}-001", f"{prefix}-002", f"{prefix}-001_@DATE@"]

        with pytest.raises(BaseException) as e:
            formatting.check_and_format_names(names, prefix)

        assert (
            str(e.value)
            == f"DUPLICATE_NAME: The prefix for {prefix}-001 duplicates the name: {prefix}-001_date-20250220."
        )

    @pytest.mark.parametrize("prefix", ["sub", "ses"])
    def test_new_name_duplicates_existing(self, prefix):
        """
        Test the function `new_name_duplicates_existing()`
        that will throw an error if a sub / ses name matches
        an existing name (unless it matches exactly).
        """

        # Check an exactly matching case that should not raise and error
        new_name = f"{prefix}-002"
        existing_names = [f"{prefix}-001", f"{prefix}-002", f"{prefix}-003"]
        error_messages = validation.new_name_duplicates_existing(
            new_name, existing_names, prefix
        )
        assert len(error_messages) == 0

        # Check a completely different case that should not raise an error.
        new_name = f"{prefix}-99999"
        existing_names = [f"{prefix}-999"]
        error_messages = validation.new_name_duplicates_existing(
            new_name, existing_names, prefix
        )
        assert len(error_messages) == 0

        # Test a single non-exact matching case (002) that raises an error.
        new_name = f"{prefix}-002_date-12345"
        existing_names = [f"{prefix}-002_date-00000", f"{prefix}-003"]
        error_messages = validation.new_name_duplicates_existing(
            new_name, existing_names, prefix
        )
        assert len(error_messages) == 1
        assert (
            f"DUPLICATE_NAME: The prefix for {prefix}-002_date-12345 duplicates the name: {prefix}-002_date-00000."
            in error_messages[0]
        )

        # Check that the exact-match case passes while
        # the match case does not.
        new_name = f"{prefix}-3"
        existing_names = [f"{prefix}-3", f"{prefix}-3_s-a"]
        error_messages = validation.new_name_duplicates_existing(
            new_name, existing_names, prefix
        )
        assert len(error_messages) == 1
        assert (
            f"DUPLICATE_NAME: The prefix for {prefix}-3 duplicates the name: {prefix}-3_s-a."
            == error_messages[0]
        )

    def test_tags_autoreplace_in_regexp(self):
        """
        Check the validation function `replace_tags_in_regexp()`
        correctly replaces tags in a regexp with their regexp equivalent.

        Test date, time and datetime with some random regexp that
        implicitly check a few other cases (e.g. underscore filling around
        the tag).
        """
        date_regexp = r"sub-\d\d@DATE@_some-tag"
        fixed_date_regexp = validation.replace_tags_in_regexp(date_regexp)
        assert fixed_date_regexp == r"sub-\d\d_date-\d\d\d\d\d\d\d\d_some-tag"

        time_regexp = r"ses-\d\d\d\d@TIME@_some-.?.?tag"
        fixed_time_regexp = validation.replace_tags_in_regexp(time_regexp)
        assert (
            fixed_time_regexp == r"ses-\d\d\d\d_time-\d\d\d\d\d\d_some-.?.?tag"
        )

        datetime_regexp = r"ses-.?.?.?@DATETIME@some-.?.?tag"
        fixed_datetime_regexp = validation.replace_tags_in_regexp(
            datetime_regexp
        )
        assert (
            fixed_datetime_regexp
            == r"ses-.?.?.?_datetime-\d\d\d\d\d\d\d\dT\d\d\d\d\d\d_some-.?.?tag"
        )
