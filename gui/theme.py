"""Slipstream **Neo** design system — a calm, premium, information-first dark
theme for a professional engineering desktop app.

One module owns the entire visual language: the token scales (spacing, radius,
type) and the colour palette, plus a single application-wide stylesheet that
restyles *every* Qt widget class so no default-Qt surface remains. Panels and
widgets read the tokens below — they never invent their own colour, margin, or
font size. See ``docs/UI_DESIGN_SYSTEM.md`` for the full language.

Inspiration: Linear, VS Code, JetBrains, Fusion 360 / ANSYS Discovery —
elegant, minimal, high-contrast, comfortable for eight-hour sessions. Not
gaming/cyberpunk/neon.

Backward compatibility: every token name that existed before Neo is preserved
(some values refined); new tokens are added alongside. No panel import breaks.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# ===========================================================================
# COLOR TOKENS — layered dark surfaces + one restrained accent + status hues
# ===========================================================================
# Elevation ladder: window < panel/surface < field < card < elevated.
BG_WINDOW = "#17181b"      # app background (deepest)
BG_PANEL = "#1d1f23"       # docks / sidebars / toolbars (surface)
BG_FIELD = "#212429"       # inputs, tables, plots (input surface)
BG_CARD = "#202226"        # elevated card surfaces
BG_ELEVATED = "#282b31"    # popovers, menus, hovered elevation
SURFACE = BG_PANEL         # semantic alias
SURFACE_ELEVATED = BG_ELEVATED
BG_HOVER = "#2b2e34"       # row/control hover
BG_PRESSED = "#323640"     # active/pressed

BORDER = "#31343b"         # hairline separators / card borders
BORDER_STRONG = "#454a54"  # emphasized borders (focus-adjacent)
GRID = "#282b31"           # chart / table gridlines

TEXT = "#e4e6eb"           # primary text (high contrast for readability)
TEXT_DIM = "#9aa1ad"       # secondary text / captions
TEXT_FAINT = "#697079"     # tertiary / disabled hints

ACCENT = "#5b8cff"         # primary action / selection / focus
ACCENT_HOVER = "#7aa2ff"
ACCENT_DIM = "#2c3a5a"     # selection fill / subtle accent surface
ACCENT_TEXT = "#ffffff"

SUCCESS = "#3fbf7f"
WARNING = "#e8a33d"
ERROR = "#e5534b"
INFO = "#4fb3d9"

FOCUS = ACCENT             # focus ring colour
SELECTION = ACCENT_DIM     # selection background
SHADOW = "#0d0e10"         # nominal shadow colour (used sparingly)

# ===========================================================================
# SPACING SCALE — 4 · 8 · 12 · 16 · 24 · 32 · 48 (one system, everywhere)
# ===========================================================================
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24
SPACE_2XL = 32
SPACE_3XL = 48

# Legacy aliases (pre-Neo call sites used these names / values).
SPACE_MD_LEGACY = 16
SECTION_SPACING = SPACE_LG   # gap between major sections within a panel
CONTROL_SPACING = SPACE_SM   # gap between adjacent controls in a row/form

# ===========================================================================
# RADIUS — 6 · 8 · 12
# ===========================================================================
RADIUS_SM = 6            # small controls (inputs, chips, buttons)
RADIUS = 8               # standard cards/panels
RADIUS_LG = 12           # large hero cards / dialogs

# ===========================================================================
# TYPOGRAPHY — Display · Heading · Subheading · Body · Caption · Stat
# ===========================================================================
FONT_FAMILY = "'Segoe UI', 'Inter', system-ui, sans-serif"
FONT_MONO = "'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace"

FONT_SIZE_DISPLAY = 26     # hero numbers / page display
FONT_SIZE_H1 = 19          # page / section titles
FONT_SIZE_H2 = 13          # sub-headers / group labels
FONT_SIZE_BODY = 12        # default body text
FONT_SIZE_SMALL = 11       # hints, captions, monospace log/console text
FONT_SIZE_CAPTION = 10     # smallest legible caption / metadata
FONT_SIZE_STAT = 26        # big numbers on stat cards

# ===========================================================================
# CARD / PANEL PADDING
# ===========================================================================
CARD_MARGIN = SPACE_LG    # internal padding for cards / section bodies
PANEL_MARGIN = SPACE_MD   # internal padding for ordinary panels
CARD_RADIUS = RADIUS

# ===========================================================================
# LAYOUT MINIMUMS — responsive floors so nothing collapses / clips
# ===========================================================================
MIN_SIDEBAR_WIDTH = 200
MIN_CENTER_WIDTH = 420
MIN_QUEUE_WIDTH = 320
MIN_PANEL_WIDTH = 300
MIN_PLOT_HEIGHT = 240
MIN_CONTROL_HEIGHT = 28
MIN_CARD_HEIGHT = 88

# ===========================================================================
# NEO UI FOUNDATION — sidebar / toolbar / brand / status tokens (additive;
# every name below is new in v2.1; nothing above was changed)
# ===========================================================================
NAV_ITEM_HEIGHT = 34      # one navigation row (icon + label) hit target
NAV_RAIL_WIDTH = 3        # accent rail on the active navigation item
BRAND_HEIGHT = 64         # sidebar brand header (wordmark + tagline)
PAGE_HEADER_HEIGHT = 54   # workspace header above the center stack
TOOLBAR_ICON_SIZE = 18    # standard icon canvas for toolbar / nav

# ===========================================================================
# ADAPTIVE WORKSPACE — workspace-header layout toggles (Stage 5; additive)
# ===========================================================================
HEADER_TOGGLE_SIZE = 28   # compact Queue / Focus toggle button in the header

# ===========================================================================
# RESPONSIVE WORKSPACE — first-show dock sizing (Stage 6; additive)
# ===========================================================================
MIN_DOCK_WIDTH = 360      # a dock's first-shown width never drops below this
MAX_DOCK_WIDTH = 560      # nor exceeds this (content stays readable)

# ===========================================================================
# DASHBOARD REVOLUTION — hero / KPI / activity / quick-action tokens (v2.2;
# additive; no existing token was changed)
# ===========================================================================
HERO_FONT_SIZE = 28            # project name in hero header
HERO_TEMPLATE_SIZE = 13        # template name / subtitle in hero header
KPI_VALUE_FONT_SIZE = 26       # big number on KPI card (v2.2: compact)
KPI_ICON_SIZE = 20             # icon canvas in KPI card
KPI_ACCENT_HEIGHT = 3          # colored accent bar at top of KPI card
CHART_MIN_HEIGHT = 420         # dashboard chart minimum height
FEED_ROW_HEIGHT = 36           # activity feed row height
QUICK_ACTION_SIZE = 44         # quick action button/icon area

# ===========================================================================
# WORKSPACE REVOLUTION — command bar / console / status-surface tokens (v2.2;
# additive; no existing token was changed)
# ===========================================================================
COMMAND_BAR_HEIGHT = 46        # top command/project strip above the pages
WARNING_SURFACE = "#3a2f1f"    # amber-tinted surface (mock banner, warn chips)
WARNING_TEXT = WARNING         # text on warning surfaces
SUCCESS_SURFACE = "#1f3a2c"    # green-tinted surface (ready/real chips)
SUCCESS_TEXT = SUCCESS         # text on success surfaces
CONSOLE_BG = "#141519"         # terminal surface (deeper than the window)
CONSOLE_TEXT = "#c9cdd6"       # terminal body text
CONSOLE_PROMPT = ACCENT        # prompt / input accent in the console

# ===========================================================================
# STATUS + SERIES colours (shared by queue, chips, pipeline, cards, plots)
# ===========================================================================
STATUS_COLORS = {
    "PENDING": "#8a93a3",
    "RUNNING": ACCENT,
    "DONE": SUCCESS,
    "FAILED": ERROR,
    "SKIP": "#6f6a52",
    # pipeline stage states
    "start": ACCENT,
    "done": SUCCESS,
    "cached": "#2fb3a8",
    "skip": "#6f6a52",
    "failed": ERROR,
    "idle": "#454a54",
}

CHART_SERIES = ["#5b8cff", "#3fbf7f", "#e8a33d", "#e5534b", "#b07fe8",
                "#2fb3a8", "#d76fa3", "#9aa0aa"]


def qcolor(token: str) -> QColor:
    return QColor(STATUS_COLORS.get(token, token))


# ===========================================================================
# APPLICATION-WIDE STYLESHEET
# ===========================================================================
QSS = f"""
/* ---- base ------------------------------------------------------------- */
* {{ outline: none; }}
QWidget {{ background: {BG_WINDOW}; color: {TEXT};
           font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_BODY}px; }}
