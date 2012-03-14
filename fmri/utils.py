# Utility Functions ---------------------------------------------------------
import os
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio          # input/output
import nipype.interfaces.freesurfer as fs
import nipype.interfaces.utility as util
from nipype.algorithms.misc import TSNR
import nipype.interfaces.fsl as fsl
import nipype.algorithms.rapidart as ra     # rapid artifact detection

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
                             csf_mask_file, selector):
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

    options = np.array([noise_mask_file, csf_mask_file])
    selector = np.array(selector)
    imgseries = load(realigned_file)
    if selector.all():  # both values of selector are true, need to concatenate
        tcomp = load(noise_mask_file)
        acomp = load(csf_mask_file)
        voxel_timecourses = imgseries.get_data()[np.nonzero(tcomp.get_data() +
                                                            acomp.get_data())]
    else:
        noise_mask_file = options[selector][0]
        noise_mask = load(noise_mask_file)
        voxel_timecourses = imgseries.get_data()[np.nonzero(noise_mask.get_data())]
    for timecourse in voxel_timecourses:
        timecourse[:] = detrend(timecourse, type='constant')
    voxel_timecourses = voxel_timecourses.byteswap().newbyteorder()
    _, _, v = sp.linalg.svd(voxel_timecourses, full_matrices=False)
    components_file = os.path.join(os.getcwd(), 'noise_components.txt')
    np.savetxt(components_file, v[:, :num_components])
    return components_file


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
    extract_csf = pe.Workflow(name='extract_csf_mask')
    inputspec = pe.Node(util.IdentityInterface(fields=['mean_file',
                                                       'reg_file',
                                                       'fsaseg_file']),
                        name='inputspec')

    # add getting the freesurfer volume
    bin = pe.Node(fs.Binarize(), name='binarize')
    bin.inputs.ventricles = True
    extract_csf.connect(inputspec, 'fsaseg_file',
                        bin, "in_file")
    voltransform = pe.MapNode(fs.ApplyVolTransform(inverse=True),
                           name='inverse_transform',iterfield=['source_file'])
    extract_csf.connect(bin, 'binary_file',
                        voltransform, 'target_file')
    extract_csf.connect(inputspec, ('reg_file', pickfirst),
                        voltransform, 'reg_file')
    extract_csf.connect(inputspec, ('mean_file', pickfirst),
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
    compproc = pe.Workflow(name=name)
    inputspec = pe.Node(util.IdentityInterface(fields=['num_components',
                                                       'realigned_file',
                                                       'in_file',
                                                       'reg_file',
                                                       'fsaseg_file',
                                                       'selector']),
                        name='inputspec')
    # selector input is bool list [True,True] where first is referring to
    # tCompcorr and second refers to aCompcorr
    outputspec = pe.Node(util.IdentityInterface(fields=['noise_components',
                                                        'stddev_file',
                                                        'tsnr_file',
                                                        'csf_mask']),
                         name='outputspec')
    # extract the principal components of the noise
    tsnr = pe.MapNode(TSNR(regress_poly=2),
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
                                                    'selector'],
                                       output_names=['noise_components'],
                                       function=extract_noise_components),
                                       name='compcor_components',
                                       iterfield=['realigned_file',
                                                  'noise_mask_file',
                                                  'csf_mask_file'])
    # Make connections
    compproc.connect(inputspec, 'realigned_file',
                     acomp, 'inputspec.mean_file')
    compproc.connect(inputspec, 'reg_file',
                     acomp, 'inputspec.reg_file')
    compproc.connect(inputspec, 'fsaseg_file',
                     acomp, 'inputspec.fsaseg_file')
    compproc.connect(inputspec, 'selector',
                     compcor, 'selector')
    compproc.connect(acomp, 'outputspec.csf_mask',
                     compcor, 'csf_mask_file')
    compproc.connect(inputspec, 'in_file',
                     tsnr, 'in_file')
    compproc.connect(inputspec, 'num_components',
                     compcor, 'num_components')
    compproc.connect(inputspec, ('realigned_file',pickfirst),
                     compcor, 'realigned_file')
    compproc.connect(getthresh, 'out_stat',
                     threshold_stddev, 'thresh')
    compproc.connect(threshold_stddev, 'out_file',
                     compcor, 'noise_mask_file')
    compproc.connect(tsnr, 'stddev_file',
                     threshold_stddev, 'in_file')
    compproc.connect(tsnr, 'stddev_file',
                     getthresh, 'in_file')
    compproc.connect(tsnr, 'stddev_file',
                     outputspec, 'stddev_file')
    compproc.connect(tsnr, 'tsnr_file',
                     outputspec, 'tsnr_file')
    compproc.connect(compcor, 'noise_components',
                     outputspec, 'noise_components')
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
    cor_smoothed_files = []
    if fwhm < 0.5:
        cor_smoothed_files = motion_files
    else:
        cor_smoothed_files = smoothed_files
    return cor_smoothed_files


