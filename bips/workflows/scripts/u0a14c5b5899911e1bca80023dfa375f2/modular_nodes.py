import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.fsl as fsl


def mod_realign(node,in_file,tr,do_slicetime,sliceorder):
    import nipype.interfaces.fsl as fsl
    import nipype.interfaces.spm as spm
    import nipype.interfaces.nipy as nipy
    import os

    if node=="nipy":
        realign = nipy.FmriRealign4d()
        realign.inputs.in_file = in_file
        realign.inputs.tr = tr
        realign.inputs.interleaved= False
        if do_slicetime:
            realign.inputs.slice_order = sliceorder
        else:
            realign.inputs.time_interp = False
            realign.inputs.slice_order = [0]

        res = realign.run()
        out_file = res.outputs.out_file
        par_file = res.outputs.par_file

    elif node=="fsl":
        if not isinstance(in_file,list):
            in_file = [in_file]
        out_file = []
        par_file = []
        # get the first volume of first run as ref file
        extract = fsl.ExtractROI()
        extract.inputs.t_min = 0
        extract.inputs.t_size=1
        extract.inputs.in_file = in_file[0]
        ref_vol = extract.run().outputs.roi_file

        for file in in_file:
            if do_slicetime:
                slicetime = fsl.SliceTimer()
                slicetime.inputs.in_file = file
                custom_order = open(os.path.abspath('FSL_custom_order_file.txt'),'w')
                for t in sliceorder:
                    custom_order.write('%d\n'%(t+1))
                custom_order.close()
                slicetime.inputs.custom_order = os.path.abspath('FSL_custom_order_file.txt') # needs to be 1-based
                slicetime.inputs.time_repetition = tr
                res = slicetime.run()
                file_to_realign = res.outputs.slice_time_corrected_file
            else:
                file_to_realign = file
            realign = fsl.MCFLIRT(interpolation='spline', ref_file=ref_vol)
            realign.inputs.save_plots = True
            realign.inputs.mean_vol = True
            realign.inputs.in_file = file_to_realign
            Realign_res = realign.run()
            out_file.append(Realign_res.outputs.out_file)
            par_file.append(Realign_res.outputs.par_file)

    elif node=='spm':
        import numpy as np
        import nibabel as nib
        import nipype.interfaces.freesurfer as fs
        if not isinstance(in_file,list):
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
        if do_slicetime:
            img = nib.load(new_in_file[0])
            num_slices = img.shape[2]
            st = spm.SliceTiming()
            st.inputs.in_files = new_in_file
            print new_in_file
            st.inputs.num_slices = num_slices
            st.inputs.time_repetition = tr
            st.inputs.time_acquisition = tr - tr/num_slices
            st.inputs.slice_order = (np.asarray(sliceorder) + 1).astype(int).tolist()
            st.inputs.ref_slice = 1
            res_st = st.run()
            file_to_realign = res_st.outputs.timecorrected_files
        else:
            file_to_realign = new_in_file
        par_file = []
        realign = spm.Realign()
        realign.inputs.in_files = file_to_realign
        res = realign.run()
        parameters = res.outputs.realignment_parameters
        if not isinstance(parameters,list):
            parameters = [parameters]
        for i, p in enumerate(parameters):
            foo = np.genfromtxt(p)
            boo = np.hstack((foo[:,3:],foo[:,:3]))
            np.savetxt(os.path.abspath('realignment_parameters_%d.txt'%i),boo,delimiter='\t')
            par_file.append(os.path.abspath('realignment_parameters_%d.txt'%i))
        out_file = res.outputs.realigned_files

    return out_file, par_file

def mod_smooth(in_file,brightness_threshold,usans,fwhm,smooth_type):
    import nipype.interfaces.fsl as fsl
    if smooth_type == 'susan':
        smooth = fsl.SUSAN()
        smooth.inputs.fwhm = fwhm
        smooth.inputs.brightness_threshold = brightness_threshold
        smooth.inputs.usans = usans
        smooth.inputs.in_file = in_file
        res = smooth.run()
        smoothed_file = res.outputs.smoothed_file
    else:
        smooth = fsl.IsotropicSmooth()
        smooth.inputs.in_file = in_file
        smooth.inputs.fwhm = fwhm
        res = smooth.run()
        smoothed_file = res.outputs.out_file
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

    susan_smooth = pe.Workflow(name=name)

    """
Set up a node to define all inputs required for the preprocessing workflow

"""

    inputnode = pe.Node(interface=util.IdentityInterface(fields=['in_files',
                                                                 'fwhm',
                                                                 'mask_file',
                                                                 'smooth_type']),
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
                                                   'smooth_type'],
        output_names=['smoothed_file'],
        function=mod_smooth),
        name='mod_smooth',
        iterfield=['in_file', 'brightness_threshold','usans'])
    susan_smooth.connect(inputnode, 'smooth_type', smooth, 'smooth_type')

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

    susan_smooth.connect(smooth, 'smoothed_file', outputnode, 'smoothed_files')

    return susan_smooth