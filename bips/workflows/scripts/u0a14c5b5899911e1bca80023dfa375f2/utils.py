# Utility Functions ---------------------------------------------------------
import os


def pickfirst(files):
    """Return first file from a list of files

    Parameters
    ----------
    files : list of filenames

    Returns
    -------
    file : returns the filename corresponding to the middle run
    """
    if isinstance(files, list):
        return files[0]
    else:
        return files


def pickmiddlerun(files):
    """Selects the middle run

    Defined as the floor of the number of runs divided by two.

    Parameters
    ----------
    files : list of filenames

    Returns
    -------
    file : returns the filename corresponding to the middle run
    """
    if isinstance(files, list):
        return files[int(len(files) / 2)]
    else:
        return files


def pickvol(filenames, fileidx, which):
    """Retrieve index of named volume

    Parameters
    ----------
    filenames: list of 4D file names
    fileidx: which 4D file to look at
    which: 'first' or 'middle'

    Returns
    -------
    idx: index of first or middle volume
    """

    from nibabel import load
    import numpy as np
    if which.lower() == 'first':
        idx = 0
    elif which.lower() == 'middle':
        idx = int(np.ceil(load(filenames[fileidx]).get_shape()[3] / 2))
    else:
        raise Exception('unknown value for volume selection : %s' % which)
    return idx

def pickidx(filenames, fileidx):
    return filenames[fileidx]

def get_threshold_op(thresh):
    return ['-thr %.10f -Tmin -bin' % (0.1 * val[1]) for val in thresh]


def getbtthresh(medianvals):
    return [0.75 * val for val in medianvals]


def chooseindex(fwhm):
    if fwhm < 1:
        return [0]
    else:
        return [1]


def getmeanscale(medianvals):
    return ['-mul %.10f' % (10000. / val) for val in medianvals]


def getusans(x):
    return [[tuple([val[0], 0.75 * val[1]])] for val in x]


def extract_noise_components(realigned_file, noise_mask_file, num_components,
                             csf_mask_file, selector,
                             realignment_parameters=None, outlier_file=None, regress_before_PCA=True):
    """Derive components most reflective of physiological noise
    
    Parameters
    ----------
    realigned_file :
    noise_mask_file :
    num_components :
    csf_mask_file :
    selector :
    
    Returns
    -------
    components_file :
    """

    import os
    from nibabel import load
    import numpy as np
    import scipy as sp
    from scipy.signal import detrend
    from nipype import logging
    logger = logging.getLogger('interface')

    def try_import(fname):
        try:
            a = np.genfromtxt(fname)
            return a
        except:
            return np.array([])

    options = np.array([noise_mask_file, csf_mask_file])
    selector = np.array(selector)
    imgseries = load(realigned_file)
    nuisance_matrix = np.ones((imgseries.shape[-1], 1))
    if realignment_parameters is not None:
        logger.debug('adding motion pars')
        logger.debug('%s %s' % (str(nuisance_matrix.shape),
            str(np.genfromtxt(realignment_parameters).shape)))
        nuisance_matrix = np.hstack((nuisance_matrix,
                                     np.genfromtxt(realignment_parameters)))
    if outlier_file is not None:
        logger.debug('collecting outliers')
        outliers = try_import(outlier_file)
        if outliers.shape == ():  # 1 outlier
            art = np.zeros((imgseries.shape[-1], 1))
            art[np.int_(outliers), 0] = 1 #  art outputs 0 based indices
            nuisance_matrix = np.hstack((nuisance_matrix, art))
        elif outliers.shape[0] == 0:  # empty art file
            pass
        else:  # >1 outlier
            art = np.zeros((imgseries.shape[-1], len(outliers)))
            for j, t in enumerate(outliers):
                art[np.int_(t), j] = 1 #  art outputs 0 based indices
            nuisance_matrix = np.hstack((nuisance_matrix, art))
    if selector.all():  # both values of selector are true, need to concatenate
        tcomp = load(noise_mask_file)
        acomp = load(csf_mask_file)
        voxel_timecourses = imgseries.get_data()[np.nonzero(tcomp.get_data() +
                                                            acomp.get_data())]
    else:
        noise_mask_file = options[selector][0]
        noise_mask = load(noise_mask_file)
        voxel_timecourses = imgseries.get_data()[np.nonzero(noise_mask.get_data())]

    voxel_timecourses = voxel_timecourses.byteswap().newbyteorder()
    voxel_timecourses[np.isnan(np.sum(voxel_timecourses,axis=1)),:] = 0
    if regress_before_PCA:
        logger.debug('Regressing motion')
        for timecourse in voxel_timecourses:
            #timecourse[:] = detrend(timecourse, type='constant')
            coef_, _, _, _ = np.linalg.lstsq(nuisance_matrix, timecourse[:, None])
            timecourse[:] = (timecourse[:, None] - np.dot(nuisance_matrix,
                                                          coef_)).ravel()

    pre_svd = os.path.abspath('pre_svd.npz')
    np.savez(pre_svd,voxel_timecourses=voxel_timecourses)
    _, _, v = sp.linalg.svd(voxel_timecourses, full_matrices=False)
    components_file = os.path.join(os.getcwd(), 'noise_components.txt')
    np.savetxt(components_file, v[:num_components, :].T)
    return components_file, pre_svd


