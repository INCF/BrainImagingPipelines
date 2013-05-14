def afni_realign(in_file,tr,do_slicetime,sliceorder,order='motion_slicetime'):
    import nipype.interfaces.afni as afni
    import nipype.interfaces.fsl as fsl
    from nipype.utils.filemanip import split_filename
    import os
    import nibabel as nib

    if not isinstance(in_file, list):
        in_file = [in_file]
    img = nib.load(in_file[0])
    Nz = img.shape[2]

    out_file = []
    par_file = []
    parameter_source = 'AFNI'

    def slicetime(file, sliceorder):
        print "running slicetiming"
        slicetime = afni.TShift(outputtype='NIFTI_GZ')
        slicetime.inputs.in_file = file
        if type(sliceorder)==list:
            custom_order = open(os.path.abspath('afni_custom_order_file.txt'),'w')
            tpattern = []
            for i in xrange(len(sliceorder)):
                tpattern.append((i*tr/float(Nz), sliceorder[i]))
                tpattern.sort(key=lambda x:x[1])
                for i,t in enumerate(tpattern):
                    print '%f\n'%(t[0])
                    custom_order.write('%f\n'%(t[0]))
            custom_order.close()
            order_file = 'afni_custom_order_file.txt'
        elif type(sliceorder)==str:
            order_file = sliceorder
        else:
            raise TypeError('sliceorder must be filepath or list')

        slicetime.inputs.args ='-tpattern @%s' % os.path.abspath(order_file)
        slicetime.inputs.tr = str(tr)+'s'
        slicetime.inputs.outputtype = 'NIFTI_GZ'
        slicetime.inputs.out_file = os.path.abspath(split_filename(file)[1] +\
                                                    "_tshift.nii.gz")

        res = slicetime.run()
        file_to_realign = res.outputs.out_file
        return file_to_realign

    def motion(file_to_realign, ref_vol):
        print "running realignment"
        realign = afni.Volreg()
        realign.inputs.in_file = file_to_realign
        realign.inputs.outputtype = 'NIFTI_GZ'
        realign.inputs.out_file = os.path.abspath("afni_corr_" +\
                                                  split_filename(file_to_realign)[1] +\
                                                  ".nii.gz")
        realign.inputs.oned_file = "afni_realignment_parameters.par"
        realign.inputs.basefile = ref_vol
        Realign_res = realign.run()
        out_file = Realign_res.outputs.out_file
        par_file = Realign_res.outputs.oned_file
        return out_file, par_file

    # get the first volume of first run as ref file
    extract = fsl.ExtractROI()
    extract.inputs.t_min = 0
    extract.inputs.t_size = 1
    extract.inputs.in_file = in_file[0]
    ref_vol = extract.run().outputs.roi_file

    for idx, file in enumerate(in_file):
        if do_slicetime:

            if order == "motion_slicetime":
                out, par = motion(file,ref_vol)
                out = slicetime(out,sliceorder)
            elif order == "slicetime_motion":
                file_to_realign = slicetime(file,sliceorder)
                if not idx:
                    extract = fsl.ExtractROI()
                    extract.inputs.t_min = 0
                    extract.inputs.t_size = 1
                    extract.inputs.in_file = file_to_realign
                    ref_vol = extract.run().outputs.roi_file
                out, par = motion(file_to_realign,ref_vol)

        else:
            file_to_realign = file
            out, par = motion(file_to_realign,ref_vol)

        out_file.append(out)
        par_file.append(par)

        return out_file, par_file, parameter_source

