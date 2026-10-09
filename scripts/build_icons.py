#!/usr/bin/env python3
"""Render the shared SVG with build-only cairosvg and Pillow dependencies."""
from io import BytesIO
from pathlib import Path
import cairosvg
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def main():
    assets=ROOT/'univpn_client/ui'
    pixels=cairosvg.svg2png(url=str(assets/'app-icon.svg'),output_width=1024,output_height=1024)
    image=Image.open(BytesIO(pixels)).convert('RGBA')
    image.save(assets/'app-icon.png')
    image.resize((512,512),Image.Resampling.LANCZOS).save(assets/'app-icon-512.png')
    image.save(assets/'app-icon.icns',format='ICNS')
    image.save(assets/'app-icon.ico',format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])


if __name__=='__main__':main()
