# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
""" 
==========================
BIP: Task-fMRI config file
==========================

Instructions:
-------------

Input your project related values into the variables and functions \
listed in this file.

Running the BIP:
----------------
In a Terminal,

cd /path/to/BrainImagingPipelines/fmri/task

Then type:

python preprocess.py

After running preprocessing, you can run the first level pipeline:

python workflow10.py


Directories:
------------

root_dir : Location of the Nipype working directory

base_dir : Base directory of data. (Should be subject-independent)

sink_dir : Location where the BIP will store the results

field_dir : (Optional) Base directory of field-map data (Should be subject-independent)
            Set this value to None if you don't want fieldmap distortion correction
            
surf_dir : Freesurfer subjects directory

crash_dir : Location to store crash files
"""

working_dir = '/mindhive/scratch/keshavan/sad/task'

base_dir = '/mnt/gablab/sad/PY_STUDY_DIR/Block/data/'

sink_dir = '/mnt/gablab/sad/bips/task'

field_dir = '/mnt/gablab/sad/Data_reorganized'

surf_dir = '/mindhive/xnat/surfaces/sad/'

crash_dir = working_dir

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

subjects = ['SAD_024']#controls+patients

run_on_grid = True
plugin = 'PBS'

plugin_args = {'qsub_args': '-l nodes=1:ppn=3'}

use_fieldmap = True

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

import numpy as np
func0 = np.vectorize(lambda x: x-1) # slice order is 0-based!
SliceOrder = func0([1,3,5,7,9,11,13,15,17,19,21,23,25,27,2,4,6,8,10,12,14,16,18,20,22,24,26]).tolist()

TR = 2.5

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

echospacing = 0.58

TE_diff = 2.46

sigma = 2

"""
Artifact Detection
^^^^^^^^^^^^^^^^^^

norm_thresh : 

z_thresh :

"""

norm_thresh = 1

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

num_noise_components = 6

"""
Highpass Filter
^^^^^^^^^^^^^^^

hpcutoff : Float
           Highpass filter cut off in Hz?
"""

hpcutoff = 128.

"""
First-Level 
-----------

Node Inputs
^^^^^^^^^^^

interscan_interval : 

film_threshold : 

overlaythresh : 2-Tuple of Floats
                the min and max z-scores to threshold the image at. \
                In the sliced and overlayed images, voxels will show \
                up if for their value x the following is true: \
                overlaythresh[0] < x < overlaythresh[1] or \
                -1*overlaythresh[0] > x > -1*overlaythresh[0]
"""

interscan_interval = 2

film_threshold = 1000

overlaythresh = (3.09, 10.00)

is_block_design = True

"""
Functions
---------

Preprocessing
^^^^^^^^^^^^^
create_dataflow : Function that finds the functional runs for each subject.
                  Must return a DataGrabber Node. See the DataGrabber_ \
                  documentation for more information.

create_fieldmap_dataflow : Function that finds the functional runs for \
                           each subject. Must return a DataGrabber Node. \
                           See the DataGrabber_ documentation for more \
                           information.

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
    datasource.inputs.field_template = dict(func='%s/f3*.nii')
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
    datasource.inputs.field_template = dict(mag='%s/fieldmap128/*run00*.nii.gz',
                                            phase='%s/fieldmap128/*run01*.nii.gz')
    datasource.inputs.template_args = dict(mag=[['subject_id']],
                                           phase=[['subject_id']])
    return datasource

"""
First-level
^^^^^^^^^^^

subjectinfo : Function with one parameter, subject_id. \
              Returns a list of Bunches, where each Bunch \
              in the list corresponds to each functional run.
              The Bunch contains values for conditions, onsets, durations, \
              amplitudes, pmod, tmod, regressor_names, and regressors. For \
              more information see the documentation in nipype for modelgen_. 

getcontrasts : Function with one parameter, subject_id. \
               Returns a list of contrasts. For more information \
               on defining contrasts_, see the nipype documentation.


.. _modelgen: http://www.mit.edu/~satra/nipype-nightly/interfaces/generated/nipype.algorithms.modelgen.html

.. _contrasts: http://www.mit.edu/~satra/nipype-nightly/interfaces/generated/nipype.interfaces.fsl.model.html#level1design

