from rich.text import Text
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
)

from datashuttle import DataShuttle
from datashuttle.tui import tui_logic


class ShowConfigsDialog(ModalScreen):
    """
    This window is used to display the existing configs. The message
    above the displayed configs can be configured depending on
    whether a new project was created or an existing project was updated.

    This screen returns None, such that it is displayed until the
    user presses OK via a callback function. See
    `ConfigsContent.setup_configs_for_a_new_project_and_switch_to_tab_screen()`
    for more information.
    """

    def __init__(self, project_configs_dict, message_before_dict=""):
        super(ShowConfigsDialog, self).__init__()

        self.project_configs_dict = project_configs_dict
        self.message_before_dict = message_before_dict

    def compose(self):
        yield Container(
            Container(
                Static(
                    self.message_before_dict,
                    id="display_configs_message_label",
                ),
                DataTable(id="modal_table", show_header=False),
                id="display_configs_message_container",
            ),
            Container(Button("OK"), id="display_configs_ok_button"),
            id="display_configs_top_container",
        )

    def on_mount(self):
        """
        The first row is empty because the header is not displayed.
        """
        ROWS = [("", "")] + [
            (key, value) for key, value in self.project_configs_dict.items()
        ]

        table = self.query_one(DataTable)
        table.add_columns(*ROWS[0])

        for row in ROWS[1:]:
            styled_row = [Text(str(cell), justify="left") for cell in row]
            table.add_row(*styled_row)

    def on_button_pressed(self) -> None:
        self.dismiss(None)


