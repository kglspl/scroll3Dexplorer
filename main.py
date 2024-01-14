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
    navigation = Navigation()
    scrolldata = None  # H5FS instance which gives us access to dataset
    scrolldata_loaded = None  # chunk of data which is loaded into memory
    canvas_display_matrix = None  # transformation on this data to display it on canvas (contains rotations and translations)

    CANVAS_PAD = 150  # padding of the cube when displayed on canvas
    SCROLLDATA_CACHE_PAD = math.ceil(math.sqrt(3 * CANVAS_PAD**2))  # performance optimization - calculate in advance needed padding when loading scrolldata chunk

    def __init__(self):
        self.parse_args()
        print(f"Opening scroll data: {self.arguments.h5fs_scroll}")
        self.scrolldata = H5FS(self.arguments.h5fs_scroll, "r").open()
        initial_position_yxz = list(np.array(self.scrolldata.dset.shape) // 2)  # initial position is in the center of scroll
        self.canvas_display_matrix = np.identity(4)
        self.init_ui()
        self.load_scroll_data_around_position(*initial_position_yxz)

    def parse_args(self):
        argparser = argparse.ArgumentParser(usage="%(prog)s [OPTION]...", description="3D viewer for Vesuvius Challenge scroll data.")
        argparser.add_argument("--h5fs-scroll", help="full path to scroll H5FS (.h5) file; the first dataset there will be used", required=True)
        self.arguments = argparser.parse_args()

    def init_ui(self):
        self.root = tk.Tk()
        # self.root.attributes("-zoomed", True)
        self.root.title("Scroll 3D Viewer")

        self.canvas = tk.Canvas(self.root, bg="white")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_canvas_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_drag_end)

    def load_scroll_data_around_position(self, y, x, z):
        print("loading data around position yxz:", (y, x, z))
        pad = self.SCROLLDATA_CACHE_PAD
        # read data from disk to memory:
        self.scrolldata_loaded = (
            self.scrolldata.dset[
                y - pad : y + pad + 1,
                x - pad : x + pad + 1,
                z - pad : z + pad + 1,
            ]
            / 256
        ).astype(np.uint8)
        # make sure it is really loaded into memory:
        print("loaded data with mean value:", self.scrolldata_loaded.mean())

        # calculate initial matrix which translates our scroll data to canvas, together with rotation and translation:
        shift = np.array(
            [
                [1, 0, 0, self.SCROLLDATA_CACHE_PAD],
                [0, 1, 0, self.SCROLLDATA_CACHE_PAD],
                [0, 0, 1, self.SCROLLDATA_CACHE_PAD],
                [0, 0, 0, 1],
            ]
        )
        # keep rotation, whatever it was (identity when we start), but reset translation:
        R = self.canvas_display_matrix
        R[:, 3] = 0
        R[3, :] = 0
        R[3, 3] = 1
        self.canvas_display_matrix = shift @ R  # note that we do not unshift - we do that just before we display the canvas, because we might be doing some more rotations before

    def on_canvas_drag_start(self, event):
        self.navigation.on_drag_start(event)

    def on_canvas_drag_move(self, event):
        self.navigation.on_drag_move(event)
        self.update_canvas()

    def on_canvas_drag_end(self, event):
        self.canvas_display_matrix = self.canvas_display_matrix @ self.navigation.transformation_matrix

        self.navigation.on_drag_end(event)

    def update_canvas(self):
        if self.scrolldata_loaded is None:
            print("scrolldata_loaded is not set, aborting")
            return

        # when moving back, we only move so that output_shape will take care of cutting the correct matrix for us
        unshift = np.array(
            [
                [1, 0, 0, -self.CANVAS_PAD],
                [0, 1, 0, -self.CANVAS_PAD],
                [0, 0, 1, 0],  # our z dimension is of size 1, no moving back after rotation
                [0, 0, 0, 1],
            ]
        )
        if self.navigation.drag_in_progress:
            M = self.canvas_display_matrix @ self.navigation.transformation_matrix @ unshift
        else:
            M = self.canvas_display_matrix @ unshift

        output_shape = np.array([2 * self.CANVAS_PAD + 1, 2 * self.CANVAS_PAD + 1, 1])
        # note that using order > 1 makes affine transformation quite slow
        a = scipy.ndimage.affine_transform(self.scrolldata_loaded, M, output_shape=output_shape, order=1)[:, :, 0]
        img = Image.fromarray(a).convert("RGBA")

        self._canvas_photoimg = ImageTk.PhotoImage(image=img)  # save to instance var so that it is not garbage collected
        self.canvas.create_image(5, 5, anchor=tk.NW, image=self._canvas_photoimg)

        # crosshair:
        pw, ph = self.CANVAS_PAD, self.CANVAS_PAD
        self.canvas.create_line((pw - 10, ph), (pw + 10, ph), width=1, fill="red")
        self.canvas.create_line((pw, ph - 10), (pw, ph + 10), width=1, fill="red")

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
