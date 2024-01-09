import argparse
import math

import numpy as np
from PIL import Image, ImageTk
import scipy
import tkinter as tk

from h5fsutil import H5FS
from uiutils import Navigation


class Scroll3DViewer:
    arguments = None
    scrolldata = None
    position = None
    _scrolldata_cache = None
    navigation = None
    canvas_pad = 150
    _scrolldata_cache_pad = math.ceil(math.sqrt(3 * canvas_pad ** 2))

    def __init__(self):
        self.parse_args()
        print(f"Opening scroll data: {self.arguments.h5fs_scroll}")
        self.scrolldata = H5FS(self.arguments.h5fs_scroll, "r").open()
        self.navigation = Navigation(*list(np.array(self.scrolldata.dset.shape) // 2))
        self.init_ui()
        self.move_to_position(*list(np.array(self.scrolldata.dset.shape) // 2))

    def parse_args(self):
        argparser = argparse.ArgumentParser(usage="%(prog)s [OPTION]...", description="3D viewer for Vesuvius Challenge scroll data.")
        argparser.add_argument("--h5fs-scroll", help="full path to scroll H5FS (.h5) file; the first dataset there will be used", required=True)
        self.arguments = argparser.parse_args()

    def init_ui(self):
        self.root = tk.Tk()
        self.root.attributes("-zoomed", True)
        self.root.title("Scroll 3D Viewer")

        self.canvas = tk.Canvas(self.root, bg="white")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self.navigation.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.navigation.on_drag_end)

    def move_to_position(self, y, x, z):
        self.position = (y, x, z)
        # prepare cache:
        pad = self._scrolldata_cache_pad
        y, x, z = self.position
        # read data from disk to memory:
        self._scrolldata_cache = (
            self.scrolldata.dset[
                y - pad : y + pad + 1,
                x - pad : x + pad + 1,
                z - pad : z + pad + 1,
            ]
            / 256
        ).astype(np.uint8)
        # make sure it is really loaded into memory:
        print("loaded data with mean value:", self._scrolldata_cache.mean())

    def on_canvas_drag(self, event):
        self.navigation.on_drag_move(event)
        self.update_canvas()

    def update_canvas(self):
        if self._scrolldata_cache is None:
            print("scrolldata_cache is not set, aborting")
            return

        shift = np.array(
            [
                [1, 0, 0, self._scrolldata_cache_pad],
                [0, 1, 0, self._scrolldata_cache_pad],
                [0, 0, 1, self._scrolldata_cache_pad],
                [0, 0, 0, 1],
            ]
        )
        # when moving back, we only move so that output_shape will take care of cutting the correct matrix for us
        unshift = np.array(
            [
                [1, 0, 0, -self.canvas_pad],
                [0, 1, 0, -self.canvas_pad],
                [0, 0, 1, 0],  # our z dimension is of size 1, no moving back after rotation
                [0, 0, 0, 1],
            ]
        )

        output_shape = np.array([2*self.canvas_pad + 1, 2*self.canvas_pad + 1, 1])
        M = shift @ self.navigation.rotation_matrix @ unshift
        # note that using order > 1 makes affine transformation quite slow
        a = scipy.ndimage.affine_transform(self._scrolldata_cache, M, output_shape=output_shape, order=1)[:, :, 0]
        img = Image.fromarray(a).convert("RGBA")

        self._canvas_photoimg = ImageTk.PhotoImage(image=img)  # save to instance var so that it is not garbage collected
        self.canvas.create_image(5, 5, anchor=tk.NW, image=self._canvas_photoimg)

        # crosshair:
        pw, ph = self.canvas_pad, self.canvas_pad
        self.canvas.create_line((pw-10, ph), (pw+10, ph), width=1, fill='red')
        self.canvas.create_line((pw, ph-10), (pw, ph+10), width=1, fill='red')

    def on_exit(self):
        print("Closing scroll data.")
        self.scrolldata.close()

    def run(self):
        try:
            self.update_canvas()
            self.root.mainloop()
        finally:
            self.on_exit()


if __name__ == "__main__":
    scroll3DViewer = Scroll3DViewer()
    scroll3DViewer.run()
