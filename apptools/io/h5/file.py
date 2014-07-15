from collections import MutableMapping

import numpy as np
import tables

from .dict_node import H5DictNode
from .table_node import H5TableNode


def get_atom(dtype):
    """ Return a PyTables Atom for the given dtype or dtype string.
    """
    return tables.Atom.from_dtype(np.dtype(dtype))


class H5File(object):
    """File object for HDF5 files.

    This class wraps PyTables to provide a cleaner, but only implements an
    interface for accessing arrays.

    Parameters
    ----------
    filename : str
        HDF5 file name.
    mode : str
        Mode to open the file:

            'r' : Read-only
            'w' : Write; create new file (an existing file would be deleted).
            'a' : Read and write to file; create if not existing
            'r+': Read and write to file; must already exist

    delete_existing : bool
        If True, an existing array node will be deleted when `create_array`
        is called. Otherwise, a ValueError will be raise.
    auto_groups : bool
        If True, `create_array` will automatically create parent groups.
    chunked : bool
        If True, the default behavior of `create_array` will be a chunked
        array (see PyTables `createCArray`).

    """
    exists_error = ("'{}' exists in '{}'; set `delete_existing` attribute "
                    "to True to overwrite existing calculations.")

    def __init__(self, filename, mode='r+', delete_existing=False,
                 auto_groups=True, chunked=False, extendable=False,
                 h5filters=None):
        self.delete_existing = delete_existing
        self.filename = filename
        self.chunked_default = chunked
        self.extendable_default = extendable
        self.auto_groups = auto_groups
        self._h5 = tables.openFile(filename, mode=mode)
        if h5filters is None:
            self.h5filters = tables.Filters(complib='blosc', complevel=5,
                                            shuffle=True)

    def close(self):
        if self._h5:
            self._h5.close()
        self._h5 = None

    def __str__(self):
        return str(self._h5)

    def __repr__(self):
        return repr(self._h5)

    def __contains__(self, node_path):
        return node_path in self._h5

    def __getitem__(self, node_path):
        try:
            node = self._h5.getNode(node_path)
        except tables.NoSuchNodeError:
            msg = "Node {!r} not found in {!r}"
            raise NameError(msg.format(node_path, self.filename))
        return _wrap_node(node)

    def iteritems(self, path='/'):
        """ Iterate over node paths and nodes of the h5 file. """
        for node in self._h5.walkNodes(where=path):
            node_path = node._v_pathname
            yield node_path, _wrap_node(node)

    def create_array(self, node_path, array_or_shape, chunked=None,
                     dtype=None, extendable=None, **kwargs):
        """Create node to store an array.

        Parameters
        ----------
        node_path : str
            PyTable node path; e.g. '/path/to/node'.
        array_or_shape : array or shape tuple
            Array or shape tuple for an array. If given a shape tuple, the
            `dtype` parameter must also specified.
        chunked : {None | bool}
            Controls whether the array is chunked. If None, use
            `chunked_default` attribute.
        dtype : str or numpy.dtype
            Data type of array. Only necessary if `array_or_shape` is a shape.
        extendable : {None | bool}
            Controls whether the array is extendable. If None, use the
            `extendable_default` attribute.
        kwargs : key/value pairs
            Keyword args passed to PyTables `File.create(C)Array`.
        """
        self._check_node(node_path)
        self._assert_valid_path(node_path)

        pick_value = lambda x, default: default if x is None else x
        chunked = pick_value(chunked, self.chunked_default)
        extendable = pick_value(extendable, self.extendable_default)
        h5 = self._h5

        if isinstance(array_or_shape, tuple):
            if dtype is None:
                msg = "`dtype` must be specified if only given array shape."
                raise ValueError(msg)
            array = None
            dtype = dtype
            shape = array_or_shape
        else:
            array = array_or_shape
            dtype = array.dtype.name
            shape = array.shape

        path, name = self.split_path(node_path)
        if extendable:
            shape = (0,) + shape[1:]
            atom = get_atom(dtype)
            node = h5.createEArray(path, name, atom, shape,
                                   filters=self.h5filters, **kwargs)
            if array is not None:
                node.append(array)
        elif chunked:
            atom = get_atom(dtype)
            node = h5.createCArray(path, name, atom, shape,
                                   filters=self.h5filters, **kwargs)
            if array is not None:
                node[:] = array
        else:
            if array is None:
                array = np.zeros(shape, dtype=dtype)
            node = h5.createArray(path, name, array, **kwargs)
        return node

    def create_group(self, group_path, **kwargs):
        """Create group.

        Parameters
        ----------
        group_path : str
            PyTable group path; e.g. '/path/to/group'.
        kwargs : key/value pairs
            Keyword args passed to PyTables `File.createGroup`.
        """
        self._check_node(group_path)
        self._assert_valid_path(group_path)
        path, name = self.split_path(group_path)
        self._h5.createGroup(path, name, **kwargs)

    def create_dict(self, node_path, data=None, **kwargs):
        """ Create dict node at the specified path.

        Parameters
        ----------
        node_path : str
            Path to node where data is stored (e.g. '/path/to/my_dict')
        data : dict
            Data for initialization, if desired.
        """
        self._check_node(node_path)
        self._assert_valid_path(node_path)
        H5DictNode.add_to_h5file(self, node_path, data=data, **kwargs)

    def create_table(self, node_path, description, **kwargs):
        """ Create table node at the specified path.

        Parameters
        ----------
        node_path : str
            Path to node where data is stored (e.g. '/path/to/my_dict')
        description : dict or numpy dtype object
            The description of the columns in the table. This is either a dict
            of column name -> dtype items or a numpy record array dtype. For
            more information, see the documentation for Table in pytables.
        """
        self._check_node(node_path)
        self._assert_valid_path(node_path)
        H5TableNode.add_to_h5file(self, node_path, description, **kwargs)

    def _check_node(self, node_path):
        """Check if node exists and create parent groups if necessary.

        Either raise error or delete depending on `delete_existing` attribute.
        """
        if self.auto_groups:
            path, name = self.split_path(node_path)
            self._create_required_groups(path)

        if node_path in self:
            if self.delete_existing:
                if isinstance(self[node_path], H5Group):
                    self.remove_group(node_path, recursive=True)
                else:
                    self.remove_node(node_path)
            else:
                msg = self.exists_error.format(node_path, self.filename)
                raise ValueError(msg)

    def _create_required_groups(self, path):
        if path not in self:
            parent, missing = self.split_path(path)
            # Call recursively to ensure that all parent groups exist.
            self._create_required_groups(parent)
            self.create_group(path)

    def remove_node(self, node_path):
        """Remove node

        Parameters
        ----------
        node_path : str
            PyTable node path; e.g. '/path/to/node'.
        """
        node = self[node_path]
        node._f_remove()

    def remove_group(self, group_path, **kwargs):
        """Remove group

        Parameters
        ----------
        group_path : str
            PyTable group path; e.g. '/path/to/group'.
        """
        self[group_path]._h5_group._g_remove(**kwargs)

    @classmethod
    def _assert_valid_path(self, node_path):
        if 'attrs' in node_path.split('/'):
            raise ValueError("'attrs' is an invalid node name.")

    @classmethod
    def split_path(cls, node_path):
        """Split node path returning the base path and node name.

        For example: '/path/to/node' will return '/path/to' and 'node'

        Parameters
        ----------
        node_path : str
            PyTable node path; e.g. '/path/to/node'.
        """
        i = node_path.rfind('/')
        if i == 0:
            return '/', node_path[1:]
        else:
            return node_path[:i], node_path[i + 1:]

    @classmethod
    def join_path(cls, *args):
        """Join parts of an h5 path.

        For example, the 3 argmuments 'path', 'to', 'node' will return
        '/path/to/node'.

        Parameters
        ----------
        args : str
            Parts of path to be joined.
        """
        path = '/'.join(part.strip('/') for part in args)
        if not path.startswith('/'):
            path = '/' + path
        return path


