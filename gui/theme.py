"""Slipstream visual theme — a calm, dense, dark engineering look.

One place owns every colour so panels never invent their own. The palette is
tuned for long sessions: low-luminance surfaces, a single restrained accent,
and status colours that survive both the queue table and the pipeline chips.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# Core palette tokens
# ---------------------------------------------------------------------------
BG_WINDOW = "#1e1f22"      # app background
BG_PANEL = "#26282c"       # dock/panel surfaces
BG_FIELD = "#2b2d31"       # inputs, tables
BG_CARD = "#2a2c31"        # elevated surfaces (stat cards, section bodies)
BG_HOVER = "#33363c"
BORDER = "#3a3d43"
BORDER_STRONG = "#4a4e57"
TEXT = "#d7dae0"
TEXT_DIM = "#9aa0aa"
ACCENT = "#4f8cff"         # actions / selection
ACCENT_DIM = "#33507f"

# ---------------------------------------------------------------------------
# Design tokens — the single source of truth for spacing/radius/type.
# GUI Modernization (v1.0.0-rc2): every panel/widget should read these
# instead of inventing its own margin/radius/font-size constant.
# ---------------------------------------------------------------------------
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 32

RADIUS = 10             # standard corner radius for cards/panels/buttons
RADIUS_SM = 6           # tighter radius for small controls (inputs, chips)

CARD_MARGIN = SPACE_MD    # internal padding for stat cards / section bodies
PANEL_MARGIN = SPACE_SM   # internal padding for ordinary panels

FONT_SIZE_H1 = 20          # page/section titles (was 17px, ad hoc)
FONT_SIZE_H2 = 13          # sub-headers / group labels
FONT_SIZE_BODY = 12        # default body text
FONT_SIZE_SMALL = 11       # hints, captions, monospace log/console text
FONT_SIZE_STAT = 26        # big numbers on stat cards

# Status vocabulary — shared by queue table, chips, pipeline stages, cards.
STATUS_COLORS = {
    "PENDING": "#8a93a3",
    "RUNNING": "#4f8cff",
    "DONE": "#3fbf7f",
    "FAILED": "#e5534b",
    "SKIP": "#6f6a52",
    # pipeline stage states
    "start": "#4f8cff",
    "done": "#3fbf7f",
    "cached": "#2fb3a8",
    "skip": "#6f6a52",
    "failed": "#e5534b",
    "idle": "#4a4e57",
}

CHART_SERIES = ["#4f8cff", "#3fbf7f", "#e8a33d", "#e5534b", "#b07fe8",
                "#2fb3a8", "#d76fa3", "#9aa0aa"]


def qcolor(token: str) -> QColor:
    return QColor(STATUS_COLORS.get(token, token))


# ---------------------------------------------------------------------------
# Application-wide stylesheet
# ---------------------------------------------------------------------------
QSS = f"""
QWidget {{ background: {BG_WINDOW}; color: {TEXT};
           font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 12px; }}
QMainWindow::separator {{ background: {BORDER}; width: 2px; height: 2px; }}

QDockWidget {{ titlebar-close-icon: none; }}
QDockWidget::title {{ background: {BG_PANEL}; padding: 5px 8px;
                      border-bottom: 1px solid {BORDER};
                      font-weight: 600; color: {TEXT_DIM}; }}

QMenuBar {{ background: {BG_PANEL}; border-bottom: 1px solid {BORDER}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: {ACCENT_DIM}; }}
QMenu {{ background: {BG_PANEL}; border: 1px solid {BORDER}; }}

QToolBar {{ background: {BG_PANEL}; border-bottom: 1px solid {BORDER};
            spacing: {SPACE_SM}px; padding: {SPACE_XS}px {SPACE_SM}px; }}
QToolButton {{ padding: {SPACE_XS}px {SPACE_SM}px; border-radius: {RADIUS_SM}px; }}
QToolButton:hover {{ background: {BG_HOVER}; }}
QToolButton:disabled {{ color: {TEXT_DIM}; }}

QStatusBar {{ background: {BG_PANEL}; border-top: 1px solid {BORDER};
              color: {TEXT_DIM}; }}

QTabWidget::pane {{ border: 1px solid {BORDER}; top: -1px; }}
QTabBar::tab {{ background: {BG_PANEL}; padding: 6px 14px;
                border: 1px solid {BORDER}; border-bottom: none; }}
QTabBar::tab:selected {{ background: {BG_WINDOW};
                         border-top: 2px solid {ACCENT}; }}

