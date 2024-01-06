import tkinter as tk


class Scroll3DViewer:
    def __init__(self):
        self.init_ui()

    def init_ui(self):
        self.root = tk.Tk()
        self.root.attributes("-zoomed", True)
        self.root.title("Scroll 3D Viewer")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    scroll3DViewer = Scroll3DViewer()
    scroll3DViewer.run()
