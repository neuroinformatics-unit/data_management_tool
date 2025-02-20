from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Iterable,
    List,
    Optional,
    Tuple,
    cast,
)

if TYPE_CHECKING:
    from textual import events
    from textual.validation import Validator

    from datashuttle.tui.app import App
    from datashuttle.tui.interface import Interface

from dataclasses import dataclass
from pathlib import Path

import pyperclip
from rich.style import Style
from rich.text import Text
from textual._segment_tools import line_pad
from textual.message import Message
from textual.strip import Strip
from textual.widgets import (
    DirectoryTree,
    Input,
    Select,
    TabPane,
)

from datashuttle.configs import canonical_folders

# --------------------------------------------------------------------------------------
# ClickableInput
# --------------------------------------------------------------------------------------


class ClickableInput(Input):
    """
    An input widget which emits a `ClickableInput.Clicked`
    signal when clicked, containing the input name
    `input` and mouse button index `button`.
    """

    @dataclass
    class Clicked(Message):
        input: ClickableInput
        ctrl: bool

    def __init__(
        self,
        mainwindow: App,
        placeholder: str,
        id: Optional[str] = None,
        validate_on: Optional[List[str]] = None,
        validators: Optional[List[Validator]] = None,
    ) -> None:
        super(ClickableInput, self).__init__(
            placeholder=placeholder,
            id=id,
            validate_on=validate_on,
            validators=validators,
        )

        self.mainwindow = mainwindow

    def _on_click(self, event: events.Click) -> None:
        self.post_message(self.Clicked(self, event.ctrl))

    def as_names_list(self) -> List[str]:
        return self.value.replace(" ", "").split(",")

    def on_key(self, event: events.Key) -> None:
        if event.key == "ctrl+q":
            pyperclip.copy(self.value)

        elif event.key == "ctrl+o":
            self.mainwindow.handle_open_filesystem_browser(Path(self.value))


# --------------------------------------------------------------------------------------
# CustomDirectoryTree
# --------------------------------------------------------------------------------------


