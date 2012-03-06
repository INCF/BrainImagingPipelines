#Imports ---------------------------------------------------------------------
import sys
from config import *
sys.path.append('..')

from nipype.utils.config import config
config.enable_debug_mode()

import nipype.interfaces.fsl as fsl         # fsl
import nipype.interfaces.utility as util    # utility
import nipype.pipeline.engine as pe         # pypeline engine

#from utils import *
from base import *

# Resting state utility functions -------------------------------------------



# Preprocessing
# -------------------------------------------------------------

def create_rest_prep(name='preproc'):
    preproc = create_prep()
    
    #add outliers and noise components
    addoutliers = pe.Node(util.Function(input_names=['motion_params','composite_norm',"compcorr_components","art_outliers","selector"],output_names=['filter_file'],function=create_filter_matrix),name='create_nuisance_filter')
    
    # regress out noise
    remove_noise = pe.Node(fsl.FilterRegressor(filter_all=True),
                       name='regress_nuisance')
    
    # bandpass filter                   
    bandpass_filter = pe.Node(fsl.TemporalFilter(),
                              name='bandpass_filter')
    
    # Get old nodes
    inputnode = preproc.get_node('inputspec')
    meanscale = preproc.get_node('scale_median')
    ad = preproc.get_node('artifactdetect')
    compcor = preproc.get_node('CompCor')
    motion_correct = preproc.get_node('realign')
    smooth = preproc.get_node('smooth_with_susan')
    highpass = preproc.get_node('highpass')
    outputnode = preproc.get_node('outputspec')
    outputnode.interface._fields.append('filter_file')
    
    #disconnect old nodes
    preproc.disconnect(motion_correct, 'out_file', smooth, 'inputnode.in_files')
    preproc.disconnect(inputnode,          ('highpass', highpass_operand),     highpass,       'op_string')
    preproc.disconnect(meanscale,          'out_file',                         highpass,       'in_file')
    
    # remove nodes
    preproc.remove_nodes([highpass])
    
    # connect nodes
    preproc.connect(ad,             'outlier_files',                            addoutliers,    'art_outliers')
    preproc.connect(ad,             'norm_files',                               addoutliers,    'composite_norm')
    preproc.connect(compcor,        ('outputspec.noise_components',pickfirst),  addoutliers,    'compcorr_components')
    preproc.connect(motion_correct, ('par_file',pickfirst),                     addoutliers,    'motion_params')
    preproc.connect(addoutliers,    'filter_file',                              remove_noise,   'design_file')
    preproc.connect(remove_noise,   'out_file',                                 bandpass_filter,'in_file')
    preproc.connect(compcor,        ('tsnr.detrended_file',pickfirst),          remove_noise,   'in_file')
    preproc.connect(bandpass_filter,'out_file',                                 smooth,         'inputnode.in_files')
    preproc.connect(meanscale, 'out_file', outputnode, 'scaled_files')
    
    bandpass_filter.inputs.highpass_sigma = highpass_sigma
    bandpass_filter.inputs.lowpass_sigma = lowpass_sigma
    addoutliers.inputs.selector = reg_params
    
    # Need to add a fields to outputnode
    preproc.connect(addoutliers,    'filter_file',           outputnode, 'filter_file')
   
    preproc.write_graph(graph2use = 'orig')
    return preproc

def prep_workflow(subj):
    
    modelflow = pe.Workflow(name='preproc')
    
    # generate preprocessing workflow
    dataflow =                                          create_dataflow()
    dataflow.inputs.subject_id =                        subj
    preproc =                                           create_rest_prep()
    preproc.inputs.fwhm_input.fwhm =                     fwhm
    
    preproc.inputs.inputspec.num_noise_components =     num_noise_components
    preproc.crash_dir =                                 crash_dir
    preproc.inputs.inputspec.fssubject_id =                   subj
    preproc.inputs.inputspec.fssubject_dir = surf_dir
    preproc.get_node('fwhm_input').iterables =          ('fwhm',fwhm)

    # make a data sink
    
    sinkd = get_datasink(subj,root_dir,fwhm)
    
    # make connections
        
    modelflow.connect(dataflow,'func',preproc,'inputspec.func')
      
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
    modelflow.connect(preproc, 'outputspec.stddev_file',            sinkd,      'preproc.tsnr.@stddev')
    modelflow.connect(preproc, 'outputspec.filter_file',            sinkd,      'preproc.regressors')
    
    # tsnr and stdev and regression file
    
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
    modelflow.connect(preproc, 'outputspec.filter_file',            outputnode,      'regressor_file')
    
    modelflow.base_dir = os.path.join(root_dir,'work_dir',subj)
    return modelflow

if __name__ == "__main__":
    preprocess = prep_workflow(subjects[0])
    if run_on_grid:
        preprocess.run(plugin='PBS')
    else:
        preprocess.run()

