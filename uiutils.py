import math

import numpy as np


class Navigation:
    rotation_matrix = None

    def __init__(self, x, y, z):
        self.position = (x, y, z)
        self.rotation_matrix = np.identity(4)

    def on_drag_start(self, event):
        self.drag_current_x = self.drag_start_x = event.x
        self.drag_current_y = self.drag_start_y = event.y
        self.drag_ctrl = self._is_ctrl_pressed(event)
        self.drag_alt = self._is_alt_pressed(event)
        self.drag_shift = self._is_shift_pressed(event)
        self.drag_rotation_matrix_start = self.rotation_matrix

    def on_drag_move(self, event):
        self.current_x = event.x
        self.current_y = event.y
        diff_x = self.current_x - self.drag_start_x
        diff_y = self.current_y - self.drag_start_y
        if self.drag_alt:
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
            self.rotation_matrix = self.drag_rotation_matrix_start @ Rh @ Rv

    def on_drag_end(self, event):
        self.drag_current_x = self.drag_start_x = None
        self.drag_current_y = self.drag_start_y = None

    def _is_ctrl_pressed(self, event):
        return event.state & 0x04

    def _is_alt_pressed(self, event):
        return (event.state & 0x08) or (event.state & 0x80)

    def _is_shift_pressed(self, event):
        return event.state & 0x01