QToolTip {{ background: {BG_ELEVATED}; color: {TEXT};
            border: 1px solid {BORDER_STRONG}; border-radius: {RADIUS_SM}px;
            padding: 6px 8px; }}
QMainWindow, QDialog {{ background: {BG_WINDOW}; }}
QMainWindow::separator {{ background: {BORDER}; width: 1px; height: 1px; }}

/* ---- docks ------------------------------------------------------------ */
QDockWidget {{ titlebar-close-icon: none; titlebar-normal-icon: none;
               color: {TEXT}; }}
QDockWidget::title {{ background: {BG_PANEL}; padding: 7px 12px;
                      border-bottom: 1px solid {BORDER};
                      font-weight: 600; font-size: {FONT_SIZE_H2}px;
                      color: {TEXT_DIM}; }}

/* ---- menu / toolbar / status ----------------------------------------- */
QMenuBar {{ background: {BG_PANEL}; border-bottom: 1px solid {BORDER};
            padding: 2px 6px; }}
QMenuBar::item {{ padding: 5px 10px; border-radius: {RADIUS_SM}px; }}
QMenuBar::item:selected {{ background: {BG_HOVER}; }}
QMenu {{ background: {BG_ELEVATED}; border: 1px solid {BORDER};
         border-radius: {RADIUS}px; padding: 6px; }}
