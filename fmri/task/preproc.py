#Imports ---------------------------------------------------------------------
import sys
sys.path.insert(0,'..')
import nipype.interfaces.fsl as fsl         # fsl
import nipype.interfaces.utility as util    # utility
import nipype.pipeline.engine as pe         # pypeline engine
import os
import numpy as np
import nipype.algorithms.rapidart as ra     # rapid artifact detection
import nipype.interfaces.io as nio          # input/output
import array
from config import *
from utils import *
from base import create_prep
from nipype.algorithms.modelgen import SpecifyModel
from nipype.algorithms.misc import TSNR
from nibabel import load
from glob import glob
from nipype.workflows.smri.freesurfer.utils import create_getmask_flow
from nipype.interfaces.base import Bunch
from copy import deepcopy
#from nipype.interfaces.nipy.preprocess import FmriRealign4d
from nipype.interfaces.nipy.preprocess import FmriRealign4d
from nipype.utils.config import config
config.enable_debug_mode()

# Preprocessing
# -------------------------------------------------------------


def prep_workflow(subj):
    
    modelflow = pe.Workflow(name='preproc')
    
    # generate preprocessing workflow
    dataflow =                                          create_dataflow(subj)
    dataflow.inputs.subject_id = subj
    preproc =                                           create_prep()
    preproc.get_node('fwhm_input').iterables =          ('fwhm',fwhm)
    preproc.inputs.inputspec.highpass =                 hpcutoff/(2*2.5)
    preproc.inputs.inputspec.num_noise_components =     num_noise_components
    preproc.crash_dir =                                 crash_dir
    preproc.inputs.inputspec.subjid =                   subj
    

    # make a data sink
    
    sinkd = get_datasink(subj,root_dir,fwhm)
    
    # make connections

    modelflow.connect(dataflow,'func',                              preproc,    'inputspec.func')
    modelflow.connect(preproc, 'outputspec.reference',              sinkd,      'preproc.motion.reference')
    modelflow.connect(preproc, 'outputspec.motion_parameters',      sinkd,      'preproc.motion')
    modelflow.connect(preproc, 'outputspec.realigned_files',        sinkd,      'preproc.motion.realigned')
    modelflow.connect(preproc, 'outputspec.mean',                   sinkd,      'preproc.meanfunc')
    modelflow.connect(preproc, 'plot_motion.out_file',              sinkd,      'preproc.motion.@plots')
    modelflow.connect(preproc, 'outputspec.mask',                   sinkd,      'preproc.mask')
    modelflow.connect(preproc, 'outputspec.outlier_files',          sinkd,      'preproc.art')
    modelflow.connect(preproc, 'outputspec.combined_motion',        sinkd,      'preproc.art.@stats')
    modelflow.connect(preproc, 'outputspec.reg_file',               sinkd,      'preproc.bbreg')
    modelflow.connect(preproc, 'outputspec.reg_cost',               sinkd,      'preproc.bbreg.@reg_cost')
    modelflow.connect(preproc, 'outputspec.highpassed_files',       sinkd,      'preproc.highpass')
    modelflow.connect(preproc, 'outputspec.smoothed_files',         sinkd,      'preproc.smooth')
    modelflow.connect(preproc, 'outputspec.tsnr_file',              sinkd,      'preproc.tsnr')
    modelflow.connect(preproc, 'outputspec.stddev_file',            sinkd,      'preproc.tsnr@stddev')
    
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
    
    modelflow.connect(preproc, 'outputspec.reference',              outputnode,      'reference')
    modelflow.connect(preproc, 'outputspec.motion_parameters',      outputnode,      'motion_parameters')
    modelflow.connect(preproc, 'outputspec.realigned_files',        outputnode,      'realigned_files')
    modelflow.connect(preproc, 'outputspec.smoothed_files',         outputnode,      'smoothed_files')
    modelflow.connect(preproc, 'outputspec.noise_components',       outputnode,      'noise_components')
    modelflow.connect(preproc, 'outputspec.mean',                   outputnode,      'mean')
    modelflow.connect(preproc, 'outputspec.mask',                   outputnode,      'mask')
    modelflow.connect(preproc, 'outputspec.outlier_files',          outputnode,      'outlier_files')
    modelflow.connect(preproc, 'outputspec.combined_motion',        outputnode,      'combined_motion')
    modelflow.connect(preproc, 'outputspec.reg_file',               outputnode,      'reg_file')
    modelflow.connect(preproc, 'outputspec.reg_cost',               outputnode,      'reg_cost')
    modelflow.connect(preproc, 'outputspec.highpassed_files',       outputnode,      'highpassed_files')
    modelflow.connect(preproc, 'outputspec.tsnr_file',              outputnode,      'tsnr_file')
    modelflow.connect(preproc, 'outputspec.stddev_file',            outputnode,      'stddev_file')
    
    
    modelflow.base_dir = os.path.join(root_dir,'work_dir',subj)
    return modelflow

if __name__ == "__main__":
    preprocess = prep_workflow(subjects[0])
    if run_on_grid:
        preprocess.run(plugin='PBS')
    else:
        preprocess.run()
    
