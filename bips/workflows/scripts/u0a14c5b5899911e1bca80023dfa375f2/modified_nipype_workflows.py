from .utils import art_mean_workflow

def get_b0(bvals):
    import numpy as np
    vals = np.genfromtxt(bvals)
    b0 = np.asarray(range(0,vals.shape[0]))[vals<1]
    b0=b0.tolist()
    print b0
    return b0

def get_params(A):
    """This is a copy of spm's spm_imatrix where

    we already know the rotations and translations matrix,
    shears and zooms (as outputs from fsl FLIRT/avscale)

    Let A = the 4x4 rotation and translation matrix

    R = [          c5*c6,           c5*s6, s5]
        [-s4*s5*c6-c4*s6, -s4*s5*s6+c4*c6, s4*c5]
        [-c4*s5*c6+s4*s6, -c4*s5*s6-s4*c6, c4*c5]


    """
    import numpy as np

    def rang(b):
        a = min(max(b, -1), 1)
        return a
    Ry = np.arcsin(A[0,2])
    #Rx = np.arcsin(A[1,2]/np.cos(Ry))
    #Rz = np.arccos(A[0,1]/np.sin(Ry))

    if (abs(Ry)-np.pi/2)**2 < 1e-9:
        Rx = 0
        Rz = np.arctan2(-rang(A[1,0]), rang(-A[2,0]/A[0,2]))
    else:
        c  = np.cos(Ry)
        Rx = np.arctan2(rang(A[1,2]/c), rang(A[2,2]/c))
        Rz = np.arctan2(rang(A[0,1]/c), rang(A[0,0]/c))

    rotations = [Rx, Ry, Rz]
    translations = [A[0,3], A[1,3], A[2,3]]

    return rotations, translations


def get_flirt_motion_parameters(flirt_out_mats):
    import nipype.interfaces.fsl.utils as fsl
    import os
    import numpy as np
    from bips.workflows.scripts.u0a14c5b5899911e1bca80023dfa375f2.modified_nipype_workflows import get_params
    motion_params = open(os.path.abspath('motion_parameters.par'),'w')
    for mat in flirt_out_mats:
        res = fsl.AvScale(mat_file = mat).run()
        A = np.asarray(res.outputs.rotation_translation_matrix)
        rotations, translations = get_params(A)
        for i in rotations+translations:
            motion_params.write('%f '%i)
        motion_params.write('\n')
    motion_params.close()
    motion_params = os.path.abspath('motion_parameters.par')
    return motion_params


def mapnode_coregistration(in_file, reference):
    import nipype.interfaces.fsl as fsl
    out_file = []
    out_matrix_file = []
    for f in in_file:
        coreg = fsl.FLIRT(no_search=True,
                          padding_size=1,
                          dof=9,
                          in_file = f,
                          reference= reference)
        res = coreg.run()
        out_file.append(res.outputs.out_file)
        out_matrix_file.append(res.outputs.out_matrix_file)
    return out_file, out_matrix_file

