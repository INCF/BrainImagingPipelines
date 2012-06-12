import nipype.interfaces.fsl as fsl         # fsl
import nipype.algorithms.rapidart as ra     # rapid artifact detection
from nipype.interfaces.fsl.utils import EPIDeWarp
from nipype.workflows.smri.freesurfer.utils import create_getmask_flow
from .modular_nodes import create_mod_smooth, mod_realign, mod_filter, mod_regressor
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util

from utils import (create_compcorr, choose_susan, art_mean_workflow, z_image,
                   getmeanscale, highpass_operand, pickfirst, whiten)


def create_filter_matrix(motion_params, composite_norm,
                         compcorr_components, art_outliers, selector):
    """Combine nuisance regressor components into a single file

    Parameters
    ----------
    motion_params : parameter file output from realignment
    composite_norm : composite norm file from artifact detection
    compcorr_components : components from compcor
    art_outliers : outlier timepoints from artifact detection
    selector : a boolean list corresponding to the files to concatenate together\
               [motion_params, composite_norm, compcorr_components, art_outliers,\
                motion derivatives]
                
    Returns
    -------
    filter_file : a file with selected parameters concatenated
    """
    import numpy as np
    import os
    if not len(selector) == 5:
        print "selector is not the right size!"
        return None

    def try_import(fname):
        try:
            a = np.genfromtxt(fname)
            return a
        except:
            return np.array([])

    options = np.array([motion_params, composite_norm,
                        compcorr_components, art_outliers])
    selector = np.array(selector)
    fieldnames = ['motion', 'comp_norm', 'compcor', 'art', 'dmotion']

    splitter = np.vectorize(lambda x: os.path.split(x)[1])
    filenames = [fieldnames[i] for i, val in enumerate(selector) if val]
    filter_file = os.path.abspath("filter_%s.txt" % "_".join(filenames))

    z = None

    for i, opt in enumerate(options[:-1][selector[:-2]]):
    # concatenate all files except art_outliers and motion_derivs
        if i == 0:
            z = try_import(opt)

        else:
            a = try_import(opt)
            if len(a.shape) == 1:
                a = np.array([a]).T
            z = np.hstack((z, a))

    if selector[-2]:
        #import outlier file
        outliers = try_import(art_outliers)
        if outliers.shape == ():  # 1 outlier
            art = np.zeros((z.shape[0], 1))
            art[np.int_(outliers), 0] = 1 #  art outputs 0 based indices
            out = np.hstack((z, art))
            
        elif outliers.shape[0] == 0:  # empty art file
            out = z
                
        else:  # >1 outlier
            art = np.zeros((z.shape[0], outliers.shape[0]))
            for j, t in enumerate(outliers):
                art[np.int_(t), j] = 1 #  art outputs 0 based indices
            out = np.hstack((z, art))
    else:
        out = z

    if selector[-1]:  # this is the motion_derivs bool
            a = try_import(motion_params)
            temp = np.zeros(a.shape)
            temp[1:, :] = np.diff(a, axis=0)
            out = np.hstack((out, temp))
    if out is not None:
        np.savetxt(filter_file, out)
        return filter_file
    else:
        filter_file = os.path.abspath("empty_file.txt")
        a = open(filter_file,'w')
        a.close()
        return filter_file


