import argparse

from PIL import Image, ImageTk
import tkinter as tk

from h5fsutil import H5FS


class Scroll3DViewer:
    arguments = None

    def __init__(self):
        self.parse_args()
        print(f"Opening scroll data: {self.arguments.h5fs_scroll}")
        self.scrolldata = H5FS(self.arguments.h5fs_scroll, "r").open()
        self.init_ui()

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

    def update_canvas(self):
        l0 = 100
        l1 = 230
        a = self.scrolldata.dset[4000:4500, 4000:4500, 7000] / 256
        a = (a.clip(l0, l1) - l0) * (255. / (l1 - l0))
        img_data = a

        img = Image.fromarray(img_data).convert("RGBA")
        self._canvas_photoimg = ImageTk.PhotoImage(image=img)  # save to instance var to make sure it is not garbage collected
        self.canvas.create_image(5, 5, anchor=tk.NW, image=self._canvas_photoimg)

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
