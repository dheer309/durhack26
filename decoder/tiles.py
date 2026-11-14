"""Locate and rectify complete version-3 patches anywhere in a crop."""
import cv2
import numpy as np
import zlib
from reedsolo import RSCodec, ReedSolomonError
from encoder.tiles import tile_points
from config import TILE_ECC_BYTES, TILE_PAIR_OFFSET


def _read(gray, scale=1., minimum_signal=4.):
    points=(np.asarray(tile_points())-.5)*scale+.5
    y=np.rint(points[:,1]*599).astype(int)
    left=np.rint((points[:,0]-TILE_PAIR_OFFSET)*599).astype(int)
    right=np.rint((points[:,0]+TILE_PAIR_OFFSET)*599).astype(int)
    sm=cv2.GaussianBlur(gray,(5,5),.8).astype(float)
    for dy,dx in ((0,0),(-2,0),(2,0),(0,-2),(0,2)):
        scores=sm[y+dy,left+dx]-sm[y+dy,right+dx]
        try:
            payload,_,errors=RSCodec(TILE_ECC_BYTES).decode(np.packbits(scores>0).tobytes())
        except (ReedSolomonError,ValueError):
            continue
        if len(payload)==8 and zlib.crc32(payload[:4])==int.from_bytes(payload[4:],'big') and np.mean(np.abs(scores))>minimum_signal:
            # Agreement describes reconstructed code symbols, not identity probability.
            expected=np.unpackbits(np.frombuffer(bytes(RSCodec(TILE_ECC_BYTES).encode(payload)),np.uint8))
            agreement=float(np.mean((scores>0)==expected))
            return int.from_bytes(payload[:4],'big'),agreement,len(errors)
    if scale == 1.:
        for alternative in (.99,1.01,.98,1.02):
            result=_read(gray,alternative,minimum_signal)
            if result:return result
    return None


def decode_tiles(image):
    h,w=image.shape[:2]
    factor=min(1.,2200/max(h,w))
    if factor<1:
        image=cv2.resize(image,None,fx=factor,fy=factor,interpolation=cv2.INTER_AREA)
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    b,g,r=cv2.split(image.astype(np.float32))
    # Yellow ink absorbs blue while neutral paper and black text affect all
    # channels together. Work in chroma so pale marks remain measurable.
    yellow=np.minimum(r,g)-b
    background=cv2.GaussianBlur(yellow,(0,0),18)
    yellow=np.maximum(yellow-background,0)
    # Threshold calibrated in 8-bit camera channel units; never scale a
    # noise-only image to full contrast.
    yellow_mask=(yellow>5).astype(np.uint8)*255
    cyan_mask=((g-r>30)&(b-r>30)).astype(np.uint8)*255
    modes=((yellow_mask, np.clip(255-yellow*5,0,255).astype(np.uint8), 6.),
           (cyan_mask,gray,4.))
    for mask,signal,minimum in modes:
        result=_find_tiles(mask,signal,minimum)
        if result is not None:return result
    return None


def _find_tiles(edges, gray, minimum_signal):
    edges=cv2.morphologyEx(edges,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    contours,_=cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    seen=[]
    dst=np.float32([[0,0],[599,0],[599,599],[0,599]])
    for contour in sorted(contours,key=cv2.contourArea,reverse=True):
        if cv2.contourArea(contour)<4500: continue
        quad=cv2.approxPolyDP(contour,.015*cv2.arcLength(contour,True),True)
        if len(quad)!=4 or not cv2.isContourConvex(quad): continue
        pts=quad.reshape(4,2).astype(np.float32)
        center=pts.mean(axis=0)
        area=cv2.contourArea(quad)
        if any(np.linalg.norm(center-c)<5 and abs(area-a)/area<.1 for c,a in seen): continue
        seen.append((center,area))
        if len(seen)>80: break
        for reflected in (False,True):
            ordered=pts[::-1] if reflected else pts
            for rotation in range(4):
                warp=cv2.warpPerspective(gray,cv2.getPerspectiveTransform(np.roll(ordered,rotation,axis=0),dst),(600,600))
                result=_read(warp,minimum_signal=minimum_signal)
                if result:return result
    return None
