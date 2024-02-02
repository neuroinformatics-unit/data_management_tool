from __future__ import annotations

from typing import TYPE_CHECKING, List, Literal, Optional

if TYPE_CHECKING:
    from pathlib import Path

    from textual.app import ComposeResult

    from datashuttle.tui.app import App
    from datashuttle.tui.interface import Interface

from textual.containers import Horizontal
from textual.widgets import (
    Button,
    Label,
)

from datashuttle.tui.custom_widgets import (
    ClickableInput,
    CustomDirectoryTree,
    DatatypeCheckboxes,
    TreeAndInputTab,
)
from datashuttle.tui.screens.create_folder_settings import (
    CreateFoldersSettingsScreen,
)
from datashuttle.tui.utils.tui_decorators import require_double_click
from datashuttle.tui.utils.tui_validators import NeuroBlueprintValidator

Prefix = Literal["sub", "ses"]


class CreateFoldersTab(TreeAndInputTab):
    """
    Create new project files formatted according to the NeuroBlueprint specification.
    """

    def __init__(self, mainwindow: App, interface: Interface) -> None:
        super(CreateFoldersTab, self).__init__(
            "Create", id="tabscreen_create_tab"
        )
        self.mainwindow = mainwindow
        self.interface = interface

        self.prev_click_time = 0.0

    def compose(self) -> ComposeResult:
        yield CustomDirectoryTree(
            self.mainwindow,
            self.interface.get_configs()["local_path"],
            id="create_folders_directorytree",
        )
        yield Label("Subject(s)", id="create_folders_subject_label")
        yield ClickableInput(
            self.mainwindow,
            id="create_folders_subject_input",
            placeholder="e.g. sub-001",
            validate_on=["changed", "submitted"],
            validators=[NeuroBlueprintValidator("sub", self)],
        )
        yield Label("Session(s)", id="tabscreen_session_label")
        yield ClickableInput(
            self.mainwindow,
            id="create_folders_session_input",
            placeholder="e.g. ses-001",
            validate_on=["changed", "submitted"],
            validators=[NeuroBlueprintValidator("ses", self)],
        )
        yield Label("Datatype(s)", id="create_folders_datatype_label")
        yield DatatypeCheckboxes(self.interface)
        yield Horizontal(
            Button("Create Folders", id="create_folders_make_button"),
            Button(
                "Settings",
                id="create_folders_settings_button",
            ),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """
        Enables the Create Folders button to read out current input values
        and use these to call project.create_folders().

        `unused_bool` is necessary to get dismiss to call
        the callback.
        """
        if event.button.id == "create_folders_make_button":
            self.create_folders()

        elif event.button.id == "create_folders_settings_button":
            self.mainwindow.push_screen(
                CreateFoldersSettingsScreen(self.mainwindow, self.interface),
                lambda unused_bool: self.revalidate_inputs(["sub", "ses"]),
            )

    @require_double_click
    def on_clickable_input_clicked(
        self, event: ClickableInput.Clicked
    ) -> None:
        """
        Handled a double click on the custom ClickableInput widget,
        which indicates the input should be filled with a suggested value.

        Determine if we have the subject or session input, and
        if it was a left or right click. Then, fill with either
        a generic suggestion or suggestion based on next sub / ses number.
        """
        input_id = event.input.id

        prefix: Literal["sub", "ses"] = (
            "sub" if "subject" in input_id else "ses"
        )

        if event.button == 1:
            self.fill_input_with_template(prefix, input_id)
        elif event.button == 3:
            self.fill_input_with_next_sub_or_ses_template(prefix, input_id)

    def on_custom_directory_tree_directory_tree_special_key_press(
        self, event: CustomDirectoryTree.DirectoryTreeSpecialKeyPress
    ):
        """
        Handle a key press on the directory tree, which can refresh the
        directorytree or fill / append subject/session folder name to
        the relevant input widget.
        """
        if event.key == "ctrl+r":
            self.reload_directorytree()

        elif event.key in ["ctrl+a", "ctrl+f"]:
            self.handle_fill_input_from_directorytree(
                "#create_folders_subject_input",
                "#create_folders_session_input",
                event,
            )

    def fill_input_with_template(self, prefix: Prefix, input_id: str) -> None:
        """
        Given the `name_template`, fill the sub or ses
        Input with the template (based on `prefix`).
        If `self.templates` is off, then just suggest "sub-" or "ses-".
        """
        if self.templates_on(prefix):
            fill_value = self.interface.get_name_templates()[prefix]
        else:
            fill_value = f"{prefix}-"

        input = self.query_one(f"#{input_id}")
        input.value = fill_value

    def templates_on(self, prefix: Prefix) -> bool:
        return (
            self.interface.get_name_templates()["on"]
            and self.interface.get_name_templates()[prefix] is not None
        )

    # Validation
    # ----------------------------------------------------------------------------------

    def revalidate_inputs(self, all_prefixes: List[str]) -> None:
        """
        Revalidate and style both subject and session
        inputs based on their value.
        """
        input_names = {
            "sub": "#create_folders_subject_input",
            "ses": "#create_folders_session_input",
        }
        for prefix in all_prefixes:
            key = input_names[prefix]

            value = self.query_one(key).value
            self.query_one(key).validate(value=value)

    def update_input_tooltip(self, message: List[str], prefix: Prefix) -> None:
        """
        Update the value of a subject or session tooltip, which
        indicates the validation status of the input value.
        """
        id = (
            "#create_folders_subject_input"
            if prefix == "sub"
            else "#create_folders_session_input"
        )
        input = self.query_one(id)
        input.tooltip = message if any(message) else None

    # ----------------------------------------------------------------------------------
    # Datashuttle Callers
    # ----------------------------------------------------------------------------------

    # Create Folders
    # ----------------------------------------------------------------------------------

    def create_folders(self) -> None:
        """
        Create project folders based on current widget input
        through the datashuttle API.
        """
        ses_names: Optional[List[str]]

        sub_names, ses_names, datatype = self.get_sub_ses_names_and_datatype(
            "#create_folders_subject_input", "#create_folders_session_input"
        )

        if ses_names == [""]:
            ses_names = None

        success, output = self.interface.create_folders(
            sub_names, ses_names, datatype
        )

        if success:
            self.reload_directorytree()
        else:
            self.mainwindow.show_modal_error_dialog(output)

    def reload_directorytree(self) -> None:
        self.query_one("#create_folders_directorytree").reload()

    # Filling Inputs
    # ----------------------------------------------------------------------------------

    def fill_input_with_next_sub_or_ses_template(
        self, prefix: Prefix, input_id: str
    ) -> None:
        """
        This fills a sub / ses Input with a suggested name based on the
        next subject / session in the project (local).

        If `name_templates` are set, then the sub- or ses- first key
        of the template name will be replaced with the suggested
        sub or ses key-value. Otherwise, the sub/ses key-value pair only
        will be suggested.

        Parameters

        prefix : Prefix
            Whether to fill the subject or session Input

        input_id : str
            The textual input name to update.
        """
        if prefix == "sub":
            next_val = self.interface.get_next_sub_number()
        else:
            sub_names = self.query_one(
                "#create_folders_subject_input"
            ).as_names_list()

            if len(sub_names) > 1:
                self.mainwindow.show_modal_error_dialog(
                    "Can only suggest next session number when a "
                    "single subject is provided."
                )
                return

            if sub_names == [""]:
                self.mainwindow.show_modal_error_dialog(
                    "Must input a subject number before suggesting "
                    "next session number."
                )
                return

            else:
                sub = sub_names[0]

            next_val = self.interface.get_next_ses_number(sub)

        if self.templates_on(prefix):
            split_name = self.interface.get_name_templates()[prefix].split("_")
            fill_value = "_".join([next_val, *split_name[1:]])
        else:
            fill_value = next_val

        input = self.query_one(f"#{input_id}")
        input.value = fill_value

    def run_local_validation(self, prefix: Prefix):
        """
        Run validation of the values stored in the
        sub / ses Input according to the passed prefix
        using core datashuttle functions.

        First, format the subject name (and session if required)
        which also performs quick name format validations. Then,
        compare the names against all current project sub / names (local)
        and check it is valid. If invalid, the functions will error
        and the error is caught and message returned. Otherwise,
        the formatted name is returned.

        Parameters
        ----------

        prefix : Prefix
        """
        sub_names = self.query_one(
            "#create_folders_subject_input"
        ).as_names_list()

        if prefix == "sub":
            ses_names = None
        else:
            ses_names = self.query_one(
                "#create_folders_session_input"
            ).as_names_list()

        success, output = self.interface.validate_names(
            sub_names,
            ses_names,
        )

        if not success:
            return False, output

        names = (
            output["format_sub"] if prefix == "sub" else output["format_ses"]
        )

        return True, f"Formatted names: {names}"

    def update_directorytree_root(self, new_root_path: Path) -> None:
        """
        Will automatically refresh the tree through the reactive attribute `path`.
        """
        self.query_one("#create_folders_directorytree").path = new_root_path
