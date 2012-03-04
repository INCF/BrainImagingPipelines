# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import os
import numpy as np
from nipype.interfaces.base import Bunch
from copy import deepcopy

# this is the configuration file for the preprocessing+first-level and fixed FX analyses scripts

# root directory
# the root directory should contain:
#   - <subject_ID>              : subject directories
#   - surfaces                  : containing freesurfer subject directories
#       - <subject_ID>
#   - work_dir                  : work directory
#   - analyses                  : output directory
#       - func                  : output subdirectory (using kanwisher lab convention)
root_dir = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/resting'
base_dir = '/mindhive/gablab/sad/SAD_STUDY_Resting/data'

# list of subjects
subjects = ['SAD_018']

# - 'norm_thresh' (for rapidart) - 4
norm_thresh = 4

# - 'z_thresh' (for rapidart) - 3
z_thresh = 3

# crash directory - still not working
crash_dir = root_dir

# - 'run_on_grid' [boolean]
run_on_grid = False

# - 'fwhm' full width at half max (currently only the second value is used)
fwhm = [0, 5]

# - 'num_noise_components' number of principle components of the noise to use
num_noise_components = 5
# first corresponds to t compcor, second to a compcor
compcor_select = [True, False]

# - 'TR' 
TR = 6.0

# Motion correction params
Interleaved = True
SliceOrder = 'ascending'


# - 'hpcutoff'
hpcutoff = 128.

# regressors
# [motion, composite norm, compcorr components, outliers]
reg_params = [True, True, True, True]

# - Bandpass cutoffs
highpass_sigma = 100/(2*TR)
lowpass_sigma = 12.5/(2*TR)

# - 'test_mode' [boolean] - affects whether where and if the workflow keeps its intermediary files.  
test_mode = True

# surf_dir - directory where the individual subject's freesurfer directories are
surf_dir = '/mindhive/xnat/surfaces/sad/'


#____________________________________________________________________________________________________________
#
#                       FUNCTIONS
#____________________________________________________________________________________________________________
#

def create_dataflow(name="datasource"):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio 
    # create a node to obtain the functional images
    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
                                                   outfields=['func','struct']),
                         name = name)
    datasource.inputs.base_directory = base_dir
    datasource.inputs.template ='*'
    datasource.inputs.field_template = dict(func='%s/resting.nii',struct='%s/struct.nii')
    datasource.inputs.template_args = dict(func=[['subject_id']], struct=[['subject_id']])#,'2','3','4','5','6']]])
    return datasource



