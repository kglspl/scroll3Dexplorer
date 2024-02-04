import math

import numpy as np


class Drag:
    transformation_matrix = None
    drag_in_progress = False

    def __init__(self):
        pass

    def on_drag_start(self, event):
        self.drag_in_progress = True
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.drag_is_rotation = self._is_alt_pressed(event)
        self.transformation_matrix = np.identity(4)

    def on_drag_move(self, event):
        diff_x = event.x - self.drag_start_x
        diff_y = event.y - self.drag_start_y
        if self.drag_is_rotation:
            fih = diff_x * math.pi / 180
            cos_fih, sin_fih = math.cos(fih), math.sin(fih)
            fiv = diff_y * math.pi / 180
            cos_fiv, sin_fiv = math.cos(fiv), math.sin(fiv)
            Rh = np.array(
                [
                    [1, 0, 0, 0],
                    [0, cos_fih, sin_fih, 0],
                    [0, -sin_fih, cos_fih, 0],
                    [0, 0, 0, 1],
                ]
            )
            Rv = np.array(
                [
                    [cos_fiv, 0, sin_fiv, 0],
                    [0, 1, 0, 0],
                    [-sin_fiv, 0, cos_fiv, 0],
                    [0, 0, 0, 1],
                ]
            )
            self.transformation_matrix = Rh @ Rv
        else:
            self.transformation_matrix = np.array(
                [
                    [1, 0, 0, -diff_y],
                    [0, 1, 0, -diff_x],
                    [0, 0, 1, 0],  # our z dimension is of size 1, no moving back after rotation
                    [0, 0, 0, 1],
                ]
            )

    def on_drag_end(self, event):
        self.drag_start_x = None
        self.drag_start_y = None
        self.drag_in_progress = False
        self.transformation_matrix = None

    def _is_ctrl_pressed(self, event):
        return event.state & 0x04

    def _is_alt_pressed(self, event):
        return (event.state & 0x08) or (event.state & 0x80)

    def _is_shift_pressed(self, event):
        return event.state & 0x01