class ConfigsContent(Container):
    """
    This screen holds widgets and logic for setting datashuttle configs.
    It is used in `NewProjectPage` to instantiate a new project and
    initialise configs, or in `TabbedContent` to update an existing
    project's configs.

    If no project exists, additional widgets are shown to allow
    entry of a project name for new project initialisation, and some
    additional information. Widgets are filled with some sensible defaults.

    Otherwise, widgets are filled with the existing projects configs.
    """

    def __init__(self, parent_class, project):
        super(ConfigsContent, self).__init__()

        self.parent_class = parent_class
        self.project = project
        self.config_ssh_widgets = []

    def compose(self):
        """
        `self.config_ssh_widgets` are SSH-setup related widgets
        that are only required when the user selects the SSH
        connection method. These are displayed / hidden based on the
        `connection_method`

        `config_screen_widgets` are core config-related widgets that are
        always displayed.

        `init_only_config_screen_widgets` are only displayed if we
        are instantiating a new project.
        """
        self.config_ssh_widgets = [
            Label("Central Host ID"),
            Input(
                placeholder="e.g. username", id="configs_central_host_id_input"
            ),
            Label("Central Host Username"),
            Input(
                placeholder="e.g. ssh.swc.ucl.ac.uk",
                id="configs_central_host_username_input",
            ),
        ]

        config_screen_widgets = [
            Label("Local Path", id="configs_local_path_label"),
            Input(
                placeholder=r"e.g. C:\path\to\my_projects\my_first_project",
                id="configs_local_path_input",
            ),
            Label("Central Path", id="configs_central_path_label"),
            Input(
                placeholder="e.g. /central/live/username/my_projects/my_first_project",
                id="configs_central_path_input",
            ),
            Label("Connection Method", id="configs_connect_method_label"),
            RadioSet(
                RadioButton(
                    "Local Filesystem",
                    id="configs_local_filesystem_radiobutton",
                ),
                RadioButton("SSH", id="configs_ssh_radiobutton"),
                id="configs_connect_method_radioset",
            ),
            *self.config_ssh_widgets,
            Container(
                Checkbox(
                    "Overwrite Old Files",
                    value=False,
                    id="configs_overwrite_files_checkbox",
                ),
                Checkbox(
                    "Verbose", value=False, id="configs_verbosity_checkbox"
                ),
                Checkbox(
                    "Show Transfer Progress",
                    value=False,
                    id="configs_transfer_progress_checkbox",
                ),
                id="configs_transfer_options_container",
            ),
            Horizontal(
                Button("Configure Project", id="configs_set_configs_button")
            ),
        ]

        init_only_config_screen_widgets = [
            Label("Configure A New Project", id="configs_banner_label"),
            Horizontal(
                Static(
                    "Set your configurations for a new project. For more "
                    "details on each section,\nsee the Datashuttle "
                    "documentation. Once configs are set, you will "
                    "be able\nto use the 'Create' and 'Transfer' tabs.",
                    id="configs_info_label",
                )
            ),
            Label("Project Name", id="configs_name_label"),
            Input(
                placeholder="e.g. my_first_project", id="configs_name_input"
            ),
        ]

        if not self.project:
            config_screen_widgets = (
                init_only_config_screen_widgets + config_screen_widgets
            )

        yield Container(*config_screen_widgets, id="configs_container")

    def on_mount(self):
        """
        When we have mounted the widgets, the following logic depends on whether
        we are setting up a new project (`self.project is `None`) or have
        an instantiated project.

        If we have a project, then we want to fill
        the widgets with the existing configs. Otherwise, we set to some
        reasonable defaults, required to determine the display of SSH widgets.
        "overwrite_files_checkbox" should be off by default anyway if
        `value` is not set, but we set here anyway as it is critical
        this is not on by default.

        TODO: this duplicates how defaults are set between TUI and
        datashuttle API, which is not good. This should be centralised.
        """
        container = self.query_one("#configs_transfer_options_container")
        container.border_title = "Transfer Options"
        if self.project:
            self.fill_widgets_with_project_configs()
        else:
            radiobutton = self.query_one(
                "#configs_local_filesystem_radiobutton"
            )
            radiobutton.value = True
            self.switch_ssh_widgets_display(display_bool=False)

            checkbox = self.query_one("#configs_overwrite_files_checkbox")
            checkbox.value = False

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """
        Update the displayed SSH widgets when the `connection_method`
        radiobuttons are changed.
        """
        display_bool = True if str(event.pressed.label) == "SSH" else False
        self.switch_ssh_widgets_display(display_bool)

    def switch_ssh_widgets_display(self, display_bool):
        """
        Show or hide SSH-related configs based on whether the current
        `connection_method` widget is "ssh" or "local_filesystem".
        """
        for widget in self.config_ssh_widgets:
            widget.display = display_bool

    def on_button_pressed(self, event: Button.Pressed):
        """
        Enables the Make Folders button to read out current input values
        and use these to call project.make_folders().
        """
        if event.button.id == "configs_set_configs_button":
            if not self.project:
                self.setup_configs_for_a_new_project_and_switch_to_tab_screen()
            else:
                self.setup_configs_for_an_existing_project()

    def setup_configs_for_a_new_project_and_switch_to_tab_screen(self):
        """
        If a project does not exist, we are in NewProjectScreen.
        We need to instantiate a new project based on the project name,
        create configs based on the current widget settings, and display
        any errors to the user, along with confirmation and the
        currently set configs.

        Once complete, we dismiss the parent screen (NewProjectScreen),
        returning the new instantiated project. Due to the mainwindow
        `push_screen` callback, this will open the TabbedContent window
        with the new project.

        Note that in order to wait at the ShowConfigsDialog screen
        until the user presses 'OK', it is necessary to wait for a
        callback function from this screen. We do not care about it's
        output, so make the callback a lambda function that when called
        will immediately call the parent's dismiss function with the
        newly instantiated project.
        """
        project_name = self.query_one("#configs_name_input").value

        try:
            project = DataShuttle(project_name)

            cfg_kwargs = self.get_datashuttle_inputs_from_widgets()

            project.make_config_file(**cfg_kwargs)

            self.parent_class.mainwindow.push_screen(
                ShowConfigsDialog(
                    tui_logic.get_textual_compatible_project_configs(
                        project.cfg
                    ),
                    "A DataShuttle project with the below "
                    "configs has now been created.\n\n Click 'OK' to proceed to "
                    "the project page, where you will \n be able to create and "
                    "transfer project folders.",
                ),
                lambda _: self.parent_class.dismiss(project),
            )

        except BaseException as e:
            self.parent_class.mainwindow.show_modal_error_dialog(str(e))

    def setup_configs_for_an_existing_project(self):
        """
        If the project already exists, we are on the TabbedContent
        screen. We need to get the configs to set from the current
        widget values and display the set values (or an error if
        there was a problem during setup) to the user.
        """
        cfg_kwargs = self.get_datashuttle_inputs_from_widgets()

        try:
            self.project.make_config_file(**cfg_kwargs)

            configs_to_show = tui_logic.get_textual_compatible_project_configs(
                self.project.cfg
            )

            self.parent_class.mainwindow.push_screen(
                ShowConfigsDialog(
                    configs_to_show,
                    "The configs for this project have been successfully"
                    " set to the following values:",
                )
            )
        except BaseException as e:
            self.parent_class.mainwindow.show_modal_error_dialog(str(e))

    def fill_widgets_with_project_configs(self):
        """
        If a configured project already exists, we want to fill the
        widgets with the current project configs. This in some instances
        requires recasting to a new type of changing the value.

        In the case of the `connection_method` widget, the associated
        "ssh" widgets are hidden / displayed based on the current setting,
        in `self.switch_ssh_widgets_display()`.
        """
        cfg_to_load = tui_logic.get_textual_compatible_project_configs(
            self.project.cfg
        )

        # Local Path
        input = self.query_one("#configs_local_path_input")
        input.value = cfg_to_load["local_path"]

        # Central Path
        input = self.query_one("#configs_central_path_input")
        input.value = cfg_to_load["central_path"]

        # Connection Method
        ssh_on = True if cfg_to_load["connection_method"] == "ssh" else False

        radiobutton = self.query_one("#configs_ssh_radiobutton")
        radiobutton.value = ssh_on

        radiobutton = self.query_one("#configs_local_filesystem_radiobutton")
        radiobutton.value = not ssh_on

        self.switch_ssh_widgets_display(display_bool=ssh_on)

        # Central Host ID
        input = self.query_one("#configs_central_host_id_input")
        value = (
            ""
            if cfg_to_load["central_host_id"] is None
            else cfg_to_load["central_host_id"]
        )
        input.value = value

        # Central Host Username
        input = self.query_one("#configs_central_host_username_input")
        value = (
            ""
            if cfg_to_load["central_host_username"] is None
            else cfg_to_load["central_host_username"]
        )
        input.value = value

        # Overwrite Files Checkbox
        checkbox = self.query_one("#configs_overwrite_files_checkbox")
        checkbox.value = self.project.cfg["overwrite_old_files"]

        # Transfer Verbosity
        checkbox = self.query_one("#configs_verbosity_checkbox")
        bool = True if self.project.cfg["transfer_verbosity"] == "v" else False
        checkbox.value = bool

        # Show Transfer Progress
        checkbox = self.query_one("#configs_transfer_progress_checkbox")
        checkbox.value = self.project.cfg["show_transfer_progress"]

    def get_datashuttle_inputs_from_widgets(self):
        """
        Get the configs to pass to `make_config_file()` from
        the current TUI settings. In some instances this requires
        changing the value form (e.g. from `bool` to `"-v"` in
        'transfer verbosity'.
        """
        cfg_kwargs = {}

        cfg_kwargs["local_path"] = self.query_one(
            "#configs_local_path_input"
        ).value

        cfg_kwargs["central_path"] = self.query_one(
            "#configs_central_path_input"
        ).value

        cfg_kwargs["connection_method"] = (
            "ssh"
            if self.query_one("#configs_ssh_radiobutton").value
            else "local_filesystem"
        )

        cfg_kwargs["central_host_id"] = self.query_one(
            "#configs_central_host_id_input"
        ).value

        cfg_kwargs["central_host_username"] = self.query_one(
            "#configs_central_host_username_input"
        ).value

        cfg_kwargs["overwrite_old_files"] = self.query_one(
            "#configs_overwrite_files_checkbox"
        ).value

        verbosity_kwarg = (
            "vv"
            if self.query_one("#configs_verbosity_checkbox").value
            else "v"
        )
        cfg_kwargs["transfer_verbosity"] = verbosity_kwarg

        cfg_kwargs["show_transfer_progress"] = self.query_one(
            "#configs_transfer_progress_checkbox"
        ).value

        return cfg_kwargs


class NewProjectScreen(Screen):
    """
    Screen for setting up a new datashuttle project, by
    inputting the desired configs. This uses the
    ConfigsContent window to display and set the configs.

    If "Main Manu" button is pressed, the callback function
    returns None, so the project screen is not switched to.

    Otherwise, the logic for creating and validating the
    project is in ConfigsContent. ConfigsContent calls
    the dismiss method of this class to return
    an initialised project to mainwindow.
    See ConfigsContent.on_button_pressed() for more details

    Parameters
    ----------

    mainwindow : TuiApp
    """

    TITLE = "Make New Project"

    def __init__(self, mainwindow):
        super(NewProjectScreen, self).__init__()

        self.mainwindow = mainwindow

    def compose(self):
        yield Header()
        yield Button("Main Menu", id="all_main_menu_buttons")
        yield ConfigsContent(self, project=None)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "all_main_menu_buttons":
            self.dismiss(None)
