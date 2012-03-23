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
from base import create_prep, create_prep_fieldmap
from utils import get_datasink, get_substitutions
from nipype.algorithms.modelgen import SpecifyModel
from nipype.algorithms.misc import TSNR
from nibabel import load
from glob import glob
from nipype.workflows.smri.freesurfer.utils import create_getmask_flow
from nipype.interfaces.base import Bunch
from copy import deepcopy
from time import ctime
from utils import pickfirst, tolist
import argparse

# Preprocessing
# -------------------------------------------------------------


def prep_workflow(subjects,fieldmap):
    
    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
                         name='subject_names')
    infosource.iterables = ('subject_id', subjects)

    modelflow = pe.Workflow(name='preproc')
    
    # make a data sink
    sinkd = get_datasink(sink_dir,fwhm)
    
    # generate preprocessing workflow
    dataflow = c.create_dataflow()

    if fieldmap:
        preproc = create_prep_fieldmap()
        preproc.inputs.inputspec.FM_Echo_spacing = c.echospacing
        preproc.inputs.inputspec.FM_TEdiff = c.TE_diff
        preproc.inputs.inputspec.FM_sigma = c.sigma
        datasource_fieldmap = c.create_fieldmap_dataflow()
        modelflow.connect(infosource, 'subject_id',
                          datasource_fieldmap, 'subject_id')
        modelflow.connect(datasource_fieldmap,'mag',
                          preproc,'fieldmap_input.magnitude_file')
        modelflow.connect(datasource_fieldmap,'phase',
                          preproc,'fieldmap_input.phase_file')
        modelflow.connect(preproc, 'outputspec.FM_unwarped_mean',
                          sinkd, 'preproc.fieldmap.@unwarped_mean')
        modelflow.connect(preproc, 'outputspec.FM_unwarped_epi',
                          sinkd, 'preproc.fieldmap.@unwarped_epi')
    else:
        preproc = create_prep()
    
    preproc.inputs.inputspec.fssubject_dir = c.surf_dir
    preproc.get_node('fwhm_input').iterables = ('fwhm',c.fwhm)
    preproc.inputs.inputspec.highpass = c.hpcutoff/(2*c.TR)
    preproc.inputs.inputspec.num_noise_components = c.num_noise_components
    preproc.crash_dir = c.crash_dir
    preproc.inputs.inputspec.ad_normthresh = c.norm_thresh
    preproc.inputs.inputspec.ad_zthresh = c.z_thresh
    preproc.inputs.inputspec.tr = c.TR
    preproc.inputs.inputspec.interleaved = c.Interleaved
    preproc.inputs.inputspec.sliceorder = c.SliceOrder
    preproc.inputs.inputspec.compcor_select = c.compcor_select
    
    # make connections
    modelflow.connect(infosource, 'subject_id',
                      sinkd, 'container')
    modelflow.connect(infosource, ('subject_id', get_substitutions),
                      sinkd, 'substitutions')
    modelflow.connect(infosource, 'subject_id',
                      dataflow, 'subject_id')
    modelflow.connect(infosource, 'subject_id', 
                      preproc, 'inputspec.fssubject_id')
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
    modelflow.connect(preproc, 'outputspec.tsnr_detrended',
                      sinkd, 'preproc.tsnr.@detrended')
    modelflow.connect(preproc, 'outputspec.stddev_file',
                      sinkd, 'preproc.tsnr.@stddev')
    modelflow.connect(preproc, 'outputspec.z_img', 
                      sinkd, 'preproc.z_image')
    modelflow.connect(preproc, 'outputspec.noise_components',
                      sinkd, 'preproc.noise_components')
    

    modelflow.base_dir = os.path.join(c.working_dir,'work_dir')
    return modelflow

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="example: \
                        run resting_preproc.py -c config.py")
    parser.add_argument('-c','--config',
                        dest='config',
                        required=True,
                        help='location of config file'
                        )
    args = parser.parse_args()
    path, fname = os.path.split(os.path.realpath(args.config))
    sys.path.append(path)
    c = __import__(fname.split('.')[0])

    preprocess = prep_workflow(c.subjects, c.fieldmap)
    realign = preprocess.get_node('preproc.realign')
    realign.plugin_args = {'qsub_args': '-l nodes=1:ppn=3'}
    realign.inputs.loops = 2
    realign.inputs.speedup = 15
    cc = preprocess.get_node('preproc.CompCor')
    cc.plugin_args = {'qsub_args': '-l nodes=1:ppn=3'}
    if c.run_on_grid:
        preprocess.run(plugin='PBS',plugin_args = c.plugin_args)
    else:
        preprocess.run()
    
