import bpy

import numpy.testing

from rprblender import logging

class SyncFixture:
    """ this executes sync callback every time an update is fired from blender(triggered in tests with scene.update())
    (hopefully) mimicking somewhat blender runtime behaviour in view_update
    """

    error = False

    def update_post(self, scene):
        self.sync()

    def set_sync(self, testee):
        self._sync_callback = testee

    def stop(self):
        logging.info('stop', tag='testing')
        assert not self.error
        bpy.app.handlers.scene_update_post.remove(self.update_post)

    def sync(self):
        logging.debug('sync', tag='testing')
        try:
            self._sync_callback()
        except:
            self.error = True
            raise

    def __enter__(self):
        bpy.app.handlers.scene_update_post.append(self.update_post)

    def __exit__(self, *args):
        self.stop()


def assert_arrays_approx_equal(a, b, digits):
    assert len(a) == len(b)
    for av, bv in zip(a, b):
        try:
            numpy.testing.assert_approx_equal(av, bv, digits)
        except AssertionError:
            raise AssertionError(
                """\nArrays are not eaual to %d significant digits:
  EXPECTED: %s
  ACTUAL: %s
""" % (digits, a, b))


def run_all_tests(pytestargs, keep_blender_running):
    import sys
    import pytest

    args = list(pytestargs)

    if keep_blender_running:
        args.append('--keep-blender-running')

    print('run_all_tests:', args)
    result = pytest.main(args)

    if not keep_blender_running:
        sys.exit(result)
