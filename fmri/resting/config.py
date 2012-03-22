# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import os
import numpy as np
from nipype.interfaces.base import Bunch
from copy import deepcopy

# this is the configuration file for the resting state preprocessing script

root_dir = '/mindhive/scratch/keshavan/sad/resting'
base_dir = '/mindhive/gablab/sad/SAD_STUDY_Resting/data'
sink_dir = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/'
field_dir = '/mindhive/gablab/sad/Data_reorganized'
# list of subjects
controls = ['SAD_017', 'SAD_018', 'SAD_019', 'SAD_020', 'SAD_021', 'SAD_022',
            'SAD_023', 'SAD_024', 'SAD_025', 'SAD_027', 'SAD_028', 'SAD_029',
            'SAD_030', 'SAD_031', 'SAD_032', 'SAD_033', 'SAD_034', 'SAD_035',
            'SAD_036', 'SAD_037', 'SAD_038', 'SAD_039', 'SAD_040', 'SAD_041',
            'SAD_043', 'SAD_044', 'SAD_045', 'SAD_046', 'SAD_047', 'SAD_048',
            'SAD_049', 'SAD_050', 'SAD_051']
patients = ['SAD_P03', 'SAD_P04', 'SAD_P05', 'SAD_P07', 'SAD_P08', 'SAD_P09',
            'SAD_P10', 'SAD_P11', 'SAD_P12', 'SAD_P13', 'SAD_P14', 'SAD_P15',
            'SAD_P16', 'SAD_P17', 'SAD_P18', 'SAD_P19', 'SAD_P20', 'SAD_P21',
            'SAD_P22', 'SAD_P23', 'SAD_P24', 'SAD_P25', 'SAD_P26', 'SAD_P27',
            'SAD_P28', 'SAD_P29', 'SAD_P30', 'SAD_P31', 'SAD_P32', 'SAD_P33',
            'SAD_P34', 'SAD_P35', 'SAD_P36', 'SAD_P37', 'SAD_P38', 'SAD_P39',
            'SAD_P40', 'SAD_P41', 'SAD_P42', 'SAD_P43', 'SAD_P44', 'SAD_P45',
            'SAD_P46', 'SAD_P47', 'SAD_P48', 'SAD_P49', 'SAD_P50', 'SAD_P51',
            'SAD_P52', 'SAD_P53', 'SAD_P54', 'SAD_P55', 'SAD_P56', 'SAD_P57',
            'SAD_P58']
subjects = ['SAD_018']#patients[0:1] #controls + patients
#subjects = subjects[:1]
fieldmap = True
# - 'norm_thresh' (for rapidart) - 4
norm_thresh = 2

# - 'z_thresh' (for rapidart) - 3
z_thresh = 3

# crash directory - still not working
crash_dir = root_dir

# - 'run_on_grid' [boolean]
run_on_grid = True

# - 'fwhm' full width at half max (currently only the second value is used)
fwhm = [0, 5]

# - 'num_noise_components' number of principle components of the noise to use
num_noise_components =  6
# first corresponds to t compcor, second to a compcor
compcor_select = [True, True]

# - 'TR' 
TR = 6.0

# Motion correction params
Interleaved = True
SliceOrder = 'ascending'

# regressors
# [motion, composite norm, compcorr components, outliers, motion derivatives]
reg_params = [True, True, True, True, True]

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
                                                   outfields=['func']),
                         name = name)
    datasource.inputs.base_directory = base_dir
    datasource.inputs.template ='*'
    datasource.inputs.field_template = dict(func='%s/resting*.nii')
    datasource.inputs.template_args = dict(func=[['subject_id']])
    return datasource
    
def create_fieldmap_dataflow(name="datasource_fieldmap"):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio 
    # create a node to obtain the functional images
    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
                                                   outfields=['mag','phase']),
                         name = name)
    datasource.inputs.base_directory = field_dir
    datasource.inputs.template ='*'
    datasource.inputs.field_template = dict(mag='%s/fieldmap_resting/*run00*.nii.gz',
                                            phase='%s/fieldmap_resting/*run01*.nii.gz')
    datasource.inputs.template_args = dict(mag=[['subject_id']],
                                           phase=[['subject_id']])
    return datasource
