#Imports ---------------------------------------------------------------------
import sys
from config import *
sys.path.append('..')

from nipype.utils.config import config
config.enable_debug_mode()

import nipype.interfaces.utility as util    # utility
import nipype.pipeline.engine as pe         # pypeline engine

from base import create_rest_prep
from utils import get_datasink, get_substitutions

# Preprocessing
# -------------------------------------------------------------

def prep_workflow(subjects):
    
    modelflow = pe.Workflow(name='preproc')

    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
                         name='subject_names')
    infosource.iterables = ('subject_id', subjects)

    # generate datagrabber
    dataflow = create_dataflow()
    modelflow.connect(infosource, 'subject_id', dataflow, 'subject_id')
    
    # generate preprocessing workflow
    preproc = create_rest_prep()
    
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

    # make a data sink

    sinkd = get_datasink(root_dir, fwhm)
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
                'stddev_file',
                'regressor_file']),
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
    modelflow.connect(preproc, 'outputspec.filter_file',
                      outputnode, 'regressor_file')

    modelflow.base_dir = os.path.join(root_dir,'work_dir')
    return modelflow

if __name__ == "__main__":
    preprocess = prep_workflow(subjects)
    if run_on_grid:
        preprocess.run(plugin='PBS',
                       plugin_args={'qsub_args': '-q many -l nodes=1:ppn=4'})
    else:
        preprocess.run()

