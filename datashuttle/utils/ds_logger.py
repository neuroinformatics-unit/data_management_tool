import logging
from pathlib import Path
from typing import Any, List, Optional

import fancylog as package
from fancylog import fancylog
from rich import print as rich_print
from rich.console import Console
from rich.filesize import decimal
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

from . import utils


def start(
    path_to_log: Path, name: str, variables: Optional[List[Any]]
) -> None:
    """"""
    fancylog.start_logging(
        path_to_log,
        package,
        filename=name,
        variables=variables,
        verbose=False,
        timestamp=True,
        file_log_level="INFO",
        write_git=False,
        log_to_console=False,
    )
    logging.info(f"Starting {name}")


def print_tree(project_path: Path) -> None:
    tree = get_rich_project_path_tree(project_path)
    rich_print(tree)


def log_tree(project_path: Path) -> None:
    tree_ = get_rich_project_path_tree(project_path)

    console = Console(color_system="windows")

    with console.capture() as capture:
        console.print(tree_, markup=True)
    logging.info(
        capture.get()
    )  # https://github.com/Textualize/rich/issues/2688


def log_names(list_of_headers, list_of_names):
    """"""
    for header, names in zip(list_of_headers, list_of_names):
        utils.log(f"{header}: {names}")


# -------------------------------------------------------------------
# File Snapshots
# -------------------------------------------------------------------


def walk_directory(
    project_path: Path, tree: Tree, show_hidden_folders: bool = True
) -> None:
    """
    Demonstrates how to display a tree of files / directories
    with the Tree renderable.

    Based on example from the Rich package.
    https://github.com/Textualize/rich/blob/master/examples/tree.py
    Note the original example contains some other cool
    features (e.g. icons) that were disabled for maximum
    cross-system use.
    """
    paths = sorted(
        project_path.iterdir(),
        key=lambda path: (Path(path).is_file(), path.name.lower()),
    )

    for path in paths:
        # Remove hidden files
        if path.name.startswith(".") and not show_hidden_folders:
            continue
        if path.is_dir():
            style = "dim" if path.name.startswith("__") else ""
            branch = tree.add(
                f"[link file://{path}]{escape(path.name)}",
                style=style,
                guide_style=style,
            )
            walk_directory(path, branch)
        else:
            text_filename = Text(path.name, "green")
            #      text_filename.highlight_regex(r"\..*$", "bold red")
            text_filename.stylize(f"link file://{path}")
            file_size = path.stat().st_size
            text_filename.append(f" ({decimal(file_size)})", "blue")
            tree.add(text_filename)


def get_rich_project_path_tree(project_path: Path) -> Tree:
    """ """
    tree = Tree(label=f"{project_path.as_posix()}/")
    walk_directory(project_path, tree)
    return tree


def close_log_filehandler():
    logger = logging.getLogger()
    handlers = logger.handlers[:]
    for handler in handlers:
        logger.removeHandler(handler)
        handler.close()