def fsl_realign(in_file,tr,do_slicetime,sliceorder,order="motion_slicetime"):
    import nipype.interfaces.fsl as fsl
    import os
    if not isinstance(in_file, list):
        in_file = [in_file]
    out_file = []
    par_file = []
    parameter_source = 'FSL'

    def slicetime(file,sliceorder):
        print "running slicetiming"
        slicetime = fsl.SliceTimer()
        slicetime.inputs.in_file = file
        sliceorder_file = os.path.abspath('FSL_custom_order.txt')
        with open(sliceorder_file, 'w') as custom_order_fp:
            for t in sliceorder:
                custom_order_fp.write('%d\n' % (t + 1))
        slicetime.inputs.custom_order = sliceorder_file
        slicetime.inputs.time_repetition = tr
        res = slicetime.run()
        file_to_realign = res.outputs.slice_time_corrected_file
        extract = fsl.ExtractROI()
        extract.inputs.t_min = 0
        extract.inputs.t_size = 1
        extract.inputs.in_file = file_to_realign
        ref_vol = extract.run().outputs.roi_file
        return file_to_realign, ref_vol

    def motion(file_to_realign,ref_vol):
        print "running realignment"
        realign = fsl.MCFLIRT(interpolation='spline', ref_file=ref_vol)
        realign.inputs.save_plots = True
        realign.inputs.save_mats = True
        realign.inputs.mean_vol = True
        realign.inputs.in_file = file_to_realign
        realign.inputs.out_file = 'fsl_corr_' +\
                                  os.path.split(file_to_realign)[1]
        Realign_res = realign.run()
        out_file = Realign_res.outputs.out_file
        par_file = Realign_res.outputs.par_file
        return out_file, par_file

    # get the first volume of first run as ref file

    extract = fsl.ExtractROI()
    extract.inputs.t_min = 0
    extract.inputs.t_size = 1
    extract.inputs.in_file = in_file[0]
    ref_vol = extract.run().outputs.roi_file

    for idx, file in enumerate(in_file):
        if do_slicetime:
            if order == 'motion_slicetime':
                out, par = motion(file,ref_vol)
                out, _ = slicetime(out,sliceorder)
            elif order == 'slicetime_motion':
                out, ref = slicetime(file,sliceorder)
                if not idx:
                    ref_vol = ref
                out, par = motion(out,ref_vol)
        else:
            file_to_realign = file
            out, par = motion(file_to_realign, ref_vol)

        out_file.append(out)
        par_file.append(par)


    return out_file, par_file, parameter_source


def spm_realign(in_file,tr,do_slicetime,sliceorder,order="motion_slicetime"):
    import numpy as np
    import nibabel as nib
    import nipype.interfaces.freesurfer as fs
    import nipype.interfaces.spm as spm
    import nipype.interfaces.fsl as fsl

    parameter_source = 'SPM'

    if not isinstance(in_file, list):
        in_file = [in_file]

    new_in_file = []
    for f in in_file:
        if f.endswith('.nii.gz'):
            convert = fs.MRIConvert()
            convert.inputs.in_file = f
            convert.inputs.out_type = 'nii'
            convert.inputs.in_type = 'niigz'
            f = convert.run().outputs.out_file
            new_in_file.append(f)
        else:
            new_in_file.append(f)

    def slicetime(new_in_file,sliceorder):
        print "running slice time correction"
        img = nib.load(new_in_file[0])
        num_slices = img.shape[2]
        st = spm.SliceTiming()
        st.inputs.in_files = new_in_file
        st.inputs.num_slices = num_slices
        st.inputs.time_repetition = tr
        st.inputs.time_acquisition = tr - tr / num_slices
        st.inputs.slice_order = (np.asarray(sliceorder) + 1).astype(int).tolist()
        st.inputs.ref_slice = 1
        res_st = st.run()
        file_to_realign = res_st.outputs.timecorrected_files
        return file_to_realign

    def realign(file_to_realign):
        print "running motion correction"
        realign = spm.Realign()
        realign.inputs.in_files = file_to_realign
        realign.inputs.register_to_mean = False
        #realign.inputs.out_prefix = 'spm_corr_'
        res = realign.run()
        parameters = res.outputs.realignment_parameters
        if not isinstance(parameters, list):
            parameters = [parameters]
        par_file = parameters
        out_file = []
        if isinstance(res.outputs.realigned_files, list):
            for rf in res.outputs.realigned_files:
                res = fsl.ImageMaths(in_file=rf,
                    out_file=rf,
                    output_type='NIFTI',
                    op_string='-nan').run()
                out_file.append(res.outputs.out_file)
        else:
            res2 = fsl.ImageMaths(in_file=res.outputs.realigned_files,
                out_file=res.outputs.realigned_files,
                output_type='NIFTI',
                op_string='-nan').run()
            out_file.append(res2.outputs.out_file)
        return out_file, par_file

    if do_slicetime:
        if order == 'motion_slicetime':
            file_to_realign = new_in_file
            out_file, par_file = realign(file_to_realign)
            out_file = slicetime(out_file,sliceorder)
        elif order=='slicetime_motion':
            out_file = slicetime(new_in_file,sliceorder)
            out_file, par_file = realign(out_file)
    else:
        file_to_realign = new_in_file
        out_file, par_file = realign(file_to_realign)

    return out_file, par_file, parameter_source

