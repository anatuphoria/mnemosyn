from __future__ import annotations



from cns_desktop.design.tokens import DATA_PALETTE, GAP, SIZE, color

from .timescale import coarse_text


LABEL_WIDTH = 164
RULER_HEIGHT = 24
OVERVIEW_HEIGHT = SIZE["overview"]
RIGHT_MARGIN = 8
BLOCK_ROW = SIZE["control"]
DOSE_ROW = SIZE["status"]
MARKER = SIZE["handle"]
BAR_GAP = GAP["tight"]
CHANGES_HEIGHT = BLOCK_ROW
MAX_BAR_ROWS = 3
LANE_HEIGHT = SIZE["lane"]
PAD = SIZE["panel_pad"]
GRIP = 8
HINT_EDGE = "drag an edge to change how long it lasts"
HINT_MOVE = "drag to move it"
GRAB = 5
SWIPE = 0.1
MIN_BLOCK_WIDTH = 6
MIN_SPAN = 30.0
INK = color("text")
MUTED = color("text2")
NORMAL = color("normal")
BLOCK = color("edited")
PLAYHEAD = color("text")
LINE = color("line")
BACKGROUND = color("s1")
BAR = color("s2")
WINDOW = color("accent")
BAR_INSET = 5
BADGE_PAD = 6
BADGE_INSET = 3
GUIDE_ALPHA = 110
FINE_STEPS = 10
TAG_PAD = 4
HIGHLIGHT_MS = 1500
LANE_COLORS = DATA_PALETTE
NAME_ROW = 15
VALUE_GAP = 6
MARK_INSET = 4
MARK_BACKING = 210
DAY = 1440.0


time_text = coarse_text