def create_prep(name='preproc'):
    """ Base preprocessing workflow for task and resting state fMRI
    
    Parameters
    ----------
    name : name of workflow. Default = 'preproc'
    
    Inputs
    ------
    inputspec.fssubject_id : 
    inputspec.fssubject_dir :
    inputspec.func :
    inputspec.highpass :
    inputspec.num_noise_components :
    inputspec.ad_normthresh :
    inputspec.ad_zthresh :
    inputspec.tr :
    inputspec.interleaved :
    inputspec.sliceorder :
    inputspec.compcor_select :
    inputspec.highpass_sigma :
    inputspec.lowpass_sigma :
    inputspec.reg_params :
    inputspec.FM_TEdiff :
    inputspec.FM_Echo_spacing :
    inputspec.FM_sigma :
    
    Outputs
    -------
    outputspec.reference : 
    outputspec.motion_parameters : 
    outputspec.realigned_files :
    outputspec.mask :
    outputspec.smoothed_files :
    outputspec.highpassed_files :
    outputspec.mean :
    outputspec.combined_motion :
    outputspec.outlier_files :
    outputspec.mask :
    outputspec.reg_cost :
    outputspec.reg_file :
    outputspec.noise_components :
    outputspec.tsnr_file :
    outputspec.stddev_file :
    outputspec.filter_file :
    outputspec.scaled_files :
    outputspec.z_img :
    outputspec.motion_plots :
    outputspec.FM_unwarped_mean :
    outputspec.FM_unwarped_epi :
    
    Returns
    -------
    workflow : preprocessing workflow
    """
    preproc = pe.Workflow(name=name)

    # Compcorr node
    compcor = create_compcorr()

    # Input node
    inputnode = pe.Node(util.IdentityInterface(fields=['fssubject_id',
                                                      'fssubject_dir',
                                                      'func',
                                                      'highpass',
                                                      'num_noise_components',
                                                      'ad_normthresh',
                                                      'ad_zthresh',
                                                      'tr',
                                                      'do_slicetime',
                                                      'sliceorder',
                                                      'compcor_select',
                                                      'highpass_freq',
                                                      'lowpass_freq',
                                                      'reg_params',
                                                      'FM_TEdiff',
                                                      'FM_Echo_spacing',
                                                      'FM_sigma',
                                                      'motion_correct_node',
                                                      'smooth_type',
                                                      'surface_fwhm',
                                                      'filter_type',
                                                      'timepoints_to_remove',
                                                      'do_whitening',
                                                      'regress_before_PCA',
                                                      'nipy_realign_parameters']),
                        name='inputspec')

    # Separate input node for FWHM
    inputnode_fwhm = pe.Node(util.IdentityInterface(fields=['fwhm']),
                             name='fwhm_input')

    # strip ids
    strip_rois = pe.MapNode(fsl.ExtractROI(),name='extractroi',iterfield='in_file')
    strip_rois.inputs.t_size = -1
    preproc.connect(inputnode,'timepoints_to_remove',strip_rois,'t_min')

    # convert BOLD images to float
    img2float = pe.MapNode(interface=fsl.ImageMaths(out_data_type='float',
                                                    op_string='',
                                                    suffix='_dtype'),
                           iterfield=['in_file'],
                           name='img2float')

    # define the motion correction node
    #motion_correct = pe.Node(interface=FmriRealign4d(),
    #                            name='realign')

    motion_correct = pe.Node(util.Function(input_names=['node','in_file','tr',
                                                        'do_slicetime','sliceorder',"nipy_dict"],
        output_names=['out_file','par_file'],
        function=mod_realign),
        name="mod_realign")

    preproc.connect(inputnode,'motion_correct_node',
                    motion_correct, 'node')

    # construct motion plots
    #plot_motion = pe.MapNode(interface=fsl.PlotMotionParams(in_source='fsl'),
    #                         name='plot_motion',
    #                         iterfield=['in_file'])

    # rapidArt for artifactual timepoint detection
    ad = pe.Node(ra.ArtifactDetect(),
                 name='artifactdetect')

    # extract the mean volume if the first functional run
    meanfunc = art_mean_workflow()

    # generate a freesurfer workflow that will return the mask
    getmask = create_getmask_flow()

    # create a SUSAN smoothing workflow, and smooth each run with
    # 75% of the median value for each run as the brightness
    # threshold.
    smooth = create_mod_smooth(name="modular_smooth",
                                 separate_masks=False)
    preproc.connect(inputnode,'smooth_type', smooth,'inputnode.smooth_type')
    # choose susan function
    """
    The following node selects smooth or unsmoothed data
    depending on the fwhm. This is because SUSAN defaults
    to smoothing the data with about the voxel size of
    the input data if the fwhm parameter is less than 1/3 of
    the voxel size.
    """
    choosesusan = pe.Node(util.Function(input_names=['fwhm',
                                                       'motion_files',
                                                       'smoothed_files'],
                                        output_names=['cor_smoothed_files'],
                                        function=choose_susan),
                          name='select_smooth')

    # scale the median value of each run to 10,000
    meanscale = pe.MapNode(interface=fsl.ImageMaths(suffix='_gms'),
                           iterfield=['in_file',
                                      'op_string'],
                           name='scale_median')

    # determine the median value of the MASKED functional runs
    medianval = pe.MapNode(interface=fsl.ImageStats(op_string='-k %s -p 50'),
                           iterfield=['in_file'],
                           name='compute_median_val')

    # temporal highpass filtering
    highpass = pe.MapNode(interface=fsl.ImageMaths(suffix='_tempfilt'),
                          iterfield=['in_file'],
                          name='highpass')

    # Calculate the z-score of output
    zscore = pe.MapNode(interface=util.Function(input_names=['image','outliers'],
                                             output_names=['z_img'],
                                             function=z_image),
                        name='z_score',
                        iterfield=['image','outliers'])

    # declare some node inputs...
    #plot_motion.iterables = ('plot_type', ['rotations', 'translations'])

    ad.inputs.parameter_source = 'FSL'
    meanfunc.inputs.inputspec.parameter_source = 'FSL'
    ad.inputs.mask_type = 'file'
    ad.inputs.use_differences = [True, False]
    getmask.inputs.inputspec.contrast_type = 't2'
    getmask.inputs.register.out_fsl_file = True
    fssource = getmask.get_node('fssource')

    # make connections...
    preproc.connect(inputnode, 'fssubject_id',
                    getmask, 'inputspec.subject_id')
    preproc.connect(inputnode, 'ad_normthresh',
                    ad, 'norm_threshold')
    preproc.connect(inputnode, 'ad_zthresh',
                    ad, 'zintensity_threshold')
    preproc.connect(inputnode, 'tr',
                    motion_correct, 'tr')
    preproc.connect(inputnode, 'nipy_realign_parameters',
        motion_correct, 'nipy_dict')
    preproc.connect(inputnode, 'do_slicetime',
                    motion_correct, 'do_slicetime')
    preproc.connect(inputnode, 'sliceorder',
                    motion_correct, 'sliceorder')
    preproc.connect(inputnode, 'compcor_select',
                    compcor, 'inputspec.selector')
    preproc.connect(inputnode, 'fssubject_dir',
                    getmask, 'inputspec.subjects_dir')

    #preproc.connect(inputnode, 'func',
    #                img2float, 'in_file')
    preproc.connect(inputnode, 'func', strip_rois, 'in_file')
    preproc.connect(strip_rois, 'roi_file', img2float, 'in_file')

    preproc.connect(img2float, 'out_file',
                    motion_correct, 'in_file')
    #preproc.connect(motion_correct, 'par_file',
    #                plot_motion, 'in_file')
    preproc.connect(motion_correct, 'out_file', 
                    meanfunc, 'inputspec.realigned_files')
    preproc.connect(motion_correct, 'par_file',
                    meanfunc, 'inputspec.realignment_parameters')
    preproc.connect(meanfunc, 'outputspec.mean_image',
                    getmask, 'inputspec.source_file')
    preproc.connect(inputnode, 'num_noise_components',
                    compcor, 'inputspec.num_components')
    preproc.connect(inputnode, 'regress_before_PCA',
                    compcor, 'inputspec.regress_before_PCA')
    preproc.connect(motion_correct, 'out_file',
                    compcor, 'inputspec.realigned_file')
    preproc.connect(meanfunc, 'outputspec.mean_image',
                    compcor, 'inputspec.mean_file')
    preproc.connect(fssource, 'aseg',
                    compcor, 'inputspec.fsaseg_file')
    preproc.connect(getmask, ('outputspec.reg_file', pickfirst),
                    compcor, 'inputspec.reg_file')
    preproc.connect(ad, 'outlier_files',
                    compcor, 'inputspec.outlier_files')
    preproc.connect(motion_correct, 'par_file',
                    compcor, 'inputspec.realignment_parameters')
    preproc.connect(motion_correct, 'out_file',
                    ad, 'realigned_files')
    preproc.connect(motion_correct, 'par_file',
                    ad, 'realignment_parameters')
    preproc.connect(getmask, ('outputspec.mask_file', pickfirst),
                    ad, 'mask_file')
    preproc.connect(getmask, ('outputspec.mask_file', pickfirst),
                    medianval, 'mask_file')
    preproc.connect(inputnode_fwhm, 'fwhm',
                    smooth, 'inputnode.fwhm')
    preproc.connect(motion_correct, 'out_file',
                    smooth, 'inputnode.in_files')
    preproc.connect(getmask, ('outputspec.mask_file',pickfirst),
                    smooth, 'inputnode.mask_file')
    preproc.connect(getmask, ('outputspec.reg_file', pickfirst),
                    smooth, 'inputnode.reg_file')
    preproc.connect(inputnode,'surface_fwhm',
                    smooth, 'inputnode.surface_fwhm')
    preproc.connect(inputnode, 'fssubject_dir',
                    smooth, 'inputnode.surf_dir')
    preproc.connect(smooth, 'outputnode.smoothed_files',
                    choosesusan, 'smoothed_files')
    preproc.connect(motion_correct, 'out_file',
                    choosesusan, 'motion_files')
    preproc.connect(inputnode_fwhm, 'fwhm',
                    choosesusan, 'fwhm')
    preproc.connect(choosesusan, 'cor_smoothed_files',
                    meanscale, 'in_file')
    preproc.connect(choosesusan, 'cor_smoothed_files',
                    medianval, 'in_file')
    preproc.connect(medianval, ('out_stat', getmeanscale),
                    meanscale, 'op_string')
    preproc.connect(inputnode, ('highpass', highpass_operand),
                    highpass, 'op_string')
    preproc.connect(meanscale, 'out_file',
                    highpass, 'in_file')
    preproc.connect(highpass, 'out_file',
                    zscore, 'image')
    preproc.connect(ad, 'outlier_files',
                    zscore, 'outliers')

    # create output node
    outputnode = pe.Node(interface=util.IdentityInterface(
        fields=['mean',
                'motion_parameters',
                'realigned_files',
                'smoothed_files',
                'highpassed_files',
                'combined_motion',
                'outlier_files',
                'outlier_stat_files',
                'mask',
                'reg_cost',
                'reg_file',
                'reg_fsl_file',
                'noise_components',
                'tsnr_file',
                'stddev_file',
                'tsnr_detrended',
                'filter_file',
                'scaled_files',
                'z_img',
                'motion_plots',
                'FM_unwarped_epi',
                'FM_unwarped_mean',
                'vsm_file',
                'bandpassed_file',
                'intensity_files',
                'noise_mask',
                'csf_mask']),
                        name='outputspec')

    # make output connection
    preproc.connect(meanfunc, 'outputspec.mean_image',
                    outputnode, 'mean')
    preproc.connect(motion_correct, 'par_file',
                    outputnode, 'motion_parameters')
    preproc.connect(motion_correct, 'out_file',
                    outputnode, 'realigned_files')
    preproc.connect(highpass, 'out_file',
                    outputnode, 'highpassed_files')
    preproc.connect(ad, 'norm_files',
                    outputnode, 'combined_motion')
    preproc.connect(ad, 'outlier_files',
                    outputnode, 'outlier_files')
    preproc.connect(ad, 'intensity_files',
                    outputnode, 'intensity_files')
    preproc.connect(ad, 'statistic_files',
                    outputnode, 'outlier_stat_files')
    preproc.connect(compcor, 'outputspec.noise_components',
                    outputnode, 'noise_components')
    preproc.connect(compcor, 'outputspec.noise_mask',
                    outputnode, 'noise_mask')
    preproc.connect(compcor, 'outputspec.csf_mask',
                    outputnode, 'csf_mask')
    preproc.connect(getmask, 'outputspec.mask_file',
                    outputnode, 'mask')
    preproc.connect(getmask, 'register.out_fsl_file',
                    outputnode, 'reg_fsl_file')                
    preproc.connect(getmask, 'outputspec.reg_file',
                    outputnode, 'reg_file')
    preproc.connect(getmask, 'outputspec.reg_cost',
                    outputnode, 'reg_cost')
    preproc.connect(choosesusan, 'cor_smoothed_files',
                    outputnode, 'smoothed_files')
    preproc.connect(compcor, 'outputspec.tsnr_file',
                    outputnode, 'tsnr_file')
    preproc.connect(compcor, 'outputspec.stddev_file',
                    outputnode, 'stddev_file')
    preproc.connect(compcor, 'outputspec.tsnr_detrended',
                    outputnode, 'tsnr_detrended')
    preproc.connect(zscore,'z_img',
                    outputnode,'z_img')
    #preproc.connect(plot_motion,'out_file',
    #                outputnode,'motion_plots')

                    

    return preproc