def mod_realign(node,in_file,tr,do_slicetime,sliceorder,
                parameters={}):
    from bips.workflows.gablab.wips.scripts.modular_nodes import spm_realign, fsl_realign, afni_realign
    keys=parameters.keys()
    if node=="nipy":
        import nipype.interfaces.nipy as nipy
        import numpy as np
        realign = nipy.FmriRealign4d()
        realign.inputs.in_file = in_file
        realign.inputs.tr = tr
        if "loops" in keys:
            realign.inputs.loops = parameters["loops"]
        if "speedup" in keys:
            realign.inputs.speedup = parameters["speedup"]
        if "between_loops" in keys:
            realign.inputs.between_loops = parameters["between_loops"]
        if do_slicetime:
            realign.inputs.slice_order = np.argsort(sliceorder).tolist()
            realign.inputs.time_interp = True

        res = realign.run()
        parameter_source = 'NiPy'
        out_file = res.outputs.out_file
        par_file = res.outputs.par_file

    elif node == "fsl":
        out_file, par_file, parameter_source = fsl_realign(in_file,tr,do_slicetime, sliceorder,parameters['order'])

    elif node == 'spm':
        out_file, par_file, parameter_source = spm_realign(in_file,tr,do_slicetime, sliceorder,parameters['order'])

    elif node == 'afni':
        out_file, par_file, parameter_source = afni_realign(in_file,tr,do_slicetime, sliceorder,parameters['order'])

    return out_file, par_file, parameter_source

def mod_smooth(in_file,brightness_threshold,usans,fwhm,
               smooth_type, reg_file, surface_fwhm, subjects_dir=None):
    import nipype.interfaces.fsl as fsl
    import nipype.interfaces.freesurfer as fs
    if smooth_type == 'susan':
        smooth = fsl.SUSAN()
        smooth.inputs.fwhm = fwhm
        smooth.inputs.brightness_threshold = brightness_threshold
        smooth.inputs.usans = usans
        smooth.inputs.in_file = in_file
        res = smooth.run()
        smoothed_file = res.outputs.smoothed_file
    elif smooth_type=='isotropic':
        smooth = fsl.IsotropicSmooth()
        smooth.inputs.in_file = in_file
        smooth.inputs.fwhm = fwhm
        res = smooth.run()
        smoothed_file = res.outputs.out_file
    elif smooth_type == 'freesurfer':
        smooth = fs.Smooth()
        smooth.inputs.reg_file = reg_file
        smooth.inputs.in_file = in_file
        smooth.inputs.surface_fwhm = surface_fwhm
        smooth.inputs.vol_fwhm = fwhm
        smooth.inputs.proj_frac_avg = (0.0,1.0,0.1)
        smooth.inputs.subjects_dir = subjects_dir
        res = smooth.run()
        smoothed_file = res.outputs.smoothed_file
    return smoothed_file

def getbtthresh(medianvals):
    return [0.75*val for val in medianvals]

def getusans(x):
    return [[tuple([val[0],0.75*val[1]])] for val in x]