def extract_csf_mask():
    """Create a workflow to extract a mask of csf voxels
    
    Inputs
    ------
    inputspec.mean_file :
    inputspec.reg_file :
    inputspec.fsaseg_file :
    
    Outputs
    -------
    outputspec.csf_mask :
    
    Returns
    -------
    workflow : workflow that extracts mask of csf voxels
    """
    import nipype.pipeline.engine as pe
    import nipype.interfaces.freesurfer as fs
    import nipype.interfaces.utility as util

    extract_csf = pe.Workflow(name='extract_csf_mask')
    inputspec = pe.Node(util.IdentityInterface(fields=['mean_file',
                                                       'reg_file',
                                                       'fsaseg_file']),
                        name='inputspec')

    bin = pe.Node(fs.Binarize(), name='binarize')
    bin.inputs.wm_ven_csf = True
    bin.inputs.match = [4, 5, 14, 15, 24, 31, 43, 44, 63]
    bin.inputs.erode = 2
    
    extract_csf.connect(inputspec, 'fsaseg_file',
                        bin, "in_file")
    voltransform = pe.Node(fs.ApplyVolTransform(inverse=True),
                           name='inverse_transform')
    extract_csf.connect(bin, 'binary_file',
                        voltransform, 'target_file')
    extract_csf.connect(inputspec, 'reg_file',
                        voltransform, 'reg_file')
    extract_csf.connect(inputspec, 'mean_file',
                        voltransform, 'source_file')
    outputspec = pe.Node(util.IdentityInterface(fields=['csf_mask']),
                         name='outputspec')
    extract_csf.connect(voltransform, 'transformed_file',
                        outputspec, 'csf_mask')
    return extract_csf


