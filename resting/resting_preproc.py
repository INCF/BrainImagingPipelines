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
            z = try_import(opt)
        else:
            a = try_import(opt)
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

def create_prep(name='preproc'):
    preproc = pe.Workflow(name=name)
    from nipype.workflows.smri.freesurfer.utils import create_getmask_flow
    from nipype.workflows.fmri.fsl.preprocess import create_susan_smooth
    
    compcor = create_compcorr()
    
    inputnode = pe.Node(interface=util.IdentityInterface(fields=['subjid',
                                                                 'func',
                                                                 'fwhm',
                                                                 'highpass',
                                                                 'num_noise_components']),
                        name='inputspec')
    inputnode_fwhm = pe.Node(interface=util.IdentityInterface(fields = ['fwhm']), name = 'fwhm_input')
    
    #add outliers and noise components
    addoutliers = pe.Node(util.Function(input_names=['motion_params','composite_norm',"compcorr_components","art_outliers","selector"],output_names=['filter_file'],function=create_filter_matrix),name='create_nuisance_filter')

    
    # convert BOLD images to float
    img2float = pe.MapNode(interface=fsl.ImageMaths(out_data_type='float',
                                                    op_string = '',
                                                    suffix='_dtype'),
                           iterfield=['in_file'],
                           name='img2float')
    
    # define the motion correction node
    motion_correct = pe.MapNode(interface=FmriRealign4d(),
                                name='realign',iterfield=['in_file']) 
    motion_correct.inputs.tr = TR
    motion_correct.inputs.interleaved = Interleaved
    motion_correct.inputs.slice_order = SliceOrder
    
    # construct motion plots
    plot_motion = pe.MapNode(interface=fsl.PlotMotionParams(in_source='fsl'),
                             name='plot_motion',
                             iterfield=['in_file'])

    # rapidArt for artifactual timepoint detection 
    ad = pe.Node(ra.ArtifactDetect(),
                 name='artifactdetect')

    # extract the mean volume if the first functional run
    meanfunc = pe.Node(interface=fsl.ImageMaths(op_string = '-Tmean',
                                                suffix='_mean'),
                       name='meanfunc')

    # generate a freesurfer workflow that will return the mask
    getmask = create_getmask_flow()


    # create a SUSAN smoothing workflow, and smooth each run with 
    # 75% of the median value for each run as the brightness 
    # threshold.
    smooth = create_susan_smooth(name="susan_smooth", separate_masks=False)

    # choose susan function
    
    choosesusan = pe.Node(util.Function(input_names = ['fwhm','motion_files','smoothed_files'], output_names = ['cor_smoothed_files'], function = choose_susan), name = 'select_smooth')

    # scale the median value of each run to 10,000
    meanscale = pe.MapNode(interface=fsl.ImageMaths(suffix='_gms'),
                           iterfield=['in_file',
                                      'op_string'],
                           name='scale_to_median')
                                        
    # determine the median value of the MASKED functional runs  
    medianval = pe.MapNode(interface=fsl.ImageStats(op_string='-k %s -p 50'),
                           iterfield = ['in_file'],
                           name='compute_median')

    # temporal highpass filtering
    highpass = pe.MapNode(interface=fsl.ImageMaths(suffix='_tempfilt'),
                          iterfield=['in_file'],
                          name='highpass')

    remove_noise = pe.Node(fsl.FilterRegressor(filter_all=True),
                       name='regress_nuisance')
                       
    bandpass_filter = pe.Node(fsl.TemporalFilter(),
                              name='bandpass_filter')

    # declare some node inputs...
    plot_motion.iterables = ('plot_type', ['rotations', 'translations'])
    ad.inputs.norm_threshold = norm_thresh
    ad.inputs.parameter_source = 'FSL'
    ad.inputs.zintensity_threshold = z_thresh
    ad.inputs.mask_type = 'file'
    ad.inputs.use_differences = [True, False]
    getmask.inputs.inputspec.subjects_dir = surf_dir
    getmask.inputs.inputspec.contrast_type = 't2'
    bandpass_filter.inputs.highpass_sigma = highpass_sigma
    bandpass_filter.inputs.lowpass_sigma = lowpass_sigma
    addoutliers.inputs.motion_params = None
    addoutliers.inputs.composite_norm = None
    addoutliers.inputs.selector = [False, False, True, True]
    
    
    #motion_correct.inputs.args = '-spline_final'

    # make connections...
    preproc.connect(inputnode,      'subjid',                                   getmask,        'inputspec.subject_id')
    preproc.connect(inputnode,      'func',                                     img2float,      'in_file')
    preproc.connect(img2float,      ('out_file',tolist),                        motion_correct, 'in_file')
    preproc.connect(motion_correct, 'par_file',                                 plot_motion,    'in_file')
    preproc.connect(motion_correct, ('out_file', pickfirst),                    meanfunc,       'in_file')
    preproc.connect(meanfunc,       'out_file',                                 getmask,        'inputspec.source_file')
    preproc.connect(inputnode,      'num_noise_components',                     compcor,        'inputspec.num_components')
    preproc.connect(motion_correct, 'out_file',                                 compcor,        'inputspec.realigned_file')
    preproc.connect(motion_correct, 'out_file',                                 compcor,        'inputspec.in_file')
    preproc.connect(motion_correct, 'out_file',                                 ad,             'realigned_files')
    preproc.connect(motion_correct, 'par_file',                                 ad,             'realignment_parameters')
    preproc.connect(getmask,        ('outputspec.mask_file',pickfirst),         ad,             'mask_file')
    preproc.connect(getmask,        ('outputspec.mask_file',pickfirst),         medianval,      'mask_file')
    preproc.connect(inputnode_fwhm, 'fwhm',                                     smooth,         'inputnode.fwhm')
    preproc.connect(bandpass_filter,'out_file',                                 smooth,         'inputnode.in_files')
    preproc.connect(getmask,        ('outputspec.mask_file',pickfirst),         smooth,         'inputnode.mask_file')
    preproc.connect(smooth,         'outputnode.smoothed_files',                choosesusan,    'smoothed_files')
    preproc.connect(motion_correct, 'out_file',                                 choosesusan,    'motion_files')
    preproc.connect(inputnode_fwhm, 'fwhm',                                     choosesusan,    'fwhm')
    preproc.connect(choosesusan,    'cor_smoothed_files',                       meanscale,      'in_file')
    preproc.connect(choosesusan,    'cor_smoothed_files',                       medianval,      'in_file')
    preproc.connect(medianval,      ('out_stat', getmeanscale),                 meanscale,      'op_string')
    preproc.connect(inputnode,      ('highpass', highpass_operand),             highpass,       'op_string')
    preproc.connect(meanscale,      'out_file',                                 highpass,       'in_file')
    preproc.connect(ad,             'outlier_files',                            addoutliers,    'art_outliers')
    preproc.connect(compcor,        ('outputspec.noise_components',pickfirst),  addoutliers,    'compcorr_components')
    preproc.connect(addoutliers,    'filter_file',                              remove_noise,   'design_file')
    preproc.connect(remove_noise,   'out_file',                                 bandpass_filter,'in_file')
    preproc.connect(compcor,        ('tsnr.detrended_file',pickfirst),          remove_noise,   'in_file')
    
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

    # make output connection
    preproc.connect(meanfunc,       'out_file',                         outputnode, 'reference')
    preproc.connect(motion_correct, 'par_file',                         outputnode, 'motion_parameters')
    preproc.connect(motion_correct, 'out_file',                         outputnode, 'realigned_files')
    preproc.connect(highpass,       'out_file',                         outputnode, 'highpassed_files')
    preproc.connect(meanfunc,       'out_file',                         outputnode, 'mean')
    preproc.connect(ad,             'norm_files',                       outputnode, 'combined_motion')
    preproc.connect(ad,             'outlier_files',                    outputnode, 'outlier_files')
    preproc.connect(compcor,        'compcor.noise_components',         outputnode, 'noise_components')
    preproc.connect(getmask,        ('outputspec.mask_file',pickfirst), outputnode, 'mask')
    preproc.connect(getmask,        'outputspec.reg_file',              outputnode, 'reg_file')
    preproc.connect(getmask,        'outputspec.reg_cost',              outputnode, 'reg_cost')
    preproc.connect(choosesusan,    'cor_smoothed_files',               outputnode, 'smoothed_files')
    preproc.connect(compcor,        'outputspec.tsnr_file',             outputnode, 'tsnr_file')
    preproc.connect(compcor,        'outputspec.stddev_file',           outputnode, 'stddev_file')
    
    preproc.write_graph(graph2use = 'orig')
    return preproc

