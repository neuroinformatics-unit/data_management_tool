import pytest
from tui_base import TuiBase

from datashuttle.tui.app import TuiApp


class TestTuiLocalOnlyProject(TuiBase):

    @pytest.mark.asyncio
    async def test_local_only_make_project(
        self,
        empty_project_paths,
    ):
        """
        Test a local-only project, where the only set config is `local_path`.
        Set up a local project, and check the 'Transfer' tab is disabled and
        set configs are propagated.
        """
        tmp_config_path, tmp_path, project_name = empty_project_paths.values()
        local_path = tmp_path / "local"

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            await self.setup_and_check_local_only_project(
                pilot, project_name, local_path
            )

            # Check the configs are set correctly on the project itself,
            # and the placeholder tab is set and disabled.
            await self.scroll_to_click_pause(
                pilot, "#configs_go_to_project_screen_button"
            )
            assert pilot.app.screen.interface.project.cfg == {
                "local_path": local_path / project_name,
                "central_path": None,
                "connection_method": None,
                "central_host_id": None,
                "central_host_username": None,
            }
            assert pilot.app.screen.query_one(
                "#placeholder_transfer_tab"
            ).disabled

            await pilot.pause()

    @pytest.mark.asyncio
    async def test_local_project_to_full(
        self,
        empty_project_paths,
    ):
        """
        It is possible to switch between a 'local-only' project (`local_path`
        only set) and a full project with all configs set, where transfer is allowed.
        Here start as a local project then set configs so we become a full project.
        """
        tmp_config_path, tmp_path, project_name = empty_project_paths.values()
        local_path = tmp_path / "local"
        central_path = tmp_path / "central"

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            # Set up a local-only project
            await self.setup_and_check_local_only_project(
                pilot, project_name, local_path
            )

            await self.scroll_to_click_pause(
                pilot, "#configs_go_to_project_screen_button"
            )

            await self.switch_tab(pilot, "configs")

            # Set full-project configs
            await self.scroll_to_click_pause(pilot, "#configs_ssh_radiobutton")
            await self.fill_input(
                pilot, "#configs_central_path_input", central_path.as_posix()
            )
            await self.fill_input(
                pilot, "#configs_central_host_username_input", "some_username"
            )
            await self.fill_input(
                pilot, "#configs_central_host_id_input", "some_host"
            )

            # Save configs, this displays a screen indicating it is necessary to
            # refresh the project manager page, check this is correct. This is to
            # refresh the tab from a placeholder to full.
            await self.scroll_to_click_pause(
                pilot,
                "#configs_save_configs_button",
            )
            await self.close_messagebox(pilot)

            assert (
                "The project type was changed from local to full."
                in pilot.app.screen.query_one(
                    "#messagebox_message_label"
                ).renderable
            )
            await self.close_messagebox(pilot)

            # Go onto the project manager window and check the
            # configs are correct and transfer tab is displayed correctly.
            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )
            assert not pilot.app.screen.query_one(
                "#tabscreen_transfer_tab"
            ).disabled

            assert pilot.app.screen.interface.project.cfg == {
                "local_path": local_path / project_name,
                "central_path": central_path / project_name,
                "connection_method": "ssh",
                "central_host_id": "some_host",
                "central_host_username": "some_username",
            }

            await pilot.pause()

    @pytest.mark.asyncio
    async def test_full_project_to_local(
        self,
        setup_project_paths,
    ):
        """
        Very similar to `test_check_local_only_project_to_full()`, but
        going from a full project to a local only. This still requires
        a refresh so the full transfer tab can be set to a placeholder.
        """
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()
        local_path = tmp_path / "local"

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            # Fixture generated a full project, switch to it's
            # project manager screen here.
            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )

            # Now set configs for a local-only project
            await self.switch_tab(pilot, "configs")

            await self.scroll_to_click_pause(
                pilot, "#configs_local_only_radiobutton"
            )

            # Save and check the refresh screen is shown
            await self.scroll_to_click_pause(
                pilot,
                "#configs_save_configs_button",
            )
            await self.close_messagebox(pilot)

            assert (
                "The project type was changed from full to local"
                in pilot.app.screen.query_one(
                    "#messagebox_message_label"
                ).renderable
            )
            await self.close_messagebox(pilot)

            # Force refresh, for some reason the project-selector button on
            # main screen is getting stuck every ~1/5 times without this.
            pilot.app.screen.recompose()
            pilot.app.refresh()
            pilot.app.screen.refresh()

            await pilot.pause()

            # Go back to the transfer screen and check the configs are
            # correct and the placeholder tab is used and disabled.
            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )
            assert pilot.app.screen.query_one(
                "#placeholder_transfer_tab"
            ).disabled

            assert pilot.app.screen.interface.project.cfg == {
                "local_path": local_path / project_name,
                "central_path": None,
                "connection_method": None,
                "central_host_id": None,
                "central_host_username": None,
            }

            await pilot.pause()

    async def setup_and_check_local_only_project(
        self, pilot, project_name, local_path
    ):
        """
        Set up a local-only project by filling in the `local_path` and setting
        the radio button to the no-connection option.
        """
        # Move to configs window
        await self.scroll_to_click_pause(
            pilot, "#mainwindow_new_project_button"
        )

        configs_content = pilot.app.screen.query_one(
            "#new_project_configs_content"
        )

        # Input `local_path` and placeholder text in `central_path` which
        # will be deleted when the no-connection option is selected.
        await self.fill_input(pilot, "#configs_name_input", project_name)
        await self.fill_input(
            pilot, "#configs_local_path_input", local_path.as_posix()
        )
        await self.fill_input(pilot, "#configs_central_path_input", "to_del")

        assert (  # just ensure this worked otherwise next test is pointless
            configs_content.query_one("#configs_central_path_input").value
            == "to_del"
        )

        # Select no-connection and check central path input is cleared and disabled
        await self.scroll_to_click_pause(
            pilot, "#configs_local_only_radiobutton"
        )

        assert (
            configs_content.query_one("#configs_central_path_input").value
            == ""
        )
        assert configs_content.query_one(
            "#configs_central_path_input"
        ).disabled

        # Save the configs and close the confirmation window.
        await self.scroll_to_click_pause(
            pilot,
            "#configs_save_configs_button",
        )
        await self.close_messagebox(pilot)