def create_prep_fieldmap(name='preproc'):
    """Rewiring of base fMRI workflow, adding fieldmap distortion correction
    """
    preproc = create_prep()
    
    inputnode = pe.Node(util.IdentityInterface(fields=['phase_file',
                                                       'magnitude_file']),
                           name="fieldmap_input")
    
    # Need to send output of mean image and realign to fieldmap correction workflow
    # Fieldmap correction workflow: takes mean image and realigns to fieldmaps, then unwarps
    # mean and epi. (Coregistration occurs in the EpiDeWarp.fsl script
    
    fieldmap = pe.Node(interface=EPIDeWarp(), name='fieldmap_unwarp')
    dewarper = pe.MapNode(interface=fsl.FUGUE(),iterfield=['in_file'],name='dewarper')
    # Get old nodes
    inputspec = preproc.get_node('inputspec')
    outputspec = preproc.get_node('outputspec')
    ad = preproc.get_node('artifactdetect')
    compcor = preproc.get_node('CompCor')
    motion_correct = preproc.get_node('mod_realign')
    smooth = preproc.get_node('modular_smooth')
    choosesusan = preproc.get_node('select_smooth')
    meanfunc = preproc.get_node('take_mean_art')
    getmask = preproc.get_node('getmask')

    # Disconnect old nodes
    preproc.disconnect(motion_correct, 'out_file',
                    compcor, 'inputspec.realigned_file')
    preproc.disconnect(motion_correct, 'out_file',
                    ad, 'realigned_files')
    preproc.disconnect(motion_correct, 'out_file',
                    smooth, 'inputnode.in_files') 
    preproc.disconnect(motion_correct, 'out_file',
                    choosesusan, 'motion_files')
    preproc.disconnect(meanfunc, 'outputspec.mean_image',
                    getmask, 'inputspec.source_file')
    preproc.disconnect(meanfunc, 'outputspec.mean_image',
                    compcor, 'inputspec.mean_file')
                    
    # Connect nodes
    preproc.connect(inputspec,'FM_TEdiff',
                    fieldmap, 'tediff')
    preproc.connect(inputspec,'FM_Echo_spacing',
                    fieldmap,'esp')
    preproc.connect(inputspec,'FM_sigma',
                    fieldmap, 'sigma')
    preproc.connect(motion_correct, 'out_file',
                    dewarper, 'in_file')
    preproc.connect(fieldmap, 'exf_mask',
                    dewarper, 'mask_file')
    preproc.connect(fieldmap, 'vsm_file',
                    dewarper, 'shift_in_file')
    preproc.connect(meanfunc, 'outputspec.mean_image',
                    fieldmap, 'exf_file')
    preproc.connect(inputnode, 'phase_file',
                    fieldmap, 'dph_file')
    preproc.connect(inputnode, 'magnitude_file',
                    fieldmap, 'mag_file')
    preproc.connect(fieldmap, 'exfdw',
                    getmask, 'inputspec.source_file')
    preproc.connect(dewarper, 'unwarped_file',
                    compcor, 'inputspec.realigned_file')
    preproc.connect(dewarper, 'unwarped_file',
                    ad, 'realigned_files')
    preproc.connect(dewarper, 'unwarped_file',
                    smooth, 'inputnode.in_files')
    preproc.connect(dewarper, 'unwarped_file',
                    choosesusan, 'motion_files')
    preproc.connect(fieldmap, 'exfdw',
                    compcor, 'inputspec.mean_file')
    preproc.connect(fieldmap, 'vsm_file',
                    outputspec, 'vsm_file')
    preproc.connect(fieldmap, 'exfdw',
                    outputspec, 'FM_unwarped_mean')
    preproc.connect(dewarper, 'unwarped_file',
                    outputspec, 'FM_unwarped_epi')
    return preproc
    
                    
                    
