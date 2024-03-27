# Scroll3DExplorer

## About

A tool for exploring scroll data for Vesuvius Challenge (https://scrollprize.org/data).

The script for downloading the data should work with any scroll data which is distributed via `volume_grids` format (which is true for PHerc0332, PHerc1667, Scroll1, Scroll2 and possibly others). Additionally, it should be fairly easy to change the app to load data from elsewhere. The app works with chunks which are loaded into memory, so only the loading part needs to be adapted.

By default, the app loads only 301x301x301 cube of data into memory. This allows working with the data even on memory or CPU constrained machines, or even machines with slow disk access. When exploring a region which is near the edge of the loaded data, use `l` to load new cube and discard the old one.

## Running

This app uses `pipenv` (`pip install pipenv`) to install its requirements:
```
$ pipenv install
```

Then run the app inside the `pipenv` environment:
```
$ pipenv shell
<shell> $ python main.py --h5fs-scroll /data/dir/scroll2_54kV.h5 --yxz 2845,4575,7750
```

The app assumes that the data exists in a file which is in H5FS format, in the first dataset of the file, with the dimensions in y (height), x (width) and z (slices) order. However it should be fairly easy to change the few places that use `self.scrolldata` (like `load_scroll_data_around_position` method) to load the data from somewhere else, for example from the Zarr archive.

### Navigation

- Panning: **drag the surface**
- Moving in/out: **mouse scrollwheel**
- Rotating: **Alt + drag**
- Rotating in screen plane: **Alt + mouse scrollwheel**
- Rotating by 90 degrees: **a / s / d**
- Zoom in/out: **Ctrl + mouse scrollwheel**
- Loading data around center point: **l**

## Downloading data

There is a script `dl.py` which can be used to download data from Vesuvius Challenge servers to a local H5FS file. It uses `volume_grids` TIFFs, where each 500x500x500 cell is packed into a single file. It is not possible to download just parts of the TIFF files using this script.

IMPORTANT: To access Vesuvius Challenge scroll data, a registration form (see https://scrollprize.org/data for instructions) must be completed. The credentials can then be used to download the data using `dl.py`.

To download the data, install python requirements first:
```
$ pipenv install
```

Then run the script inside the `pipenv` environment, e.g.:
```
$ pipenv shell
<shell> $ python dl.py --actions=download-apply --h5fs-scroll=/data/dir/scroll2_54kV.h5 --url=http://dl.ash2txt.org/full-scrolls/Scroll2.volpkg/volume_grids/20230210143520/ --download-dir=/data/dir/downloads/ --auth=user:pass --roi-xyz=4500-5000,2500-3000,7500-8000 --scroll-size-xyz=11984,10112,14428
```

This will download a single cell from http://dl.ash2txt.org/full-scrolls/Scroll2.volpkg/volume_grids/20230210143520/cell_yxz_006_010_016.tif (as indicated by Region of Interest - `--roi`), create the H5FS file and write the downloaded data to it, in the format which is supported by Scroll3DExplorer out of the box. Note that H5FS files only take as much space as needed so the resulting file will only take about 250MB (but will grow once more data is downloaded and written to it).

The script splits downloading and applying the data into two separate actions, which can be controled through `--actions` parameter. For most cases action `download-apply` is sufficient though.

Note that the data takes a lot of disk space (explore the original files to get a feeling of the final size). Since the original files are preserved, this system takes *twice* as much disk space as needed. If you decide that you don't need the original files, feel free to replace them with empty files with the same name. This will indicate to `dl.py` that they were already applied, so the script will not try to re-download them again (assuming the action `download-apply` is used), which would happen if the files were simply removed.

The dimensions when creating a new H5FS file must be specified through `--scroll-size-xyz` parameter. They can be obtained from the server from the scroll's `volumes/meta.json` file (width/height/slices).

The reason for split `download` and `apply` actions is that H5FS file can't be written to while another process is reading from it. Splitting the process into `download` and `apply` actions allows downloading the data in the background, while using the explorer app at the same time. Once the data is downloaded `apply` can be used to apply all the data in the selected region of interest, which is usually very fast compared to downloading.

## License

MIT License

Copyright (c) 2024 kglspl

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
