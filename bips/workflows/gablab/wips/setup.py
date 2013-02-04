# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
def configuration(parent_package='',top_path=None):
    from numpy.distutils.misc_util import Configuration
    config = Configuration('bips', parent_package, top_path)

    # List all packages to be loaded here
    config.add_subpackage('dicom')
    config.add_subpackage('dmri')
    config.add_subpackage('fmri')
    config.add_subpackage('fmri/preprocessing')
    config.add_subpackage('fmri/resting')
    config.add_subpackage('fmri/misc')
    config.add_subpackage('fmri/viz')
    config.add_subpackage('fmri/first_level')
    config.add_subpackage('fmri/group_analysis')
    config.add_subpackage('smri')

    # List all data directories to be loaded here
    return config

if __name__ == '__main__':
    from numpy.distutils.core import setup
    setup(**configuration(top_path='').todict())