def create_eddy_correct_pipeline(name="eddy_correct"):
    """Creates a pipeline that replaces eddy_correct script in FSL. It takes a
    series of diffusion weighted images and linearly corregisters them to one
    reference image.

    Example
    -------

    >>> nipype_eddycorrect = create_eddy_correct_pipeline("nipype_eddycorrect")
    >>> nipype_eddycorrect.inputs.inputnode.in_file = 'diffusion.nii'
    >>> nipype_eddycorrect.inputs.inputnode.ref_num = 0
    >>> nipype_eddycorrect.run() # doctest: +SKIP

    Inputs::

    inputnode.in_file
    inputnode.ref_num

    Outputs::

    outputnode.eddy_corrected
    """
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    import nipype.interfaces.fsl as fsl
    inputnode = pe.Node(interface = util.IdentityInterface(fields=["in_file", "bvals"]),
        name="inputnode")

    pipeline = pe.Workflow(name=name)

    split = pe.MapNode(fsl.Split(dimension='t'), name="split", iterfield=['in_file'])
    pipeline.connect([(inputnode, split, [("in_file", "in_file")])])

    getb0 = pe.Node(util.Function(input_names=['bvals'],
                                    output_names=['b0'],
                                    function=get_b0),
        name='get_b0_indices')

    pick_ref = pe.MapNode(util.Select(), name="pick_b0_scans", iterfield=["inlist"])
    pick0 = pe.MapNode(util.Select(index=0), name="pick_first_scan", iterfield=["inlist"])


    getmotion = pe.MapNode(util.Function(input_names=['flirt_out_mats'],
                                         output_names=['motion_params'],
                                         function=get_flirt_motion_parameters),
        name='getmotion', iterfield=['flirt_out_mats'])



    pipeline.connect(split, 'out_files', pick_ref, "inlist")
    pipeline.connect(split, 'out_files', pick0, "inlist")
    pipeline.connect(inputnode,'bvals', getb0, 'bvals')
    pipeline.connect(getb0, 'b0', pick_ref, "index")
    #pipeline.connect([(split, pick_ref, [("out_files", "inlist")]),
    #    (inputnode, pick_ref, [("ref_num", "index")])])

    coregistration = pe.MapNode(util.Function(input_names=['in_file', 'reference'],
        output_names=['out_file', 'out_matrix_file'],
        function = mapnode_coregistration),
        name = "coregister_b0",
        iterfield=["in_file","reference"])
    pipeline.connect([(pick_ref, coregistration, [("out", "in_file")]),
        (pick0, coregistration, [("out", "reference")])])

    art_mean = art_mean_workflow()
    art_mean.inputs.inputspec.parameter_source='FSL'

    pipeline.connect(coregistration,'out_matrix_file', getmotion, 'flirt_out_mats')
    pipeline.connect(getmotion, 'motion_params', art_mean, 'inputspec.realignment_parameters')

    merge = pe.MapNode(fsl.Merge(dimension="t"), name="merge", iterfield=["in_files"])
    pipeline.connect([(coregistration, merge, [("out_file", "in_files")])
    ])

    pipeline.connect(merge,'merged_file',art_mean,'inputspec.realigned_files')

    outputnode = pe.Node(interface = util.IdentityInterface(fields=["eddy_corrected","mean_image","coreg_mat_files"]),
        name="outputnode")

    pipeline.connect(art_mean, 'outputspec.mean_image', outputnode, "mean_image")

    coreg_all = coregistration.clone("coregister_all")
    pipeline.connect(split, 'out_files', coreg_all, 'in_file')
    pipeline.connect(art_mean,'outputspec.mean_image',coreg_all,"reference")

    merge_all = merge.clone("merge_all")
    pipeline.connect([(coreg_all, merge_all, [("out_file", "in_files")])
    ])
    pipeline.connect(coreg_all, 'out_matrix_file', outputnode, "coreg_mat_files")
    pipeline.connect(merge_all,'merged_file',outputnode,"eddy_corrected")

    return pipeline

"""
Connect the nodes
"""
def get_aparc_aseg(files):
    for name in files:
        if 'aparc+aseg' in name:
            return name
    raise ValueError('aparc+aseg.mgz not found')

def create_getmask_flow(name='getmask', dilate_mask=True):
    """Registers a source file to freesurfer space and create a brain mask in
source space

Requires fsl tools for initializing registration

Parameters
----------

name : string
name of workflow
dilate_mask : boolean
indicates whether to dilate mask or not

Example
-------

>>> getmask = create_getmask_flow()
>>> getmask.inputs.inputspec.source_file = 'mean.nii'
>>> getmask.inputs.inputspec.subject_id = 's1'
>>> getmask.inputs.inputspec.subjects_dir = '.'
>>> getmask.inputs.inputspec.contrast_type = 't2'


Inputs::

inputspec.source_file : reference image for mask generation
inputspec.subject_id : freesurfer subject id
inputspec.subjects_dir : freesurfer subjects directory
inputspec.contrast_type : MR contrast of reference image

Outputs::

outputspec.mask_file : binary mask file in reference image space
outputspec.reg_file : registration file that maps reference image to
freesurfer space
outputspec.reg_cost : cost of registration (useful for detecting misalignment)
"""
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu
    import nipype.interfaces.freesurfer as fs
    import nipype.interfaces.io as nio
    """
Initialize the workflow
"""

    getmask = pe.Workflow(name=name)

    """
Define the inputs to the workflow.
"""

    inputnode = pe.Node(niu.IdentityInterface(fields=['source_file',
                                                      'subject_id',
                                                      'subjects_dir',
                                                      'contrast_type']),
        name='inputspec')

    """
Define all the nodes of the workflow:

fssource: used to retrieve aseg.mgz
threshold : binarize aseg
register : coregister source file to freesurfer space
voltransform: convert binarized aseg to source file space

"""

    fssource = pe.Node(nio.FreeSurferSource(),
        name = 'fssource')
    threshold = pe.Node(fs.Binarize(min=0.5, out_type='nii'),
        name='threshold')
    register = pe.MapNode(fs.BBRegister(init='fsl'),
        iterfield=['source_file'],
        name='register')
    voltransform = pe.MapNode(fs.ApplyVolTransform(inverse=True),
        iterfield=['source_file', 'reg_file'],
        name='transform')

    """
Connect the nodes
"""

    getmask.connect([
        (inputnode, fssource, [('subject_id','subject_id'),
            ('subjects_dir','subjects_dir')]),
        (inputnode, register, [('source_file', 'source_file'),
            ('subject_id', 'subject_id'),
            ('subjects_dir', 'subjects_dir'),
            ('contrast_type', 'contrast_type')]),
        (inputnode, voltransform, [('subjects_dir', 'subjects_dir'),
            ('source_file', 'source_file')]),
        (fssource, threshold, [(('aparc_aseg', get_aparc_aseg), 'in_file')]),
        (register, voltransform, [('out_reg_file','reg_file')]),
        (threshold, voltransform, [('binary_file','target_file')])
    ])


    """
Add remaining nodes and connections

dilate : dilate the transformed file in source space
threshold2 : binarize transformed file
"""

    threshold2 = pe.MapNode(fs.Binarize(min=0.5, out_type='nii'),
        iterfield=['in_file'],
        name='threshold2')
    if dilate_mask:
        threshold2.inputs.dilate = 1
    getmask.connect([
        (voltransform, threshold2, [('transformed_file', 'in_file')])
    ])

    """
Setup an outputnode that defines relevant inputs of the workflow.
"""

    outputnode = pe.Node(niu.IdentityInterface(fields=["mask_file",
                                                       "reg_file",
                                                       "reg_cost"
    ]),
        name="outputspec")
    getmask.connect([
        (register, outputnode, [("out_reg_file", "reg_file")]),
        (register, outputnode, [("min_cost_file", "reg_cost")]),
        (threshold2, outputnode, [("binary_file", "mask_file")]),
    ])
    return getmask

