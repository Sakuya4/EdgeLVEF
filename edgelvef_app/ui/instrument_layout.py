"""Pure layout constants, independently testable without GTK."""

SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
STATS_HEIGHT = 82
VIDEO_MINIMUM_HEIGHT = 1


def minimum_content_size():
    return 1, STATS_HEIGHT + VIDEO_MINIMUM_HEIGHT