"""

def subjectinfo(subject_id):
    from nipype.interfaces.base import Bunch
    from copy import deepcopy
    #from . import get_run_numbers
    print "Subject ID: %s\n"%str(subject_id)  
    output = []
    names = ['AngryFaces','NeutralFaces','PotentScenes','EmotionalScenes','NeutralScenes']
    regular = ['SAD_017','SAD_019','SAD_021','SAD_023','SAD_025','SAD_028','SAD_030','SAD_032','SAD_034','SAD_036','SAD_038','SAD_040',
'SAD_043','SAD_045','SAD_047','SAD_049','SAD_051','SAD2_019','SAD2_025','SAD2_028','SAD2_032','SAD2_030','SAD2_036','SAD2_038',
'SAD2_047','SAD2_049','SAD_P03','SAD_P04','SAD_P07','SAD_P09','SAD_P11','SAD_P13','SAD_P15','SAD_P17','SAD_P19','SAD_P21',
'SAD_P24','SAD_P26','SAD_P28','SAD_P30','SAD_P32','SAD_P33','SAD_P35','SAD_P37','SAD_P39','SAD_P41','SAD_P43','SAD_P46',
'SAD_P48','SAD_P49','SAD_P53','SAD_P54','SAD_P57','SAD_P58','SAD_POST09','SAD_POST07','SAD_POST04','SAD_POST13','SAD_POST11','SAD_POST21','SAD_POST24',
'SAD_POST26','SAD_POST28','SAD_POST30','SAD_POST35','SAD_POST39','SAD_POST41','SAD_POST46','SAD_POST53']

    cb = ['SAD_018','SAD_020','SAD_022','SAD_024','SAD_027','SAD_029','SAD_031','SAD_033','SAD_035','SAD_037','SAD_039','SAD_041','SAD_044',
'SAD_046','SAD_048','SAD_050','SAD2_020','SAD2_022','SAD2_024','SAD2_027','SAD2_029','SAD2_031','SAD2_033','SAD2_039','SAD2_046',
'SAD2_050','SAD2_044','SAD_P05','SAD_P06','SAD_P08','SAD_P10','SAD_P12','SAD_P14','SAD_P16','SAD_P18','SAD_P20','SAD_P22','SAD_P23','SAD_P25',
'SAD_P27','SAD_P29','SAD_P31','SAD_P34','SAD_P36','SAD_P38','SAD_P40','SAD_P42','SAD_P44','SAD_P45',
'SAD_P47','SAD_P50','SAD_P51','SAD_P52','SAD_P55','SAD_P56','SAD_POST05','SAD_POST06','SAD_POST08','SAD_POST10','SAD_POST12','SAD_POST14',
'SAD_POST16','SAD_POST20','SAD_POST22','SAD_POST27','SAD_POST31','SAD_POST34','SAD_POST38','SAD_POST36','SAD_POST44','SAD_POST45','SAD_POST47',
'SAD_POST50','SAD_POST51','SAD_POST52']
    def get_run_numbers(subject_id):
        if subject_id == "SAD_018":
            return [0, 1]
        else:
            return [0]
        
    for r in range(len(get_run_numbers(subject_id))):
        if subject_id in regular:
	        onsets = [[45,120,240,315,405,465],[60,135,195,285,420,495],[30,105,255,330,375,525],[15,165,210,300,390,510],[75,150,225,345,435,480]]
        elif subject_id in cb:
	        onsets = [[75,135,225,300,420,495],[45,120,255,345,405,480],[15,165,210,285,435,510],[30,150,240,330,375,525],[60,105,195,315,390,465]]
        else: 
	        raise Exception('%s unknown' %subject_id)
        durations = [[15],[15],[15],[15],[15]]
        output.insert(r,
                      Bunch(conditions=names,
                            onsets=deepcopy(onsets),
                            durations=deepcopy(durations),
                            amplitudes=None,
                            tmod=None,
                            pmod=None,
                            regressor_names=None,
                            regressors=None))
    return output

def getcontrasts(subject_id):
    cont1 = ['AngryFaces_NeutralFaces','T', ['AngryFaces','NeutralFaces'],[1,-1]]
    cont2 = ['EmotionalScenes_NeutralScenes','T', ['EmotionalScenes','NeutralScenes'],[1,-1]]
    cont3 = ['NeutralFaces_NeutralScenes','T', ['NeutralFaces','NeutralScenes'],[1,-1]]
    cont4 = ['AngryFaces_EmotionalScenes','T', ['AngryFaces','EmotionalScenes'],[1,-1]]
    cont5 = ['AFES_NFNS','T', ['AngryFaces','EmotionalScenes','NeutralFaces','NeutralScenes'],[.5,.5,-.5,-.5]]
    cont6 = ['NFAF_NSES','T', ['NeutralFaces','AngryFaces','NeutralScenes','EmotionalScenes'],[.5,.5,-.5,-.5]]
    cont7 = ['AFNS_NFES','T', ['AngryFaces','NeutralScenes','NeutralFaces','EmotionalScenes'],[.5,.5,-.5,-.5]]
    cont8 = ['All_Fix','T', ['AngryFaces','NeutralFaces','PotentScenes','EmotionalScenes','NeutralScenes'],[.2,.2,.2,.2,.2]]
    cont9 = ['AngryFaces_NeutralScenes','T', ['AngryFaces','NeutralScenes'],[1,-1]]
    cont10 = ['PotentScenes_NeutralScenes','T', ['PotentScenes','NeutralScenes'],[1,-1]]
    cont11 = ['Faces_Fixation', 'T', ['AngryFaces','NeutralFaces'], [.5,.5]]
    cont12 = ['Places_Fixation', 'T', ['EmotionalScenes','NeutralScenes','PotentScenes'],[.33,.33,.33]]
    cont13 = ['AngryFaces_Fix', 'T', ['AngryFaces'], [1]]
    cont14 = ['NeutralFaces_Fix', 'T', ['NeutralFaces'], [1]]
    cont15 = ['PotentScenes_Fix', 'T', ['PotentScenes'], [1]]
    cont16 = ['EmotionalScenes_Fix', 'T', ['EmotionalScenes'], [1]]
    cont17 = ['NeutralScenes_Fix', 'T', ['NeutralScenes'], [1]]
    contrasts = [cont1,cont2,cont3,cont4,cont5,cont6,cont7,cont8,cont9,cont10,cont11,cont12,cont13,cont14,cont15,cont16,cont17]
    return contrasts


