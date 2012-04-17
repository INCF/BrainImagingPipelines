""" This file contains defines parameters for nipy that we use to fill
settings in setup.py, the nipy top-level docstring, and for building the
docs.  In setup.py in particular, we exec this file, so it cannot import nipy
"""


# bips version information.  An empty _version_extra corresponds to a
# full release.  '.dev' as a _version_extra string means this is a development
# version
_version_major = 0
_version_minor = 1
_version_micro = 0
_version_extra = '.dev'

def get_nipype_gitversion():
    """Nipype version as reported by the last commit in git

    Returns
    -------
    None or str
      Version of NiPype according to git.
    """
    import os
    import subprocess
    try:
        import bips
        gitpath = os.path.realpath(os.path.join(os.path.dirname(bips.__file__),
                                                os.path.pardir))
    except:
        gitpath = os.getcwd()
    gitpathgit = os.path.join(gitpath, '.git')
    if not os.path.exists(gitpathgit):
        return None
    ver = None
    try:
        o, _ = subprocess.Popen('git describe', shell=True, cwd=gitpath,
                                stdout=subprocess.PIPE).communicate()
    except Exception:
        pass
    else:
        ver = o.strip().split('-')[-1]
    return ver

if '.dev' in _version_extra:
    gitversion = get_nipype_gitversion()
    if gitversion:
        _version_extra = '.' + gitversion + '-' + 'dev'

# Format expected by setup.py and doc/source/conf.py: string of form "X.Y.Z"
__version__ = "%s.%s.%s%s" % (_version_major,
                              _version_minor,
                              _version_micro,
                              _version_extra)

CLASSIFIERS = ["Development Status :: 4 - Beta",
               "Environment :: Console",
               "Intended Audience :: Science/Research",
               "License :: OSI Approved :: BSD License",
               "Operating System :: OS Independent",
               "Programming Language :: Python",
               "Topic :: Scientific/Engineering"]

description  = 'Neuroimaging in Python: Pipelines and Interfaces'

# Note: this long_description is actually a copy/paste from the top-level
# README.rst.txt, so that it shows up nicely on PyPI.  So please remember to edit
# it only in one place and sync it correctly.
long_description = \
"""
=============================
BIPS: Brain Imaging Pipelines
=============================

The goal of BIPS is to present a set of brain imaging workflows for analysis of
diffusion, structural and functional mri data.

"""

# requirement versions
NIPYPE_MIN_VERSION = '0.5.3'

NAME                = 'bips'
MAINTAINER          = "bips developers"
MAINTAINER_EMAIL    = "akeshavan@mit.edu, satra@mit.edu"
DESCRIPTION         = description
LONG_DESCRIPTION    = long_description
URL                 = "http://bips.incf.org"
DOWNLOAD_URL        = "http://github.com/INCF/BrainImagingPipelines/archives/master"
LICENSE             = "Apache 2.0"
CLASSIFIERS         = CLASSIFIERS
AUTHOR              = "bips developmers"
AUTHOR_EMAIL        = "akeshavan@mit.edu, satra@mit.edu"
PLATFORMS           = "OS Independent"
MAJOR               = _version_major
MINOR               = _version_minor
MICRO               = _version_micro
ISRELEASE           = _version_extra == ''
VERSION             = __version__
REQUIRES            = ["nipype (>=0.5.3)"]
STATUS              = 'beta'
