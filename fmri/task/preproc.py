#Imports ---------------------------------------------------------------------
import sys
sys.path.insert(0,'..')
sys.path.insert(0,'../qa')
import nipype.interfaces.fsl as fsl         # fsl
import nipype.interfaces.utility as util    # utility
import nipype.pipeline.engine as pe         # pypeline engine
import os
import numpy as np
import nipype.algorithms.rapidart as ra     # rapid artifact detection
import nipype.interfaces.io as nio          # input/output
import array
from config import *
from base import create_prep
from utils import get_datasink, get_substitutions
from nipype.algorithms.modelgen import SpecifyModel
from nipype.algorithms.misc import TSNR
from nibabel import load
from glob import glob
from nipype.workflows.smri.freesurfer.utils import create_getmask_flow
from nipype.interfaces.base import Bunch
from copy import deepcopy
#from nipype.interfaces.nipy.preprocess import FmriRealign4d
#from nipype.interfaces.nipy.preprocess import FmriRealign4d
from QA_fmri import QA_workflow
from time import ctime
from utils import pickfirst, tolist
#from nipype.utils.config import NipypeConfig as config
#config.enable_debug_mode()

# Preprocessing
# -------------------------------------------------------------


def prep_workflow(subj):
    
    modelflow = pe.Workflow(name='preproc')
    
    # Get QA workflow
    
    QA = QA_workflow()
    
    
    # generate preprocessing workflow
    dataflow = create_dataflow(subj)
    dataflow.inputs.subject_id = subj
    preproc = create_prep()
    preproc.inputs.inputspec.fssubject_id = subj
    preproc.inputs.inputspec.fssubject_dir = surf_dir
    preproc.get_node('fwhm_input').iterables = ('fwhm',fwhm)
    preproc.inputs.inputspec.highpass = hpcutoff/(2*2.5)
    preproc.inputs.inputspec.num_noise_components = num_noise_components
    preproc.crash_dir = crash_dir
    preproc.inputs.inputspec.ad_normthresh = norm_thresh
    preproc.inputs.inputspec.ad_zthresh = z_thresh
    preproc.inputs.inputspec.tr = TR
    preproc.inputs.inputspec.interleaved = Interleaved
    preproc.inputs.inputspec.sliceorder = SliceOrder
    preproc.inputs.inputspec.compcor_select = compcor_select
    
    # For QA:
    
    def config_params(sub):
        runs = get_run_numbers(sub)
        cfg = [['Subject',sub],
               ['Runs',str(len(runs))],
               ['Run Numbers', str(runs)],
               ['Date',ctime()],
               ['Art Thresh Norm',str(norm_thresh)],
               ['Art Thresh Z',str(z_thresh)],
               ['FWHM',str(fwhm)],
               ['Film Threshold',str(film_threshold)],
               ['TR',str(TR)],
               ['Highpass Cutoff',str(hpcutoff)],
               ['Number of noise components',str(num_noise_components)]] 
        return cfg
    
    QA.inputs.inputspec.config_params = config_params(subj)
    QA.inputs.inputspec.subject_id = subj
    QA.inputs.inputspec.sd = surf_dir
    QA.inputs.inputspec.TR = TR
    
    # make a data sink

    sinkd = get_datasink(root_dir,fwhm)
    sinkd.inputs.container = subj
    sinkd.inputs.substitutions = get_substitutions(subj)

    # make connections
    
    modelflow.connect(preproc, 'outputspec.motion_plots', 
                      QA, 'inputspec.motion_plots')
    modelflow.connect(dataflow, ('func', tolist),
                      QA, 'inputspec.in_file')
    modelflow.connect(preproc, ('outputspec.outlier_files',pickfirst),
                      QA, 'inputspec.art_file')
    modelflow.connect(preproc, ('outputspec.combined_motion',pickfirst),
                      QA, 'inputspec.ADnorm')
    modelflow.connect(preproc, ('outputspec.reg_file',pickfirst),
                      QA, 'inputspec.reg_file')
    modelflow.connect(preproc, ('outputspec.tsnr_file',pickfirst),
                      QA, 'inputspec.tsnr')
    
    modelflow.connect(dataflow,'func',
                      preproc, 'inputspec.func')
    modelflow.connect(preproc, 'outputspec.reference',
                      sinkd, 'preproc.motion.reference')
    modelflow.connect(preproc, 'outputspec.motion_parameters',
                      sinkd, 'preproc.motion')
    modelflow.connect(preproc, 'outputspec.realigned_files',
                      sinkd, 'preproc.motion.realigned')
    modelflow.connect(preproc, 'outputspec.mean',
                      sinkd, 'preproc.meanfunc')
    modelflow.connect(preproc, 'plot_motion.out_file',
                      sinkd, 'preproc.motion.@plots')
    modelflow.connect(preproc, 'outputspec.mask',
                      sinkd, 'preproc.mask')
    modelflow.connect(preproc, 'outputspec.outlier_files',
                      sinkd, 'preproc.art')
    modelflow.connect(preproc, 'outputspec.combined_motion',
                      sinkd, 'preproc.art.@stats')
    modelflow.connect(preproc, 'outputspec.reg_file',
                      sinkd, 'preproc.bbreg')
    modelflow.connect(preproc, 'outputspec.reg_cost',
                      sinkd, 'preproc.bbreg.@reg_cost')
    modelflow.connect(preproc, 'outputspec.highpassed_files',
                      sinkd, 'preproc.highpass')
    modelflow.connect(preproc, 'outputspec.smoothed_files',
                      sinkd, 'preproc.smooth')
    modelflow.connect(preproc, 'outputspec.tsnr_file',
                      sinkd, 'preproc.tsnr')
    modelflow.connect(preproc, 'outputspec.stddev_file',
                      sinkd, 'preproc.tsnr.@stddev')
    modelflow.connect(preproc, 'outputspec.z_img', 
                      sinkd, 'preproc.z_image')

    # create output node
    outputnode = pe.Node(interface=util.IdentityInterface(
        fields=['reference',
                'motion_parameters',
                'realigned_files',
                'mask',
                'smoothed_files',
                'highpassed_files',
                'mean',
                'combined_motion',
                'outlier_files',
                'mask',
                'reg_cost',
                'reg_file',
                'noise_components',
                'tsnr_file',
                'stddev_file']),
                 name='outputspec')

    #Make more connections    

    modelflow.connect(preproc, 'outputspec.reference',
                      outputnode, 'reference')
    modelflow.connect(preproc, 'outputspec.motion_parameters',
                      outputnode, 'motion_parameters')
    modelflow.connect(preproc, 'outputspec.realigned_files',
                      outputnode, 'realigned_files')
    modelflow.connect(preproc, 'outputspec.smoothed_files',
                      outputnode, 'smoothed_files')
    modelflow.connect(preproc, 'outputspec.noise_components',
                      outputnode, 'noise_components')
    modelflow.connect(preproc, 'outputspec.mean',
                      outputnode, 'mean')
    modelflow.connect(preproc, 'outputspec.mask',
                      outputnode, 'mask')
    modelflow.connect(preproc, 'outputspec.outlier_files',
                      outputnode, 'outlier_files')
    modelflow.connect(preproc, 'outputspec.combined_motion',
                      outputnode, 'combined_motion')
    modelflow.connect(preproc, 'outputspec.reg_file',
                      outputnode, 'reg_file')
    modelflow.connect(preproc, 'outputspec.reg_cost',
                      outputnode, 'reg_cost')
    modelflow.connect(preproc, 'outputspec.highpassed_files',
                      outputnode, 'highpassed_files')
    modelflow.connect(preproc, 'outputspec.tsnr_file',
                      outputnode, 'tsnr_file')
    modelflow.connect(preproc, 'outputspec.stddev_file',
                      outputnode, 'stddev_file')

    modelflow.base_dir = os.path.join(root_dir,'work_dir',subj)
    return modelflow

if __name__ == "__main__":
    for sub in subjects:
        preprocess = prep_workflow(sub)
        if run_on_grid:
            preprocess.run(plugin='PBS')
        else:
            preprocess.run()
    