def create_rest_prep(name='preproc',fieldmap=False):
    """Rewiring of base fMRI workflow to add resting state preprocessing
    
    components.
    
    Parameters
    ----------
    name : name of workflow. Default = 'preproc'
    
    Inputs
    ------
    inputspec.fssubject_id : 
    inputspec.fssubject_dir :
    inputspec.func :
    inputspec.highpass :
    inputspec.num_noise_components :
    inputspec.ad_normthresh :
    inputspec.ad_zthresh :
    inputspec.tr :
    inputspec.interleaved :
    inputspec.sliceorder :
    inputspec.compcor_select :
    inputspec.highpass_sigma :
    inputspec.lowpass_sigma :
    inputspec.reg_params :
    
    Outputs
    -------
    outputspec.reference : 
    outputspec.motion_parameters : 
    outputspec.realigned_files :
    outputspec.mask :
    outputspec.smoothed_files :
    outputspec.highpassed_files :
    outputspec.mean :
    outputspec.combined_motion :
    outputspec.outlier_files :
    outputspec.mask :
    outputspec.reg_cost :
    outputspec.reg_file :
    outputspec.noise_components :
    outputspec.tsnr_file :
    outputspec.stddev_file :
    outputspec.filter_file :
    outputspec.scaled_files :
    outputspec.z_img :
    
    Returns
    -------
    workflow : resting state preprocessing workflow
    """
    if fieldmap:
        preproc = create_prep_fieldmap()
    else:
        preproc = create_prep()

    #add outliers and noise components
    addoutliers = pe.MapNode(util.Function(input_names=['motion_params',
                                                     'composite_norm',
                                                     "compcorr_components",
                                                     "art_outliers",
                                                     "selector"],
                                        output_names=['filter_file'],
                                        function=create_filter_matrix),
                          name='create_nuisance_filter',
                          iterfield=['motion_params',
                                       'composite_norm',
                                       'compcorr_components',
                                       'art_outliers'])

    # regress out noise
    remove_noise = pe.MapNode(util.Function(input_names=["in_file","design_file","mask"],
        output_names=["out_file"],function=mod_regressor),
        name='regress_nuisance',iterfield=["in_file","design_file"])

    #pe.MapNode(fsl.FilterRegressor(filter_all=True),
                   #    name='regress_nuisance',
                   #    iterfield=['design_file','in_file'])

    # bandpass filter
    #bandpass_filter = pe.MapNode(fsl.TemporalFilter(),
    #                          name='bandpass_filter',
    #                          iterfield=['in_file'])

    bandpass_filter = pe.MapNode(util.Function(input_names=['in_file',
                                                            'algorithm',
                                                            'lowpass_freq',
                                                            'highpass_freq',
                                                            'tr'],
                                output_names=['out_file'],
                                function=mod_filter),
                      name='bandpass_filter',iterfield=['in_file'])

    whitening = pe.MapNode(util.Function(input_names=['in_file',
                                                      "do_whitening"],
                                         output_names=["out_file"],
                                         function=whiten),
        name="whitening",iterfield=["in_file"])

    # Get old nodes
    inputnode = preproc.get_node('inputspec')
    meanscale = preproc.get_node('scale_median')
    medianval = preproc.get_node('compute_median_val')
    ad = preproc.get_node('artifactdetect')
    compcor = preproc.get_node('CompCor')
    motion_correct = preproc.get_node('mod_realign')
    smooth = preproc.get_node('modular_smooth')
    highpass = preproc.get_node('highpass')
    outputnode = preproc.get_node('outputspec')
    choosesusan = preproc.get_node('select_smooth')
    getmask = preproc.get_node('getmask')
    zscore = preproc.get_node('z_score')

    #disconnect old nodes
    preproc.disconnect(motion_correct, 'out_file',
                       smooth, 'inputnode.in_files')
    preproc.disconnect(motion_correct, 'out_file',
                       choosesusan, 'motion_files')
    preproc.disconnect(choosesusan, 'cor_smoothed_files',
                       medianval, 'in_file')
    preproc.disconnect(highpass, 'out_file',
                       zscore, 'image')

    if fieldmap:
        fieldmap = preproc.get_node('dewarper')
        preproc.disconnect(fieldmap, 'unwarped_file', 
                           smooth, 'inputnode.in_files')
        preproc.disconnect(fieldmap, 'unwarped_file',
                           choosesusan, 'motion_files')
    # remove nodes
    preproc.remove_nodes([highpass])

    # connect nodes
    preproc.connect(inputnode,'do_whitening',
                    whitening, "do_whitening")
    preproc.connect(inputnode,'tr',
        bandpass_filter,'tr')
    preproc.connect(inputnode,'filter_type',
        bandpass_filter,'algorithm')
    preproc.connect(ad, 'outlier_files',
                    addoutliers, 'art_outliers')
    preproc.connect(ad, 'norm_files',
                    addoutliers, 'composite_norm')
    preproc.connect(compcor, 'outputspec.noise_components', 
                    addoutliers, 'compcorr_components')
    preproc.connect(motion_correct, 'par_file',  
                    addoutliers, 'motion_params')
    preproc.connect(addoutliers, 'filter_file',
                    remove_noise, 'design_file')
    preproc.connect(getmask, ('outputspec.mask_file', pickfirst),
                    remove_noise, 'mask')
    preproc.connect(remove_noise, 'out_file',
                    smooth, 'inputnode.in_files')
    preproc.connect(remove_noise, 'out_file',
                    choosesusan, 'motion_files')
    preproc.connect(compcor, 'tsnr.detrended_file',
                    remove_noise, 'in_file')

    preproc.connect(meanscale, 'out_file',
                    whitening, "in_file")
    preproc.connect(whitening, "out_file",
                    bandpass_filter, 'in_file')

    preproc.connect(bandpass_filter, 'out_file',
                    outputnode, 'bandpassed_file')
    preproc.connect(choosesusan, 'cor_smoothed_files',
                    medianval, 'in_file')
    preproc.connect(meanscale, 'out_file',
                    outputnode, 'scaled_files')
    preproc.connect(inputnode, 'highpass_freq',
                    bandpass_filter, 'highpass_freq')
    preproc.connect(inputnode, 'lowpass_freq',
                    bandpass_filter, 'lowpass_freq')
    preproc.connect(bandpass_filter, 'out_file',
                    zscore, 'image')
    preproc.connect(inputnode, 'reg_params',
                    addoutliers, 'selector')
    preproc.connect(addoutliers, 'filter_file',
                    outputnode, 'filter_file')
    return preproc


