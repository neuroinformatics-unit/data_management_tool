import re

import pytest
import test_utils
from tui_base import TuiBase

from datashuttle.configs import canonical_configs
from datashuttle.tui.app import TuiApp
from datashuttle.tui.screens.create_folder_settings import (
    CreateFoldersSettingsScreen,
)
from datashuttle.tui.screens.project_manager import ProjectManagerScreen


class TestTuiCreateFolders(TuiBase):

    # -------------------------------------------------------------------------
    # General test Create Folders
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.parametrize("test_multi_input", [True, False])
    async def test_create_folders_sub_and_ses(
        self, setup_project_paths, test_multi_input
    ):
        """
        Basic test that folders are created as expected through the TUI.
        """
        # Define folders to create
        if test_multi_input:
            sub_text = "sub-001, sub-002"
            sub_test_list = ["sub-001", "sub-002"]
            ses_text = "ses-001,ses-010"
            ses_test_list = ["ses-001", "ses-010"]
        else:
            sub_text = "sub-001"
            sub_test_list = [sub_text]
            ses_text = "ses-001"
            ses_test_list = [ses_text]

        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            # Set up the TUI on the 'create' tab, filling the
            # input with the subject and session folders to create.
            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )
            project = pilot.app.screen.interface.project

            await self.turn_off_all_datatype_checkboxes(pilot)

            await self.fill_input(
                pilot, "#create_folders_subject_input", sub_text
            )

            await self.create_folders_and_check_output(
                pilot,
                project,
                subs=sub_test_list,
                sessions=[],
                folder_used=test_utils.get_all_broad_folders_used(value=False),
            )

            await self.fill_input(
                pilot, "#create_folders_session_input", ses_text
            )

            # Create the folders and check these were properly created.
            # Then, iterate through the datatype checkboxes, turning each
            # one on and creating the folders, checking they are created successfully.
            await self.create_folders_and_check_output(
                pilot,
                project,
                subs=sub_test_list,
                sessions=ses_test_list,
                folder_used=test_utils.get_all_broad_folders_used(value=False),
            )

            await self.iterate_and_check_all_datatype_folders(
                pilot, subs=sub_test_list, sessions=ses_test_list
            )

            await pilot.pause()

    @pytest.mark.asyncio
    async def test_create_folders_formatted_names(self, setup_project_paths):
        """
        Test preview tooltips and create folders with _@DATE@ formatting.
        The @TO@ key is not tested.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:
            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )

            # Fill the subject input with names with @DATE@ tags and
            # check the tooltip displays the formatted value.
            await self.fill_input(
                pilot,
                "#create_folders_subject_input",
                "sub-001_@DATE@, sub-002_@DATE@",
            )

            sub_1_regexp = "sub\-001_date\-\d{8}"
            sub_2_regexp = "sub\-002_date\-\d{8}"
            sub_tooltip_regexp = (
                "Formatted names: \['"
                + sub_1_regexp
                + "', '"
                + sub_2_regexp
                + "'\]"
            )
            sub_tooltip = pilot.app.screen.query_one(
                "#create_folders_subject_input"
            ).tooltip

            assert re.fullmatch(sub_tooltip_regexp, sub_tooltip)

            # Similarly fill the session input and check the tooltip
            await self.fill_input(
                pilot, "#create_folders_session_input", "ses-001@TO@003_@DATE@"
            )

            ses_1_regexp = "ses\-001_date\-\d{8}"
            ses_2_regexp = "ses\-002_date\-\d{8}"
            ses_3_regexp = "ses\-003_date\-\d{8}"
            ses_tooltip_regexp = (
                "Formatted names: \['"
                + ses_1_regexp
                + "', '"
                + ses_2_regexp
                + "', '"
                + ses_3_regexp
                + "'\]"
            )
            ses_tooltip = pilot.app.screen.query_one(
                "#create_folders_session_input"
            ).tooltip
            assert re.fullmatch(ses_tooltip_regexp, ses_tooltip)

            # Create the folders and check the formatted
            # version are created successfully.
            await self.scroll_to_click_pause(
                pilot,
                "#create_folders_create_folders_button",
            )

            project = pilot.app.screen.interface.project
            sub_level_names = sorted(
                list((project.cfg["local_path"] / "rawdata").glob("sub-*"))
            )

            assert re.fullmatch(sub_1_regexp, sub_level_names[0].stem)
            assert re.fullmatch(sub_2_regexp, sub_level_names[1].stem)

            for sub in sub_level_names:
                ses_level_names = sorted(
                    list(
                        (project.cfg["local_path"] / "rawdata" / sub).glob(
                            "ses-*"
                        )
                    )
                )
                assert re.fullmatch(ses_1_regexp, ses_level_names[0].stem)
                assert re.fullmatch(ses_2_regexp, ses_level_names[1].stem)
                assert re.fullmatch(ses_3_regexp, ses_level_names[2].stem)

            await pilot.pause()

    # -------------------------------------------------------------------------
    # Test Validation
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_folders_bad_validation_tooltips(
        self, setup_project_paths
    ):
        """
        Check that correct tooltips are displayed when
        various invalid subject or session names are provided.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )

            await self.fill_input(
                pilot, "#create_folders_subject_input", "sub-abc"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_subject_input"
                ).tooltip
                == "Invalid character in subject or session value: abc"
            )

            await self.fill_input(
                pilot, "#create_folders_session_input", "ses-001_ses-001"
            )

            # The validation is necessarily setup to validate both
            # subject and session together, so the ses input displays
            # the sub problem.
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_session_input"
                ).tooltip
                == "Invalid character in subject or session value: abc"
            )

            await self.fill_input(
                pilot, "#create_folders_subject_input", "sub-001"
            )

            assert (
                pilot.app.screen.query_one(
                    "#create_folders_subject_input"
                ).tooltip
                == "Formatted names: ['sub-001']"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_session_input"
                ).tooltip
                == "There is more than one instance of ses in "
                "ses-001_ses-001. NeuroBlueprint names must contain "
                "only one instance of each key."
            )

            await self.fill_input(
                pilot, "#create_folders_session_input", "ses-001"
            )

            await self.scroll_to_click_pause(
                pilot,
                "#create_folders_create_folders_button",
            )

            await self.fill_input(
                pilot, "#create_folders_subject_input", "sub-001_@DATE@"
            )
            assert (
                "A sub already exists with the same sub id as"
                in pilot.app.screen.query_one(
                    "#create_folders_subject_input"
                ).tooltip
            )

            await pilot.pause()

    @pytest.mark.asyncio
    async def test_validation_error_and_bypass_validation(
        self, setup_project_paths
    ):
        """
        Test validation and bypass validation options by
        first trying to create an invalid folder name, and
        checking an error displays. Next, turn on 'bypass validation'
        and check the folders are created despite being invalid.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )

            await self.fill_input(
                pilot, "#create_folders_subject_input", "sub-abc"
            )
            await self.fill_input(
                pilot, "#create_folders_session_input", "ses-abc"
            )

            await self.scroll_to_click_pause(
                pilot, "#create_folders_create_folders_button"
            )

            assert (
                pilot.app.screen.query_one(
                    "#messagebox_message_label"
                ).renderable
                == "Invalid character in subject or session value: abc"
            )
            await self.close_messagebox(pilot)

            assert not any(
                list(
                    (
                        pilot.app.screen.interface.project.cfg["local_path"]
                        / "rawdata"
                    ).glob("*")
                )
            )
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_button"
            )
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_bypass_validation_checkbox"
            )
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_close_button"
            )

            await self.scroll_to_click_pause(
                pilot, "#create_folders_create_folders_button"
            )

            assert (
                pilot.app.screen.interface.project.cfg["local_path"]
                / "rawdata"
                / "sub-abc"
            ).is_dir()
            assert (
                pilot.app.screen.interface.project.cfg["local_path"]
                / "rawdata"
                / "sub-abc"
                / "ses-abc"
            ).is_dir()

            await pilot.pause()

    # -------------------------------------------------------------------------
    # Test Name Templates
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_name_template_next_sub_or_ses_and_validation(
        self, setup_project_paths
    ):
        """
        Test validation and double-click for next sub / ses
        values when 'name templates' is set in the 'Settings' window.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )

            # Set some name template and check the tooltips
            # indicate mismatches correctly
            pilot.app.screen.interface.project.set_name_templates(
                {"on": True, "sub": "sub-\d\d\d", "ses": "ses-...."}
            )

            await self.fill_input(
                pilot, "#create_folders_subject_input", "sub-0001"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_subject_input"
                ).tooltip
                == "The name: sub-0001 does not match "
                "the template: sub-\\d\\d\\d"
            )

            # It is expected that sub errors propagate to session input.
            # This is because subject and ses must be validated at
            # the same time, to check duplicate ses within subjects.
            await self.fill_input(
                pilot, "#create_folders_session_input", "ses-0001"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_session_input"
                ).tooltip
                == "The name: sub-0001 does not "
                "match the template: sub-\\d\\d\\d"
            )

            # Try and make the folders, displaying a validation error.
            await self.scroll_to_click_pause(
                pilot, "#create_folders_create_folders_button"
            )

            assert pilot.app.screen.query_one(
                "#messagebox_message_label"
            ).renderable == (
                "The name: sub-0001 does not match the template: sub-\\d\\d\\d"
            )
            await self.close_messagebox(pilot)

            # Now make the correct folders respecting the name templates
            await self.fill_input(
                pilot, "#create_folders_subject_input", "sub-001"
            )

            await self.scroll_to_click_pause(
                pilot, "#create_folders_create_folders_button"
            )

            # Now fill in a bad ses name template, because we
            # tested sub above but not ses.
            await self.fill_input(
                pilot, "#create_folders_session_input", "ses-001"
            )

            assert (
                pilot.app.screen.query_one(
                    "#create_folders_subject_input"
                ).tooltip
                == "Formatted names: ['sub-001']"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_session_input"
                ).tooltip
                == "The name: ses-001 does not match the template: ses-...."
            )

            # Finally, double-click the input to suggest next
            # ses / sub numbers, which should respect the name templates.
            await self.double_click(
                pilot, "#create_folders_subject_input", control=True
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_subject_input"
                ).value
                == "sub-\\d\\d\\d"
            )

            await self.double_click(
                pilot, "#create_folders_session_input", control=True
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_session_input"
                ).value
                == "ses-...."
            )

            await self.double_click(
                pilot, "#create_folders_subject_input", control=False
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_subject_input"
                ).value
                == "sub-002"
            )

            await self.fill_input(
                pilot, "#create_folders_subject_input", "sub-001"
            )
            await self.double_click(
                pilot, "#create_folders_session_input", control=False
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_session_input"
                ).value
                == "ses-0002"
            )
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_get_next_sub_and_ses_no_template(self, setup_project_paths):
        """
        Test the double click on Input correctly fills with the
        next sub or ses (or prefix only when CTRL is pressed).
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            await self.setup_existing_project_create_tab_filled_sub_and_ses(
                pilot, project_name, create_folders=True
            )

            # Double-click with CTRL modifier key
            await self.double_click(
                pilot, "#create_folders_subject_input", control=True
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_subject_input"
                ).value
                == "sub-"
            )

            await self.double_click(
                pilot, "#create_folders_session_input", control=True
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_session_input"
                ).value
                == "ses-"
            )

            # Double click without CTRL modifier key.
            await self.double_click(pilot, "#create_folders_subject_input")
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_subject_input"
                ).value
                == "sub-002"
            )

            await self.fill_input(
                pilot, "#create_folders_subject_input", "sub-001"
            )
            await self.double_click(pilot, "#create_folders_session_input")
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_session_input"
                ).value
                == "ses-002"
            )

            await pilot.pause()

    # -------------------------------------------------------------------------
    # Test Top Level Folders
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_folders_settings_top_level_folder(
        self, setup_project_paths
    ):
        """
        Check the folders are created in the correct top level
        folder when this is changed in the 'Settings' screen.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            # Open the CreateFoldersSettingsScreen
            await self.setup_existing_project_create_tab_filled_sub_and_ses(
                pilot, project_name, create_folders=False
            )

            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_button"
            )

            assert isinstance(pilot.app.screen, CreateFoldersSettingsScreen)

            # Check that switching the select updates the
            # underlying config (rawdata)
            assert (
                pilot.app.screen.interface.tui_settings[
                    "top_level_folder_select"
                ]["create_tab"]
                == "rawdata"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_settings_toplevel_select"
                ).value
                == "rawdata"
            )

            # Switch the select
            await pilot.click("#create_folders_settings_toplevel_select")
            await pilot.click(
                "#create_folders_settings_toplevel_select", offset=(2, 5)
            )
            await pilot.pause()

            assert (
                pilot.app.screen.interface.tui_settings[
                    "top_level_folder_select"
                ]["create_tab"]
                == "derivatives"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_settings_toplevel_select"
                ).value
                == "derivatives"
            )

            # Create folders and check they are created in the derivatives.
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_close_button"
            )

            assert isinstance(pilot.app.screen, ProjectManagerScreen)

            await self.scroll_to_click_pause(
                pilot, "#create_folders_create_folders_button"
            )

            project = pilot.app.screen.interface.project
            test_utils.check_folder_tree_is_correct(
                base_folder=(project.cfg["local_path"] / "derivatives"),
                subs=["sub-001"],
                sessions=["ses-001"],
                folder_used=test_utils.get_all_broad_folders_used(),
            )

            await pilot.pause()

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    async def iterate_and_check_all_datatype_folders(
        self, pilot, subs, sessions
    ):
        project = pilot.app.screen.interface.project
        folder_used = test_utils.get_all_broad_folders_used(value=False)

        for datatype in canonical_configs.get_broad_datatypes():

            await self.scroll_to_click_pause(
                pilot,
                f"#create_{datatype}_checkbox",
            )
            folder_used[datatype] = True

            await self.create_folders_and_check_output(
                pilot, project, subs, sessions, folder_used
            )

    async def create_folders_and_check_output(
        self, pilot, project, subs, sessions, folder_used
    ):
        await self.scroll_to_click_pause(
            pilot,
            "#create_folders_create_folders_button",
        )

        test_utils.check_folder_tree_is_correct(
            base_folder=test_utils.get_top_level_folder_path(project),
            subs=subs,
            sessions=sessions,
            folder_used=folder_used,
        )
