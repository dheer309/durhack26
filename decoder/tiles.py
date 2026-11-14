"""Locate and rectify complete version-3 patches anywhere in a crop."""
import cv2
import numpy as np
import zlib
from reedsolo import RSCodec, ReedSolomonError
from encoder.tiles import tile_points
from config import TILE_ECC_BYTES, TILE_PAIR_OFFSET


def _read(gray, scale=1.):
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
        if len(payload)==8 and zlib.crc32(payload[:4])==int.from_bytes(payload[4:],'big') and np.mean(np.abs(scores))>4:
            # Agreement describes reconstructed code symbols, not identity probability.
            expected=np.unpackbits(np.frombuffer(bytes(RSCodec(TILE_ECC_BYTES).encode(payload)),np.uint8))
            agreement=float(np.mean((scores>0)==expected))
            return int.from_bytes(payload[:4],'big'),agreement,len(errors)
    if scale == 1.:
        for alternative in (.99,1.01,.98,1.02):
            result=_read(gray,alternative)
            if result:return result
    return None


def decode_tiles(image):
    h,w=image.shape[:2]
    factor=min(1.,2200/max(h,w))
    if factor<1:
        image=cv2.resize(image,None,fx=factor,fy=factor,interpolation=cv2.INTER_AREA)
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    edges=((image[:,:,1].astype(float)-image[:,:,2]>30) & (image[:,:,0].astype(float)-image[:,:,2]>30)).astype(np.uint8)*255
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
        # Contour ordering remains cyclic under arbitrary rotation/perspective.
        for reflected in (False,True):
            ordered=pts[::-1] if reflected else pts
            for rotation in range(4):
                warp=cv2.warpPerspective(gray,cv2.getPerspectiveTransform(np.roll(ordered,rotation,axis=0),dst),(600,600))
                result=_read(warp)
                if result: return result
    return None
