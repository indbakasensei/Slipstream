"""Case image browser — geometry / mesh / contour pictures per case.

Shows every image file found in the selected case's artifact directory
(thumbnails on the left, zoomable preview on the right). Sources today:
whatever the user exports from Fluent, the experimental
``fluent.capture_images`` step, or the mock's generated demo contours."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QComboBox, QGraphicsPixmapItem, QGraphicsScene,
                               QGraphicsView, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton,
                               QSplitter, QVBoxLayout, QWidget)

from gui.state import AppState

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

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Case:"))
        self.case_box = QComboBox()
        self.case_box.currentIndexChanged.connect(self._case_changed)
        bar.addWidget(self.case_box, 1)
        refresh = QPushButton("Refresh"); refresh.clicked.connect(self.refresh)
        openf = QPushButton("Open folder"); openf.clicked.connect(self._open_dir)
        fit = QPushButton("Fit"); fit.clicked.connect(self._fit)
        bar.addWidget(refresh); bar.addWidget(openf); bar.addWidget(fit)

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(150, 96))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setSpacing(8)
        self.list.currentItemChanged.connect(self._show_selected)

        self.scene = QGraphicsScene(self)
        self.pix_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pix_item)
        self.view = _ZoomView(self.scene)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.path_lbl = QLabel("")
        self.path_lbl.setProperty("hint", True)

        right = QWidget(); rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self.view, 1); rl.addWidget(self.path_lbl)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.list); split.addWidget(right)
        split.setSizes([260, 640])

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addLayout(bar); lay.addWidget(split, 1)

        state.datasetChanged.connect(self._sync_cases)
        state.caseSelected.connect(self._select_row)

    # ------------------------------------------------------------------ #
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
        if not self._dir:
            self.path_lbl.setText("No artifacts yet for this case.")
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
        self.path_lbl.setText(f"{self._dir}   ·   {self.list.count()} image(s)")
        if self.list.count():
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

    def _load(self, path: Path) -> None:
        pm = QPixmap(str(path))
        self.pix_item.setPixmap(pm)
        self.scene.setSceneRect(self.pix_item.boundingRect())
        self._fit()
        self.path_lbl.setText(str(path))

    def _fit(self) -> None:
        if not self.pix_item.pixmap().isNull():
            self.view.fitInView(self.pix_item, Qt.KeepAspectRatio)

    def _open_dir(self) -> None:
        if self._dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._dir)))
