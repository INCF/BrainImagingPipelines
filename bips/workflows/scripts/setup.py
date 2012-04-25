# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
def configuration(parent_package='',top_path=None):
    from numpy.distutils.misc_util import Configuration
    config = Configuration('scripts', parent_package, top_path)

    # List all packages to be loaded here
    config.add_subpackage('u0a14c5b5899911e1bca80023dfa375f2')
    config.add_subpackage('ua780b1988e1c11e1baf80019b9f22493')

    # List all data directories to be loaded here
    return config

if __name__ == '__main__':
    from numpy.distutils.core import setup
    setup(**configuration(top_path='').todict())