def get_substitutions(subject_id):
    subs = [('_subject_id_%s/' % subject_id, ''),
            ('_plot_type_', ''),
            ('_fwhm', 'fwhm'),
            ('_dtype_mcf_mask_mean', '_mean'),
            ('_dtype_mcf_mask_smooth_mask_gms_tempfilt',
             '_smoothed_preprocessed'),
            ('_dtype_mcf_mask_gms_tempfilt',
             '_unsmoothed_preprocessed'),
            ('_dtype_mcf', '_mcf')]

    for i in range(4):
        subs.append(('_plot_motion%d' % i, ''))
        subs.append(('_highpass%d/' % i, ''))
        subs.append(('_realign%d/' % i, ''))
        subs.append(('_meanfunc2%d/' % i, ''))
    return subs


def get_datasink(root_dir, fwhm):
    sinkd = pe.Node(nio.DataSink(), name='sinkd')
    sinkd.inputs.base_directory = os.path.join(root_dir, 'analyses', 'func')
    #sinkd.inputs.container = subj
    #sinkd.inputs.substitutions = getsubs(subj)
    sinkd.inputs.regexp_substitutions = [('mask/fwhm_%d/_threshold([0-9]*)/.*nii' % x,
                                          'mask/fwhm_%d/funcmask.nii' % x) for x in fwhm]
    sinkd.inputs.regexp_substitutions.append(('realigned/fwhm_([0-9])/_copy_geom([0-9]*)/',
                                              'realigned/'))
    sinkd.inputs.regexp_substitutions.append(('motion/fwhm_([0-9])/', 'motion/'))
    sinkd.inputs.regexp_substitutions.append(('bbreg/fwhm_([0-9])/', 'bbreg/'))
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

    def try_import(fname):
        try:
            a = np.genfromtxt(fname)
            if a.shape == ():
                return [a]
            else:
                return a
        except:
            return np.array([])

    mean_image = os.path.abspath(split_filename(image)[1] + '.nii.gz')
    img, aff = nib.load(image).get_data(), nib.load(image).get_affine()
    weights = np.ones(img.shape[3])
    outs = try_import(art_file)
    weights[np.int_(outs)] = 0 #  art outputs 0 based indices
    mean_img = np.average(img, axis=3, weights=weights)
    final_image = nib.Nifti1Image(mean_img, aff) 
    final_image.to_filename(mean_image) 

    return mean_image


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
    wkflw = pe.Workflow(name=name)

    # define nodes
    inputspec = pe.Node(util.IdentityInterface(fields=['realigned_files',
                                                       'parameter_source',
                                                       'realignment_parameters']),
                            name='inputspec')

    meanimg = pe.MapNode(util.Function(input_names=['image','art_file'],
                                       output_names=['mean_image'],
                                       function=weight_mean),
                                       name='weighted_mean',
                                       iterfield=['image','art_file'])
    
    ad = pe.MapNode(ra.ArtifactDetect(),
                 name='strict_artifact_detect', 
                 iterfield=['realignment_parameters',
                 'realigned_files'])

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
    import math
    import nibabel as nib
    from scipy.stats.mstats import zscore
    from nipype.utils.filemanip import split_filename
    import os

    def try_import(fname):
        try:
            a = np.genfromtxt(fname)
            if a.shape == ():
                return [a]
            else:
                return a
        except:
            return np.array([])

    z_img = os.path.abspath('z_' + split_filename(image)[1] + '.nii.gz')      
    arts = try_import(outliers)
    imgt, aff = nib.load(image).get_data(), nib.load(image).get_affine()
    weights = np.bool_(np.zeros(imgt.shape))
    for a in arts:
        weights[:, :, :, np.int_(a)] = True
    imgt_mask = np.ma.array(imgt, mask=weights)
    z = zscore(imgt_mask, axis=3)
    final_image = nib.Nifti1Image(z, aff)
    final_image.to_filename(z_img)
    return z_img


tolist = lambda x: [x]
highpass_operand = lambda x: '-bptf %.10f -1' % x
