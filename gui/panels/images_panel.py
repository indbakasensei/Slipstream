"""Case image browser — geometry / mesh / contour pictures per case.

Shows every image file found in the selected case's artifact directory
(thumbnails on the left, zoomable preview on the right). Sources today:
whatever the user exports from Fluent, the experimental
``fluent.capture_images`` step, or the mock's generated demo contours.

v2.2 Workspace Revolution: restyled as an engineering image-inspection
workspace — a painted-icon toolbar (refresh / open folder / fit), a metadata
readout (filename · dimensions · size · path) for the inspected image, and a
polished engineering empty state. Presentation only; the data model, zoom
behaviour, and every public attribute are preserved.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QComboBox, QFrame, QGraphicsPixmapItem,
                               QGraphicsScene, QGraphicsView, QGridLayout,
                               QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QPushButton, QSplitter,
                               QStackedLayout, QVBoxLayout, QWidget)

from gui import theme
from gui.state import AppState
from gui.widgets import SectionHeader, make_icon

_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


class _ZoomView(QGraphicsView):
    def wheelEvent(self, e):
        factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class ImagesPanel(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._dir: Optional[Path] = None

        # -- header + case selector -------------------------------------- #
        header = QHBoxLayout()
        header.setSpacing(theme.SPACE_MD)
        header.addWidget(SectionHeader("Images", icon_name="images"), 1)

        self.case_box = QComboBox()
        self.case_box.currentIndexChanged.connect(self._case_changed)

        # Toolbar — only real actions: refresh, open the artifacts folder,
        # fit-to-view. Painted icons + tooltips; nothing invented.
        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(make_icon("reload", theme.TEXT_DIM))
        self.refresh_btn.setToolTip("Refresh image list")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh)

        self.open_folder_btn = QPushButton()
        self.open_folder_btn.setIcon(make_icon("folder", theme.TEXT_DIM))
        self.open_folder_btn.setToolTip("Open the artifacts folder")
        self.open_folder_btn.setCursor(Qt.PointingHandCursor)
        self.open_folder_btn.clicked.connect(self._open_dir)

        self.fit_btn = QPushButton()
        self.fit_btn.setIcon(make_icon("zoom", theme.TEXT_DIM))
        self.fit_btn.setToolTip("Fit image to view")
        self.fit_btn.setCursor(Qt.PointingHandCursor)
        self.fit_btn.clicked.connect(self._fit)

        for b in (self.refresh_btn, self.open_folder_btn, self.fit_btn):
            b.setFixedSize(theme.MIN_CONTROL_HEIGHT + 4, theme.MIN_CONTROL_HEIGHT + 4)
            b.setIconSize(QSize(15, 15))

        tb = QHBoxLayout()
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(theme.SPACE_SM)
        cap = QLabel("Case:")
        cap.setProperty("caption", True)
        tb.addWidget(cap)
        tb.addWidget(self.case_box, 1)
        tb.addWidget(self.refresh_btn)
        tb.addWidget(self.open_folder_btn)
        tb.addWidget(self.fit_btn)

        # -- thumbnail strip + preview ----------------------------------- #
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(150, 96))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setSpacing(8)
        self.list.setUniformItemSizes(True)
        self.list.currentItemChanged.connect(self._show_selected)

        self.scene = QGraphicsScene(self)
        self.pix_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pix_item)
        self.view = _ZoomView(self.scene)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)

        # Metadata readout for the inspected image (real data only).
        self._meta_file = QLabel("—")
        self._meta_dims = QLabel("—")
        self._meta_size = QLabel("—")
        meta = QFrame()
        meta.setProperty("imageSurface", True)
        ml = QGridLayout(meta)
        ml.setContentsMargins(theme.SPACE_MD, theme.SPACE_SM,
                              theme.SPACE_MD, theme.SPACE_SM)
        ml.setSpacing(theme.SPACE_SM)
        ml.setHorizontalSpacing(theme.SPACE_LG)
        for c, cap_txt in enumerate(("File", "Dimensions", "Size")):
            c_lbl = QLabel(cap_txt)
            c_lbl.setProperty("imageMetaCaption", True)
            ml.addWidget(c_lbl, 0, c)
        for c, lbl in enumerate((self._meta_file, self._meta_dims,
                                 self._meta_size)):
            lbl.setProperty("imageMetaValue", True)
            ml.addWidget(lbl, 1, c)

        self.path_lbl = QLabel("")
        self.path_lbl.setProperty("hint", True)
        self.path_lbl.setWordWrap(True)

        right = QWidget(); rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(theme.SPACE_SM)
        rl.addWidget(self.view, 1)
        rl.addWidget(meta)
        rl.addWidget(self.path_lbl)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.list); split.addWidget(right)
        split.setSizes([210, 560])
        split.setChildrenCollapsible(False)

        # -- empty state --------------------------------------------------- #
        self._empty = QWidget()
        el = QVBoxLayout(self._empty)
        el.setAlignment(Qt.AlignCenter)
        ic = make_icon("images", theme.TEXT_DIM, 48)
        if ic is not None:
            ic_lbl = QLabel()
            ic_lbl.setPixmap(ic.pixmap(48, 48))
            ic_lbl.setAlignment(Qt.AlignCenter)
            el.addWidget(ic_lbl)
        t_lbl = QLabel("No Image Available")
        t_lbl.setProperty("imageEmptyTitle", True)
        t_lbl.setAlignment(Qt.AlignCenter)
        el.addWidget(t_lbl)
        h_lbl = QLabel("Open or generate a study image to inspect geometry.")
        h_lbl.setProperty("imageEmptyHint", True)
        h_lbl.setAlignment(Qt.AlignCenter)
        el.addWidget(h_lbl)

        self._stack = QStackedLayout()
        self._stack.addWidget(split)      # index 0 — workspace
        self._stack.addWidget(self._empty)  # index 1 — empty state

        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.PANEL_MARGIN, theme.PANEL_MARGIN,
                               theme.PANEL_MARGIN, theme.PANEL_MARGIN)
        lay.setSpacing(theme.SPACE_SM)
        lay.addLayout(header)
        lay.addLayout(tb)
        lay.addLayout(self._stack, 1)

        state.datasetChanged.connect(self._sync_cases)
        state.caseSelected.connect(self._select_row)

    # ------------------------------------------------------------------ #
    def _show_workspace(self) -> None:
        self._stack.setCurrentIndex(0)

    def _show_empty(self) -> None:
        self._stack.setCurrentIndex(1)

    def _sync_cases(self) -> None:
        cur = self.case_box.currentData()
        self.case_box.blockSignals(True)
        self.case_box.clear()
        for _, rec in self.state.df.iterrows():
            self.case_box.addItem(str(rec["CaseID"]), int(rec["Row"]))
        if cur is not None:
            i = self.case_box.findData(cur)
            if i >= 0:
                self.case_box.setCurrentIndex(i)
        self.case_box.blockSignals(False)
        if self.case_box.currentIndex() < 0 and self.case_box.count():
            self.case_box.setCurrentIndex(0)
        self.refresh()

    def _select_row(self, row: int) -> None:
        i = self.case_box.findData(row)
        if i >= 0:
            self.case_box.setCurrentIndex(i)   # triggers refresh

    def _case_changed(self, _i: int) -> None:
        self.refresh()

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        row = self.case_box.currentData()
        self._dir = self.state.case_dir_for(int(row)) if row is not None else None
        self.list.clear()
        self.pix_item.setPixmap(QPixmap())
        self._meta_clear()
        if not self._dir:
            self.path_lbl.setText("")
            self._show_empty()
            return
        files = self.image_files()
        for p in files:
            pm = QPixmap(str(p))
            if pm.isNull():
                continue
            it = QListWidgetItem(QIcon(pm.scaled(150, 96, Qt.KeepAspectRatio,
                                                 Qt.SmoothTransformation)),
                                 p.name)
            it.setData(Qt.UserRole, str(p))
            self.list.addItem(it)
        if not self.list.count():
            self.path_lbl.setText(f"{self._dir}   ·   no readable images")
            self._show_empty()
            return
        self.path_lbl.setText(f"{self._dir}   ·   {self.list.count()} image(s)")
        self._show_workspace()
        self.list.setCurrentRow(0)

    def image_files(self) -> List[Path]:
        if not self._dir:
            return []
        return sorted(p for p in self._dir.rglob("*")
                      if p.suffix.lower() in _EXTS)

    def show_file(self, path: Path) -> None:
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == str(path):
                self.list.setCurrentRow(i)
                return
        self._load(path)

    # ------------------------------------------------------------------ #
    def _show_selected(self, item: Optional[QListWidgetItem], _prev=None):
        if item:
            self._load(Path(item.data(Qt.UserRole)))

    def _meta_clear(self) -> None:
        for lbl in (self._meta_file, self._meta_dims, self._meta_size):
            lbl.setText("—")

    def _meta_show(self, path: Path, pm: QPixmap) -> None:
        self._meta_file.setText(path.name)
        self._meta_dims.setText(f"{pm.width()} x {pm.height()} px")
        try:
            self._meta_size.setText(self._fmt_size(path.stat().st_size))
        except OSError:
            self._meta_size.setText("—")

    @staticmethod
    def _fmt_size(n: int) -> str:
        if n >= 1 << 20:
            return f"{n / (1 << 20):.1f} MB"
        if n >= 1 << 10:
            return f"{n / (1 << 10):.0f} KB"
        return f"{n} B"

    def _load(self, path: Path) -> None:
        pm = QPixmap(str(path))
        self.pix_item.setPixmap(pm)
        self.scene.setSceneRect(self.pix_item.boundingRect())
        self._fit()
        self.path_lbl.setText(str(path))
        self._meta_show(path, pm)

    def _fit(self) -> None:
        if not self.pix_item.pixmap().isNull():
            self.view.fitInView(self.pix_item, Qt.KeepAspectRatio)

    def _open_dir(self) -> None:
        if self._dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._dir)))
