#Imports ---------------------------------------------------------------------
import sys
from config import *
sys.path.append('..')

import nipype.interfaces.utility as util    # utility
import nipype.pipeline.engine as pe         # pypeline engine
import os

from base import create_rest_prep
from utils import get_datasink, get_substitutions

# Preprocessing
# -------------------------------------------------------------

def prep_workflow(subjects, fieldmap):
    
    modelflow = pe.Workflow(name='preproc')

    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
                         name='subject_names')
    infosource.iterables = ('subject_id', subjects)

    # generate datagrabber
    dataflow = create_dataflow()
    modelflow.connect(infosource, 'subject_id',
                      dataflow, 'subject_id')
    
    # generate preprocessing workflow
    preproc = create_rest_prep(fieldmap=fieldmap)
    
    # make a data sink
    sinkd = get_datasink(sink_dir, fwhm)
    
    if fieldmap:
        datasource_fieldmap = create_fieldmap_dataflow()
        preproc.inputs.inputspec.FM_Echo_spacing = echospacing
        preproc.inputs.inputspec.FM_TEdiff = TE_diff
        preproc.inputs.inputspec.FM_sigma = sigma
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
    
    # inputs
    preproc.inputs.fwhm_input.fwhm = fwhm
    preproc.inputs.inputspec.num_noise_components = num_noise_components
    preproc.crash_dir = crash_dir
    modelflow.connect(infosource, 'subject_id', preproc, 'inputspec.fssubject_id')
    preproc.inputs.inputspec.fssubject_dir = surf_dir
    preproc.get_node('fwhm_input').iterables = ('fwhm',fwhm)
    preproc.inputs.inputspec.ad_normthresh = norm_thresh
    preproc.inputs.inputspec.ad_zthresh = z_thresh
    preproc.inputs.inputspec.tr = TR
    preproc.inputs.inputspec.interleaved = Interleaved
    preproc.inputs.inputspec.sliceorder = SliceOrder
    preproc.inputs.inputspec.compcor_select = compcor_select
    preproc.inputs.inputspec.highpass_sigma = highpass_sigma
    preproc.inputs.inputspec.lowpass_sigma = lowpass_sigma
    preproc.inputs.inputspec.reg_params = reg_params

    
    modelflow.connect(infosource, 'subject_id', sinkd, 'container')
    modelflow.connect(infosource, ('subject_id', get_substitutions),
                      sinkd, 'substitutions')

    # make connections

    modelflow.connect(dataflow,'func',
                      preproc,'inputspec.func')
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
    modelflow.connect(preproc, 'outputspec.filter_file',
                      sinkd, 'preproc.regressors')
    modelflow.connect(preproc, 'outputspec.z_img', 
                      sinkd, 'preproc.z_image')
    
    modelflow.base_dir = os.path.join(root_dir,'work_dir')
    return modelflow

if __name__ == "__main__":
    preprocess = prep_workflow(subjects, fieldmap)
    realign = preprocess.get_node('preproc.realign')
    realign.inputs.loops = 2
    realign.inputs.speedup = 15
    realign.plugin_args = {'qsub_args': '-l nodes=1:ppn=3'}
    # add for regress nuisance
    if run_on_grid:
        preprocess.run(plugin='PBS', plugin_args = {'qsub_args': '-q many'})
    else:
        preprocess.run()

