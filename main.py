import argparse
import math

import numpy as np
from PIL import Image, ImageTk
import scipy
import tkinter as tk

from h5fsutil import H5FS
from uiutils import Drag


class Scroll3DExplorer:
    arguments = None
    drag = Drag()
    scrolldata = None  # H5FS instance which gives us access to dataset
    scrolldata_loaded = None  # chunk of data which is loaded into memory
    canvas_display_matrix = None  # transformation on this data to display it on canvas (contains rotations and translations)

    color_clip = None  # example: [150 * 256, 200 * 256]

    _canvas_3d_photoimgs = None
    _window_close_requested = False
    _hide_ui_action_trace_handle = None

    ANIMATION_DELAY = 10
    HIDE_UI_ACTION_TRACE_DELAY = 2000
    CANVAS_PAD = 150  # padding of the cube when displayed on canvas
    SCROLLDATA_CACHE_PAD = math.ceil(math.sqrt(3 * CANVAS_PAD**2))  # performance optimization - calculate in advance padding needed when loading scrolldata chunk
    SHIFT_TO_SCROLLDATA_LOADED_CENTER = np.array(
        [
            [1, 0, 0, SCROLLDATA_CACHE_PAD],
            [0, 1, 0, SCROLLDATA_CACHE_PAD],
            [0, 0, 1, SCROLLDATA_CACHE_PAD],
            [0, 0, 0, 1],
        ]
    )

    def __init__(self):
        self.parse_args()
        print(f"Opening scroll data: {self.arguments.h5fs_scroll}")
        self.scrolldata = H5FS(self.arguments.h5fs_scroll, "r").open()

        initial_position_yxz = [int(p) for p in self.arguments.yxz.split(",")]
        if len(initial_position_yxz) != 3:
            raise ("Initial scroll position (--yxz) should have exactly 3 coordinates")
        self.position_yxz = initial_position_yxz

        self.canvas_display_matrix = np.identity(4)

        if self.arguments.zoom:
            self.canvas_display_matrix /= float(self.arguments.zoom)
            self.canvas_display_matrix[3, 3] = 1.0

        self.init_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.request_window_close)
        self.load_scroll_data_around_current_position()
        # we don't update canvases on every change, instead we update them animation style for performance reasons
        self.root.after(self.ANIMATION_DELAY, self.animate)

    def parse_args(self):
        argparser = argparse.ArgumentParser(usage="%(prog)s [OPTION]...", description="3D explorer of Vesuvius Challenge scroll data.")
        argparser.add_argument("--h5fs-scroll", help="full path to scroll H5FS (.h5) file; the first dataset there will be used", required=True)
        argparser.add_argument("--yxz", help="initial position, comma separated values; uses central position by default", required=True)
        argparser.add_argument("--zoom", help="initial zoom", required=False)
        self.arguments = argparser.parse_args()

    def init_ui(self):
        self.root = tk.Tk()
        self.root.attributes("-zoomed", True)
        self.root.title("Scroll 3D Explorer")

        self.center_frame = tk.Frame(self.root, bg="white")
        self.center_frame.pack(side=tk.TOP, fill="both", expand=True)

        self.nav3d_frame = tk.Frame(self.center_frame, width="201", bg="white")
        self.nav3d_frame.pack(side=tk.LEFT, fill=tk.Y, expand=False)

        self.canvas_z = tk.Canvas(self.nav3d_frame, bg="white", highlightthickness=5, highlightbackground="green")
        self.canvas_z.pack(fill="both", expand=True)
        self.canvas_x = tk.Canvas(self.nav3d_frame, bg="white", highlightthickness=5, highlightbackground="red")
        self.canvas_x.pack(fill="both", expand=True)
        self.canvas_y = tk.Canvas(self.nav3d_frame, bg="white", highlightthickness=5, highlightbackground="blue")
        self.canvas_y.pack(fill="both", expand=True)
        self.canvas_z_text = self.canvas_z.create_text(10, 10, anchor=tk.NW, text="Z: /", fill="red", font=("Helvetica", 15, "bold"))
        self.canvas_x_text = self.canvas_x.create_text(10, 10, anchor=tk.NW, text="X: /", fill="red", font=("Helvetica", 15, "bold"))
        self.canvas_y_text = self.canvas_y.create_text(10, 10, anchor=tk.NW, text="Y: /", fill="red", font=("Helvetica", 15, "bold"))

        self.canvas = tk.Canvas(self.center_frame, bg="white")
        self.canvas.pack(fill="both", expand=True)

        current_zoom_level = self.get_current_zoom()
        self.zoom_level_text = self.canvas.create_text(10, 10, anchor=tk.NW, text=f"Zoom: {current_zoom_level:.2f}", fill="red", font=("Helvetica", 15, "bold"))
        self.ui_action_trace_text = self.canvas.create_text(100, 100, anchor=tk.SE, text="", fill="yellow", font=("Helvetica", 15, "bold"))

        self.canvas.bind("<ButtonPress-1>", self.on_canvas_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_drag_end)
        self.canvas.bind("<MouseWheel>", self.on_scroll)
        # On Linux, Button-4 is scroll up and Button-5 is scroll down
        self.canvas.bind("<Button-4>", self.on_scroll)
        self.canvas.bind("<Button-5>", self.on_scroll)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        self.root.bind("<Key>", self.key_handler)

    def on_canvas_resize(self, event):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.canvas.moveto(self.ui_action_trace_text, cw - 100, ch - 100)

    def request_window_close(self):
        self._window_close_requested = True

    def key_handler(self, ev):
        # print(repr(ev.keysym), ev.state)
        # self.display_ui_action_trace(f'{repr(ev.keysym)}, {ev.state}')

        # L - load scroll data around position
        if ev.keysym in ["l"]:
            self.display_ui_action_trace(f"Key pressed: L (... please wait, loading ...)")
            # 4x4 matrix canvas_display_matrix transforms our 3D scroll coordinates (from the center of the scroll chunk in memory) into
            # rotated and translated 3D coordinates which are ready to be shown on canvas. To load data from H5FS dataset, we must:
            # - find the offset of the new center (which might be dislocated in 3D, not just 2D) using self.canvas_display_matrix
            # - load new scroll data chunk around previous center + offset
            # - change self.canvas_display_matrix so that it only contains rotation (no translations)
            self.load_scroll_data_around_current_position()
            return

        # A/S/D - rotate in different directions
        if ev.keysym in ["a", "s", "d"]:
            self.display_ui_action_trace(f"Key pressed: {ev.keysym.upper()}")
            axis = ["a", "s", "d"].index(ev.keysym)
            self.rotate90(axis)
            return

    def get_current_position(self):
        offset = self.canvas_display_matrix @ np.array([0, 0, 0, 1])
        new_position_yxz = (self.position_yxz[i] + round(offset[i]) for i in range(3))
        return new_position_yxz

    def get_current_zoom(self):
        return 1.0 / self.canvas_display_matrix[0, 0]

    def rotate90(self, axis):
        R = np.identity(4)
        i, j = tuple([a for a in range(3) if a != axis])
        R[i, i] = 0  # cos(90)
        R[i, j] = 1  # sin(90)
        R[j, i] = -1  # -sin(90)
        R[j, j] = 0  # cos(90)
        self.canvas_display_matrix = self.canvas_display_matrix @ R

    def load_scroll_data_around_current_position(self):
        y, x, z = self.get_current_position()
        print("loading data around position yxz:", (y, x, z))
        pad = self.SCROLLDATA_CACHE_PAD
        # read data from disk to memory:
        self.scrolldata_loaded = self.scrolldata.dset[
            y - pad : y + pad + 1,
            x - pad : x + pad + 1,
            z - pad : z + pad + 1,
        ].astype(np.uint16)
        self.position_yxz = (y, x, z)

        # mark the edge of the available data:
        self.scrolldata_loaded[0, :, :] = 0xFFFF
        self.scrolldata_loaded[:, 0, :] = 0xFFFF
        self.scrolldata_loaded[:, :, 0] = 0xFFFF
        self.scrolldata_loaded[-1, :, :] = 0xFFFF
        self.scrolldata_loaded[:, -1, :] = 0xFFFF
        self.scrolldata_loaded[:, :, -1] = 0xFFFF

        # make sure it is really loaded into memory:
        print("loaded data with mean value:", self.scrolldata_loaded.mean())

        # calculate initial matrix which translates our scroll data to canvas, together with rotation and translation:
        # keep rotation, whatever it was (identity when we start), but reset translation:
        R = self.canvas_display_matrix
        R[:, 3] = 0
        R[3, :] = 0
        R[3, 3] = 1
        self.canvas_display_matrix = R  # note that we do not unshift - we do that just before we display the canvas, because we might be doing some more rotations before

    def on_canvas_drag_start(self, event):
        self.drag.on_drag_start(event)
        self.display_ui_action_trace(f"Mouse drag{' with ALT' if self.drag._is_alt_pressed(event) else ''}")

    def on_canvas_drag_move(self, event):
        self.drag.on_drag_move(event)
        self.display_ui_action_trace(f"Mouse drag{' with ALT' if self.drag._is_alt_pressed(event) else ''}")

    def on_canvas_drag_end(self, event):
        # now that the drag is over, roll up its transformation matrix into our display matrix:
        self.canvas_display_matrix = self.canvas_display_matrix @ self.drag.transformation_matrix

        self.drag.on_drag_end(event)

    def on_scroll(self, event):
        ctrl_pressed = event.state & 0x04
        alt_pressed = (event.state & 0x08) or (event.state & 0x80)
        delta = 1 if event.num == 4 else -1
        if ctrl_pressed:
            self.display_ui_action_trace("Mouse scroll with CTRL")
            self.zoom(delta)
        elif alt_pressed:
            self.display_ui_action_trace("Mouse scroll with ALT")
            self.rotate_sideways(delta)
        else:
            self.display_ui_action_trace("Mouse scroll")
            self.move_in_out(delta)

    def animate(self):
        self.update_canvas()
        self.update_nav3d_display()

        if self._window_close_requested:
            self.before_exit()
            self.root.destroy()
        else:
            self.root.after(self.ANIMATION_DELAY, self.animate)

    def display_ui_action_trace(self, message):
        if self._hide_ui_action_trace_handle:
            self.root.after_cancel(self._hide_ui_action_trace_handle)
            self._hide_ui_action_trace_handle = None

        self.canvas.itemconfigure(self.ui_action_trace_text, text=message)
        self._hide_ui_action_trace_handle = self.root.after(self.HIDE_UI_ACTION_TRACE_DELAY, self._hide_ui_action_trace)
        self.canvas.update_idletasks()  # display message before performing the action (important when task is slower, like loading data)

    def _hide_ui_action_trace(self):
        self._hide_ui_action_trace_handle = None
        self.canvas.itemconfigure(self.ui_action_trace_text, text="")

    def update_canvas(self):
        if self.scrolldata_loaded is None:
            print("scrolldata_loaded is not set, aborting")
            return

        pw, ph = self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2

        # when moving back, we only move so that output_shape will take care of cutting the correct matrix for us
        unshift = np.array(
            [
                [1, 0, 0, -ph],
                [0, 1, 0, -pw],
                [0, 0, 1, 0],  # our z dimension is of size 1, no moving back after rotation
                [0, 0, 0, 1],
            ]
        )
        if self.drag.drag_in_progress:
            M = self.SHIFT_TO_SCROLLDATA_LOADED_CENTER @ self.canvas_display_matrix @ self.drag.transformation_matrix @ unshift
        else:
            M = self.SHIFT_TO_SCROLLDATA_LOADED_CENTER @ self.canvas_display_matrix @ unshift

        output_shape = np.array([2 * ph + 1, 2 * pw + 1, 1])
        # note that using order > 1 makes affine transformation quite slow
        a = scipy.ndimage.affine_transform(self.scrolldata_loaded, M, output_shape=output_shape, order=1)[:, :, 0]

        a = self.adjust_colorspace(a)

        a = (a / 256).astype(np.uint8)
        img = Image.fromarray(a).convert("RGBA")

        self._canvas_photoimg = ImageTk.PhotoImage(image=img)  # save to instance var so that it is not garbage collected
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._canvas_photoimg)

        # crosshair:
        self.canvas.create_line((pw - 10, ph), (pw + 10, ph), width=1, fill="red")
        self.canvas.create_line((pw, ph - 10), (pw, ph + 10), width=1, fill="red")

        # raise all texts:
        self.canvas.tag_raise(self.zoom_level_text)
        self.canvas.tag_raise(self.ui_action_trace_text)

    def update_nav3d_display(self):
        scroll_y, scroll_x, scroll_z = self.get_current_position()

        imgs = []
        for i, c in enumerate([self.canvas_z, self.canvas_x, self.canvas_y]):
            c.update()  # this is needed to get the real w/h of canvases
            pw, ph = c.winfo_width() // 2, c.winfo_height() // 2
            if i == 0:
                img_data = (self.scrolldata.dset[scroll_y - ph : scroll_y + ph, scroll_x - pw : scroll_x + pw, scroll_z] // 256).astype(np.uint8)
            elif i == 1:
                img_data = (self.scrolldata.dset[scroll_y - ph : scroll_y + ph, scroll_x, scroll_z - pw : scroll_z + pw] // 256).astype(np.uint8)
            else:
                img_data = (self.scrolldata.dset[scroll_y, scroll_x - ph : scroll_x + ph, scroll_z - pw : scroll_z + pw] // 256).astype(np.uint8)
            img = Image.fromarray(img_data).convert("RGBA")
            imgs.append(img)

        # Draw vicinity points on images while still in Image format:
        # imgs = self.draw_vicinity_points_on_nav3d(imgs, pw, ph, surface_x, surface_y, scroll_x, scroll_y, scroll_z)
        # imgs = self.draw_normals_on_nav3d(imgs, pw, ph, scroll_nx, scroll_ny, scroll_nz)

        # Render photoimages on nav3d canvases:
        self._canvas_3d_photoimgs = []  # PhotoImage's must be saved on instance or they will be garbage collected before displayed
        for i, c in enumerate([self.canvas_z, self.canvas_x, self.canvas_y]):
            self._canvas_3d_photoimgs.append(ImageTk.PhotoImage(image=imgs[i]))  # must be on instance or it will be garbage collected before it is displayed
            c.create_image(5, 5, anchor=tk.NW, image=self._canvas_3d_photoimgs[i])

        # Draw center navigation lines on canvases:
        b = 5  # border offset
        for i, c in enumerate([self.canvas_z, self.canvas_x, self.canvas_y]):
            if i == 0:  # 0 == z
                c.create_line((pw + b, 0), (pw + b, ph // 2), width=2, fill="red")
                c.create_line((pw + b, round(1.5 * ph)), (pw + b, 2 * ph + 1), width=2, fill="red")
                c.create_line((0, ph + b), (pw // 2, ph + b), width=2, fill="blue")
                c.create_line((round(1.5 * pw), ph + b), (2 * pw + 1, ph + b), width=2, fill="blue")
            elif i == 1:  # 1 == x
                c.create_line((pw + b, 0), (pw + b, ph // 2), width=2, fill="green")
                c.create_line((pw + b, round(1.5 * ph)), (pw + b, 2 * ph + 1), width=2, fill="green")
                c.create_line((0, ph + b), (pw // 2, ph + b), width=2, fill="blue")
                c.create_line((round(1.5 * pw), ph + b), (2 * pw + 1, ph + b), width=2, fill="blue")
            else:  # 2 == y
                c.create_line((pw + b, 0), (pw + b, ph // 2), width=2, fill="green")
                c.create_line((pw + b, round(1.5 * ph)), (pw + b, 2 * ph + 1), width=2, fill="green")
                c.create_line((0, ph + b), (pw // 2, ph + b), width=2, fill="red")
                c.create_line((round(1.5 * pw), ph + b), (2 * pw + 1, ph + b), width=2, fill="red")

        # Update labels with 3D coordinates:
        self.canvas_z.itemconfigure(self.canvas_z_text, text=f"Z: {scroll_z}")
        self.canvas_x.itemconfigure(self.canvas_x_text, text=f"X: {scroll_x}")
        self.canvas_y.itemconfigure(self.canvas_y_text, text=f"Y: {scroll_y}")
        self.canvas_z.tag_raise(self.canvas_z_text)
        self.canvas_x.tag_raise(self.canvas_x_text)
        self.canvas_y.tag_raise(self.canvas_y_text)
        self.canvas_z.pack(fill=tk.BOTH, expand=True)
        self.canvas_x.pack(fill=tk.BOTH, expand=True)
        self.canvas_y.pack(fill=tk.BOTH, expand=True)

    def adjust_colorspace(self, a):
        if self.color_clip:
            min_, max_ = self.color_clip
            a[a < min_] = min_
            a[a > max_] = max_
            a = (a - min_) * (0xFFFF / (max_ - min_))
        return a

    def zoom(self, delta):
        scale = 1.1 if delta < 0 else 1 / 1.1
        M = np.array(
            [
                [scale, 0, 0, 0],
                [0, scale, 0, 0],
                [0, 0, scale, 0],
                [0, 0, 0, 1],
            ]
        )
        self.canvas_display_matrix = self.canvas_display_matrix @ M
        # update label:
        current_zoom_level = self.get_current_zoom()
        self.canvas.itemconfigure(self.zoom_level_text, text=f"Zoom: {current_zoom_level:.2f}")

    def move_in_out(self, delta):
        M = np.array(
            [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, delta],
                [0, 0, 0, 1],
            ]
        )
        self.canvas_display_matrix = self.canvas_display_matrix @ M

    def rotate_sideways(self, delta):
        fi = delta * math.pi / 180
        cos_fi, sin_fi = math.cos(fi), math.sin(fi)
        M = np.array(
            [
                [cos_fi, sin_fi, 0, 0],
                [-sin_fi, cos_fi, 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, 1],
            ]
        )
        self.canvas_display_matrix = self.canvas_display_matrix @ M

    def before_exit(self):
        print("Closing scroll data.")
        self.scrolldata.close()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    scroll3DExplorer = Scroll3DExplorer()
    scroll3DExplorer.run()