def create_get_stats_flow(name='getstats', withreg=False):
    """Retrieves stats from labels

    Parameters
    ----------

    name : string
        name of workflow
    withreg : boolean
        indicates whether to register source to label

    Example
    -------


    Inputs::

           inputspec.source_file : reference image for mask generation
           inputspec.label_file : label file from which to get ROIs

           (optionally with registration)
           inputspec.reg_file : bbreg file (assumes reg from source to label
           inputspec.inverse : boolean whether to invert the registration
           inputspec.subjects_dir : freesurfer subjects directory

    Outputs::

           outputspec.stats_file : stats file
    """
    import nipype.pipeline.engine as pe
    import nipype.interfaces.freesurfer as fs
    import nipype.interfaces.utility as niu

    """
    Initialize the workflow
    """

    getstats = pe.Workflow(name=name)

    """
    Define the inputs to the workflow.
    """

    if withreg:
        inputnode = pe.Node(niu.IdentityInterface(fields=['source_file',
                                                          'label_file',
                                                          'reg_file',
                                                          'subjects_dir','inverse']),
            name='inputspec')
    else:
        inputnode = pe.Node(niu.IdentityInterface(fields=['source_file',
                                                          'label_file']),
            name='inputspec')


    statnode = pe.MapNode(fs.SegStats(),
        iterfield=['segmentation_file','in_file'],
        name='segstats')

    """
    Convert between source and label spaces if registration info is provided

    """
    if withreg:
        voltransform = pe.MapNode(fs.ApplyVolTransform(inverse=True, interp='nearest'),
            iterfield=['source_file', 'reg_file'],
            name='transform')
        getstats.connect(inputnode, 'reg_file', voltransform, 'reg_file')
        getstats.connect(inputnode, 'source_file', voltransform, 'source_file')
        getstats.connect(inputnode, 'label_file', voltransform, 'target_file')
        getstats.connect(inputnode, 'subjects_dir', voltransform, 'subjects_dir')

        def switch_labels(inverse, transform_output, source_file, label_file):
            if inverse:
                return transform_output, source_file
            else:
                return label_file, transform_output

        chooser = pe.MapNode(niu.Function(input_names = ['inverse',
                                                         'transform_output',
                                                         'source_file',
                                                         'label_file'],
            output_names = ['label_file',
                            'source_file'],
            function=switch_labels),
            iterfield=['transform_output','source_file'],
            name='chooser')
        getstats.connect(inputnode,'source_file', chooser, 'source_file')
        getstats.connect(inputnode,'label_file', chooser, 'label_file')
        getstats.connect(inputnode,'inverse', chooser, 'inverse')
        getstats.connect(voltransform, 'transformed_file', chooser, 'transform_output')
        getstats.connect(chooser, 'label_file', statnode, 'segmentation_file')
        getstats.connect(chooser, 'source_file', statnode, 'in_file')
    else:
        getstats.connect(inputnode, 'label_file', statnode, 'segmentation_file')
        getstats.connect(inputnode, 'source_file', statnode, 'in_file')

    """
    Setup an outputnode that defines relevant inputs of the workflow.
    """

    outputnode = pe.Node(niu.IdentityInterface(fields=["stats_file"
    ]),
        name="outputspec")
    getstats.connect([
        (statnode, outputnode, [("summary_file", "stats_file")]),
    ])
    return getstats