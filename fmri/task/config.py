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
root_dir = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/'
base_dir = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/data/'


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
compcor_select = [True, True]
# - 'TR' 
TR = 2.5

# Motion correction params
Interleaved = True
SliceOrder = 'ascending'


# - 'interscan_interval'
interscan_interval = 2

# - 'film_threshold'
film_threshold = 1000

# - 'hpcutoff'
hpcutoff = 128.

# - 'test_mode' [boolean] - affects whether where and if the workflow keeps its intermediary files.  
test_mode = True

# - 'auto_fixedfx' [boolean] - will automatically run fixedfx analyses at the end of first level modelfitting
auto_fixedfx = True

# surf_dir - directory where the individual subject's freesurfer directories are
surf_dir = '/mindhive/xnat/surfaces/sad/'

# overlaythresh is the min and max z-scores to threshold the image at. a tuple of floats. in the sliced and
# overlayed images, voxels will show up if for their value x the following is true:
# overlaythresh[0] < x < overlaythresh[1] or -1*overlaythresh[0] > x > -1*overlaythresh[0]
overlaythresh = (3.09, 10.00)

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
    datasource.inputs.field_template = dict(func='%s/f%s.nii',struct='%s/struct.nii')
    #datasource.inputs.subject_id = subj
    datasource.inputs.template_args = dict(func=[['subject_id',['3']]], struct=[['subject_id']])#,'2','3','4','5','6']]])
    return datasource

def get_onsets(subject_id):
        
    output = subjectinfo(subject_id)
    
    info = output[0]
    return info
    
   
def get_run_numbers(subject_id):
    #behav_path = os.path.join(root_dir,subject_id,'boldnii','run_para.txt')
    #paraidx = np.genfromtxt(behav_path,dtype=object)[:,0]
    #runs = [int(para) for para in paraidx]
    return [3]#,2,3,4,5,6]

def getinfo(subject_id):
    runs = ['3']#,'2','3','4','5','6']#deepcopy(get_run_numbers(subject_id))
    info = dict(func=[['subject_id', 'fwhm', 'subject_id', runs]],
                motion=[['subject_id', 'subject_id', runs]],
                outliers=[['subject_id', 'subject_id', runs]])
    #dict(func=[['subject_id',['00','01']]],struct=[['subject_id']])
    return info


def subjectinfo(subject_id):
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
 
    for r in range(1):
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


