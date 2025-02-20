import pytest
import test_utils
from tui_base import TuiBase

from datashuttle.configs import canonical_configs
from datashuttle.tui.app import TuiApp


class TestDatatypesTUI(TuiBase):
    """
    Test the datatype selection screen for the Create and Transfer tab.
    """

    @pytest.mark.asyncio
    async def test_select_displayed_datatypes_create(
        self, setup_project_paths
    ):
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            # Set up the TUI on the 'create' tab, filling the
            # input with the subject and session folders to create.
            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )

            # Open the datatypes screen
            await self.scroll_to_click_pause(
                pilot,
                "#create_folders_displayed_datatypes_button",
            )

            # Toggle all datatypes. This will leave only narrow datatypes
            # (assuming default of showing broad datatypes is maintained).

            pilot.app.screen.query_one(
                "#displayed_datatypes_selection_list"
            ).toggle_all()

            await self.scroll_to_click_pause(
                pilot, "#displayed_datatypes_save_button"
            )

            # Check all narrow datatypes are registered (and False)
            narrow_datatype_names = (
                canonical_configs.quick_get_narrow_datatypes()
            )

            for datatype in narrow_datatype_names:
                assert (
                    pilot.app.query_one(f"#create_{datatype}_checkbox").value
                    is False
                )

            # Select a couple and check they are created
            await self.scroll_to_click_pause(pilot, "#create_ecephys_checkbox")
            await self.scroll_to_click_pause(pilot, "#create_fusi_checkbox")
            await self.fill_input(
                pilot, "#create_folders_subject_input", "sub-001"
            )
            await self.fill_input(
                pilot, "#create_folders_session_input", "ses-001"
            )
            await self.scroll_to_click_pause(
                pilot,
                "#create_folders_create_folders_button",
            )
            folders_used = test_utils.get_all_broad_folders_used(value=False)
            folders_used["ecephys"] = True
            folders_used["fusi"] = True

            test_utils.check_folder_tree_is_correct(
                base_folder=tmp_path / "local" / project_name / "rawdata",
                subs=["sub-001"],
                sessions=["ses-001"],
                folder_used=folders_used,
            )
            # For good measure, reopen and toggle all and save, which will
            # now show only the broad datatypes. These will be False as
            # if a checkbox is removed it is also unset.
            await self.scroll_to_click_pause(
                pilot,
                "#create_folders_displayed_datatypes_button",
            )
            pilot.app.screen.query_one(
                "#displayed_datatypes_selection_list"
            ).toggle_all()
            await self.scroll_to_click_pause(
                pilot, "#displayed_datatypes_save_button"
            )

            broad_datatype_names = canonical_configs.get_broad_datatypes()

            for datatype in broad_datatype_names:
                # check all are shown and False again (because False on reset)
                assert (
                    pilot.app.query_one(f"#create_{datatype}_checkbox").value
                    is False
                )

            # Now reopen the datatypes window, toggle everything but quit
            # instead of save. Check that broad datatypes are still shown
            # as expected.
            await self.scroll_to_click_pause(
                pilot,
                "#create_folders_displayed_datatypes_button",
            )
            pilot.app.screen.query_one(
                "#displayed_datatypes_selection_list"
            ).toggle_all()
            await self.scroll_to_click_pause(
                pilot, "#displayed_datatypes_close_button"
            )
            for datatype in broad_datatype_names:
                # check all are shown and False again
                assert (
                    pilot.app.query_one(f"#create_{datatype}_checkbox").value
                    is False
                )

            # Confirm also that narrow datatypes are not shown.
            with pytest.raises(BaseException):
                pilot.app.query_one(
                    f"#create_{narrow_datatype_names[0]}_checkbox"
                )

    @pytest.mark.asyncio
    async def test_select_displayed_datatypes_transfer(
        self, setup_project_paths, mocker
    ):
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            # Set up the TUI on the 'transfer' tab (custom) and
            # open the datatype selection screen
            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )

            await self.switch_tab(pilot, "transfer")
            await self.scroll_to_click_pause(
                pilot, "#transfer_custom_radiobutton"
            )
            await self.scroll_to_click_pause(
                pilot,
                "#transfer_tab_displayed_datatypes_button",
            )

            # Toggle all datatypes (broad are on by default,
            # so now we have narrow only). Save and check they
            # are now displayed.
            pilot.app.screen.query_one(
                "#displayed_datatypes_selection_list"
            ).toggle_all()
            await self.scroll_to_click_pause(
                pilot, "#displayed_datatypes_save_button"
            )
            narrow_datatype_names = (
                canonical_configs.quick_get_narrow_datatypes()
            )

            for datatype in narrow_datatype_names:
                assert (
                    pilot.app.query_one(f"#transfer_{datatype}_checkbox").value
                    is False
                )

            # Turn on a single checkbox and run a transfer, checking that
            # the underlying function is called correctly (monkeypatch)
            await self.scroll_to_click_pause(
                pilot, "#transfer_ecephys_checkbox"
            )
            await self.scroll_to_click_pause(pilot, "#transfer_fusi_checkbox")
            await self.fill_input(pilot, "#transfer_subject_input", "sub-001")
            await self.fill_input(pilot, "#transfer_session_input", "ses-001")

            spy_transfer_func = mocker.spy(
                pilot.app.screen.interface.project, "upload_custom"
            )
            await self.scroll_to_click_pause(
                pilot, "#transfer_transfer_button"
            )
            await self.scroll_to_click_pause(pilot, "#confirm_ok_button")
            await self.close_messagebox(pilot)

            _, kwargs = spy_transfer_func.call_args_list[0]
            assert kwargs["sub_names"] == ["sub-001"]
            assert kwargs["ses_names"] == ["ses-001"]
            assert kwargs["datatype"] == ["ecephys", "fusi"]
            assert kwargs["overwrite_existing_files"] == "never"
            assert kwargs["dry_run"] is False
