"""Version 3: independently decodable, repeated watermark patches."""
import random
import zlib
import pymupdf
from reedsolo import RSCodec

from config import (TILE_COLS, TILE_ROWS, TILE_ECC_BYTES, TILE_SEED, TILE_REGISTRATION_RGB,
                    TILE_REGISTRATION_WIDTH, TILE_DOT_RADIUS, TILE_DOT_OPACITY, TILE_PAIR_OFFSET, TILE_DOT_RGB, TILE_REGISTRATION_OPACITY)

def tile_points():
    rng = random.Random(TILE_SEED)
    points = [(.10 + x*.8/15 + rng.uniform(-.006,.006), .12 + y*.76/15 + rng.uniform(-.004,.004)) for y in range(16) for x in range(16)]
    rng.shuffle(points)
    return points

def add_tiles(page, identifier):
    raw = identifier.to_bytes(4, 'big')
    bits = [int(bit) for b in RSCodec(TILE_ECC_BYTES).encode(raw + zlib.crc32(raw).to_bytes(4,'big')) for bit in f'{b:08b}']
    width, height = page.rect.width, page.rect.height
    inverse = page.derotation_matrix
    shape = page.new_shape()
    for row in range(TILE_ROWS):
        for col in range(TILE_COLS):
            x0, y0 = (.035+col*.315)*width, (.035+row*.235)*height
            tw, th = .30*width, .22*height
            # Registration boundary permits a crop to be rectified independently.
            shape.draw_rect(pymupdf.Rect(x0,y0,x0+tw,y0+th)*inverse)
    shape.finish(color=TILE_REGISTRATION_RGB, width=TILE_REGISTRATION_WIDTH, stroke_opacity=TILE_REGISTRATION_OPACITY)
    shape.commit(overlay=True)
    shape = page.new_shape()
    for row in range(TILE_ROWS):
        for col in range(TILE_COLS):
            x0,y0=(.035+col*.315)*width,(.035+row*.235)*height
            tw,th=.30*width,.22*height
            for (x,y),bit in zip(tile_points(),bits):
                p=pymupdf.Point(x0+(x+(TILE_PAIR_OFFSET if bit else -TILE_PAIR_OFFSET))*tw,y0+y*th)*inverse
                shape.draw_circle(p, tw*TILE_DOT_RADIUS)
    shape.finish(color=None,fill=TILE_DOT_RGB,fill_opacity=TILE_DOT_OPACITY)
    shape.commit(overlay=True)
