# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
import os

from workflows import list_workflows, configure_workflow, run_workflow

from info import (LONG_DESCRIPTION as __doc__,
                  URL as __url__,
                  STATUS as __status__,
                  __version__)

from numpy.testing import Tester


class BipsTester(Tester):
    def test(self, label='fast', verbose=1, extra_argv=None,
             doctests=False, coverage=False):
        # setuptools does a chmod +x on ALL python modules when it
        # installs.  By default, as a security measure, nose refuses to
        # import executable files.  To forse nose to execute our tests, we
        # must supply the '--exe' flag.  List thread on this:
        # http://www.mail-archive.com/distutils-sig@python.org/msg05009.html
        if not extra_argv:
            extra_argv = ['--exe']
        else:
            extra_argv.append('--exe')
        super(BipsTester, self).test(label, verbose, extra_argv,
                                       doctests, coverage)
    # Grab the docstring from numpy
    #test.__doc__ = Tester.test.__doc__

test = BipsTester().test
bench = BipsTester().bench


def _test_local_install():
    """ Warn the user that running with nipy being
        imported locally is a bad idea.
    """
    if os.getcwd() == os.sep.join(
                            os.path.abspath(__file__).split(os.sep)[:-2]):
        import warnings
        warnings.warn('Running the tests from the install directory may '
                     'trigger some failures')

_test_local_install()

# Set up package information function
def get_info():
    from pkg_info import get_pkg_info
    print "calling get info"
    return get_pkg_info(os.path.dirname(__file__))

# Cleanup namespace
del _test_local_install

# If this file is exec after being imported, the following lines will
# fail
try:
    del Tester
except:
    pass
