from __future__ import annotations

from typing import TYPE_CHECKING, List, Literal, Optional

if TYPE_CHECKING:

    from textual.app import ComposeResult

    from datashuttle.tui.interface import Interface


import copy

from textual import on
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Label,
    SelectionList,
    Static,
)
from textual.widgets.selection_list import Selection

# --------------------------------------------------------------------------------------
# Select Displayed Datatypes Screen
# --------------------------------------------------------------------------------------

tooltips = {
    # datatypes
    "ephys": "electrophysiology",
    "behav": "behaviour",
    "funcimg": "functional imaging",
    "anat": "anatomy",
    "ecephys": "extracellular electrophysiology",
    "icephys": "intracellular electrophysiology",
    "cscope": "head-mounted widefield macroscope",
    "f2pe": "functional 2-photon excitation imaging",
    "fmri": "functional magnetic resonance imaging",
    "fusi": "functional ultra-sound imaging",
    "2pe": "2-photon excitation microscopy",
    "bf": "bright-field microscopy",
    "cars": "coherent anti-Stokes Raman spectroscopy",
    "conf": "confocal microscopy",
    "dic": "differential interference contrast microscopy",
    "df": "dark-field microscopy",
    "fluo": "fluorescence microscopy",
    "mpe": "multi-photon excitation microscopy",
    "nlo": "nonlinear optical microscopy",
    "oct": "optical coherence tomography",
    "pc": "phase-contrast microscopy",
    "pli": "polarized-light microscopy",
    "sem": "scanning electron microscopy",
    "spim": "selective plane illumination microscopy",
    "sr": "super-resolution microscopy",
    "tem": "transmission electron microscopy",
    "uct": "micro-CT",
    "mri": "magnetic resonance imaging",
    # transfer special keys
    "all": "transfer everything in the session folder",
    "all_datatype": "transfer datatype folders only",
    "all_non_datatype": "transfer non-datatype folders only",
}


class DisplayedDatatypesScreen(ModalScreen):
    """
    Screen to select the which datatype checkboxes to show on the Create / Transfer tabs.

    Display a SessionList widget which all canonical broad and narrow-type
    datatypes. When selected, this will update DatatypeCheckboxes (coordinates
    by the calling tab) with the checkboxes to show.

    Notes
    -----
    A copy of the interface configs are held for the lifetime of this screen.
    The persistent settings are updated only when the 'Save' button is pressed.
    Note this is different to `DatatypeCheckboxes` which is saved on
    every click. The reason this is not done here is because:
        a) We have the choice not to because it is a screen with defined open / close point
        b) Clicking options very quickly is possible in this widget because the
           checkboxes are so close together. Testing indicate that when writing to
           file after each click, syncing could get messed up and the wrong checkboxes
           displayed on the window.
    """

    def __init__(
        self,
        create_or_transfer: Literal["create", "transfer"],
        interface: Interface,
    ) -> None:
        super(DisplayedDatatypesScreen, self).__init__()

        self.interface = interface
        self.create_or_transfer = create_or_transfer

        self.settings_key = get_tui_settings_key_name(self.create_or_transfer)

        self.datatype_config = copy.deepcopy(
            self.interface.get_tui_settings()[self.settings_key]
        )

    def compose(self) -> ComposeResult:
        """
        Collect the datatypes names and status from
        the persistent settings and display.
        """
        selections = []
        for idx, (datatype, setting) in enumerate(
            self.datatype_config.items()
        ):
            selection = Selection(
                f"{datatype} ({tooltips[datatype]})",
                idx,
                setting["displayed"],
                id=f"#{get_checkbox_name(self.create_or_transfer, datatype)}",
            )
            selections.append(selection)

        yield Container(
            Vertical(
                Label(
                    "Select datatype checkboxes to display:",
                    id="display_datatypes_toplevel_label",  # TODO: CHANGE NAME
                ),
                SelectionList[int](
                    *selections, id="displayed_datatypes_selection_list"
                ),
                id="display_datatypes_selection_container",
            ),
            Vertical(),
            Horizontal(
                Button("Save", id="displayed_datatypes_save_button"),
                Horizontal(),
                Button("Close", id="displayed_datatypes_close_button"),
                id="displayed_datatypes_button_container",
            ),
            id="display_datatypes_screen_container",
        )

    def on_mount(self):
        pass

    #    self.query_one("#display_datatypes_screen_container").action_scroll_up()
    # assert False, f"{dir(self.query_one('#displayed_datatypes_selection_list'))}"

    def on_button_pressed(self, event):
        """
        When 'Save' is pressed, the configs copied on this class
        are updated back onto the interface configs, and written to disk.
        Otherwise, close the screen without saving.
        """
        if event.button.id == "displayed_datatypes_save_button":
            self.interface.save_tui_settings(
                self.datatype_config, self.settings_key
            )
            self.dismiss()

        elif event.button.id == "displayed_datatypes_close_button":
            self.dismiss()

    def on_selection_list_selection_toggled(
        self, event: SelectionList.SelectionMessage.SelectionToggled
    ):
        """
        When a selection is toggled, update the configs with
        the 'displayed' status and save to disk.
        """
        datatype_name = event.selection.prompt.plain
        datatype_name = datatype_name.split(" ")[0]
        is_checked = not event.selection.initial_state
        self.datatype_config[datatype_name]["displayed"] = is_checked

        if not is_checked:
            self.datatype_config[datatype_name]["on"] = False