def create_first(name='modelfit'):
    """First level task-fMRI modelling workflow
    
    Parameters
    ----------
    name : name of workflow. Default = 'modelfit'
    
    Inputs
    ------
    inputspec.session_info :
    inputspec.interscan_interval :
    inputspec.contrasts :
    inputspec.film_threshold :
    inputspec.functional_data :
    inputspec.bases :
    inputspec.model_serial_correlations :
    
    Outputs
    -------
    outputspec.copes :
    outputspec.varcopes :
    outputspec.dof_file :
    outputspec.pfiles :
    outputspec.parameter_estimates :
    outputspec.zstats :
    outputspec.tstats :
    outputspec.design_image :
    outputspec.design_file :
    outputspec.design_cov :
    
    Returns
    -------
    workflow : first-level workflow
    """
    modelfit = pe.Workflow(name=name)

    inputspec = pe.Node(util.IdentityInterface(fields=['session_info',
                                                       'interscan_interval',
                                                       'contrasts',
                                                       'film_threshold',
                                                       'functional_data',
                                                       'bases',
                                                       'model_serial_correlations']),
                        name='inputspec')
    
    
    
    level1design = pe.Node(interface=fsl.Level1Design(), 
                           name="create_level1_design")

    modelgen = pe.MapNode(interface=fsl.FEATModel(), 
                          name='generate_model',
                          iterfield = ['fsf_file', 
                                       'ev_files'])
    
    modelestimate = pe.MapNode(interface=fsl.FILMGLS(smooth_autocorr=True,
                                                     mask_size=5),
                               name='estimate_model',
                               iterfield = ['design_file',
                                            'in_file'])

    conestimate = pe.MapNode(interface=fsl.ContrastMgr(), 
                             name='estimate_contrast',
                             iterfield = ['tcon_file',
                                          'param_estimates',
                                          'sigmasquareds', 
                                          'corrections',
                                          'dof_file'])

    ztopval = pe.MapNode(interface=fsl.ImageMaths(op_string='-ztop',
                                                  suffix='_pval'),
                         name='z2pval',
                         iterfield=['in_file'])
    outputspec = pe.Node(util.IdentityInterface(fields=['copes',
                                                        'varcopes',
                                                        'dof_file', 
                                                        'pfiles',
                                                        'parameter_estimates',
                                                        'zstats',
                                                        'tstats',
                                                        'design_image',
                                                        'design_file',
                                                        'design_cov']),
                         name='outputspec')

    # Utility function

    pop_lambda = lambda x : x[0]

    # Setup the connections

    modelfit.connect([
        (inputspec, level1design, [('interscan_interval', 'interscan_interval'),
                                   ('session_info', 'session_info'),
                                   ('contrasts', 'contrasts'),
                                   ('bases', 'bases'),
                                   ('model_serial_correlations',
                                    'model_serial_correlations')]),
        (inputspec, modelestimate,  [('film_threshold',         'threshold'),
                                     ('functional_data',        'in_file')]),
        (level1design,modelgen,     [('fsf_files',              'fsf_file'),
                                     ('ev_files',               'ev_files')]),
        (modelgen, modelestimate,   [('design_file',            'design_file')]),
        (modelgen, conestimate,     [('con_file',               'tcon_file')]),
        (modelestimate, conestimate,[('param_estimates',        'param_estimates'),
                                     ('sigmasquareds',          'sigmasquareds'),
                                     ('corrections',            'corrections'),
                                     ('dof_file',               'dof_file')]),
        (conestimate, ztopval,      [(('zstats', pop_lambda),   'in_file')]),
        (ztopval, outputspec,       [('out_file',               'pfiles')]),
        (modelestimate, outputspec, [('param_estimates',        'parameter_estimates'),
                                     ('dof_file',               'dof_file')]),
        (conestimate, outputspec,   [('copes',                  'copes'),
                                     ('varcopes',               'varcopes'),
                                     ('tstats',                 'tstats'),
                                     ('zstats',                 'zstats')])])
    modelfit.connect(modelgen, 'design_image',
                     outputspec, 'design_image')
    modelfit.connect(modelgen, 'design_file',
                     outputspec, 'design_file')
    modelfit.connect(modelgen, 'design_cov',
                     outputspec, 'design_cov')
    return modelfit
    
#def smri(name = "smri"):
    
    