class CustomDirectoryTree(DirectoryTree):
    """
    Base class for directory tree with some customised additions:
        - filter out top-level folders that are not canonical
        - add additional keyboard shortcuts defined in `on_key`.
    """

    @dataclass
    class DirectoryTreeSpecialKeyPress(Message):
        key: str
        node_path: Optional[Path]

    def __init__(
        self, mainwindow: App, path: Path, id: Optional[str] = None
    ) -> None:
        super(CustomDirectoryTree, self).__init__(path=path, id=id)

        self.mainwindow = mainwindow

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """
        Filter out all hidden folders and files from DirectoryTree
        display.
        """
        return [path for path in paths if not path.name.startswith(".")]

    def on_key(self, event: events.Key) -> None:
        """
        Handle key presses on the CustomDirectoryTree. Depending on the keys pressed,
        copy the path under the cursor, refresh the directorytree or
        emit a DirectoryTreeSpecialKeyPress event.
        """
        if event.key == "ctrl+q":
            path_ = self.get_node_at_line(self.hover_line).data.path
            pyperclip.copy(path_.as_posix())

        elif event.key == "ctrl+o":
            path_ = self.get_node_at_line(self.hover_line).data.path
            self.mainwindow.handle_open_filesystem_browser(path_)

        elif event.key == "ctrl+r":
            self.post_message(
                self.DirectoryTreeSpecialKeyPress(event.key, node_path=None)
            )

        elif event.key in ["ctrl+a", "ctrl+f", "ctrl+n"]:
            path_ = self.get_node_at_line(self.hover_line).data.path
            self.post_message(
                self.DirectoryTreeSpecialKeyPress(event.key, node_path=path_)
            )

    # Overridden Methods
    # ----------------------------------------------------------------------------------

    def _render_line(
        self, y: int, x1: int, x2: int, base_style: Style
    ) -> Strip:
        """
        This function is overridden from textual's `Tree` class to stop
        CSS styling on hovering and clicking which was distracting /
        changed the default color used for transfer status, respectively.

        Note better approaches should be possible, see textual issue #4028.
        """
        tree_lines = self._tree_lines
        width = self.size.width

        if y >= len(tree_lines):
            return Strip.blank(width, base_style)

        line = tree_lines[y]

        is_hover = self.hover_line >= 0 and any(
            node._hover for node in line.path
        )

        cache_key = (
            y,
            is_hover,
            width,
            self._updates,
            self._pseudo_class_state,
            tuple(node._updates for node in line.path),
        )
        if cache_key in self._line_cache:
            strip = self._line_cache[cache_key]
        else:
            base_guide_style = self.get_component_rich_style(
                "tree--guides", partial=True
            )
            guide_hover_style = base_guide_style
            # Removed from original
            #            guide_hover_style = base_guide_style +
            #            self.get_component_rich_style(
            #               "tree--guides-hover", partial=True
            #          )
            guide_selected_style = (
                base_guide_style
                + self.get_component_rich_style(
                    "tree--guides-selected", partial=True
                )
            )

            hover = line.path[0]._hover
            selected = line.path[0]._selected and self.has_focus

            def get_guides(style: Style) -> tuple[str, str, str, str]:
                """Get the guide strings for a given style.

                Args:
                    style: A Style object.

                Returns:
                    Strings for space, vertical, terminator and cross.
                """
                lines: tuple[
                    Iterable[str], Iterable[str], Iterable[str], Iterable[str]
                ]
                if self.show_guides:
                    lines = self.LINES["default"]
                    if style.bold:
                        lines = self.LINES["bold"]
                    elif style.underline2:
                        lines = self.LINES["double"]
                else:
                    lines = ("  ", "  ", "  ", "  ")

                guide_depth = max(0, self.guide_depth - 2)
                guide_lines = tuple(
                    f"{characters[0]}{characters[1] * guide_depth} "  # type: ignore
                    for characters in lines
                )
                return cast("tuple[str, str, str, str]", guide_lines)

            if is_hover:
                line_style = self.get_component_rich_style(
                    "tree--highlight-line"
                )
            else:
                line_style = base_style

            guides = Text(style=line_style)
            guides_append = guides.append

            guide_style = base_guide_style
            for node in line.path[1:]:
                if hover:
                    guide_style = guide_hover_style
                if selected:
                    guide_style = guide_selected_style

                space, vertical, _, _ = get_guides(guide_style)
                guide = space if node.is_last else vertical
                if node != line.path[-1]:
                    guides_append(guide, style=guide_style)
                hover = hover or node._hover
                selected = (selected or node._selected) and self.has_focus

            if len(line.path) > 1:
                _, _, terminator, cross = get_guides(guide_style)
                if line.last:
                    guides.append(terminator, style=guide_style)
                else:
                    guides.append(cross, style=guide_style)

            label_style = self.get_component_rich_style(
                "tree--label", partial=True
            )
            if self.hover_line == y:
                label_style += self.get_component_rich_style(
                    "tree--highlight", partial=True
                )
            # Removed from original
            #            if self.cursor_line == y:
            #               label_style += self.get_component_rich_style(
            #                  "tree--cursor", partial=False
            #             )

            label = self.render_label(
                line.path[-1], line_style, label_style
            ).copy()
            label.stylize(Style(meta={"node": line.node._id, "line": y}))
            guides.append(label)

            segments = list(guides.render(self.app.console))
            pad_width = max(self.virtual_size.width, width)
            segments = line_pad(
                segments, 0, pad_width - guides.cell_len, line_style
            )
            strip = self._line_cache[cache_key] = Strip(segments)

        strip = strip.crop(x1, x2)
        return strip


# --------------------------------------------------------------------------------------
# TreeAndInputTab
# --------------------------------------------------------------------------------------


