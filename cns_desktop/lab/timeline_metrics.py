from __future__ import annotations



from cns_desktop.design.tokens import DATA_PALETTE, SIZE, color


LABEL_WIDTH = 150
RULER_HEIGHT = 24
OVERVIEW_HEIGHT = SIZE["overview"]
RIGHT_MARGIN = 8
CHANGES_HEIGHT = SIZE["lane"]
LANE_HEIGHT = SIZE["lane"]
PAD = SIZE["panel_pad"]
EDGE = 6
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


def time_text(minutes: float) -> str:
    minutes = round(minutes)
    days, rest = divmod(minutes, 1440)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days} d {hours} h" if hours else f"{days} d"
    return f"{hours} h {mins} min" if mins else f"{hours} h"