def create_compcorr(name='CompCor'):
    """Workflow that implements (t and/or a) compcor method from 
    
    Behzadi et al[1]_.
    
    Parameters
    ----------
    name : name of workflow. Default = 'CompCor'
    
    Inputs
    ------
    inputspec.num_components :
    inputspec.realigned_file :
    inputspec.in_file :
    inputspec.reg_file :
    inputspec.fsaseg_file :
    inputspec.selector :
    
    Outputs
    -------
    outputspec.noise_components :
    outputspec.stddev_file :
    outputspec.tsnr_file :
    outputspec.csf_mask :
    
    References
    ----------
    .. [1] Behzadi Y, Restom K, Liau J, Liu TT. A component based\
           noise correction method (CompCor) for BOLD and perfusion\
           based fMRI. Neuroimage. 2007 Aug 1;37(1):90-101. DOI_.

    .. _DOI: http://dx.doi.org/10.1016/j.neuroimage.2007.04.042
    """
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    from nipype.algorithms.misc import TSNR
    import nipype.interfaces.fsl as fsl
    compproc = pe.Workflow(name=name)
    inputspec = pe.Node(util.IdentityInterface(fields=['num_components',
                                                       'realigned_file',
                                                       'mean_file',
                                                       'reg_file',
                                                       'fsaseg_file',
                                                      'realignment_parameters',
                                                       'outlier_files',
                                                       'selector',
                                                       'regress_before_PCA']),
                        name='inputspec')
    # selector input is bool list [True,True] where first is referring to
    # tCompcorr and second refers to aCompcorr
    outputspec = pe.Node(util.IdentityInterface(fields=['noise_components',
                                                        'stddev_file',
                                                        'tsnr_file',
                                                        'csf_mask',
                                                        'noise_mask',
                                                        'tsnr_detrended',
                                                        'pre_svd']),
                         name='outputspec')
    # extract the principal components of the noise
    tsnr = pe.MapNode(TSNR(regress_poly=2),  #SG: advanced parameter
                      name='tsnr',
                      iterfield=['in_file'])

    # additional information for the noise prin comps
    getthresh = pe.MapNode(interface=fsl.ImageStats(op_string='-p 98'),
                            name='getthreshold',
                            iterfield=['in_file'])

    # and a bit more...
    threshold_stddev = pe.MapNode(fsl.Threshold(),
                                  name='threshold',
                                  iterfield=['in_file', 'thresh'])

    acomp = extract_csf_mask()

    # compcor actually extracts the components
    compcor = pe.MapNode(util.Function(input_names=['realigned_file',
                                                    'noise_mask_file',
                                                    'num_components',
                                                    'csf_mask_file',
                                                    'realignment_parameters',
                                                    'outlier_file',
                                                    'selector',
                                                    'regress_before_PCA'],
                                       output_names=['noise_components','pre_svd'],
                                       function=extract_noise_components),
                                       name='compcor_components',
                                       iterfield=['realigned_file',
                                                  'noise_mask_file',
                                                  'realignment_parameters',
                                                  'outlier_file'])
    # Make connections
    compproc.connect(inputspec, 'mean_file',
                     acomp, 'inputspec.mean_file')
    compproc.connect(inputspec, 'reg_file',
                     acomp, 'inputspec.reg_file')
    compproc.connect(inputspec, 'fsaseg_file',
                     acomp, 'inputspec.fsaseg_file')
    compproc.connect(inputspec, 'selector',
                     compcor, 'selector')
    compproc.connect(acomp, ('outputspec.csf_mask',pickfirst),
                     compcor, 'csf_mask_file')
    compproc.connect(acomp, ('outputspec.csf_mask',pickfirst),
        outputspec, 'csf_mask')
    compproc.connect(inputspec, 'realigned_file',
                     tsnr, 'in_file')
    compproc.connect(inputspec, 'num_components',
                     compcor, 'num_components')

    compproc.connect(inputspec, 'realignment_parameters',
                     compcor, 'realignment_parameters')
    compproc.connect(inputspec, 'outlier_files',
                     compcor, 'outlier_file')

    compproc.connect(getthresh, 'out_stat',
                     threshold_stddev, 'thresh')
    compproc.connect(threshold_stddev, 'out_file',
                     compcor, 'noise_mask_file')
    compproc.connect(threshold_stddev, 'out_file',
                     outputspec, 'noise_mask')
    compproc.connect(tsnr, 'stddev_file',
                     threshold_stddev, 'in_file')
    compproc.connect(tsnr, 'stddev_file',
                     getthresh, 'in_file')
    compproc.connect(tsnr, 'stddev_file',
                     outputspec, 'stddev_file')
    compproc.connect(tsnr, 'tsnr_file',
                     outputspec, 'tsnr_file')
    compproc.connect(tsnr, 'detrended_file',
                     outputspec, 'tsnr_detrended')
    compproc.connect(tsnr, 'detrended_file',
                     compcor, 'realigned_file')
    compproc.connect(compcor, 'noise_components',
                     outputspec, 'noise_components')
    compproc.connect(compcor, 'pre_svd',
                      outputspec, 'pre_svd')
    compproc.connect(inputspec, 'regress_before_PCA',
                     compcor, 'regress_before_PCA')
    return compproc


