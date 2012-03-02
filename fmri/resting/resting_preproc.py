#Imports ---------------------------------------------------------------------
import sys
from config import *
sys.path.append('..')
import nipype.interfaces.fsl as fsl         # fsl
import nipype.interfaces.utility as util    # utility
import nipype.pipeline.engine as pe         # pypeline engine
import os
import numpy as np
import nipype.algorithms.rapidart as ra     # rapid artifact detection
import nipype.interfaces.io as nio          # input/output
import array
from utils import *
from base import create_prep
from nipype.algorithms.modelgen import SpecifyModel
from nipype.algorithms.misc import TSNR
from nibabel import load
from glob import glob
from nipype.workflows.smri.freesurfer.utils import create_getmask_flow
from nipype.interfaces.base import Bunch
from copy import deepcopy
from nipype.interfaces.nipy.preprocess import FmriRealign4d
from nipype.utils.config import config
config.enable_debug_mode()

# Resting state utility functions -------------------------------------------
def create_filter_matrix(motion_params, composite_norm, compcorr_components, art_outliers, selector):
    import numpy as np
    import os
    if not len(selector) == 4:
        print "selector is not the right size!"
        return None
    
    def try_import(fname):
        try:
            a = np.genfromtxt(fname)
            return a
        except:
            return np.array([])
            
    options = np.array([motion_params, composite_norm, compcorr_components, art_outliers])
    selector = np.array(selector)
    
    splitter = np.vectorize(lambda x: os.path.split(x)[1])
    filenames = ['%s' % item for item in splitter(options[selector])]
    filter_file = os.path.abspath("filter+%s+outliers.txt"%"+".join(filenames))
    
    z = None
    
    for i, opt in enumerate(options[:-1][selector[:-1]]): # concatenate all files except art_outliers    
        if i ==0:
            print opt
            z = try_import(opt)
            print z.shape
        else:
            a = try_import(opt)
            if len(a.shape)==1:
                a = np.array([a]).T
            print a.shape, z.shape
            z = np.hstack((z,a))
    
    if selector[-1]:
        #import outlier file
        outliers = try_import(art_outliers)
        if outliers.shape[0] == 0: # empty art file
            out = z
        elif outliers.shape ==(): # 1 outlier
            art = np.zeros((z.shape[0],1))
            art[np.int_(outliers)-1,0] = 1
            out = np.hstack((z,art))
        else: # >1 outlier
            art = np.zeros((z.shape[0],outliers.shape[0]))
            for j,t in enumerate(a):
                art[np.int_(t)-1,j] = 1
            out = np.hstack((z,art))
    else:
        out = z
        
    np.savetxt(filter_file,out)
    return filter_file


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
    compcor = preproc.get_node('compcorr')
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
    preproc.inputs.inputspec.subjid =                   subj
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