QMenu::item {{ padding: 6px 22px 6px 12px; border-radius: {RADIUS_SM}px; }}
QMenu::item:selected {{ background: {ACCENT_DIM}; color: {TEXT}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 6px 8px; }}

QToolBar {{ background: {BG_PANEL}; border: none;
            border-bottom: 1px solid {BORDER};
            spacing: {SPACE_XS}px; padding: {SPACE_SM}px {SPACE_MD}px; }}
QToolButton {{ padding: {SPACE_XS}px {SPACE_MD}px; border-radius: {RADIUS_SM}px;
               color: {TEXT}; }}
QToolButton:hover {{ background: {BG_HOVER}; }}
QToolButton:pressed {{ background: {BG_PRESSED}; }}
QToolButton:disabled {{ color: {TEXT_FAINT}; }}

QStatusBar {{ background: {BG_PANEL}; border-top: 1px solid {BORDER};
              color: {TEXT_DIM}; }}
QStatusBar::item {{ border: none; }}

/* ---- tabs ------------------------------------------------------------- */
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: {RADIUS}px;
                    top: -1px; background: {BG_PANEL}; }}
QTabBar::tab {{ background: transparent; color: {TEXT_DIM};
                padding: 7px 16px; margin-right: 2px;
                border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:hover {{ color: {TEXT}; }}
QTabBar::tab:selected {{ color: {TEXT}; font-weight: 600;
                         border-bottom: 2px solid {ACCENT}; }}

/* ---- tables / lists / trees ------------------------------------------ */
QTableWidget, QTableView, QTreeWidget, QTreeView, QListWidget {{
    background: {BG_FIELD}; alternate-background-color: {BG_PANEL};
    border: 1px solid {BORDER}; border-radius: {RADIUS}px;
    gridline-color: {GRID};
    selection-background-color: {ACCENT_DIM}; selection-color: {TEXT};
    outline: none; }}
QTableView::item, QTreeView::item, QListWidget::item {{ padding: 5px 6px; }}
QTableView::item:hover, QTreeView::item:hover, QListWidget::item:hover {{
    background: {BG_HOVER}; }}
QTableView::item:selected, QTreeView::item:selected,
QListWidget::item:selected {{ background: {ACCENT_DIM}; color: {TEXT}; }}
QHeaderView {{ background: {BG_PANEL}; }}
QHeaderView::section {{ background: {BG_PANEL}; color: {TEXT_DIM};
    padding: 7px 8px; border: none; border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER}; font-weight: 600;
    font-size: {FONT_SIZE_CAPTION}px; text-transform: uppercase;
    letter-spacing: 0.4px; }}
QHeaderView::section:hover {{ background: {BG_HOVER}; color: {TEXT}; }}
QTableCornerButton::section {{ background: {BG_PANEL}; border: none; }}

/* ---- inputs ----------------------------------------------------------- */
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {BG_FIELD}; border: 1px solid {BORDER};
    border-radius: {RADIUS_SM}px; padding: 5px {SPACE_SM}px;
    selection-background-color: {ACCENT_DIM}; }}
