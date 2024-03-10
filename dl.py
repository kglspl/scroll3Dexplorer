import argparse
import enum
import math
import os
import time

import h5py
import numpy as np
import requests
from scipy import ndimage
from skimage import io


class Actions(str, enum.Enum):
    download = "download"
    download_apply = "download-apply"
    apply = "apply"
    dummy = "dummy"


class ScrollDataDownloader:
    SCROLL_MULTIZOOM_LEVELS = [
        (None, "scroll"),
        (2, "scroll_scale_2"),
        (4, "scroll_scale_4"),
    ]
    r = None
    allow_downloading = False
    apply_if_downloaded = False
    apply_always = False
    dummy = False
    roi = None
    url = None
    download_dir = None
    h5fs_scroll = None

    def __init__(self):
        arguments = self._parse_arguments()

        self.allow_downloading = "download" in arguments.actions.value.split("-")
        self.apply_if_downloaded = "apply" in arguments.actions.value.split("-")
        self.apply_always = arguments.actions == Actions.apply
        self.dummy = arguments.actions == Actions.dummy

        self.url = arguments.url
        if self.allow_downloading:
            username, password = arguments.auth.split(":", 2)
            self.r = requests.Session()
            self.r.auth = (username, password)

        x0, x1, y0, y1, z0, z1 = [int(x) for d in arguments.roi_xyz.split(",", 3) for x in d.split("-", 2)]
        self.roi = (x0, x1, y0, y1, z0, z1)

        self.download_dir = arguments.download_dir
        self.h5fs_scroll = arguments.h5fs_scroll
        x, y, z = arguments.scroll_size_xyz.split(",", 3)
        self.h5fs_scroll_shape = (int(y), int(x), int(z))

    def _parse_arguments(self):
        # we parse just --actions here so that we can set `required` argument correctly on other arguments when real parsing happens:
        pre = argparse.ArgumentParser(add_help=False)
        pre.add_argument("--actions", required=False, default=None, type=Actions)
        pre.add_argument("--h5fs-scroll", required=False, default=None)
        args_pre, _ = pre.parse_known_args()

        # parse arguments:
        downloading = args_pre.actions in [Actions.download, Actions.download_apply]
        applying = args_pre.actions in [Actions.apply, Actions.download_apply]
        argparser = argparse.ArgumentParser(usage="%(prog)s [OPTION]...", description="Scroll data downloader for Vesuvius Challenge. See https://scrollprize.org/data for details.")
        argparser.add_argument(
            "--actions",
            help=f"which action(s) to perform: {', '.join([t.value for t in Actions])}; note that download-apply will only apply the newly downloaded files while apply will force applying",
            required=True,
            default="download-apply",
            type=Actions,
        )
        argparser.add_argument(
            "--h5fs-scroll",
            help="full path to target scroll H5FS (.h5) file; file will be created if it doesn't exist yet, but directory must exist",
            required=applying,
        )
        argparser.add_argument(
            "--url", help="download URL prefix for volume grids TIFFs (e.g. 'http://dl.ash2txt.org/full-scrolls/Scroll1.volpkg/volume_grids/20230205180739/' for scroll 1)", required=True
        )
        argparser.add_argument("--download-dir", help="full path to a target directory where downloaded files are / will be saved", required=downloading or applying)
        argparser.add_argument(
            "--auth",
            metavar="USERNAME:PASSWORD",
            help="credentials for downloading data from Vesuvius Challenge servers (see https://scrollprize.org/data for registration form)",
            required=downloading,
        )
        argparser.add_argument("--roi-xyz", help="region of interest to download / apply, in x0-x1,y0-y1,z0-y1 notation (e.g. '0-1000,0-700,0-50')", required=downloading or applying)
        if applying:
            h5scroll_exists = os.path.exists(args_pre.h5fs_scroll)
            if not h5scroll_exists:
                print(f"File {args_pre.h5fs_scroll} does not exist yet.")
        argparser.add_argument(
            "--scroll-size-xyz",
            help="full scroll data size in x,y,z notation, where x is slice width, y is height and z is number of slices / original TIFFs (e.g. '8096,7888,14376' for Scroll1); only required if target file doesn't exist yet; see scroll's volumes/meta.json file for width/height/slices",
            required=applying and args_pre.h5fs_scroll and not h5scroll_exists,
        )
        arguments = argparser.parse_args()
        return arguments

    def download_and_apply_roi(self):
        if not os.path.exists(self.download_dir) or not os.path.isdir(self.download_dir):
            raise Exception(f"Download directory {self.download_dir} does not exist or is not a directory")

        x0, x1, y0, y1, z0, z1 = self.roi
        print(f"ROI: x: {x0}-{x1}, y: {y0}-{y1}, z: {z0}-{z1}")
        try:
            if self.apply_if_downloaded or self.apply_always:
                f = h5py.File(self.h5fs_scroll, "a")
                dsets = []
                for scale, dataset_name in self.SCROLL_MULTIZOOM_LEVELS:
                    shape = self.h5fs_scroll_shape if scale is None else tuple(math.ceil(s / scale) for s in self.h5fs_scroll_shape)
                    print(f"  Opening dataset for scale {scale}, shape: {shape}")
                    dset = f.require_dataset(dataset_name, shape=shape, dtype=np.uint16, chunks=(250, 250, 250))
                    dsets.append(dset)

            total_count = (math.ceil(y1 / 500.0) - y0 // 500) * (math.ceil(x1 / 500.0) - x0 // 500) * (math.ceil(z1 / 500.0) - z0 // 500)
            print(f"Total count: {total_count}")
            count = 0
            for y in range(max(0, y0 // 500), math.ceil(y1 / 500.0)):
                for x in range(max(0, x0 // 500), math.ceil(x1 / 500.0)):
                    for z in range(max(0, z0 // 500), math.ceil(z1 / 500.0)):
                        start = time.time()
                        tif_name = self._get_grid_cell_original_name(x, y, z)
                        filename = os.path.join(self.download_dir, tif_name)
                        dl_url = os.path.join(self.url, tif_name)
                        print(f"Downloading {x},{y},{z} into {filename} from {dl_url}")
                        newly_downloaded = self._download_if_not_exists(filename, dl_url)
                        end = time.time()
                        if (newly_downloaded and self.apply_if_downloaded) or self.apply_always:
                            lapsed = end - start
                            print(f"Downloaded {x},{y},{z} ({filename}) in {lapsed:.2f}s, reading")
                            a = io.imread(filename)
                            print(f"Transposing")
                            a = np.transpose(a, (1, 2, 0))  # change the axes so that we have y, h, x, the same as elsewhere

                            for i, (scale, _) in enumerate(self.SCROLL_MULTIZOOM_LEVELS):
                                print(f"Writing zoom {'1' if scale is None else '1/' + str(scale)}")
                                dset = dsets[i]
                                if scale is None:
                                    zoomed_a = a
                                    y0, x0, z0 = (int(d * 500) for d in (y, x, z))
                                else:
                                    zoomed_a = ndimage.zoom(a, 1 / scale)
                                    y0, x0, z0 = (math.floor((d * 500) / scale) for d in (y, x, z))
                                dset[
                                    y0 : y0 + zoomed_a.shape[0],
                                    x0 : x0 + zoomed_a.shape[1],
                                    z0 : z0 + zoomed_a.shape[2],
                                ] = zoomed_a
                        print(f"Done y={y},x={x},z={z}, {count} / {total_count}\n")
                        count += 1
            print("Done.")
        finally:
            if self.apply_if_downloaded or self.apply_always:
                f.close()

    def _get_grid_cell_original_name(self, x, y, z):
        if x < 0 or y < 0 or z < 0:
            raise Exception(f"Negative coordinates will not work: {x}, {y}, {z}")
        tif_name = f"cell_yxz_{y + 1:03}_{x + 1:03}_{z + 1:03}.tif"
        return tif_name

    def _download_if_not_exists(self, output_filename, dl_url):
        print(f"Downloading: {dl_url}")

        if os.path.isfile(output_filename):
            print(f"  - file {output_filename} already exists, not downloading")
            return False

        if self.dummy:
            print(f"  - dummy run, not downloading")
            return False

        if not self.allow_downloading:
            raise Exception(f"  - file {output_filename} does not exist, but downloading is not allowed")

        response = self.r.get(dl_url, headers={"Accept-Encoding": "gzip"})
        with open(output_filename, "wb") as f:
            f.write(response.content)

        return True


def main():
    sdd = ScrollDataDownloader()
    sdd.download_and_apply_roi()


if __name__ == "__main__":
    main()
