"""Test HTML utils"""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import ctypes
import os
import re
import stat
import shutil
import tempfile

import nose.tools as nt

from traitlets.tests.utils import check_help_all_output
from jupyter_server.utils import url_escape, url_unescape, is_hidden, is_file_hidden, secure_write
from ipython_genutils.py3compat import cast_unicode
from ipython_genutils.tempdir import TemporaryDirectory
from ipython_genutils.testing.decorators import skip_if_not_win32, skip_win32


def test_help_output():
    """jupyter server --help-all works"""
    check_help_all_output('jupyter_server')

def test_url_escape():

    # changes path or notebook name with special characters to url encoding
    # these tests specifically encode paths with spaces
    path = url_escape('/this is a test/for spaces/')
    nt.assert_equal(path, '/this%20is%20a%20test/for%20spaces/')

    path = url_escape('notebook with space.ipynb')
    nt.assert_equal(path, 'notebook%20with%20space.ipynb')

    path = url_escape('/path with a/notebook and space.ipynb')
    nt.assert_equal(path, '/path%20with%20a/notebook%20and%20space.ipynb')

    path = url_escape('/ !@$#%^&* / test %^ notebook @#$ name.ipynb')
    nt.assert_equal(path,
        '/%20%21%40%24%23%25%5E%26%2A%20/%20test%20%25%5E%20notebook%20%40%23%24%20name.ipynb')

def test_url_unescape():

    # decodes a url string to a plain string
    # these tests decode paths with spaces
    path = url_unescape('/this%20is%20a%20test/for%20spaces/')
    nt.assert_equal(path, '/this is a test/for spaces/')

    path = url_unescape('notebook%20with%20space.ipynb')
    nt.assert_equal(path, 'notebook with space.ipynb')

    path = url_unescape('/path%20with%20a/notebook%20and%20space.ipynb')
    nt.assert_equal(path, '/path with a/notebook and space.ipynb')

    path = url_unescape(
        '/%20%21%40%24%23%25%5E%26%2A%20/%20test%20%25%5E%20notebook%20%40%23%24%20name.ipynb')
    nt.assert_equal(path, '/ !@$#%^&* / test %^ notebook @#$ name.ipynb')

def test_is_hidden():
    with TemporaryDirectory() as root:
        subdir1 = os.path.join(root, 'subdir')
        os.makedirs(subdir1)
        nt.assert_equal(is_hidden(subdir1, root), False)
        nt.assert_equal(is_file_hidden(subdir1), False)

        subdir2 = os.path.join(root, '.subdir2')
        os.makedirs(subdir2)
        nt.assert_equal(is_hidden(subdir2, root), True)
        nt.assert_equal(is_file_hidden(subdir2), True)#
        # root dir is always visible
        nt.assert_equal(is_hidden(subdir2, subdir2), False)

        subdir34 = os.path.join(root, 'subdir3', '.subdir4')
        os.makedirs(subdir34)
        nt.assert_equal(is_hidden(subdir34, root), True)
        nt.assert_equal(is_hidden(subdir34), True)

        subdir56 = os.path.join(root, '.subdir5', 'subdir6')
        os.makedirs(subdir56)
        nt.assert_equal(is_hidden(subdir56, root), True)
        nt.assert_equal(is_hidden(subdir56), True)
        nt.assert_equal(is_file_hidden(subdir56), False)
        nt.assert_equal(is_file_hidden(subdir56, os.stat(subdir56)), False)

@skip_if_not_win32
def test_is_hidden_win32():
    with TemporaryDirectory() as root:
        root = cast_unicode(root)
        subdir1 = os.path.join(root, u'subdir')
        os.makedirs(subdir1)
        assert not is_hidden(subdir1, root)
        r = ctypes.windll.kernel32.SetFileAttributesW(subdir1, 0x02)
        print(r)
        assert is_hidden(subdir1, root)
        assert is_file_hidden(subdir1)

@skip_if_not_win32
def test_secure_write_win32():
    def fetch_win32_permissions(filename):
        '''Extracts file permissions on windows using icacls'''
        role_permissions = {}
        for index, line in enumerate(os.popen("icacls %s" % filename).read().splitlines()):
            if index == 0:
                line = line.split(filename)[-1].strip().lower()
            match = re.match(r'\s*([^:]+):\(([^\)]*)\)', line)
            if match:
                usergroup, permissions = match.groups()
                usergroup = usergroup.lower().split('\\')[-1]
                permissions = set(p.lower() for p in permissions.split(','))
                role_permissions[usergroup] = permissions
            elif not line.strip():
                break
        return role_permissions

    def check_user_only_permissions(fname):
        # Windows has it's own permissions ACL patterns
        import win32api
        username = win32api.GetUserName().lower()
        permissions = fetch_win32_permissions(fname)
        print(permissions) # for easier debugging
        nt.assert_true(username in permissions)
        nt.assert_equal(permissions[username], set(['r', 'w']))
        nt.assert_true('administrators' in permissions)
        nt.assert_equal(permissions['administrators'], set(['f']))
        nt.assert_true('everyone' not in permissions)
        nt.assert_equal(len(permissions), 2)

    directory = tempfile.mkdtemp()
    fname = os.path.join(directory, 'check_perms')
    try:
        with secure_write(fname) as f:
            f.write('test 1')
        check_user_only_permissions(fname)
        with open(fname, 'r') as f:
            nt.assert_equal(f.read(), 'test 1')
    finally:
        shutil.rmtree(directory)

@skip_win32
def test_secure_write_unix():
    directory = tempfile.mkdtemp()
    fname = os.path.join(directory, 'check_perms')
    try:
        with secure_write(fname) as f:
            f.write('test 1')
        mode = os.stat(fname).st_mode
        nt.assert_equal('0600', oct(stat.S_IMODE(mode)).replace('0o', '0'))
        with open(fname, 'r') as f:
            nt.assert_equal(f.read(), 'test 1')

        # Try changing file permissions ahead of time
        os.chmod(fname, 0o755)
        with secure_write(fname) as f:
            f.write('test 2')
        mode = os.stat(fname).st_mode
        nt.assert_equal('0600', oct(stat.S_IMODE(mode)).replace('0o', '0'))
        with open(fname, 'r') as f:
            nt.assert_equal(f.read(), 'test 2')
    finally:
        shutil.rmtree(directory)