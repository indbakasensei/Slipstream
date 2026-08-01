"""WorkspaceHeader — the workspace chrome above the center page stack.

Composes a :class:`PageHeader` with the current page's icon + title and a
one-line context subtitle ("project · template · schedule"). The main window
drives it: ``set_page()`` on navigation, ``set_context()`` whenever the
project/template changes. Purely presentational.
"""

from __future__ import annotations

from gui.widgets.page_header import PageHeader


class WorkspaceHeader(PageHeader):
    def __init__(self, parent=None):
        super().__init__(icon="", parent=parent)
        self.page_id: str = ""

    def set_page(self, page_id: str, title: str) -> None:
        """Switch the leading icon + title to ``page_id``/``title``."""
        self.page_id = page_id
        self.set_title(title)
        self.set_icon(page_id)          # icon name == page id (plugin pages
                                        # with unknown icons render text-only)

    def set_context(self, project: str, template: str, schedule: str = "") -> None:
        """Update the subtitle context line. Empty pieces are omitted."""
        bits = []
        if project:
            bits.append(f"Project: {project}")
        if template:
            bits.append(f"Template: {template}")
        if schedule:
            bits.append(f"Schedule: {schedule}")
        self.set_subtitle("   ·   ".join(bits))
