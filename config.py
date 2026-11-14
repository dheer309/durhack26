"""Physical language parameters shared by encoder and decoder.

Coordinates are proportional to the displayed page, so different paper sizes work.
"""
PAGE_WIDTH, PAGE_HEIGHT = 595.2756, 841.8898  # legacy document builder
COLS, ROWS = 32, 24
ECC_BYTES = 8
REPEATS = 6
SEED = 26014
MARGIN_X, MARGIN_Y = .055, .055
PAIR_OFFSET = .007
DOT_RADIUS = .0022  # proportion of page width; about 0.92 mm diameter on A4
DOT_GREY = .20
DOT_OPACITY = .48
ANCHOR_SIZE = .005
NORMAL_WIDTH, NORMAL_HEIGHT = 1200, 1600

# Version 3 repeated, independently registered patches (color printer required).
TILE_COLS, TILE_ROWS = 3, 4
TILE_ECC_BYTES = 24
TILE_SEED = 927031
TILE_REGISTRATION_RGB = (.35, .65, .65)
TILE_REGISTRATION_WIDTH = 1.2
TILE_DOT_RADIUS = .007
TILE_DOT_OPACITY = .85
TILE_PAIR_OFFSET = .014