def create_mod_smooth(name="susan_smooth", separate_masks=True):
    """Create a SUSAN smoothing workflow

Parameters
----------

::

name : name of workflow (default: susan_smooth)
separate_masks : separate masks for each run

Inputs::

inputnode.in_files : functional runs (filename or list of filenames)
inputnode.fwhm : fwhm for smoothing with SUSAN
inputnode.mask_file : mask used for estimating SUSAN thresholds (but not for smoothing)

Outputs::

outputnode.smoothed_files : functional runs (filename or list of filenames)

Example
-------

>>> smooth = create_susan_smooth()
>>> smooth.inputs.inputnode.in_files = 'f3.nii'
>>> smooth.inputs.inputnode.fwhm = 5
>>> smooth.inputs.inputnode.mask_file = 'mask.nii'
>>> smooth.run() # doctest: +SKIP

"""
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    import nipype.interfaces.fsl as fsl
    susan_smooth = pe.Workflow(name=name)

    """
Set up a node to define all inputs required for the preprocessing workflow

"""

    inputnode = pe.Node(interface=util.IdentityInterface(fields=['in_files',
                                                                 'fwhm',
                                                                 'mask_file',
                                                                 'smooth_type',
                                                                 'reg_file',
                                                                 'surface_fwhm',
                                                                 'surf_dir']),
        name='inputnode')

    """
Smooth each run using SUSAN with the brightness threshold set to 75%
of the median value for each run and a mask consituting the mean
functional
"""

    #smooth = pe.MapNode(interface=fsl.SUSAN(),
    #    iterfield=['in_file', 'brightness_threshold','usans'],
    #    name='smooth')

    smooth = pe.MapNode(util.Function(input_names=['in_file',
                                                   'brightness_threshold',
                                                   'usans',
                                                   'fwhm',
                                                   'smooth_type',
                                                   'reg_file',
                                                   'surface_fwhm',
                                                   'subjects_dir'],
        output_names=['smoothed_file'],
        function=mod_smooth),
        name='mod_smooth',
        iterfield=['in_file', 'brightness_threshold','usans'])
    susan_smooth.connect(inputnode, 'smooth_type', smooth, 'smooth_type')
    susan_smooth.connect(inputnode,'reg_file',smooth, 'reg_file')
    susan_smooth.connect(inputnode,'surface_fwhm', smooth,'surface_fwhm')
    susan_smooth.connect(inputnode,'surf_dir', smooth, 'subjects_dir')
    """
Determine the median value of the functional runs using the mask
"""


    if separate_masks:
        median = pe.MapNode(interface=fsl.ImageStats(op_string='-k %s -p 50'),
            iterfield = ['in_file', 'mask_file'],
            name='median')
    else:
        median = pe.MapNode(interface=fsl.ImageStats(op_string='-k %s -p 50'),
            iterfield = ['in_file'],
            name='median')
    susan_smooth.connect(inputnode, 'in_files', median, 'in_file')
    susan_smooth.connect(inputnode, 'mask_file', median, 'mask_file')

    """
Mask the motion corrected functional runs with the dilated mask
"""

    if separate_masks:
        mask = pe.MapNode(interface=fsl.ImageMaths(suffix='_mask',
            op_string='-mas'),
            iterfield=['in_file', 'in_file2'],
            name='mask')
    else:
        mask = pe.MapNode(interface=fsl.ImageMaths(suffix='_mask',
            op_string='-mas'),
            iterfield=['in_file'],
            name='mask')
    susan_smooth.connect(inputnode, 'in_files', mask, 'in_file')
    susan_smooth.connect(inputnode, 'mask_file', mask, 'in_file2')

    """
Determine the mean image from each functional run
"""

    meanfunc = pe.MapNode(interface=fsl.ImageMaths(op_string='-Tmean',
        suffix='_mean'),
        iterfield=['in_file'],
        name='meanfunc2')
    susan_smooth.connect(mask, 'out_file', meanfunc, 'in_file')

    """
Merge the median values with the mean functional images into a coupled list
"""

    merge = pe.Node(interface=util.Merge(2, axis='hstack'),
        name='merge')
    susan_smooth.connect(meanfunc,'out_file', merge, 'in1')
    susan_smooth.connect(median,'out_stat', merge, 'in2')

    """
Define a function to get the brightness threshold for SUSAN
"""
    susan_smooth.connect(inputnode, 'fwhm', smooth, 'fwhm')
    susan_smooth.connect(inputnode, 'in_files', smooth, 'in_file')
    susan_smooth.connect(median, ('out_stat', getbtthresh), smooth, 'brightness_threshold')
    susan_smooth.connect(merge, ('out', getusans), smooth, 'usans')

    outputnode = pe.Node(interface=util.IdentityInterface(fields=['smoothed_files']),
        name='outputnode')

    #susan_smooth.connect(smooth, 'smoothed_file', outputnode, 'smoothed_files')

    if separate_masks:
        applymask = pe.MapNode(interface=fsl.ApplyMask(),
            iterfield=['in_file', 'mask_file'],
            name='applymask')
    else:
        applymask = pe.MapNode(interface=fsl.ApplyMask(),
            iterfield=['in_file'],
            name='applymask')

    susan_smooth.connect(smooth,'smoothed_file', applymask,'in_file')
    susan_smooth.connect(inputnode, 'mask_file', applymask, 'mask_file')
    susan_smooth.connect(applymask, 'out_file',  outputnode, 'smoothed_files')

    return susan_smooth

