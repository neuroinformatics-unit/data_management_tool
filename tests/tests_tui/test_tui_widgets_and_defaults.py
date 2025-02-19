import platform
from typing import Union

import pytest
from tui_base import TuiBase

from datashuttle import DataShuttle
from datashuttle.configs import canonical_configs
from datashuttle.tui.app import TuiApp
from datashuttle.tui.screens.create_folder_settings import (
    CreateFoldersSettingsScreen,
)
from datashuttle.tui.screens.new_project import NewProjectScreen


class TestTuiWidgets(TuiBase):
    """
    This class performs fundamental checks on the default display
    of widgets and that changing widgets properly change underlying
    configs. This does not perform any functional tests e.g.
    creation of configs of new files.
    """

    # -------------------------------------------------------------------------
    # Test Configs New Project
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_new_project_configs(self, empty_project_paths):
        """
        Test all widgets display as expected on the New Project configs page.
        """
        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            # Select a new project, check NewProjectScreen is displayed correctly.
            await self.scroll_to_click_pause(
                pilot, "#mainwindow_new_project_button"
            )

            assert pilot.app.screen_stack[0].id == "_default"
            assert isinstance(pilot.app.screen_stack[1], NewProjectScreen)
            assert pilot.app.screen_stack[1].title == "Make New Project"

            configs_content = pilot.app.screen.query_one(
                "#new_project_configs_content"
            )

            # New Project Labels --------------------------------------------------

            assert (
                configs_content.query_one("#configs_banner_label").renderable
                == "Make A New Project"
            )
            assert (
                configs_content.query_one("#configs_info_label").renderable
                == "Set your configurations for a new project. For more details on "
                "each section,\nsee the Datashuttle documentation. Once configs "
                "are set, you will be able\nto use the 'Create' and 'Transfer' tabs."
            )

            # Project Name --------------------------------------------------------

            assert (
                configs_content.query_one("#configs_name_label").renderable
                == "Project Name"
            )
            assert configs_content.query_one("#configs_name_input").value == ""
            assert (
                configs_content.query_one("#configs_name_input").placeholder
                == "e.g. my_first_project"
            )

            # Local Path ----------------------------------------------------------

            assert (
                configs_content.query_one(
                    "#configs_local_path_label"
                ).renderable
                == "Local Path"
            )
            assert (
                configs_content.query_one("#configs_local_path_input").value
                == ""
            )

            if platform.system() == "Windows":
                assert (
                    configs_content.query_one(
                        "#configs_local_path_input"
                    ).placeholder
                    == "e.g. C:\\path\\to\\local\\my_projects\\my_first_project"
                )
            else:
                assert (
                    configs_content.query_one(
                        "#configs_local_path_input"
                    ).placeholder
                    == "e.g. /path/to/local/my_projects/my_first_project"
                )

            # Connection Method ---------------------------------------------------

            assert (
                configs_content.query_one(
                    "#configs_connect_method_label"
                ).renderable
                == "Connection Method"
            )
            assert (
                configs_content.query_one(
                    "#configs_connect_method_radioset"
                ).pressed_button.label._text[0]
                == "Local Filesystem"
            )

            # Central Path (Local Filesystem) ------------------------------------------

            assert (
                configs_content.query_one(
                    "#configs_central_path_label"
                ).renderable
                == "Central Path"
            )
            assert (
                configs_content.query_one("#configs_central_path_input").value
                == ""
            )
            if platform.system() == "Windows":

                assert (
                    configs_content.query_one(
                        "#configs_central_path_input"
                    ).placeholder
                    == "e.g. C:\\path\\to\\central\\my_projects\\my_first_project"
                )
            else:
                assert (
                    configs_content.query_one(
                        "#configs_central_path_input"
                    ).placeholder
                    == "e.g. /path/to/central/my_projects/my_first_project"
                )

            # Check Non SSH widgets hidden / disabled ----------------------------------
            await self.check_new_project_ssh_widgets(
                configs_content, ssh_on=False
            )

            # Change to SSH
            await self.scroll_to_click_pause(pilot, "#configs_ssh_radiobutton")
            await self.check_new_project_ssh_widgets(
                configs_content, ssh_on=True
            )

            # Central Path (SSH) ------------------------------------------

            assert (
                configs_content.query_one("#configs_central_path_input").value
                == ""
            )
            assert (
                configs_content.query_one(
                    "#configs_central_path_input"
                ).placeholder
                == "e.g. /nfs/path_on_server/myprojects/central"
            )

            # Central Host ID -------------------------------------------------

            assert (
                configs_content.query_one(
                    "#configs_central_host_id_label"
                ).renderable
                == "Central Host ID"
            )
            assert (
                configs_content.query_one(
                    "#configs_central_host_id_input"
                ).value
                == ""
            )
            assert (
                configs_content.query_one(
                    "#configs_central_host_id_input"
                ).placeholder
                == "e.g. ssh.swc.ucl.ac.uk"
            )

            # Central Host Username -------------------------------------------

            assert (
                configs_content.query_one(
                    "#configs_central_host_username_label"
                ).renderable
                == "Central Host Username"
            )
            assert (
                configs_content.query_one(
                    "#configs_central_host_username_input"
                ).value
                == ""
            )
            assert (
                configs_content.query_one(
                    "#configs_central_host_username_input"
                ).placeholder
                == "e.g. username"
            )

            await pilot.pause()

    async def check_new_project_ssh_widgets(
        self, configs_content, ssh_on, save_pressed=False
    ):
        """"""
        assert configs_content.query_one(
            "#configs_setup_ssh_connection_button"
        ).visible is (
            ssh_on and save_pressed
        )  # Only enabled after project creation.
        assert (
            configs_content.query_one(
                "#configs_central_path_select_button"
            ).display
            is not ssh_on
        )

        for id in [
            "#configs_central_host_id_label",
            "#configs_central_host_id_input",
            "#configs_central_host_username_label",
            "#configs_central_host_username_input",
        ]:
            assert configs_content.query_one(id).display is ssh_on

    # -------------------------------------------------------------------------
    # Test Configs Existing Project
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_existing_project_configs(self, setup_project_paths):
        """
        Because the underlying screen is shared between new and existing
        project configs, in the existing project configs just check
        widgets are hidden as expected.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            # Navigate to the existing project and click onto the
            # configs tab.
            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )
            await self.switch_tab(pilot, "configs")
            configs_content = pilot.app.screen.query_one(
                "#tabscreen_configs_content"
            )

            for id in [
                "#configs_info_label",
                "#configs_banner_label",
                "#configs_name_label",
                "#configs_name_input",
            ]:
                with pytest.raises(BaseException) as e:
                    configs_content.query_one(id)
                assert "No nodes match" in str(e)

            await pilot.pause()

    # -------------------------------------------------------------------------
    # Test Create
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_folders_widgets_display(self, setup_project_paths):
        """
        Test all widgets on the 'Create' tab of the project manager screen
        are displayed as expected.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )

            assert (
                pilot.app.screen.query_one(
                    "#create_folders_subject_label"
                ).renderable
                == "Subject(s)"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_subject_input"
                ).placeholder
                == "e.g. sub-001"
            )

            assert (
                pilot.app.screen.query_one(
                    "#create_folders_session_label"
                ).renderable
                == "Session(s)"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_session_input"
                ).placeholder
                == "e.g. ses-001"
            )

            assert (
                pilot.app.screen.query_one(
                    "#create_folders_datatype_label"
                ).renderable
                == "Datatype(s)"
            )

            assert (
                pilot.app.screen.query_one(
                    "#create_behav_checkbox"
                ).label._text[0]
                == "behav"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_ephys_checkbox"
                ).label._text[0]
                == "ephys"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_funcimg_checkbox"
                ).label._text[0]
                == "funcimg"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_anat_checkbox"
                ).label._text[0]
                == "anat"
            )

            assert (
                pilot.app.screen.query_one(
                    "#create_folders_create_folders_button"
                ).label._text[0]
                == "Create Folders"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_settings_button"
                ).label._text[0]
                == "Settings"
            )

            await pilot.pause()

    # -------------------------------------------------------------------------
    # Test Create Settings
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_folder_settings_widgets(self, setup_project_paths):
        """
        Test the widgets in the 'Settings' menu of the project
        manager's 'Create' tab.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            await self.setup_existing_project_create_tab_filled_sub_and_ses(
                pilot, project_name, create_folders=False
            )
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_button"
            )

            assert isinstance(pilot.app.screen, CreateFoldersSettingsScreen)

            assert (
                pilot.app.screen.query_one(
                    "#create_folders_settings_toplevel_label"
                ).renderable
                == "Top level folder:"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_settings_toplevel_select"
                ).value
                == "rawdata"
            )

            assert (
                pilot.app.screen.query_one(
                    "#create_folders_settings_bypass_validation_checkbox"
                ).label._text[0]
                == "Bypass validation"
            )
            assert (
                pilot.app.screen.query_one(
                    "#create_folders_settings_bypass_validation_checkbox"
                ).value
                is False
            )

            assert (
                pilot.app.screen.query_one(
                    "#template_settings_validation_on_checkbox"
                ).label._text[0]
                == "Template Validation"
            )
            assert (
                pilot.app.screen.query_one(
                    "#template_settings_validation_on_checkbox"
                ).value
                is False
            )

            assert (
                pilot.app.screen.query_one(
                    "#template_inner_container"
                ).disabled
                is True
            )
            await self.scroll_to_click_pause(
                pilot, "#template_settings_validation_on_checkbox"
            )
            assert (
                pilot.app.screen.query_one(
                    "#template_inner_container"
                ).disabled
                is False
            )

            assert (
                " A 'Template' can be set check subject or session names"
                in pilot.app.screen.query_one(
                    "#template_message_label"
                ).renderable
            )

            assert (
                pilot.app.screen.query_one(
                    "#template_settings_radioset"
                ).pressed_button.label._text[0]
                == "Subject"
            )
            assert (
                pilot.app.screen.query_one("#template_settings_input").value
                == ""
            )
            assert (
                pilot.app.screen.query_one(
                    "#template_settings_input"
                ).placeholder
                == "sub-"
            )

            await self.scroll_to_click_pause(
                pilot, "#template_settings_session_radiobutton"
            )
            assert (
                pilot.app.screen.query_one("#template_settings_input").value
                == ""
            )
            assert (
                pilot.app.screen.query_one(
                    "#template_settings_input"
                ).placeholder
                == "ses-"
            )

            await pilot.pause()

    @pytest.mark.asyncio
    async def test_name_templates_widgets_and_settings(
        self, setup_project_paths
    ):
        """
        Check the 'Name Templates' section of the 'Create' tab 'Settings
        page. Here both subject and session configs share the same
        input, so ensure these are mapped correctly by the radiobutton setting,
        and that the underlying configs are set correctly.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        sub_regexp = "sub-\d\d\d"
        ses_regexp = "ses-00\d_????"

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            await self.setup_existing_project_create_tab_filled_sub_and_ses(
                pilot, project_name, create_folders=False
            )

            # Check the default template settings are as expected
            expected_template = {"on": False, "sub": None, "ses": None}
            assert (
                pilot.app.screen.interface.get_name_templates()
                == expected_template
            )
            assert (
                pilot.app.screen.interface.project.get_name_templates()
                == expected_template
            )

            # Go to the Settings window, turn on validation and fill a sub regexp
            # into the Input
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_button"
            )

            await self.scroll_to_click_pause(
                pilot, "#template_settings_validation_on_checkbox"
            )
            await self.fill_input(
                pilot, "#template_settings_input", sub_regexp
            )

            # Close the window and check the template settings are stored as expected
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_close_button"
            )

            expected_template = {"on": True, "sub": sub_regexp, "ses": None}
            assert (
                pilot.app.screen.interface.get_name_templates()
                == expected_template
            )
            assert (
                pilot.app.screen.interface.project.get_name_templates()
                == expected_template
            )

            # Refresh the project and check settings have persisted
            await self.exit_to_main_menu_and_reeneter_project_manager(
                pilot, project_name
            )

            assert (
                pilot.app.screen.interface.get_name_templates()
                == expected_template
            )
            assert (
                pilot.app.screen.interface.project.get_name_templates()
                == expected_template
            )

            # Go back onto the Settings window and explore more options - enter a
            # subject regexp and turn the templates off, then close and check
            # all settings are as expected.
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_button"
            )
            assert (
                pilot.app.screen.query_one(
                    "#template_settings_validation_on_checkbox"
                ).value
                is True
            )
            assert (
                pilot.app.screen.query_one("#template_settings_input").value
                == sub_regexp
            )

            await self.scroll_to_click_pause(
                pilot, "#template_settings_session_radiobutton"
            )
            assert (
                pilot.app.screen.query_one("#template_settings_input").value
                == ""
            )

            await self.fill_input(
                pilot, "#template_settings_input", ses_regexp
            )
            await self.scroll_to_click_pause(
                pilot, "#template_settings_validation_on_checkbox"
            )
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_close_button"
            )

            expected_template = {
                "on": False,
                "sub": sub_regexp,
                "ses": ses_regexp,
            }
            assert (
                pilot.app.screen.interface.get_name_templates()
                == expected_template
            )
            assert (
                pilot.app.screen.interface.project.get_name_templates()
                == expected_template
            )

            # Refresh the project and do a final check all settings have
            # persisted and are updated correctly on the TUI.
            await self.exit_to_main_menu_and_reeneter_project_manager(
                pilot, project_name
            )
            assert (
                pilot.app.screen.interface.get_name_templates()
                == expected_template
            )
            assert (
                pilot.app.screen.interface.project.get_name_templates()
                == expected_template
            )

            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_button"
            )
            assert (
                pilot.app.screen.query_one(
                    "#template_settings_validation_on_checkbox"
                ).value
                is False
            )
            assert (
                pilot.app.screen.query_one("#template_settings_input").value
                == sub_regexp
            )

            await self.scroll_to_click_pause(
                pilot, "#template_settings_validation_on_checkbox"
            )
            await self.scroll_to_click_pause(
                pilot, "#template_settings_session_radiobutton"
            )
            assert (
                pilot.app.screen.query_one("#template_settings_input").value
                == ses_regexp
            )

            await pilot.pause()

    @pytest.mark.asyncio
    async def test_bypass_validation_settings(self, setup_project_paths):
        """
        Test all configs that underly the 'bypass validation'
        setting are updated correctly by the widget.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            await self.setup_existing_project_create_tab_filled_sub_and_ses(
                pilot, project_name, create_folders=False
            )
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_button"
            )

            assert (
                pilot.app.screen.query_one(
                    "#create_folders_settings_bypass_validation_checkbox"
                ).value
                is False
            )
            assert (
                pilot.app.screen.interface.tui_settings["bypass_validation"]
                is False
            )

            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_bypass_validation_checkbox"
            )

            assert (
                pilot.app.screen.query_one(
                    "#create_folders_settings_bypass_validation_checkbox"
                ).value
                is True
            )
            assert (
                pilot.app.screen.interface.tui_settings["bypass_validation"]
                is True
            )

            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_close_button"
            )
            await self.exit_to_main_menu_and_reeneter_project_manager(
                pilot, project_name
            )
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_button"
            )

            assert (
                pilot.app.screen.query_one(
                    "#create_folders_settings_bypass_validation_checkbox"
                ).value
                is True
            )
            assert (
                pilot.app.screen.interface.tui_settings["bypass_validation"]
                is True
            )

            await pilot.pause()

    @pytest.mark.asyncio
    async def test_all_top_level_folder_selects(self, setup_project_paths):
        """
        Test all 'top level folder' selects (in Create and Transfer tabs)
        update the underlying configs correctly.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            # Open project, check top level folder are correct
            await self.setup_existing_project_create_tab_filled_sub_and_ses(
                pilot, project_name, create_folders=False
            )
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_button"
            )

            await self.check_top_folder_select(
                pilot,
                "#create_folders_settings_toplevel_select",
                "create_tab",
                "rawdata",
                move_to_position=False,
            )
            await self.check_top_folder_select(
                pilot,
                "#create_folders_settings_toplevel_select",
                "create_tab",
                "derivatives",
                move_to_position=5,
            )

            # Exit project, return and check values are updated property
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_close_button"
            )
            await self.exit_to_main_menu_and_reeneter_project_manager(
                pilot, project_name
            )

            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_button"
            )
            await self.check_top_folder_select(
                pilot,
                "#create_folders_settings_toplevel_select",
                "create_tab",
                "derivatives",
                move_to_position=5,
            )

            # Move to transfer tab top level folder option, perform the same
            # actions, checking create settings toplevel select is not changed
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_close_button"
            )
            await self.switch_tab(pilot, "transfer")

            await self.scroll_to_click_pause(
                pilot, "#transfer_toplevel_radiobutton"
            )
            await self.check_top_folder_select(
                pilot,
                "#transfer_toplevel_select",
                "toplevel_transfer",
                "rawdata",
                move_to_position=False,
            )
            await self.check_top_folder_select(
                pilot,
                "#transfer_toplevel_select",
                "toplevel_transfer",
                "derivatives",
                move_to_position=5,
            )

            # Now the same for custom
            await self.scroll_to_click_pause(
                pilot, "#transfer_custom_radiobutton"
            )
            await self.check_top_folder_select(
                pilot,
                "#transfer_custom_select",
                "custom_transfer",
                "rawdata",
                move_to_position=False,
            )
            await self.check_top_folder_select(
                pilot,
                "#transfer_custom_select",
                "custom_transfer",
                "derivatives",
                move_to_position=5,
            )

            # Now go back to main menu, go back and check all are as expected
            # and switch back to original value for good measure.
            await self.exit_to_main_menu_and_reeneter_project_manager(
                pilot, project_name
            )

            # recheck create settings
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_button"
            )
            await self.check_top_folder_select(
                pilot,
                "#create_folders_settings_toplevel_select",
                "create_tab",
                "derivatives",
                move_to_position=False,
            )
            await self.check_top_folder_select(
                pilot,
                "#create_folders_settings_toplevel_select",
                "create_tab",
                "rawdata",
                move_to_position=4,
            )

            # recheck transfer toplevel
            await self.scroll_to_click_pause(
                pilot, "#create_folders_settings_close_button"
            )
            await self.switch_tab(pilot, "transfer")

            await self.scroll_to_click_pause(
                pilot, "#transfer_toplevel_radiobutton"
            )

            await self.check_top_folder_select(
                pilot,
                "#transfer_toplevel_select",
                "toplevel_transfer",
                "derivatives",
                move_to_position=False,
            )
            await self.check_top_folder_select(
                pilot,
                "#transfer_toplevel_select",
                "toplevel_transfer",
                "rawdata",
                move_to_position=4,
            )

            # recheck transfer custom
            await self.scroll_to_click_pause(
                pilot, "#transfer_custom_radiobutton"
            )
            await self.check_top_folder_select(
                pilot,
                "#transfer_custom_select",
                "custom_transfer",
                "derivatives",
                move_to_position=False,
            )
            await self.check_top_folder_select(
                pilot,
                "#transfer_custom_select",
                "custom_transfer",
                "rawdata",
                move_to_position=4,
            )
            await pilot.pause()

    async def check_top_folder_select(
        self,
        pilot,
        id,
        tab_name,
        expected_val,
        move_to_position: Union[bool, int] = False,
    ):
        """
        If move to position is not False, must be int specifying position
        """
        if move_to_position:
            await self.move_select_to_position(pilot, id, move_to_position)

        assert (
            pilot.app.screen.interface.tui_settings["top_level_folder_select"][
                tab_name
            ]
            == expected_val
        )
        assert pilot.app.screen.query_one(id).value == expected_val

        assert (
            pilot.app.screen.interface.project._load_persistent_settings()[
                "tui"
            ]["top_level_folder_select"][tab_name]
            == expected_val
        )

    @pytest.mark.asyncio
    async def test_all_checkboxes(self, setup_project_paths):
        """
        Check all datatype checkboxes (Create and Transfer tab)
        correctly update the underlying configs. These are tested
        together to ensure there are no strange interaction between
        these as they both share stored in the project's 'tui'
        persistent settings.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )

            # Turn off all broad datatype checkboxes
            await self.turn_off_all_datatype_checkboxes(pilot)
            expected_create = canonical_configs.get_tui_config_defaults()[
                "tui"
            ]["create_checkboxes_on"]
            for datatype in ["behav", "ephys", "funcimg", "anat"]:
                expected_create[datatype]["on"] = False

            # Cycle through all checkboxes, turning on sequentially
            # and checking all configs are correct.
            for datatype in ["behav", "ephys", "funcimg", "anat"]:
                await self.change_checkbox(
                    pilot, f"#create_{datatype}_checkbox"
                )
                expected_create[datatype]["on"] = True
                self.check_datatype_checkboxes(
                    pilot, "create", expected_create
                )

            # Now turn off an arbitrary subset so they are not longer all on
            # (which is default). Reload the screen, and check the checkboxes
            # are still correct.
            await self.change_checkbox(pilot, "#create_ephys_checkbox")
            await self.change_checkbox(pilot, "#create_anat_checkbox")
            expected_create["ephys"]["on"] = False
            expected_create["anat"]["on"] = False

            await self.exit_to_main_menu_and_reeneter_project_manager(
                pilot, project_name
            )

            self.check_datatype_checkboxes(pilot, "create", expected_create)

            # Now we got to custom transfer checkboxes and do the same.
            # These are done in the same test to check they don't
            # interact in a weird way.
            await self.switch_tab(pilot, "transfer")
            await self.scroll_to_click_pause(
                pilot, "#transfer_custom_radiobutton"
            )

            # Now turn off all transfer checkboxes
            await self.turn_off_all_datatype_checkboxes(pilot, tab="transfer")

            expected_transfer = canonical_configs.get_tui_config_defaults()[
                "tui"
            ]["transfer_checkboxes_on"]
            for datatype in ["all", "all_datatype", "all_non_datatype"]:
                expected_transfer[datatype]["on"] = False

            for datatype in [
                "behav",
                "ephys",
                "funcimg",
                "anat",
                "all",
                "all_datatype",
                "all_non_datatype",
            ]:
                await self.change_checkbox(
                    pilot, f"#transfer_{datatype}_checkbox"
                )
                expected_transfer[datatype]["on"] = True
                self.check_datatype_checkboxes(
                    pilot, "transfer", expected_transfer
                )

            # Reload the screen, and check everything is as previously
            # set on both create and transfer tabs
            await self.exit_to_main_menu_and_reeneter_project_manager(
                pilot, project_name
            )

            self.check_datatype_checkboxes(pilot, "create", expected_create)

            await self.switch_tab(pilot, "transfer")
            await self.scroll_to_click_pause(
                pilot, "#transfer_custom_radiobutton"
            )
            self.check_datatype_checkboxes(pilot, "create", expected_create)

            await pilot.pause()

    def check_datatype_checkboxes(self, pilot, tab, expected_on):
        """"""
        assert tab in ["create", "transfer"]
        if tab == "create":
            id = "#create_folders_datatype_checkboxes"
            dict_key = "create_checkboxes_on"
        else:
            id = "#transfer_custom_datatype_checkboxes"
            dict_key = "transfer_checkboxes_on"

        assert pilot.app.screen.query_one(id).datatype_config == expected_on
        assert pilot.app.screen.interface.tui_settings[dict_key] == expected_on
        assert (
            pilot.app.screen.interface.project._load_persistent_settings()[
                "tui"
            ][dict_key]
            == expected_on
        )

    # -------------------------------------------------------------------------
    # Test Transfer
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_all_transfer_widgets(self, setup_project_paths):
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            # Navigate to the existing project and click onto the
            # configs tab.
            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )
            await self.switch_tab(pilot, "transfer")

            # Checkboxes, on and label
            assert (
                pilot.app.screen.query_one(
                    "#transfer_all_radiobutton"
                ).label._text[0]
                == "All"
            )
            assert (
                pilot.app.screen.query_one(
                    "#transfer_toplevel_radiobutton"
                ).label._text[0]
                == "Top Level"
            )
            assert (
                pilot.app.screen.query_one(
                    "#transfer_custom_radiobutton"
                ).label._text[0]
                == "Custom"
            )

            # All data label
            assert (
                pilot.app.screen.query_one("#transfer_all_label").renderable
                == "All data from: \n\n - Rawdata \n - "
                "Derivatives \n\nwill be transferred."
            )

            # upload / download widget
            assert (
                pilot.app.screen.query_one(
                    "#transfer_switch_upload_label"
                ).renderable
                == "Upload"
            )
            assert (
                pilot.app.screen.query_one("#transfer_switch").value is False
            )
            assert (
                pilot.app.screen.query_one(
                    "#transfer_switch_download_label"
                ).renderable
                == "Download"
            )
            assert (
                pilot.app.screen.query_one(
                    "#transfer_transfer_button"
                ).label._text[0]
                == "Transfer"
            )

            await self.scroll_to_click_pause(
                pilot, "#transfer_toplevel_radiobutton"
            )
            assert (
                pilot.app.screen.query_one(
                    "#transfer_toplevel_label_top"
                ).renderable
                == "Select top-level folder to transfer."
            )
            assert (
                pilot.app.screen.query_one("#transfer_toplevel_select").value
                == "rawdata"
            )

            await self.scroll_to_click_pause(
                pilot, "#transfer_custom_radiobutton"
            )
            assert (
                pilot.app.screen.query_one(
                    "#transfer_custom_label_top"
                ).renderable
                == "Select top-level folder to transfer."
            )
            assert (
                pilot.app.screen.query_one("#transfer_custom_select").value
                == "rawdata"
            )

            assert (
                pilot.app.screen.query_one(
                    "#transfer_subject_label"
                ).renderable
                == "Subject(s)"
            )
            assert (
                pilot.app.screen.query_one(
                    "#transfer_subject_input"
                ).placeholder
                == "e.g. sub-001"
            )

            assert (
                pilot.app.screen.query_one(
                    "#transfer_session_label"
                ).renderable
                == "Session(s)"
            )
            assert (
                pilot.app.screen.query_one(
                    "#transfer_session_input"
                ).placeholder
                == "e.g. ses-001"
            )

            assert (
                pilot.app.screen.query_one(
                    "#transfer_datatype_label"
                ).renderable
                == "Datatype(s)"
            )

            assert (
                pilot.app.screen.query_one(
                    "#transfer_behav_checkbox"
                ).label._text[0]
                == "behav"
            )
            assert (
                pilot.app.screen.query_one(
                    "#transfer_ephys_checkbox"
                ).label._text[0]
                == "ephys"
            )
            assert (
                pilot.app.screen.query_one(
                    "#transfer_funcimg_checkbox"
                ).label._text[0]
                == "funcimg"
            )
            assert (
                pilot.app.screen.query_one(
                    "#transfer_anat_checkbox"
                ).label._text[0]
                == "anat"
            )

            assert (
                pilot.app.screen.query_one(
                    "#transfer_all_checkbox"
                ).label._text[0]
                == "all"
            )
            assert (
                pilot.app.screen.query_one(
                    "#transfer_all_datatype_checkbox"
                ).label._text[0]
                == "all datatype"
            )
            assert (
                pilot.app.screen.query_one(
                    "#transfer_all_non_datatype_checkbox"
                ).label._text[0]
                == "all non datatype"
            )

            for id in [
                "#transfer_behav_checkbox",
                "#transfer_ephys_checkbox",
                "#transfer_funcimg_checkbox",
                "#transfer_anat_checkbox",
                "#transfer_all_datatype_checkbox",
                "#transfer_all_non_datatype_checkbox",
            ]:
                assert pilot.app.screen.query_one(id).value is False

            assert (
                pilot.app.screen.query_one("#transfer_all_checkbox").value
                is True
            )

            await pilot.pause()

    @pytest.mark.asyncio
    async def test_overwrite_existing_files(self, setup_project_paths):
        """ """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            # Navigate to the existing project and click onto the
            # configs tab.
            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )
            await self.switch_tab(pilot, "transfer")

            # default is off
            self.check_overwrite_existing_files_configs(
                pilot, project_name, value="Never"
            )

            # now  check "Always"
            await self.scroll_to_click_pause(
                pilot, "#transfer_tab_overwrite_select"
            )
            await self.move_select_to_position(
                pilot, "#transfer_tab_overwrite_select", position=5
            )
            self.check_overwrite_existing_files_configs(
                pilot, project_name, value="Always"
            )
            # reload project screen to check persistence of settings.
            await self.exit_to_main_menu_and_reeneter_project_manager(
                pilot, project_name
            )
            await self.switch_tab(pilot, "transfer")

            self.check_overwrite_existing_files_configs(
                pilot, project_name, value="Always"
            )

            # now  check "If Source Newer"
            await self.move_select_to_position(
                pilot, "#transfer_tab_overwrite_select", position=6
            )
            self.check_overwrite_existing_files_configs(
                pilot, project_name, value="If Source Newer"
            )
            # reload project and check settings persist
            await self.exit_to_main_menu_and_reeneter_project_manager(
                pilot, project_name
            )
            await self.switch_tab(pilot, "transfer")

            self.check_overwrite_existing_files_configs(
                pilot, project_name, value="If Source Newer"
            )

    @pytest.mark.asyncio
    async def test_dry_run(self, setup_project_paths):
        """
        Test the dry run setting. This is very similar in structure
        to `test_overwrite_existing_files()`, merge if more persistent
        settings added.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            # Navigate to the existing project and click onto the
            # configs tab.
            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )
            await self.switch_tab(pilot, "transfer")

            # default is off
            self.check_dry_run(pilot, project_name, value=False)

            await self.change_checkbox(pilot, "#transfer_tab_dry_run_checkbox")

            self.check_dry_run(pilot, project_name, value=True)

            # reload project screen to check persistence of settings.
            await self.exit_to_main_menu_and_reeneter_project_manager(
                pilot, project_name
            )
            await self.switch_tab(pilot, "transfer")

            self.check_dry_run(pilot, project_name, value=True)

    # Persistent settings checkers --------------------------------------------
    # These are painfully similar methods, but just different enough to
    # warrant separation. But if more persistent settings are added,
    # combine.

    def check_dry_run(self, pilot, project_name, value):
        assert (
            pilot.app.screen.query_one("#transfer_tab_dry_run_checkbox").value
            == value
        )

        assert pilot.app.screen.interface.tui_settings["dry_run"] is value

        project = DataShuttle(project_name)
        persistent_settings = project._load_persistent_settings()
        assert persistent_settings["tui"]["dry_run"] is value

    def check_overwrite_existing_files_configs(
        self, pilot, project_name, value
    ):
        """"""
        assert (
            pilot.app.screen.query_one("#transfer_tab_overwrite_select").value
            == value
        )

        format_keys = {
            "Never": "never",
            "Always": "always",
            "If Source Newer": "if_source_newer",
        }
        format_val = format_keys[value]

        assert (
            pilot.app.screen.interface.tui_settings["overwrite_existing_files"]
            == format_val
        )

        project = DataShuttle(project_name)
        persistent_settings = project._load_persistent_settings()
        assert (
            persistent_settings["tui"]["overwrite_existing_files"]
            == format_val
        )
