import pytest_asyncio
import test_utils
from textual.widgets._tabbed_content import ContentTab

from datashuttle.configs import canonical_configs
from datashuttle.tui.screens.project_manager import ProjectManagerScreen
from datashuttle.tui.screens.project_selector import ProjectSelectorScreen


class TuiBase:
    """
    Contains fixtuers and helper functions for TUI tests.
    """

    def tui_size(self):
        """
        If the TUI screen in the test environment is not
        large enough, often the error
        `textual.pilot.OutOfBounds: Target offset is
         outside of currently-visible screen region.`
        is encountered.

        The solution is to ensure the screen is large enough
        in the test environment.
        """
        return (500, 500)

    @pytest_asyncio.fixture(scope="function")
    async def empty_project_paths(self, tmp_path_factory, monkeypatch):
        """
        Get the paths and project name for a non-existent (i.e. not
        yet setup) project.
        """
        project_name = "my-test-project"
        tmp_path = tmp_path_factory.mktemp("test")
        tmp_config_path = tmp_path / "config"

        self.monkeypatch_get_datashuttle_path(tmp_config_path, monkeypatch)
        self.monkeypatch_print(monkeypatch)

        assert not any(list(tmp_config_path.glob("**")))

        yield {
            "tmp_config_path": tmp_config_path,
            "tmp_path": tmp_path,
            "project_name": project_name,
        }

    @pytest_asyncio.fixture(scope="function")
    async def setup_project_paths(self, empty_project_paths):
        """
        Get the paths and project name for a setup project.
        """
        test_utils.setup_project_fixture(
            empty_project_paths["tmp_path"],
            empty_project_paths["project_name"],
        )

        return empty_project_paths

    def monkeypatch_get_datashuttle_path(self, tmp_config_path, _monkeypatch):
        """
        For these tests, store the datashuttle configs (usually stored in
        Path.home()) in the `tmp_path` provided by pytest, as it simplifies
        testing here.

        This is not done for general tests because
        1) It is further from the actual datashuttle behaviour
        2) It fails for testing CLI, because CLI spawns a new process in
           which `get_datashuttle_path()` is not monkeypatched.
        """

        def mock_get_datashuttle_path():
            return tmp_config_path

        _monkeypatch.setattr(
            "datashuttle.configs.canonical_folders.get_datashuttle_path",
            mock_get_datashuttle_path,
        )

    def monkeypatch_print(self, _monkeypatch):
        """
        Calls to `print` in datashuttle crash the TUI in the
        test environment. I am not sure why. Get around this
        in tests by monkeypatching the datashuttle print method.
        """

        def return_none(arg1, arg2=None):
            return

        _monkeypatch.setattr(
            "datashuttle.utils.utils.print_message_to_user", return_none
        )

    async def fill_input(self, pilot, id, value):
        """
        Fill and input of `id` with `value`.
        """
        await self.scroll_to_click_pause(pilot, id)
        pilot.app.screen.query_one(id).value = ""
        await pilot.press(*value)
        await pilot.pause()

    async def setup_existing_project_create_tab_filled_sub_and_ses(
        self, pilot, project_name, create_folders=False
    ):
        """
        Set up an existing project and switch to the 'Create' tab
        on the project manager screen.
        """
        await self.check_and_click_onto_existing_project(pilot, project_name)

        await self.fill_input(
            pilot, "#create_folders_subject_input", "sub-001"
        )
        await self.fill_input(
            pilot, "#create_folders_session_input", "ses-001"
        )
        if create_folders:
            await self.scroll_to_click_pause(
                pilot,
                "#create_folders_create_folders_button",
            )

    async def double_click(self, pilot, id, control=False):
        """
        Double-click on a widget of `id`, if `control` is `True` the
        control modifier key will be used.
        """
        for _ in range(2):
            await self.scroll_to_click_pause(pilot, id, control=control)

    async def reload_tree_nodes(self, pilot, id, num_nodes):
        """
        For some reason, for TUI tree nodes to register in the
        test environment all need to have `reload_node` called on
        the node.
        """
        for node in range(num_nodes):
            await pilot.app.screen.query_one(id).reload_node(
                pilot.app.screen.query_one(id).get_node_at_line(node)
            )
            await pilot.pause()

    async def hover_and_press_tree(self, pilot, id, hover_line, press_string):
        """
        Hover over a directorytree at a node-line and press a specific string
        """
        await pilot.pause()
        pilot.app.screen.query_one(id).hover_line = hover_line
        await pilot.pause()
        await self.press_tree(pilot, id, press_string)

    async def press_tree(self, pilot, id, press_string):
        """
        Click on a tree to give it focus and press buttons
        """
        await self.scroll_to_click_pause(pilot, id)
        await pilot.press(press_string)
        await pilot.pause()

    async def scroll_to_and_pause(self, pilot, id):
        """
        Scroll to a widget and pause.
        """
        widget = pilot.app.screen.query_one(id)
        widget.scroll_visible(animate=False)
        await pilot.pause()

    async def scroll_to_click_pause(self, pilot, id, control=False):
        """
        Scroll to a widget, click it and call pause.
        """
        await self.scroll_to_and_pause(pilot, id)
        await pilot.click(id, control=control)
        await pilot.pause()

    async def check_and_click_onto_existing_project(self, pilot, project_name):
        """
        From the main menu, go onto the select project page and
        select the project created in the test environment.
        Perform general TUI checks during the navigation.
        """
        await pilot.click("#mainwindow_existing_project_button")
        await pilot.pause()

        assert isinstance(pilot.app.screen, ProjectSelectorScreen)
        assert len(pilot.app.screen.project_names) == 1
        assert project_name in pilot.app.screen.project_names

        await pilot.click(f"#{project_name}")
        await pilot.pause()

        assert isinstance(pilot.app.screen, ProjectManagerScreen)
        assert pilot.app.screen.title == f"Project: {project_name}"
        assert (
            pilot.app.screen.query_one("#tabscreen_tabbed_content").active
            == "tabscreen_create_tab"
        )

    async def change_checkbox(self, pilot, id):
        pilot.app.screen.query_one(id).toggle()
        await pilot.pause()

    async def switch_tab(self, pilot, tab):
        assert tab in ["create", "transfer", "configs", "logging"]
        content_tab = ContentTab.add_prefix(f"tabscreen_{tab}_tab")
        await self.scroll_to_click_pause(pilot, f"Tab#{content_tab}")

    async def turn_off_all_datatype_checkboxes(self, pilot, tab="create"):
        """
        Make sure all checkboxes are off to start
        """
        assert tab in ["create", "transfer"]

        checkbox_names = canonical_configs.get_broad_datatypes()
        if tab == "create":
            checkboxes_id = "#create_folders_datatype_checkboxes"
        else:
            checkbox_names.extend(["all", "all_datatype", "all_non_datatype"])
            checkboxes_id = "#transfer_custom_datatype_checkboxes"

        for datatype in checkbox_names:
            id = f"#{tab}_{datatype}_checkbox"
            if pilot.app.screen.query_one(id).value:
                await self.change_checkbox(pilot, id)

        datatype_config = pilot.app.screen.query_one(
            checkboxes_id
        ).datatype_config

        assert all(val["on"] is False for val in datatype_config.values())

    async def exit_to_main_menu_and_reeneter_project_manager(
        self, pilot, project_name
    ):
        """
        Exist from the project manager screen, then re-enter back
        into the project. This refreshes the screen and is important in
        testing state is preserved across re-loading.
        """
        await self.scroll_to_click_pause(pilot, "#all_main_menu_buttons")
        assert pilot.app.screen.id == "_default"
        await self.check_and_click_onto_existing_project(pilot, project_name)

    async def close_messagebox(self, pilot):
        """
        Close a messageobox, for some reason clicking the 'OK'
        button does not work.
        """
        pilot.app.screen.on_button_pressed()
        await pilot.pause()

    async def move_select_to_position(self, pilot, id, position):
        """
        Move a select widget to a specific position (e.g. "rawdata"
        or "derivatives" select). The position can be determined
        by trial and error.
        """
        await pilot.click(id)
        await pilot.click(id, offset=(2, position))
        await pilot.pause()
