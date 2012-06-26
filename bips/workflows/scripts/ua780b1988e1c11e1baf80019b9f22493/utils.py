# Utility Functions ---------------------------------------------------------


def convert_affine(unwarped_brain, mean_func, out_fsl_file):
    """Converts fsl-style Affine registration into ANTS compatible itk format

    Parameters
    ----------
    unwarped_brain : structural reference image
    mean_func : image that was coregistered
    out_fsl_file : fsl-style coregistration matrix

    Returns
    -------
    file : returns the filename corresponding to the converted registration
    """
    import os
    cmd = "c3d_affine_tool -ref %s -src %s %s -fsl2ras \
-oitk fsl2antsAffine.txt" % (unwarped_brain, mean_func, out_fsl_file)
    os.system(cmd)
    return os.path.abspath('fsl2antsAffine.txt')


def get_image_dimensions(images):
    """Return dimensions of list of images

    Parameters
    ----------
    images : list of filenames

    Returns
    -------
    list : returns dimensions of input image list
    """
    import nibabel as nb

    if isinstance(images, list):
        dims = []
        for image in images:
            dims.append(len(nb.load(image).get_shape()))
    else:
        dims = len(nb.load(images).get_shape())
    return dims

def pick_file(in_files,match):
    import os
    for file in in_files:
        if match == os.path.split(file)[1]:
            return file
    else:
        raise Exception("Can't find %s"%match)

def fs_segment(name="segment"):
    from nipype.interfaces.io import FreeSurferSource
    from nipype.interfaces.utility import IdentityInterface
    import nipype.interfaces.freesurfer as fs
    import nipype.pipeline.engine as pe
    import os
    wf = pe.Workflow(name=name)
    inputspec = pe.Node(IdentityInterface(fields=['subject_id',
                                                  'subjects_dir']),
        name="inputspec")
    fssource = pe.Node(FreeSurferSource(),name="fssource")
    wf.connect(inputspec,"subject_id",fssource,"subject_id")
    wf.connect(inputspec,"subjects_dir",fssource,"subjects_dir")
    bin_wm = pe.Node(fs.Binarize(),name="get_wm")
    bin_wm.inputs.out_type='nii.gz'
    bin_wm.inputs.match = [2,41]
    bin_gm = bin_wm.clone("get_gm")
    bin_gm.inputs.out_type='nii.gz'
    bin_gm.inputs.match=[3,42]
    bin_csf = bin_wm.clone("get_csf")
    bin_csf.inputs.out_type='nii.gz'
    bin_csf.inputs.match = [4, 5, 14, 15, 24, 31, 43, 44, 63]
    wf.connect(fssource,("ribbon",pick_file,'ribbon.mgz'),bin_wm,"in_file")
    wf.connect(fssource,("ribbon",pick_file,'ribbon.mgz'),bin_gm,"in_file")
    wf.connect(fssource,("aparc_aseg",pick_file,'aparc+aseg.mgz'),bin_csf,"in_file")
    outputspec=pe.Node(IdentityInterface(fields=["gm","wm","csf"]),
        name='outputspec')
    wf.connect(bin_wm,"binary_file",outputspec,"wm")
    wf.connect(bin_gm,"binary_file",outputspec,"gm")
    wf.connect(bin_csf,"binary_file",outputspec,"csf")
    return wf

def warp_segments(name="warp_segments"):
    import nipype.pipeline.engine as pe
    from nipype.interfaces.utility import IdentityInterface
    wf = pe.Workflow(name=name)
    seg = fs_segment()
    inputspec = pe.Node(IdentityInterface(fields=['subject_id',
                                                  'subjects_dir',
                                                  'warp_file',
                                                  'ants_affine',
                                                  'warped_brain']),
        name="inputspec")
    from nipype.interfaces.ants import ApplyTransforms
    ap = pe.MapNode(ApplyTransforms(),name="apply_transforms",iterfield=["input_image"])
    wf.connect(inputspec,"subject_id",seg,"inputspec.subject_id")
    wf.connect(inputspec,"subjects_dir",seg,"inputspec.subjects_dir")
    from nipype.interfaces.utility import Merge
    merge = pe.Node(Merge(3),name="merge")
    wf.connect(seg,"outputspec.wm",merge,'in1')
    wf.connect(seg,"outputspec.gm",merge,"in2")
    wf.connect(seg,"outputspec.csf",merge,"in3")
    wf.connect(merge,"out",ap,"input_image")
    wf.connect(inputspec,"warped_brain",ap,"reference_image")
    merge1 = pe.Node(Merge(2),name="get_transformations")
    wf.connect(inputspec,"warp_file",merge1,"in1")
    wf.connect(inputspec,"ants_affine",merge1,"in2")
    wf.connect(merge1,"out",ap,"transformation_files")
    outputspec=pe.Node(IdentityInterface(fields=["out_files"]),name='outputspec')
    wf.connect(ap,"output_image",outputspec,"out_files")
    return wf