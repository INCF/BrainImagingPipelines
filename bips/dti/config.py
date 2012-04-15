# Imports
import nipype.interfaces.io as nio           # Data i/o
import nipype.interfaces.fsl as fsl          # fsl
import nipype.interfaces.utility as util     # utility
import nipype.pipeline.engine as pe          # pypeline engine
import os                                    # system functions


dataDir = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/data'
workingdir = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1output/workflows/dti'
subjects = ['SAD_018']

skeleton_thresh = 0.2

# bet options
frac = 0.34

def get_datasource():

    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
                                                   outfields=['dwi', 'bvec',
                                                              'bval']),
                         name='datasource')
    datasource.inputs.base_directory = os.path.abspath(dataDir)
    datasource.inputs.template = os.path.join(dataDir,'%s','dti','%s')
    datasource.inputs.template_args = dict(dwi=[['subject_id', 'diffusionseries.nii.gz']],
                                           bvec=[['subject_id', 'bvecs']],
                                           bval=[['subject_id', 'bvals']])
    return datasource
    

