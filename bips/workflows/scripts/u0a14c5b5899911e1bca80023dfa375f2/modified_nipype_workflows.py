import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.fsl as fsl
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

    inputnode = pe.Node(interface = util.IdentityInterface(fields=["in_file", "bvals"]),
        name="inputnode")

    pipeline = pe.Workflow(name=name)

    split = pe.MapNode(fsl.Split(dimension='t'), name="split", iterfield=['in_file'])
    pipeline.connect([(inputnode, split, [("in_file", "in_file")])])

    getb0 = pe.Node(util.Function(input_names=['bvals'],
                                    output_names=['b0'],
                                    function=get_b0),
        name='get_b0_indices')

    pick_ref = pe.MapNode(util.Select(), name="pick_ref", iterfield=["inlist"])
    pick0 = pe.MapNode(util.Select(index=0), name="pick0_ref", iterfield=["inlist"])


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
        name = "coregistration",
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

    outputnode = pe.Node(interface = util.IdentityInterface(fields=["eddy_corrected","mean_image"]),
        name="outputnode")

    pipeline.connect(art_mean, 'outputspec.mean_image', outputnode, "mean_image")

    coreg_all = coregistration.clone("coreg_all")
    pipeline.connect(split, 'out_files', coreg_all, 'in_file')
    pipeline.connect(art_mean,'outputspec.mean_image',coreg_all,"reference")

    merge_all = merge.clone("merge_all")
    pipeline.connect([(coreg_all, merge_all, [("out_file", "in_files")])
    ])

    pipeline.connect(merge_all,'merged_file',outputnode,"eddy_corrected")

    return pipeline