def choose_susan(fwhm, motion_files, smoothed_files):
    """The following node selects smooth or unsmoothed data
    
    depending on the fwhm. This is because SUSAN defaults
    to smoothing the data with about the voxel size of
    the input data if the fwhm parameter is less than 1/3 of
    the voxel size.
    
    Parameters
    ----------
    fwhm :
    motion_file :
    smoothed_files :
    
    Returns
    -------
    File : either the smoothed or unsmoothed
           file depending on fwhm
    """
    #SG: determine the value under which susan smooths with 2x
    #    voxel value #dbg
    if fwhm < 0.5:
        cor_smoothed_files = motion_files
    else:
        cor_smoothed_files = smoothed_files
    return cor_smoothed_files


def get_substitutions(subject_id, use_fieldmap):
    subs = [('_subject_id_%s/' % subject_id, ''),
            ('_fwhm', 'fwhm'),
            ('_register0/', ''),
            ('_threshold20/aparc+aseg_thresh_warped_dil_thresh',
             '%s_brainmask' % subject_id),
            ('st.','.'),
            ]
    if use_fieldmap:
        subs.append(('vsm.nii', '%s_vsm.nii' % subject_id))

    for i in range(20):  #SG: assumes max 4 runs
        subs.append(('_bandpass_filter%d/' % i, '%s_r%02d_' % (subject_id, i)))
        subs.append(('_scale_median%d/' % i, '%s_r%02d_' % (subject_id, i)))
        subs.append(('_create_nuisance_filter%d/' % i,
                     '%s_r%02d_' % (subject_id, i)))
        subs.append(('_tsnr%d/' % i, '%s_r%02d_' % (subject_id, i)))
        subs.append(('_z_score%d/' % i, '%s_r%02d_' % (subject_id, i)))
        subs.append(('_threshold%d/'%i,'%s_r%02d_'%(subject_id, i)))
        subs.append(('_compcor_components%d/'%i, '%s_r%02d_'%(subject_id, i)))
    return subs

def get_regexp_substitutions(subject_id, use_fieldmap):
    subs = [('corr.*_filt', 'bandpassed'),
            ('corr.*_gms', 'fullspectrum'),
            ('corr.*%s' % subject_id, '%s_register' % subject_id),
            ('corr.*_tsnr', 'tsnr'),
            #('motion/.*dtype', 'motion/%s' % subject_id),
            ('mean/corr.*nii', 'mean/%s_mean.nii' % subject_id),
            ('corr', ''),
            ('_roi_dtype_',''),
            ('__','_')
            ]
    return subs


def get_datasink(root_dir, fwhm):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio
    sinkd = pe.Node(nio.DataSink(), name='sinkd')
    sinkd.inputs.base_directory = os.path.join(root_dir)
    return sinkd


def weight_mean(image, art_file):
    """Calculates the weighted mean of a 4d image, where 
    
    the weight of outlier timpoints is = 0.
    
    Parameters
    ----------
    image : File to take mean
    art_file : text file specifying outlier timepoints
    
    Returns
    -------
    File : weighted mean image
    """
    import nibabel as nib
    import numpy as np
    from nipype.utils.filemanip import split_filename
    import os

    
    if not isinstance(image,list):
        image = [image]
    if not isinstance(art_file,list):
        art_file = [art_file]
    
    def try_import(fname):
        try:
            a = np.genfromtxt(fname)
            return np.atleast_1d(a).astype(int)
        except:
            return np.array([]).astype(int)
    
    mean_image_fname = os.path.abspath(split_filename(image[0])[1])
    
    total_weights = []
    meanimage = []
    for i, im in enumerate(image):
        img = nib.load(im)
        weights=np.ones(img.shape[3])
        weights[try_import(art_file[i])] = 1
        meanimage.append(img.shape[3]*np.average(img.get_data(), axis=3, weights=weights))
        total_weights.append(img.shape[3])
    mean_all = np.average(meanimage, weights=total_weights, axis=0)

    final_image = nib.Nifti1Image(mean_all, img.get_affine(), img.get_header()) 
    final_image.to_filename(mean_image_fname+'.nii.gz') 

    return mean_image_fname+'.nii.gz'