class TreeAndInputTab(TabPane):
    """
    A parent class that defined common methods for screens with
    a directory tree and sub / session inputs, .e. the Create tab
    and the Transfer tab.
    """

    def handle_fill_input_from_directorytree(
        self, sub_input_key: str, ses_input_key: str, event: events.Key
    ) -> None:
        """
        When a CustomDirectoryTree key is pressed, we typically
        want to perform an action that involves an Input. These are
        coordinated here. Note that the 'copy' and 'refresh'
        features of the tree is handled at the level of the
        CustomDirectoryTree.

        Event Keys
        ----------

        "ctrl+a" : When CTRL and A are held at the same time, the sub / ses
                   node under the mouse is appended to the relevant Input

        "ctrl+f" : When CTRL and F are held at the same time, the sub / ses node
                  under the mouse is filled into the relevant Input (i.e. previous
                  value deleted).

        Parameters
        ----------

        sub_input_key : str
            The textual widget id for the subject input (prefixed with #)

        ses_input_key : str
            The textual widget id for the session input (prefixed with #)

        event : DirectoryTreeSpecialKeyPress
            A DirectoryTreeSpecialKeyPress event triggered from the
            CustomDirectoryTree.
        """
        if event.key == "ctrl+a":
            self.append_sub_or_ses_name_to_input(
                sub_input_key,
                ses_input_key,
                name=event.node_path.stem,
            )
        elif event.key == "ctrl+f":
            self.insert_sub_or_ses_name_to_input(
                sub_input_key,
                ses_input_key,
                name=event.node_path.stem,
            )

    def insert_sub_or_ses_name_to_input(
        self, sub_input_key: str, ses_input_key: str, name: str
    ) -> None:
        """
        see `handle_directorytree_key_pressed` for `sub_input_key` and
        `ses_input_key`.

        name : str
            The sub or ses name to append to the input.
        """
        if name.startswith("sub-"):
            self.query_one(sub_input_key).value = name
        elif name.startswith("ses-"):
            self.query_one(ses_input_key).value = name

    def append_sub_or_ses_name_to_input(
        self, sub_input_key: str, ses_input_key: str, name: str
    ) -> None:
        """
        see `insert_sub_or_ses_name_to_input`.
        """
        if name.startswith("sub-"):
            if not self.query_one(sub_input_key).value:
                self.query_one(sub_input_key).value = name
            else:
                self.query_one(sub_input_key).value += f", {name}"

        if name.startswith("ses-"):
            if not self.query_one(ses_input_key).value:
                self.query_one(ses_input_key).value = name
            else:
                self.query_one(ses_input_key).value += f", {name}"

    def get_sub_ses_names_and_datatype(
        self, sub_input_key: str, ses_input_key: str
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        see `handle_fill_input_from_directorytree` for parameters.
        """
        sub_names = self.query_one(sub_input_key).as_names_list()
        ses_names = self.query_one(ses_input_key).as_names_list()
        datatype = self.query_one("DatatypeCheckboxes").selected_datatypes()

        return sub_names, ses_names, datatype


class TopLevelFolderSelect(Select):
    """
    A Select widget for display and updating of top-level-folders. The
    Create tab and transfer tabs (custom, top-level-folder) all have
    top level folder selects that perform the same function. This
    widget unifies these in a single place.

    When updated,the status of the widget is stored in the persistent_settings "tui"
    value specific to the select widget. When folders a made / transferred,
    the top-level folder to use is read from the settings.

    Parameters
    ----------

    existing_only : bool
        If `True`, only top level folders that actually exist in the
        project are displayed. Otherwise, all possible canonical
        top-level-folders are displayed.

    id : str
        Textualize widget id
    """

    def __init__(self, interface: Interface, id: str) -> None:
        self.interface = interface

        top_level_folders = [
            (folder, folder)
            for folder in canonical_folders.get_top_level_folders()
        ]

        if id == "create_folders_settings_toplevel_select":
            self.settings_key = "create_tab"
        elif id == "transfer_toplevel_select":
            self.settings_key = "toplevel_transfer"
        elif id == "transfer_custom_select":
            self.settings_key = "custom_transfer"
        else:
            raise ValueError(
                "TopLevelSelect id not recognised. Must be matched to"
                "a persistent settings field"
            )

        if not any(top_level_folders):
            value = Select.BLANK
            allow_blank = True
        else:
            value = self.get_top_level_folder(init=True)
            allow_blank = False

        super(TopLevelFolderSelect, self).__init__(
            top_level_folders, value=value, id=id, allow_blank=allow_blank
        )

    def get_top_level_folder(self, init: bool = False) -> str:
        """
        Get the top level folder from `persistent_settings`,
        performing a confidence-check that it matches the textual display.
        """
        top_level_folder = self.interface.tui_settings[
            "top_level_folder_select"
        ][self.settings_key]

        if not init:
            assert (
                top_level_folder == self.get_displayed_top_level_folder()
            ), "config and widget should never be out of sync."

        return top_level_folder

    def get_displayed_top_level_folder(self) -> str:
        """
        Get the top level folder that is currently selected
        on the select widget.
        """
        assert self.value in canonical_folders.get_top_level_folders()
        return self.value

    def on_select_changed(self, event: Select.Changed) -> None:
        """
        When the select is changed, update the linked persistent setting.
        """
        top_level_folder = event.value

        if event.value != Select.BLANK:

            self.interface.save_tui_settings(
                top_level_folder, "top_level_folder_select", self.settings_key
            )