class H5Attrs(MutableMapping):
    """ An attributes dictionary for an h5 node.

    This intercepts `__setitem__` so that python sequences can be converted to
    numpy arrays. This helps preserve the readability of our HDF5 files by
    other (non-python) programs.
    """

    def __init__(self, node_attrs):
        self._node_attrs = node_attrs

    def __delitem__(self, key):
        del self._node_attrs[key]

    def __getitem__(self, key):
        return self._node_attrs[key]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self._node_attrs._f_list())

    def __setitem__(self, key, value):
        if isinstance(value, tuple) or isinstance(value, list):
            value = np.array(value)
        self._node_attrs[key] = value

    def get(self, key, default=None):
        return default if key not in self else self[key]

    def keys(self):
        return self._node_attrs._f_list()

    def values(self):
        return [self[k] for k in self.keys()]

    def items(self):
        return [(k, self[k]) for k in self.keys()]


class H5Group(object):
    """ A group node in an H5File.

    This is a thin wrapper around PyTables' Group object to expose attributes
    and maintain the dict interface of H5File.
    """

    def __init__(self, pytables_group):
        self._h5_group = pytables_group
        self.attrs = H5Attrs(self._h5_group._v_attrs)

    def __contains__(self, node_path):
        return node_path in self._h5_group

    def __str__(self):
        return str(self._h5_group)

    def __repr__(self):
        return repr(self._h5_group)

    def __getitem__(self, node_path):
        parts = node_path.split('/')
        # PyTables stores children as attributes
        node = self._h5_group.__getattr__(parts[0])
        node = _wrap_node(node)
        if len(parts) == 1:
            return node
        else:
            return node['/'.join(parts[1:])]

    @property
    def name(self):
        return self._h5_group._v_name

    @property
    def children_names(self):
        return self._h5_group._v_children.keys()

    @property
    def subgroup_names(self):
        return self._h5_group._v_groups.keys()


def _wrap_node(node):
    """ Wrap PyTables node object, if necessary. """
    if isinstance(node, tables.Group):
        if H5DictNode.is_dict_node(node):
            node = H5DictNode(node)
        else:
            node = H5Group(node)
    elif H5TableNode.is_table_node(node):
        node = H5TableNode(node)
    return node