def art_mean_workflow(name="take_mean_art"):
    """Calculates mean image after running art w/ norm = 0.5, z=2
    
    Parameters
    ----------
    name : name of workflow. Default = 'take_mean_art'
    
    Inputs
    ------
    inputspec.realigned_files :
    inputspec.parameter_source :
    inputspec.realignment_parameters :
    
    Outputs
    -------
    outputspec.mean_image :
    
    Returns
    -------
    workflow : mean image workflow
    """
    # define workflow
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    import nipype.algorithms.rapidart as ra     # rapid artifact detection
    wkflw = pe.Workflow(name=name)

    # define nodes
    inputspec = pe.Node(util.IdentityInterface(fields=['realigned_files',
                                                       'parameter_source',
                                                       'realignment_parameters']),
                            name='inputspec')

    meanimg = pe.Node(util.Function(input_names=['image','art_file'],
                                       output_names=['mean_image'],
                                       function=weight_mean),
                                       name='weighted_mean')
    
    ad = pe.Node(ra.ArtifactDetect(),
                 name='strict_artifact_detect')

    outputspec = pe.Node(util.IdentityInterface(fields=['mean_image']),
                         name='outputspec')

    # inputs
    ad.inputs.zintensity_threshold = 2
    ad.inputs.norm_threshold = 0.5
    ad.inputs.use_differences = [True, False]
    ad.inputs.mask_type = 'spm_global'

    # connections
    wkflw.connect(inputspec, 'parameter_source',
                  ad, 'parameter_source')
    wkflw.connect(inputspec, 'realigned_files',
                  ad, 'realigned_files')
    wkflw.connect(inputspec, 'realignment_parameters',
                  ad, 'realignment_parameters')
    wkflw.connect(ad, 'outlier_files',
                  meanimg, 'art_file')
    wkflw.connect(inputspec, 'realigned_files',
                  meanimg, 'image')
    wkflw.connect(meanimg, 'mean_image',
                  outputspec, 'mean_image')
    return wkflw


def z_image(image,outliers):
    """Calculates z-score of timeseries removing timpoints with outliers.

    Parameters
    ----------
    image :
    outliers :

    Returns
    -------
    File : z-image
    """
    import numpy as np
    import nibabel as nib
    from nipype.utils.filemanip import split_filename
    import os
    if isinstance(image,list):
        image = image[0]
    if isinstance(outliers,list):
        outliers = outliers[0]
        
    def try_import(fname):
        try:
            a = np.genfromtxt(fname)
            return np.atleast_1d(a).astype(int)
        except:
            return np.array([]).astype(int)

    z_img = os.path.abspath('z_no_outliers_' + split_filename(image)[1] + '.nii.gz')
    arts = try_import(outliers)
    img = nib.load(image)
    data, aff = np.asarray(img.get_data()), img.get_affine()

    z_img2 = os.path.abspath('z_' + split_filename(image)[1] + '.nii.gz')
    z2 = (data - np.mean(data, axis=3)[:,:,:,None])/np.std(data,axis=3)[:,:,:,None]
    final_image = nib.Nifti1Image(z2, aff)
    final_image.to_filename(z_img2)

    if arts.size:
        data_mask = np.delete(data, arts, axis=3)
        z = (data_mask - np.mean(data_mask, axis=3)[:,:,:,None])/np.std(data_mask,axis=3)[:,:,:,None]
    else:
        z = z2
    final_image = nib.Nifti1Image(z, aff)
    final_image.to_filename(z_img)

    z_img = [z_img, z_img2]
    return z_img


def tolist(x):
    if isinstance(x,list):
        return x
    else:
        return [x]

highpass_operand = lambda x: '-bptf %.10f -1' % x

def whiten(in_file, do_whitening):
    out_file = in_file
    if do_whitening:
        import os
        from glob import glob
        from nipype.utils.filemanip import split_filename
        split_fname = split_filename(in_file)
        out_file = os.path.abspath(split_fname[1]+"_whitened"+split_fname[2])
        os.system('film_gls -ac -output_pwdata %s'%in_file)
        result = glob(os.path.join(os.path.abspath('results'),'prewhitened_data.*'))[0]
        out_file=result
    return out_file