QLineEdit:hover, QDoubleSpinBox:hover, QSpinBox:hover, QComboBox:hover {{
    border-color: {BORDER_STRONG}; }}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background: {BG_ELEVATED};
    border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px;
    selection-background-color: {ACCENT_DIM}; padding: 4px; }}
QDoubleSpinBox::up-button, QSpinBox::up-button,
QDoubleSpinBox::down-button, QSpinBox::down-button {{
    background: transparent; border: none; width: 16px; }}

/* ---- buttons ---------------------------------------------------------- */
QPushButton {{ background: {BG_FIELD}; border: 1px solid {BORDER};
               border-radius: {RADIUS_SM}px; padding: 6px {SPACE_LG}px;
               color: {TEXT}; min-height: {MIN_CONTROL_HEIGHT - 12}px; }}
QPushButton:hover {{ background: {BG_HOVER}; border-color: {BORDER_STRONG}; }}
QPushButton:pressed {{ background: {BG_PRESSED}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; background: {BG_PANEL}; }}
QPushButton[accent="true"] {{ background: {ACCENT}; color: {ACCENT_TEXT};
                              border: none; font-weight: 600; }}
QPushButton[accent="true"]:hover {{ background: {ACCENT_HOVER}; }}
QPushButton[accent="true"]:pressed {{ background: {ACCENT}; }}
QPushButton[accent="true"]:disabled {{ background: {ACCENT_DIM};
                                       color: {TEXT_DIM}; }}
QPushButton[flat="true"] {{ background: transparent; border: none;
                           text-align: left; color: {TEXT_DIM};
                           padding: {SPACE_SM}px {SPACE_MD}px; }}
QPushButton[flat="true"]:hover {{ background: {BG_HOVER}; color: {TEXT}; }}
QPushButton[flat="true"][active="true"] {{ background: {ACCENT_DIM};
                                          color: {TEXT}; font-weight: 600; }}
QPushButton[ghost="true"] {{ background: transparent;
                            border: 1px solid {BORDER}; color: {TEXT_DIM}; }}
QPushButton[ghost="true"]:hover {{ border-color: {ACCENT};
                                  color: {TEXT}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: {RADIUS_SM - 2}px;
    border: 1px solid {BORDER_STRONG}; background: {BG_FIELD}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

/* ---- progress --------------------------------------------------------- */
QProgressBar {{ background: {BG_FIELD}; border: 1px solid {BORDER};
    border-radius: {RADIUS_SM}px; text-align: center; color: {TEXT};
    height: 18px; font-size: {FONT_SIZE_CAPTION}px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: {RADIUS_SM - 2}px;
                       margin: 1px; }}

/* ---- group boxes ------------------------------------------------------ */
QGroupBox {{ background: {BG_CARD}; border: 1px solid {BORDER};
             border-radius: {RADIUS}px; margin-top: 14px;
             padding: {SPACE_MD}px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: {SPACE_MD}px;
                    padding: 0 6px; color: {TEXT_DIM}; font-weight: 600;
                    font-size: {FONT_SIZE_H2}px; }}

/* ---- cards / sections (design-system surfaces) ------------------------ */
QFrame[card="true"] {{ background: {BG_CARD}; border: 1px solid {BORDER};
                       border-radius: {RADIUS}px; }}
QFrame[card="true"][hero="true"] {{ border-radius: {RADIUS_LG}px; }}
QFrame[section="true"] {{ background: {BG_PANEL}; border: 1px solid {BORDER};
                         border-radius: {RADIUS}px; }}
QFrame[divider="true"] {{ background: {BORDER}; border: none;
                          max-height: 1px; min-height: 1px; }}
QLabel[badge="true"] {{ border-radius: {RADIUS_SM}px; padding: 1px 8px;
                        font-weight: 600; font-size: {FONT_SIZE_CAPTION}px; }}

/* ---- monospace surfaces ---------------------------------------------- */
QPlainTextEdit, QTextEdit {{ font-family: {FONT_MONO};
    font-size: {FONT_SIZE_SMALL}px; }}

/* ---- scrollbars (thin, unobtrusive) ---------------------------------- */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER_STRONG}; border-radius: 5px;
                               min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {TEXT_FAINT}; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER_STRONG}; border-radius: 5px;
                                 min-width: 28px; }}