def mod_filter(in_file, algorithm, lowpass_freq, highpass_freq, tr):
    import os
    from nipype.utils.filemanip import fname_presuffix
    if algorithm == 'fsl':
        import nipype.interfaces.fsl as fsl
        filter = fsl.TemporalFilter()
        filter.inputs.in_file = in_file
        if highpass_freq < 0:
            filter.inputs.highpass_sigma = -1
        else:
            filter.inputs.highpass_sigma = 1 / (2 * tr * highpass_freq)
        if lowpass_freq < 0:
            filter.inputs.lowpass_sigma = -1
        else:
            filter.inputs.lowpass_sigma = 1 / (2 * tr * lowpass_freq)
        res = filter.run()
        out_file = res.outputs.out_file
    else:
        import nitime.fmri.io as io
        from nitime.analysis import FilterAnalyzer
        import nibabel as nib
        import numpy as np

        T = io.time_series_from_file(in_file, TR=tr)
        if highpass_freq < 0:
            highpass_freq = 0
        if lowpass_freq < 0:
            lowpass_freq = None
        filt_order = np.floor(T.shape[3]/3)
        if filt_order % 2 == 1:
            filt_order -= 1
        F = FilterAnalyzer(T, ub=lowpass_freq, lb=highpass_freq,
                           filt_order=filt_order)
        if algorithm == 'IIR':
            Filtered_data = F.iir.data
            suffix = '_iir_filt'
        elif algorithm == 'Boxcar':
            Filtered_data = F.filtered_boxcar.data
            suffix = '_boxcar_filt'
        elif algorithm == 'Fourier':
            Filtered_data = F.filtered_fourier.data
            suffix = '_fourier_filt'
        elif algorithm == 'FIR':
            Filtered_data = F.fir.data
            suffix = '_fir_filt'
        else:
            raise ValueError('Unknown Nitime filtering algorithm: %s' %
                             algorithm)

        out_file = fname_presuffix(in_file, suffix=suffix,
                                   newpath=os.getcwd())

        out_img = nib.Nifti1Image(Filtered_data,
                                  nib.load(in_file).get_affine())
        out_img.to_filename(out_file)

    return out_file

def mod_regressor(design_file,in_file,mask):
    import nipype.interfaces.fsl as fsl
    if "empty_file.txt" in design_file:
        return in_file
    else:
        reg = fsl.FilterRegressor(filter_all=True)
        reg.inputs.in_file = in_file
        reg.inputs.design_file = design_file
        reg.inputs.mask = mask
        res = reg.run()
        out_file = res.outputs.out_file
        return out_file

def mod_despike(in_file, do_despike):
    out_file=in_file
    if do_despike:
        from nipype.interfaces.afni import Despike
        from nipype.utils.filemanip import fname_presuffix
        ds = Despike(in_file=in_file,out_file=fname_presuffix(in_file,'','_despike'))
        out_file = ds.run().outputs.out_file
    return out_file

