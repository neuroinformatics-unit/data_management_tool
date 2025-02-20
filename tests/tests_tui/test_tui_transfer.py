import pytest
import test_utils
from tui_base import TuiBase

from datashuttle.configs import canonical_configs
from datashuttle.tui.app import TuiApp


class TestTuiTransfer(TuiBase):
    """
    Test transferring through the TUI (entire project, top
    level only or custom). This class leverages the underlying
    test utils that check API transfers.
    """

    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    @pytest.mark.asyncio
    async def test_transfer_entire_project(
        self, setup_project_paths, upload_or_download
    ):
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        subs, sessions = test_utils.get_default_sub_sessions_to_test()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )
            await self.switch_tab(pilot, "transfer")

            project = pilot.app.screen.interface.project

            base_path_to_check = self.setup_project_for_data_transfer(
                project,
                subs,
                sessions,
                ["rawdata", "derivatives"],
                upload_or_download,
            )

            await self.run_transfer(pilot, upload_or_download)

            for top_level_folder in ["rawdata", "derivatives"]:
                test_utils.check_datatype_sub_ses_uploaded_correctly(
                    base_path_to_check / top_level_folder,
                    ["behav", "ephys", "funcimg", "anat"],
                    subs,
                    sessions,
                )

            await pilot.pause()

            await self.check_persistent_settings(pilot)

            await pilot.pause()

    async def check_persistent_settings(self, pilot):
        """
        Run transfer with each overwrite setting and check it is propagated
        to datashuttle methods.
        """
        await self.set_and_check_persistent_settings(pilot, "never", True)

        await self.set_and_check_persistent_settings(pilot, "always", False)

        await self.set_and_check_persistent_settings(
            pilot, "if_source_newer", True
        )

    async def set_overwrite_checkbox(self, pilot, overwrite_setting):
        """"""
        all_positions = {"never": None, "always": 5, "if_source_newer": 6}
        position = all_positions[overwrite_setting]

        if position is not None:
            await self.move_select_to_position(
                pilot, "#transfer_tab_overwrite_select", position=position
            )

    async def set_transfer_tab_dry_run_checkbox(self, pilot, dry_run_setting):
        if (
            pilot.app.screen.query_one("#transfer_tab_dry_run_checkbox")
            is not dry_run_setting
        ):
            await self.change_checkbox(pilot, "#transfer_tab_dry_run_checkbox")

    async def set_and_check_persistent_settings(
        self, pilot, overwrite_setting, dry_run_setting
    ):
        """
        Run transfer with an overwrite setting and check it is propagated
        to datashuttle methods by checking the logs.
        """
        await self.set_overwrite_checkbox(pilot, overwrite_setting)
        await self.set_transfer_tab_dry_run_checkbox(pilot, dry_run_setting)

        logging_path = pilot.app.screen.interface.project.get_logging_path()

        test_utils.delete_log_files(logging_path)
        await self.scroll_to_click_pause(pilot, "#transfer_transfer_button")
        await self.scroll_to_click_pause(pilot, "#confirm_ok_button")
        await self.close_messagebox(pilot)

        log = test_utils.read_log_file(logging_path)
        assert f"overwrite_existing_files': '{overwrite_setting}'" in log
        assert f"dry_run': {dry_run_setting}" in log

    @pytest.mark.parametrize("top_level_folder", ["rawdata", "derivatives"])
    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    @pytest.mark.asyncio()
    async def test_transfer_top_level_folder(
        self, setup_project_paths, top_level_folder, upload_or_download
    ):
        """"""
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        subs, sessions = test_utils.get_default_sub_sessions_to_test()

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )
            await self.switch_tab(pilot, "transfer")
            await self.scroll_to_click_pause(
                pilot, "#transfer_toplevel_radiobutton"
            )
            project = pilot.app.screen.interface.project

            base_path_to_check = self.setup_project_for_data_transfer(
                project, subs, sessions, [top_level_folder], upload_or_download
            )

            await self.switch_top_level_folder_select(
                pilot, "#transfer_toplevel_select", top_level_folder
            )

            await self.run_transfer(pilot, upload_or_download)

            test_utils.check_working_top_level_folder_only_exists(
                top_level_folder,
                base_path_to_check / top_level_folder,
                subs,
                sessions,
            )
            await pilot.pause()

            await self.check_persistent_settings(
                pilot,
            )

            await pilot.pause()

    @pytest.mark.parametrize("top_level_folder", ["rawdata", "derivatives"])
    @pytest.mark.parametrize("upload_or_download", ["upload", "download"])
    @pytest.mark.asyncio
    async def test_transfer_custom(
        self, setup_project_paths, top_level_folder, upload_or_download
    ):
        tmp_config_path, tmp_path, project_name = setup_project_paths.values()

        subs, sessions = test_utils.get_default_sub_sessions_to_test()

        sub_to_transfer = "sub-002"
        ses_to_transfer = "ses-003"

        app = TuiApp()
        async with app.run_test(size=self.tui_size()) as pilot:

            await self.check_and_click_onto_existing_project(
                pilot, project_name
            )
            await self.switch_tab(pilot, "transfer")
            await self.scroll_to_click_pause(
                pilot, "#transfer_custom_radiobutton"
            )
            project = pilot.app.screen.interface.project

            base_path_to_check = self.setup_project_for_data_transfer(
                project, subs, sessions, [top_level_folder], upload_or_download
            )

            await self.switch_top_level_folder_select(
                pilot, "#transfer_custom_select", top_level_folder
            )

            await self.fill_input(
                pilot, "#transfer_subject_input", sub_to_transfer
            )

            await self.fill_input(
                pilot, "#transfer_session_input", ses_to_transfer
            )

            await self.scroll_to_click_pause(
                pilot, "#transfer_all_checkbox"
            )  # turn this off

            await self.scroll_to_click_pause(
                pilot, "#transfer_behav_checkbox"
            )  # and these on...
            await self.scroll_to_click_pause(
                pilot, "#transfer_funcimg_checkbox"
            )

            await self.run_transfer(pilot, upload_or_download)

            folders_used = test_utils.get_all_broad_folders_used(value=False)
            folders_used.update({"behav": True, "funcimg": True})

            test_utils.check_working_top_level_folder_only_exists(
                top_level_folder,
                base_path_to_check / top_level_folder,
                [sub_to_transfer],
                [ses_to_transfer],
                folders_used,
            )

            await pilot.pause()

            await self.check_persistent_settings(
                pilot,
            )

            await pilot.pause()

    async def switch_top_level_folder_select(
        self, pilot, id, top_level_folder
    ):

        if top_level_folder == "rawdata":
            assert pilot.app.screen.query_one(id).value == "rawdata"
        else:
            await self.move_select_to_position(pilot, id, position=5)
            assert pilot.app.screen.query_one(id).value == "derivatives"

    async def run_transfer(self, pilot, upload_or_download):
        """"""
        # Check assumed default is correct on the transfer switch
        assert pilot.app.screen.query_one("#transfer_switch").value is False

        if upload_or_download == "download":
            await self.scroll_to_click_pause(pilot, "#transfer_switch")

        await self.scroll_to_click_pause(pilot, "#transfer_transfer_button")
        await self.scroll_to_click_pause(pilot, "#confirm_ok_button")
        await self.close_messagebox(pilot)

    def setup_project_for_data_transfer(
        self,
        project,
        subs,
        sessions,
        top_level_folder_list,
        upload_or_download,
    ):
        """"""
        for top_level_folder in top_level_folder_list:
            test_utils.make_and_check_local_project_folders(
                project,
                top_level_folder,
                subs,
                sessions,
                canonical_configs.get_broad_datatypes(),
            )
        (
            _,
            base_path_to_check,
        ) = test_utils.handle_upload_or_download(
            project, upload_or_download, transfer_method=None
        )

        return base_path_to_check
