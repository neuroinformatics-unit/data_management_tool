from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:

    from textual.app import ComposeResult

    from datashuttle.tui.app import App
    from datashuttle.tui.interface import Interface

import webbrowser

from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    RadioButton,
    RadioSet,
)

from datashuttle.configs import links
from datashuttle.tui.custom_widgets import TopLevelFolderSelect
from datashuttle.tui.tooltips import get_tooltip


class CreateFoldersSettingsScreen(ModalScreen):
    """
    This screen handles setting datashuttle's `name_template`'s, as well
    as the top-level-folder select and option to bypass all validation.

    Name Templates
    --------------
    These are regexp templates that can be validated against
    during folder creation / project validation.

    An input is provided to input a `name_template` for validation. When
    the window is closed, the `name_template` is stored in datashuttle's
    persistent settings.

    The Create tab validation of input widgets is immediately updated
    on closing of this screen.

    Attributes
    ----------

    Because the Input for `name_templates` is shared between subject
    and session, the values are held in the `input_values` attribute.
    These are loaded from `persistent_settings` on init.
    """

    TITLE = "Create Folders Settings"

    def __init__(self, mainwindow: App, interface: Interface) -> None:
        super(CreateFoldersSettingsScreen, self).__init__()

        self.mainwindow = mainwindow
        self.input_mode = "sub"
        self.interface = interface

        self.input_values: Dict[str, Optional[str]]

        self.input_values = {
            "sub": "",
            "ses": "",
        }

    def action_link_docs(self) -> None:
        webbrowser.open(links.get_docs_link())

    def compose(self) -> ComposeResult:
        sub_on = True if self.input_mode == "sub" else False
        ses_on = not sub_on

        explanation = """
        A 'Template' can be set check subject or session names are
        formatted in a specific way.

        For example:
            sub-\d\d_id-.?.?.?_.*

        Visit the [@click=screen.link_docs()]Documentation[/] for more information.
        """

        bypass_validation = self.interface.tui_settings["bypass_validation"]

        yield Container(
            Horizontal(
                Label(
                    "Top level folder:",
                    id="create_folders_settings_toplevel_label",
                ),
                TopLevelFolderSelect(
                    self.interface,
                    id="create_folders_settings_toplevel_select",
                ),
            ),
            Checkbox(
                "Bypass validation",
                value=bypass_validation,
                id="create_folders_settings_bypass_validation_checkbox",
            ),
            Container(
                Horizontal(
                    Checkbox(
                        "Template Validation",
                        id="template_settings_validation_on_checkbox",
                        value=self.interface.get_name_templates()["on"],
                    ),
                    id="template_inner_horizontal_container",
                ),
                Container(
                    Label(explanation, id="template_message_label"),
                    Container(
                        RadioSet(
                            RadioButton(
                                "Subject",
                                id="template_settings_subject_radiobutton",
                                value=sub_on,
                            ),
                            RadioButton(
                                "Session",
                                id="template_settings_session_radiobutton",
                                value=ses_on,
                            ),
                            id="template_settings_radioset",
                        ),
                        Input(id="template_settings_input"),
                        id="template_other_widgets_container",
                    ),
                    id="template_inner_container",
                ),
                id="template_top_container",
            ),
            Container(),
            Button("Close", id="create_folders_settings_close_button"),
            id="create_tab_settings_outer_container",
        )

    def on_mount(self) -> None:
        for id in [
            "#create_folders_settings_toplevel_select",
            "#create_folders_settings_bypass_validation_checkbox",
            "#template_settings_validation_on_checkbox",
        ]:
            self.query_one(id).tooltip = get_tooltip(id)

        self.init_input_values_holding_variable()
        self.fill_input_from_template()
        self.switch_template_container_disabled()

    def init_input_values_holding_variable(self) -> None:
        name_templates = self.interface.get_name_templates()
        self.input_values["sub"] = name_templates["sub"]
        self.input_values["ses"] = name_templates["ses"]

    def switch_template_container_disabled(self) -> None:
        is_on = self.query_one(
            "#template_settings_validation_on_checkbox"
        ).value
        self.query_one("#template_inner_container").disabled = not is_on

    def fill_input_from_template(self) -> None:
        """
        Fill the `name_templates` Input, that is shared
        between subject and session, depending on the
        current radioset value.
        """
        input = self.query_one("#template_settings_input")
        value = self.input_values[self.input_mode]

        if value is None:
            input.value = ""
            input.placeholder = f"{self.input_mode}-"
        else:
            input.value = value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """
        On close, update the `name_templates` stored in
        `persistent_settings` with those set on the TUI.

        Setting may error if templates are turned on but
        no template exists for either subject or session.
        """
        if event.button.id == "create_folders_settings_close_button":
            success, output = self.interface.set_name_templates(
                self.make_name_templates_from_widgets()
            )
            if success:
                self.dismiss(True)
            else:
                self.mainwindow.show_modal_error_dialog(output)

        elif event.button.id == "create_settings_bypass_validation_button":
            self.interface.save_tui_settings(False, "bypass_validation")

    def make_name_templates_from_widgets(self) -> Dict:
        return {
            "on": self.query_one(
                "#template_settings_validation_on_checkbox"
            ).value,
            "sub": self.input_values["sub"],
            "ses": self.input_values["ses"],
        }

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """
        Turn `name_templates` on or off and update the TUI accordingly.
        """
        is_on = event.value

        if event.checkbox.id == "template_settings_validation_on_checkbox":
            self.switch_template_container_disabled()

        elif (
            event.checkbox.id
            == "create_folders_settings_bypass_validation_checkbox"
        ):
            self.interface.save_tui_settings(is_on, "bypass_validation")

            self.query_one(
                "#template_settings_validation_on_checkbox"
            ).disabled = is_on

            if is_on:
                disable_container = True
            else:
                disable_container = not self.query_one(
                    "#template_settings_validation_on_checkbox"
                ).value
            self.query_one("#template_inner_container").disabled = (
                disable_container
            )

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """
        Update the displayed SSH widgets when the `connection_method`
        radiobuttons are changed.
        """
        label = str(event.pressed.label)
        assert label in ["Subject", "Session"], "Unexpected label."
        self.input_mode = "sub" if label == "Subject" else "ses"

        self.fill_input_from_template()

    def on_input_changed(self, message: Input.Changed) -> None:
        if message.input.id == "template_settings_input":
            val = None if message.value == "" else message.value
            self.input_values[self.input_mode] = val