QScrollBar::handle:horizontal:hover {{ background: {TEXT_FAINT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}

/* ---- splitter --------------------------------------------------------- */
QSplitter::handle {{ background: {BG_WINDOW}; }}
QSplitter::handle:horizontal {{ width: 4px; }}
QSplitter::handle:vertical {{ height: 4px; }}
QSplitter::handle:hover {{ background: {ACCENT_DIM}; }}

/* ---- typography roles ------------------------------------------------- */
QLabel[display="true"] {{ font-size: {FONT_SIZE_DISPLAY}px; font-weight: 700;
                          color: {TEXT}; }}
QLabel[h1="true"] {{ font-size: {FONT_SIZE_H1}px; font-weight: 700; }}
QLabel[h2="true"] {{ font-size: {FONT_SIZE_H2}px; font-weight: 600;
                     color: {TEXT_DIM}; }}
QLabel[caption="true"] {{ font-size: {FONT_SIZE_CAPTION}px; color: {TEXT_FAINT};
                          text-transform: uppercase; letter-spacing: 0.5px; }}
QLabel[hint="true"] {{ color: {TEXT_DIM}; font-size: {FONT_SIZE_SMALL}px; }}
QLabel[stat="true"] {{ font-size: {FONT_SIZE_STAT}px; font-weight: 700; }}
QLabel[metric="true"] {{ font-size: {FONT_SIZE_H1}px; font-weight: 700;
                         font-family: {FONT_MONO}; }}

/* ====================================================================== */
/* NEO UI FOUNDATION — sidebar / workspace / toolbar / status (v2.1.0)    */
/* ====================================================================== */

/* ---- brand header ----------------------------------------------------- */
QWidget[brand="true"] {{ background: {BG_PANEL};
                        border-bottom: 1px solid {BORDER}; }}
QLabel[brandName="true"] {{ font-size: 14px; font-weight: 700;
                           letter-spacing: 2px; color: {TEXT}; }}
QLabel[brandTagline="true"] {{ font-size: {FONT_SIZE_CAPTION}px;
                              color: {TEXT_FAINT}; letter-spacing: 0.8px; }}
QLabel[brandVersion="true"] {{ font-size: {FONT_SIZE_CAPTION}px;
                             color: {TEXT_DIM}; background: {BG_FIELD};
                             border: 1px solid {BORDER};
                             border-radius: {RADIUS_SM}px; padding: 1px 8px; }}

/* ---- navigation items -------------------------------------------------- */
QPushButton[navItem="true"] {{ background: transparent; border: none;
    border-left: {NAV_RAIL_WIDTH}px solid transparent;
    border-radius: {RADIUS_SM}px; text-align: left;
    padding: {SPACE_SM}px {SPACE_MD}px; color: {TEXT_DIM};
    font-size: {FONT_SIZE_BODY}px; }}
QPushButton[navItem="true"]:hover {{ background: {BG_HOVER}; color: {TEXT}; }}
QPushButton[navItem="true"]:pressed {{ background: {BG_PRESSED}; }}
QPushButton[navItem="true"][active="true"] {{ background: {ACCENT_DIM};
    color: {TEXT}; border-left-color: {ACCENT}; font-weight: 600; }}
QPushButton[navItem="true"][active="true"]:hover {{ background: {ACCENT_DIM};
    color: {TEXT}; }}

/* ---- collapsible section headers (uppercase caption chrome) ------------ */
QPushButton[sectionHeader="true"] {{ background: transparent; border: none;
    text-align: left; color: {TEXT_FAINT}; font-size: {FONT_SIZE_CAPTION}px;
    font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase;
    padding: {SPACE_XS}px {SPACE_MD}px; }}
QPushButton[sectionHeader="true"]:hover {{ color: {TEXT_DIM}; }}

/* ---- workspace header --------------------------------------------------- */
QWidget[pageHeader="true"] {{ background: {BG_WINDOW};
                             border-bottom: 1px solid {BORDER}; }}

/* ---- toolbar grouping ---------------------------------------------------- */
QToolBar QToolButton {{ font-weight: 600; padding: {SPACE_XS}px {SPACE_MD}px; }}
QToolButton[toolbarAccent="true"] {{ background: {ACCENT}; color: {ACCENT_TEXT};
    border: none; }}
QToolButton[toolbarAccent="true"]:hover {{ background: {ACCENT_HOVER}; }}
QToolButton[toolbarAccent="true"]:disabled {{ background: {ACCENT_DIM};
    color: {TEXT_DIM}; }}
QToolButton[toolbarWarning="true"] {{ color: {WARNING}; }}
QLabel[toolbarGroup="true"] {{ color: {TEXT_FAINT};
    font-size: {FONT_SIZE_CAPTION}px; font-weight: 700; letter-spacing: 1px;
    padding: 0 {SPACE_SM}px; }}
QFrame[toolGroup="true"] {{ background: {BG_FIELD};
    border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px; }}

/* ---- status bar ----------------------------------------------------------- */
QLabel[statusInfo="true"] {{ color: {TEXT_DIM}; font-size: {FONT_SIZE_SMALL}px;
    padding: 2px 10px; }}
QLabel[statusSep="true"] {{ color: {BORDER_STRONG}; }}

/* ---- empty states --------------------------------------------------------- */
QLabel[emptyTitle="true"] {{ font-size: {FONT_SIZE_DISPLAY}px;
    font-weight: 700; color: {TEXT}; }}
QLabel[emptyHint="true"] {{ color: {TEXT_DIM}; font-size: {FONT_SIZE_BODY}px; }}

/* ---- dashboard revolution: hero header ------------------------------------ */
/* v2.2 Workspace Revolution: the hero is a flat workspace banner now, not a
   floating elevated card — it pinches project identity without dominating. */
QFrame[hero="true"] {{ background: transparent; border: none; }}
QLabel[heroTitle="true"] {{ font-size: {HERO_FONT_SIZE}px; font-weight: 700;
    color: {TEXT}; }}
QLabel[heroMeta="true"] {{ color: {TEXT_DIM}; font-size: {HERO_TEMPLATE_SIZE}px;
    font-weight: 600; letter-spacing: 0.4px; }}
QLabel[heroDesc="true"] {{ color: {TEXT_DIM}; font-size: {FONT_SIZE_BODY}px; }}
QLabel[mockBadge="true"] {{ font-size: {FONT_SIZE_SMALL}px; font-weight: 700;
    letter-spacing: 1px; padding: 3px 10px; border-radius: 9px;
    background: {ACCENT_DIM}; color: {ACCENT}; }}
QLabel[mockBadgeReal="true"] {{ font-size: {FONT_SIZE_SMALL}px; font-weight: 700;
    letter-spacing: 1px; padding: 3px 10px; border-radius: 9px;
    background: {ACCENT_DIM}; color: {ACCENT}; }}

/* ---- dashboard revolution: KPI cards -------------------------------------- */
QFrame[kpiCard="true"] {{ background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: {RADIUS_LG}px; }}
QFrame[kpiCard="true"]:hover {{ border: 1px solid {BORDER_STRONG}; }}
QLabel[kpiValue="true"] {{ font-size: {KPI_VALUE_FONT_SIZE}px; font-weight: 700;
    color: {TEXT}; }}
QLabel[kpiCaption="true"] {{ color: {TEXT_DIM}; font-size: {FONT_SIZE_SMALL}px;
    letter-spacing: 0.5px; }}

/* ---- dashboard revolution: section cards ----------------------------------- */
/* v2.2 Workspace Revolution: sections keep a quiet grouped surface (one
   step off the panel, not a heavy floating card). */
QFrame[dashSection="true"] {{ background: {BG_PANEL}; border: 1px solid {BORDER};
    border-radius: {RADIUS}px; }}
QLabel[dashSectionTitle="true"] {{ color: {TEXT}; font-size: {FONT_SIZE_BODY}px;
    font-weight: 700; }}
QLabel[dashSectionHint="true"] {{ color: {TEXT_FAINT}; font-size: {FONT_SIZE_SMALL}px; }}

/* ---- dashboard revolution: quick actions ----------------------------------- */
QPushButton[quickAction="true"] {{ background: {BG_FIELD}; border: 1px solid {BORDER};
    border-radius: {RADIUS_SM}px; color: {TEXT}; font-weight: 600;
    padding: {SPACE_SM}px; text-align: left; }}
QPushButton[quickAction="true"]:hover {{ background: {BG_HOVER};
    border: 1px solid {ACCENT}; }}
QPushButton[quickAction="true"]:pressed {{ background: {BG_PRESSED}; }}

/* ====================================================================== */
/* WORKSPACE REVOLUTION — command bar / console / telemetry (v2.2.0)       */
/* ====================================================================== */

/* ---- command / project bar ------------------------------------------- */
QWidget[commandBar="true"] {{ background: {BG_PANEL};
    border-bottom: 1px solid {BORDER}; }}
QWidget[pageHeader="true"] {{ background: {BG_PANEL};
    border-bottom: 1px solid {BORDER}; }}
QLabel[mockBanner="true"] {{ background: {WARNING_SURFACE}; color: {WARNING_TEXT};
    font-weight: 700; font-size: {FONT_SIZE_SMALL}px; letter-spacing: 0.4px;
    padding: 5px 8px; border-bottom: 1px solid {BORDER_STRONG}; }}

/* ---- adaptive workspace: header layout toggles (Stage 5) ---------------- */
QPushButton[headerToggle="true"] {{ background: transparent;
    border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px;
    padding: 0; color: {TEXT_DIM}; }}
QPushButton[headerToggle="true"]:hover {{ background: {BG_HOVER};
    border-color: {BORDER_STRONG}; }}
QPushButton[headerToggle="true"][active="true"] {{ background: {ACCENT_DIM};
    border-color: {ACCENT_DIM}; color: {ACCENT}; }}
QPushButton[headerToggle="true"]:disabled {{ color: {TEXT_FAINT};
    background: transparent; border-color: {BORDER}; }}

/* ---- engineering terminal (log + console) ----------------------------- */
QLabel[levelChip="true"] {{ font-family: {FONT_MONO}; font-weight: 700;
    font-size: {FONT_SIZE_CAPTION}px; padding: 1px 6px; border-radius: 3px;
    background: {BG_FIELD}; color: {TEXT_DIM}; }}
QPlainTextEdit[console="true"] {{ background: {CONSOLE_BG}; color: {CONSOLE_TEXT};
    font-family: {FONT_MONO}; font-size: {FONT_SIZE_SMALL}px;
    border: none; selection-background-color: {ACCENT_DIM}; }}
QLineEdit[consoleInput="true"] {{ background: {CONSOLE_BG}; color: {CONSOLE_TEXT};
    font-family: {FONT_MONO}; font-size: {FONT_SIZE_SMALL}px;
    border: none; border-top: 1px solid {BORDER}; padding: 6px 10px; }}

/* ---- telemetry blocks (monitor live readouts) ------------------------- */
QFrame[telemetry="true"] {{ background: {BG_FIELD}; border: 1px solid {BORDER};
    border-radius: {RADIUS_SM}px; }}
QLabel[telemetryValue="true"] {{ font-family: {FONT_MONO};
    font-size: {FONT_SIZE_STAT}px; font-weight: 700; color: {TEXT}; }}
QLabel[telemetryCaption="true"] {{ color: {TEXT_FAINT};
    font-size: {FONT_SIZE_CAPTION}px; text-transform: uppercase;
    letter-spacing: 0.6px; }}

/* ---- queue engineering worklist ---------------------------------------- */
QWidget[queueFilters="true"] {{ background: transparent; }}
QPushButton[queueFilter="true"] {{
    background: {BG_FIELD}; color: {TEXT_DIM};
    border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px;
    padding: 4px 12px; font-size: {FONT_SIZE_SMALL}px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.4px; }}
QPushButton[queueFilter="true"]:hover {{ background: {BG_HOVER}; color: {TEXT}; }}
QPushButton[queueFilter="true"][active="true"] {{
    background: {ACCENT}; color: {ACCENT_TEXT}; border-color: {ACCENT}; }}
QFrame[queueSummary="true"] {{ background: {BG_FIELD}; border: 1px solid {BORDER};
    border-radius: {RADIUS_SM}px; }}
QLabel[queueSummaryValue="true"] {{ color: {TEXT}; font-size: {FONT_SIZE_BODY}px;
    font-weight: 700; }}
QLabel[queueSummaryCaption="true"] {{ color: {TEXT_FAINT};
    font-size: {FONT_SIZE_CAPTION}px; text-transform: uppercase; }}

/* ---- charts analytical workspace --------------------------------------- */
QWidget[chartToolbar="true"] {{ background: {BG_PANEL}; border: 1px solid {BORDER};
    border-radius: {RADIUS}px; }}
QFrame[chartEmpty="true"] {{ background: {BG_FIELD}; border: 1px dashed {BORDER};
    border-radius: {RADIUS}px; }}
QLabel[chartEmptyTitle="true"] {{ color: {TEXT_DIM}; font-size: {FONT_SIZE_H2}px;
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; }}
QLabel[chartEmptyHint="true"] {{ color: {TEXT_FAINT};
    font-size: {FONT_SIZE_BODY}px; }}

/* ---- parameters engineering control panel ------------------------------- */
QLabel[paramName="true"] {{ color: {TEXT}; font-weight: 600;
    font-size: {FONT_SIZE_BODY}px; }}
QLabel[paramMeta="true"] {{ color: {TEXT_FAINT};
    font-size: {FONT_SIZE_CAPTION}px; text-transform: uppercase;
    letter-spacing: 0.4px; }}

/* ---- images engineering workspace ---------------------------------------- */
QFrame[imageSurface="true"] {{ background: {BG_FIELD}; border: 1px solid {BORDER};
    border-radius: {RADIUS}px; }}
QLabel[imageMetaCaption="true"] {{ color: {TEXT_FAINT};
    font-size: {FONT_SIZE_CAPTION}px; text-transform: uppercase;
    letter-spacing: 0.5px; }}
QLabel[imageMetaValue="true"] {{ color: {TEXT}; font-family: {FONT_MONO};
    font-size: {FONT_SIZE_SMALL}px; }}
QLabel[imageEmptyTitle="true"] {{ color: {TEXT_DIM}; font-size: {FONT_SIZE_H2}px;
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; }}
QLabel[imageEmptyHint="true"] {{ color: {TEXT_FAINT};
    font-size: {FONT_SIZE_BODY}px; }}
"""


def apply_theme(app: QApplication) -> None:
    """Fusion base + Neo dark palette + the QSS above. Call once at startup."""
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(BG_WINDOW))
    pal.setColor(QPalette.Base, QColor(BG_FIELD))
    pal.setColor(QPalette.AlternateBase, QColor(BG_PANEL))
    pal.setColor(QPalette.Text, QColor(TEXT))
    pal.setColor(QPalette.WindowText, QColor(TEXT))
    pal.setColor(QPalette.Button, QColor(BG_FIELD))
    pal.setColor(QPalette.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.BrightText, QColor("#ffffff"))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor(ACCENT_TEXT))
    pal.setColor(QPalette.ToolTipBase, QColor(BG_ELEVATED))
    pal.setColor(QPalette.ToolTipText, QColor(TEXT))
    pal.setColor(QPalette.PlaceholderText, QColor(TEXT_FAINT))
    pal.setColor(QPalette.Link, QColor(ACCENT))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor(TEXT_FAINT))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(TEXT_FAINT))
    app.setPalette(pal)
    app.setStyleSheet(QSS)

    # pyqtgraph defaults consistent with the theme.
    try:
        import pyqtgraph as pg
        pg.setConfigOptions(background=BG_FIELD, foreground=TEXT,
                            antialias=True)
    except ImportError:
        pass