# --------------------------------------------------------------------------------------
# DatatypeCheckboxes
# --------------------------------------------------------------------------------------


class DatatypeCheckboxes(Static):
    """
    Dynamically-populated checkbox widget for convenient datatype
    selection during folder creation.

    Parameters
    ----------

    settings_key : 'create' if datatype checkboxes for the create tab,
                   'transfer' for the transfer tab. Transfer tab includes
                   additional datatype options (e.g. "all").

    Attributes
    ----------

    datatype_config : a Dictionary containing datatype as key (e.g. "ephys", "behav")
                      and values are `bool` indicating whether the checkbox is on / off.
                      If 'transfer', then transfer datatype arguments (e.g. "all")
                      are also included. This structure mirrors
                      the `persistent_settings` dictionaries.

    Notes
    -----
    The use of persistent configs is similar to `DisplayedDatatypesScreen`,
    however because this screen persists through the lifetime of the app
    there is no clear time point in which to save the checkbox status.
    Therefore, the configs are updated (written to disk) on each click.
    """

    def __init__(
        self,
        interface: Interface,
        create_or_transfer: Literal["create", "transfer"] = "create",
        id: Optional[str] = None,
    ) -> None:
        super(DatatypeCheckboxes, self).__init__(id=id)

        self.interface = interface
        self.create_or_transfer = create_or_transfer

        self.settings_key = get_tui_settings_key_name(self.create_or_transfer)

        # `datatype_config` is basically just a convenience wrapper
        # around interface.get_tui_settings
        self.datatype_config = self.interface.get_tui_settings()[
            self.settings_key
        ]

    def compose(self) -> ComposeResult:
        for datatype, setting in self.datatype_config.items():
            if setting["displayed"]:
                yield Checkbox(
                    datatype.replace("_", " "),
                    id=get_checkbox_name(self.create_or_transfer, datatype),
                    value=setting["on"],
                )

    @on(Checkbox.Changed)
    def on_checkbox_changed(self) -> None:
        """
        When a checkbox is changed, update the `self.datatype_config`
        to contain new boolean values for each datatype. Also update
        the stored `persistent_settings`.
        """
        for datatype in self.datatype_config.keys():
            if self.datatype_config[datatype]["displayed"]:
                self.datatype_config[datatype]["on"] = self.query_one(
                    f"#{get_checkbox_name(self.create_or_transfer, datatype)}"
                ).value

        self.interface.save_tui_settings(
            self.datatype_config, self.settings_key
        )

    def on_mount(self) -> None:
        """ """
        for datatype in self.datatype_config.keys():
            if self.datatype_config[datatype]["displayed"]:
                self.query_one(
                    f"#{get_checkbox_name(self.create_or_transfer, datatype)}"
                ).tooltip = tooltips[datatype]

    def selected_datatypes(self) -> List[str]:
        """
        Get the names of the datatype options for which the
        checkboxes are switched on.
        """
        selected_datatypes = [
            datatype
            for datatype, settings in self.datatype_config.items()
            if settings["on"]
        ]
        return selected_datatypes


# Helpers
# --------------------------------------------------------------------------------------


def get_checkbox_name(
    create_or_transfer: Literal["create", "transfer"], datatype
):
    return f"{create_or_transfer}_{datatype}_checkbox"


def get_tui_settings_key_name(
    create_or_transfer: Literal["create", "transfer"],
) -> str:
    if create_or_transfer == "create":
        settings_key = "create_checkboxes_on"
    else:
        settings_key = "transfer_checkboxes_on"
    return settings_key
