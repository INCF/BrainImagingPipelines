# Utility Functions ---------------------------------------------------------
import os
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio          # input/output
import nipype.interfaces.freesurfer as fs
import nipype.interfaces.utility as util
from nipype.algorithms.misc import TSNR
import nipype.interfaces.fsl as fsl


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
    voltransform = pe.Node(fs.ApplyVolTransform(inverse=True),
                           name='inverse_transform')
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
                                                  'noise_mask_file'])
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
    compproc.connect(inputspec, 'realigned_file',
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
    cor_smoothed_files = []
    if fwhm < 0.5:
        cor_smoothed_files = motion_files
    else:
        cor_smoothed_files = smoothed_files
    return cor_smoothed_files


def getsubs(subject_id):
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


def get_datasink(subj, root_dir, fwhm):
    sinkd = pe.Node(nio.DataSink(), name='sinkd')
    sinkd.inputs.base_directory = os.path.join(root_dir, 'analyses', 'func')
    sinkd.inputs.container = subj
    sinkd.inputs.substitutions = getsubs(subj)
    sinkd.inputs.regexp_substitutions = [('mask/fwhm_%d/_threshold([0-9]*)/.*nii' % x,
                                          'mask/fwhm_%d/funcmask.nii' % x) for x in fwhm]
    sinkd.inputs.regexp_substitutions.append(('realigned/fwhm_([0-9])/_copy_geom([0-9]*)/',
                                              'realigned/'))
    sinkd.inputs.regexp_substitutions.append(('motion/fwhm_([0-9])/', 'motion/'))
    sinkd.inputs.regexp_substitutions.append(('bbreg/fwhm_([0-9])/', 'bbreg/'))
    return sinkd

tolist = lambda x: [x]
highpass_operand = lambda x: '-bptf %.10f -1' % x
