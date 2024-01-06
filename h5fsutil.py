import h5py


class H5FS(object):
    def __init__(self, filename, mode):
        self.filename = filename
        self.f = h5py.File(filename, mode)
        self.dset = None

    def open(self, name=None):
        dset_info = self._h5_get_dataset_info(name)
        if dset_info is None:
            if name is None:
                raise Exception(f"No datasets found in {self.filename}")
            else:
                raise Exception(f"Dataset {name} not found in {self.filename}")

        self.dset = self.f.require_dataset(**dset_info)
        return self

    def require_dataset(self, name, shape, dtype, **kwargs):
        return self.f.require_dataset(name, shape, dtype, **kwargs)

    # from: https://stackoverflow.com/a/53340677
    def _h5_get_dataset_info(self, requested_name=None, obj=None):
        if obj is None:
            obj = self.f["/"]

        if type(obj) in [h5py._hl.group.Group, h5py._hl.files.File]:
            for key in obj.keys():
                result = self._h5_get_dataset_info(obj=obj[key])
                if result is not None:
                    return result
        elif type(obj) == h5py._hl.dataset.Dataset:
            if requested_name is None or obj.name == requested_name:
                return {
                    "name": obj.name,
                    "shape": obj.shape,
                    "dtype": obj.dtype,
                    "chunks": obj.chunks,
                }

        return None

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
