# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

""" 
===================================
BIP: Resting-state fMRI config file
===================================

Instructions:
-------------

Input your project related values into the variables and functions \
listed in this file.

Running the BIP:
----------------
In a Terminal type::

  cd /path/to/BrainImagingPipelines/fmri/task

Then type::

  python preprocess.py -c your_config_file.py


Directories:
------------

working_dir : Location of the Nipype working directory

base_dir : Base directory of data. (Should be subject-independent)

sink_dir : Location where the BIP will store the results

field_dir : (Optional) Base directory of field-map data (Should be subject-independent)
            Set this value to None if you don't want fieldmap distortion correction
            
surf_dir : Freesurfer subjects directory

crash_dir : Location to store crash files
"""

working_dir = '/mindhive/scratch/satra/sad/resting'

base_dir = '/mindhive/gablab/sad/SAD_STUDY_Resting/data'

sink_dir = '/mindhive/gablab/sad/bips/resting'

field_dir = '/mindhive/gablab/sad/Data_reorganized'

crash_dir = working_dir

surf_dir = '/mindhive/xnat/surfaces/sad/'

"""
Workflow Inputs:
----------------

subjects : List of Strings
           Subject id's. Note: These MUST match the subject id's in the \
           Freesurfer directory. For simplicity, the subject id's should \
           also match with the location of individual functional files.
           
run_on_grid : Boolean
              True to run pipeline with PBS plugin, False to run serially

plugin_args : Dict
              Plugin arguments.
              
fieldmap : Boolean
           True to include fieldmap distortion correction. Note: field_dir \
           must be specified
           
test_mode : Boolean
            Affects whether where and if the workflow keeps its \
            intermediary files. True to keep intermediary files.  
           
"""

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
subjects = patients + controls
subjects = ['SAD_024']

run_on_grid = False

plugin_args = {'qsub_args': '-q many'}

test_mode = True

"""
Node Inputs
-----------

Motion / Slice Timing Correction
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Interleaved : Boolean
              True for Interleaved
              
SliceOrder : List or 'ascending' or 'descending'
             Order of slice aquisition, alternatively can be set to \
             'ascending' or 'descending'. Note: Slice order is \
             0-based.  

TR : Float 
     TR of scan

"""

Interleaved = True

SliceOrder = 'ascending'

TR = 6.0

"""
Fieldmap Correction
^^^^^^^^^^^^^^^^^^^

echospacing : Float 
              EPI echo spacing

TE_diff : Float
          difference in B0 field map TEs

sigma : Int
        2D spatial gaussing smoothing stdev (default = 2mm)

"""

use_fieldmap = True

echospacing = 0.7  #SG: CHECK THIS

TE_diff = 2.46

sigma = 2

"""
Artifact Detection
^^^^^^^^^^^^^^^^^^

norm_thresh : 

z_thresh :

"""

norm_thresh = 2

z_thresh = 3

"""
Smoothing
^^^^^^^^^
fwhm : Full width at half max. The data will be smoothed at all values \
       specified in this list.

"""

fwhm = [0, 5]

"""          
CompCor
^^^^^^^

compcor_select : The first value in the list corresponds to applying \
                 t-compcor, and the second value to a-compcor. Note: \
                 both can be true

num_noise_components : number of principle components of the noise to use               
"""

compcor_select = [True, True]

num_noise_components =  6

"""
Filter Regressor
^^^^^^^^^^^^^^^^

reg_params : List of Bools
             True/False to regress out: 
             [motion, composite norm, compcorr components, outliers, motion derivatives]            

"""

reg_params = [True, True, True, True, True]

"""
Bandpass Filter
^^^^^^^^^^^^^^^

highpass_sigma : Float
                 Highpass  cut off in mm
lowpass _sigma : Float
                 Lowpass cut off in mm

"""

highpass_sigma = 100/(2*TR)

lowpass_sigma = 12.5/(2*TR)

"""
Functions
---------

Preprocessing
^^^^^^^^^^^^^

create_dataflow : Function that finds the functional runs for each subject.
                  Must return a DataGrabber Node. See the DataGrabber_ \
                  documentation for more information. Node should have output \
                  "func" which has the functional runs

create_fieldmap_dataflow : Function that finds the functional runs for \
                           each subject. Must return a DataGrabber Node. \
                           See the DataGrabber_ documentation for more \
                           information. Node should have outsputs "mag" for \
                           the magnitude image and "phase" for the phase image.

.. _Datagrabber: http://www.mit.edu/~satra/nipype-nightly/users/grabbing_and_sinking.html 

"""

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