def prep_workflow(subj):
    
    def getsubs(subject_id):
        subs = [('_subject_id_%s/'%subject_id,''),
                ('_plot_type_',''),
                ('_fwhm','fwhm'),
                ('_dtype_mcf_mask_mean','_mean'),
                ('_dtype_mcf_mask_smooth_mask_gms_tempfilt','_smoothed_preprocessed'),
                ('_dtype_mcf_mask_gms_tempfilt','_unsmoothed_preprocessed'),
                ('_dtype_mcf','_mcf')]
        
        for i in range(4):
            subs.append(('_plot_motion%d'%i, ''))
            subs.append(('_highpass%d/'%i, ''))
            subs.append(('_realign%d/'%i, ''))
            subs.append(('_meanfunc2%d/'%i, ''))
        return subs

    modelflow = pe.Workflow(name='preproc')
    
    # generate preprocessing workflow
    dataflow =                                          create_dataflow(subj)
    preproc =                                           create_prep()
    preproc.inputs.inputspec.fwhm =                     fwhm
    preproc.inputs.inputspec.highpass =                 hpcutoff/(2*2.5)
    preproc.inputs.inputspec.num_noise_components =     num_noise_components
    preproc.crash_dir =                                 crash_dir
    preproc.inputs.inputspec.subjid =                   subj
    preproc.get_node('fwhm_input').iterables =          ('fwhm',fwhm)

    # make a data sink
    sinkd = pe.Node(nio.DataSink(), name='sinkd')
    sinkd.inputs.base_directory = os.path.join(root_dir,'analyses','func')
    sinkd.inputs.container = subj
    sinkd.inputs.substitutions = getsubs(subj)
    sinkd.inputs.regexp_substitutions = [('mask/fwhm_%d/_threshold([0-9]*)/.*nii'%x,'mask/fwhm_%d/funcmask.nii'%x) for x in fwhm]
    sinkd.inputs.regexp_substitutions.append(('realigned/fwhm_([0-9])/_copy_geom([0-9]*)/','realigned/'))
    sinkd.inputs.regexp_substitutions.append(('motion/fwhm_([0-9])/','motion/'))
    sinkd.inputs.regexp_substitutions.append(('bbreg/fwhm_([0-9])/','bbreg/'))
    
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
    preprocess.run()