QTableWidget, QTableView, QTreeWidget, QListWidget {{
    background: {BG_FIELD}; alternate-background-color: {BG_PANEL};
    border: 1px solid {BORDER}; gridline-color: {BORDER};
    selection-background-color: {ACCENT_DIM}; selection-color: {TEXT}; }}
QHeaderView::section {{ background: {BG_PANEL}; color: {TEXT_DIM};
    padding: 4px 6px; border: none; border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER}; font-weight: 600; }}

QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
    background: {BG_FIELD}; border: 1px solid {BORDER};
    border-radius: {RADIUS_SM}px; padding: 3px {SPACE_SM}px; }}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{ background: {BG_PANEL};
    selection-background-color: {ACCENT_DIM}; }}

QPushButton {{ background: {BG_FIELD}; border: 1px solid {BORDER};
               border-radius: {RADIUS_SM}px; padding: 5px {SPACE_MD}px; }}
QPushButton:hover {{ background: {BG_HOVER}; }}
QPushButton:disabled {{ color: {TEXT_DIM}; }}
QPushButton[accent="true"] {{ background: {ACCENT}; color: white;
                              border: none; font-weight: 600; }}
QPushButton[accent="true"]:hover {{ background: #659aff; }}
QPushButton[accent="true"]:disabled {{ background: {ACCENT_DIM}; }}
QPushButton[flat="true"] {{ background: transparent; border: none;
                           text-align: left; padding: {SPACE_SM}px {SPACE_MD}px; }}
QPushButton[flat="true"]:hover {{ background: {BG_HOVER}; }}
QPushButton[flat="true"][active="true"] {{ background: {ACCENT_DIM};
                                          color: {TEXT}; font-weight: 600; }}

QProgressBar {{ background: {BG_FIELD}; border: 1px solid {BORDER};
    border-radius: {RADIUS_SM}px; text-align: center; color: {TEXT}; height: 16px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: {RADIUS_SM - 3}px; }}

QGroupBox {{ border: 1px solid {BORDER}; border-radius: {RADIUS}px;
             margin-top: 10px; padding-top: {SPACE_SM}px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: {SPACE_SM}px; padding: 0 4px;
                    color: {TEXT_DIM}; font-weight: 600; }}

/* Card / section surfaces — GUI Modernization design system */
QFrame[card="true"] {{ background: {BG_CARD}; border: 1px solid {BORDER};
                       border-radius: {RADIUS}px; }}
QFrame[section="true"] {{ background: {BG_PANEL}; border: 1px solid {BORDER};
                         border-radius: {RADIUS}px; }}
QLabel[badge="true"] {{ border-radius: {RADIUS_SM}px; padding: 1px 8px;
                        font-weight: 600; font-size: {FONT_SIZE_SMALL}px; }}

QPlainTextEdit, QTextEdit {{ background: {BG_FIELD};
    border: 1px solid {BORDER};
    font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 11px; }}

QScrollBar:vertical {{ background: {BG_WINDOW}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px;
                               min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {TEXT_DIM}; }}
QScrollBar:horizontal {{ background: {BG_WINDOW}; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 5px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}

QSplitter::handle {{ background: {BORDER}; }}
QLabel[hint="true"] {{ color: {TEXT_DIM}; font-size: {FONT_SIZE_SMALL}px; }}
QLabel[h1="true"] {{ font-size: {FONT_SIZE_H1}px; font-weight: 700; }}
QLabel[h2="true"] {{ font-size: {FONT_SIZE_H2}px; font-weight: 600; color: {TEXT_DIM}; }}
QLabel[stat="true"] {{ font-size: {FONT_SIZE_STAT}px; font-weight: 700; }}
"""


def apply_theme(app: QApplication) -> None:
    """Fusion style + dark palette + the QSS above. Call once at startup."""
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(BG_WINDOW))
    pal.setColor(QPalette.Base, QColor(BG_FIELD))
    pal.setColor(QPalette.AlternateBase, QColor(BG_PANEL))
    pal.setColor(QPalette.Text, QColor(TEXT))
    pal.setColor(QPalette.WindowText, QColor(TEXT))
    pal.setColor(QPalette.Button, QColor(BG_FIELD))
    pal.setColor(QPalette.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase, QColor(BG_PANEL))
    pal.setColor(QPalette.ToolTipText, QColor(TEXT))
    pal.setColor(QPalette.PlaceholderText, QColor(TEXT_DIM))
    app.setPalette(pal)
    app.setStyleSheet(QSS)

    # pyqtgraph defaults consistent with the theme
    try:
        import pyqtgraph as pg
        pg.setConfigOptions(background=BG_FIELD, foreground=TEXT,
                            antialias=True)
    except ImportError:
        pass
