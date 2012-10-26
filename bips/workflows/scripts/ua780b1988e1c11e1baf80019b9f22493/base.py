from bips.workflows.scripts.ua780b1988e1c11e1baf80019b9f22493.utils import (convert_affine, get_image_dimensions)


def get_struct_norm_workflow(name='normalize_struct'):
    """ Base structural workflow for normalization

    Parameters
    ----------
    name : name of workflow. Default = 'normalize_struct'

    Inputs
    ------
    inputspec.template_file :
    inputspec.brain :
    inputspec.segmentation :

    Outputs
    -------
    outputspec.warp_field :
    outputspec.affine_transformation :
    outputspec.inverse_warp :
    outputspec.unwarped_brain :
    outputspec.warped_brain :

    Returns
    -------
    workflow : structural normalization workflow
    """
    #inputs to workflow
    import nipype.interfaces.freesurfer as fs
    import nipype.interfaces.ants as ants
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    inputspec = pe.Node(
        util.IdentityInterface(
            fields=['template_file', 'brain', 'segmentation']),
        name='inputspec')

    #converts brain from freesurfer mgz into nii
    brain_2nii = pe.Node(
        fs.preprocess.MRIConvert(),
        name='brain_2nii')
    brain_2nii.inputs.out_type = 'nii'

    #converts freesurfer segmentation into nii
    aparcaseg_2nii = pe.Node(
        fs.preprocess.MRIConvert(),
        name='aparcaseg_2nii')
    aparcaseg_2nii.inputs.out_type = 'nii'

    #create mask excluding everything outside of cortical surface (from
    #freesurfer segmentation file)
    create_mask = pe.Node(
        fs.model.Binarize(),
        name='create_mask')
    create_mask.inputs.min = 1
    create_mask.inputs.dilate = 1
    create_mask.inputs.out_type = 'nii'

    #apply mask to anatomical
    apply_mask = pe.Node(
        fs.utils.ApplyMask(),
        name='apply_mask')

    #use ANTS to warp the masked anatomical image to a template image
    warp_brain = pe.Node(
        ants.GenWarpFields(),
        name='warp_brain')

    #collects workflow outputs
    outputspec = pe.Node(
        util.IdentityInterface(
            fields=['warp_field', 'affine_transformation',
                'inverse_warp', 'unwarped_brain', 'warped_brain']),
        name='outputspec')

    normalize_struct = pe.Workflow(name=name)
    normalize_struct.connect([
        (inputspec, warp_brain, [('template_file', 'reference_image')]),
        (inputspec, brain_2nii, [('brain', 'in_file')]),
        (inputspec, aparcaseg_2nii, [('segmentation', 'in_file')]),
        (aparcaseg_2nii, create_mask, [('out_file', 'in_file')]),
        (create_mask, apply_mask, [('binary_file', 'mask_file')]),
        (brain_2nii, apply_mask, [('out_file', 'in_file')]),
        (apply_mask, warp_brain, [('out_file', 'input_image')]),
        (apply_mask, outputspec, [('out_file', 'unwarped_brain')]),
        (warp_brain, outputspec, [('affine_transformation',
                                   'affine_transformation'),
            ('warp_field', 'warp_field'),
            ('inverse_warp_field', 'inverse_warp'),
            ('output_file', 'warped_brain')])])

    return normalize_struct


def get_post_struct_norm_workflow(name='normalize_post_struct'):
    """ Base post-structural workflow for normalization

    Parameters
    ----------
    name : name of workflow. Default = 'normalize_post_struct'

    Inputs
    ------
    inputspec.template_file :
    inputspec.unwarped_brain :
    inputspec.warp_field :
    inputspec.affine_transformation :
    inputspec.out_fsl_file :
    inputspec.moving_image :
    inputspec.mean_func :

    Outputs
    -------
    outputspec.warped_image :

    Returns
    -------
    workflow : post-structural normalization workflow
    """
    #inputs to workflow
    import nipype.interfaces.freesurfer as fs
    import nipype.interfaces.ants as ants
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    inputspec = pe.Node(
        util.IdentityInterface(
            fields=['template_file', 'unwarped_brain', 'warp_field',
                'affine_transformation', 'out_fsl_file', 'moving_image',
                'mean_func']),
        name='inputspec')

    #makes fsl-style coregistration ANTS compatible
    fsl_reg_2_itk = pe.Node(
        util.Function(
            input_names=['unwarped_brain', 'mean_func', 'out_fsl_file'],
            output_names=['fsl2antsAffine'],
            function=convert_affine),
        name='fsl_reg_2_itk')

    #collects series of transformations to be applied to the moving images
    collect_transforms = pe.Node(
        util.Merge(3),
        name='collect_transforms')

    #performs series of transformations on moving images
    warp_images = pe.MapNode(
        ants.WarpTimeSeriesImageMultiTransform(),
        name='warp_images',
        iterfield=['moving_image', 'dimension'])

    #collects workflow outputs
    outputspec = pe.Node(
        util.IdentityInterface(
            fields=['warped_image']),
        name='outputspec')

    #initializes and connects workflow nodes
    normalize_post_struct = pe.Workflow(name=name)
    normalize_post_struct.connect([
        (inputspec, fsl_reg_2_itk, [('unwarped_brain', 'unwarped_brain')]),
        (inputspec, fsl_reg_2_itk, [('out_fsl_file', 'out_fsl_file')]),
        (inputspec, fsl_reg_2_itk, [('mean_func', 'mean_func')]),
        (fsl_reg_2_itk, collect_transforms, [('fsl2antsAffine', 'in3')]),
        (inputspec, collect_transforms, [('warp_field', 'in1'),
            ('affine_transformation', 'in2')]),
        (inputspec, warp_images, [('moving_image', 'moving_image')]),
        (inputspec, warp_images, [(('moving_image', get_image_dimensions),
                                    'dimension')]),
        (inputspec, warp_images, [('template_file', 'reference_image')]),
        (collect_transforms, warp_images, [('out',
                                    'transformation_series')]),
        (warp_images, outputspec, [('output_image', 'warped_image')])])

    return normalize_post_struct


def get_full_norm_workflow(name="normalize_struct_and_post"):
    """ Combined tructural and post-structural workflow for normalization

    Parameters
    ----------
    name : name of workflow. Default = 'normalize_struct_and_post'

    Inputs
    ------
    inputspec.template_file :
    inputspec.brain :
    inputspec.segmentation :
    inputspec.out_fsl_file :
    inputspec.moving_image :
    inputspec.mean_func :

    Outputs
    -------
    outputspec.warped_image : normalized moving_image image
    outputspec.warp_field :
    outputspec.affine_transformation :
    outputspec.inverse_warp :
    outputspec.unwarped_brain :
    outputspec.warped_brain : normalized 

    Returns
    -------
    workflow : combined structural and post-structural normalization workflow
    """
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    normalize_struct = get_struct_norm_workflow()
    normalize_post_struct = get_post_struct_norm_workflow()

    inputspec = pe.Node(
        util.IdentityInterface(
            fields=['template_file', 'brain', 'segmentation', 'out_fsl_file',
                'moving_image', 'mean_func']),
        name='inputspec')

    outputspec = pe.Node(
        util.IdentityInterface(
            fields=['warped_image', 'warp_field', 'affine_transformation',
                'inverse_warp', 'unwarped_brain', 'warped_brain']),
        name='outputspec')

    combined_workflow = pe.Workflow(name=name)
    combined_workflow.connect([
        (inputspec, normalize_struct, [('template_file',
                                        'inputspec.template_file')]),
        (inputspec, normalize_struct, [('brain', 'inputspec.brain')]),
        (inputspec, normalize_struct, [('segmentation',
                                        'inputspec.segmentation')]),
        (inputspec, normalize_post_struct, [('template_file',
                                        'inputspec.template_file')]),
        (normalize_struct, normalize_post_struct, [('outputspec.warp_field',
                                        'inputspec.warp_field')]),
        (normalize_struct, normalize_post_struct, [(
                                        'outputspec.affine_transformation',
                                        'inputspec.affine_transformation')]),
        (normalize_struct, normalize_post_struct, [(
                                        'outputspec.unwarped_brain',
                                        'inputspec.unwarped_brain')]),
        (inputspec, normalize_post_struct, [('out_fsl_file',
                                        'inputspec.out_fsl_file')]),
        (inputspec, normalize_post_struct, [('moving_image',
                                        'inputspec.moving_image')]),
        (inputspec, normalize_post_struct, [('mean_func',
                                        'inputspec.mean_func')]),
        (normalize_struct, outputspec, [('outputspec.warp_field',
                                        'warp_field')]),
        (normalize_struct, outputspec, [('outputspec.affine_transformation',
                                        'affine_transformation')]),
        (normalize_struct, outputspec, [('outputspec.inverse_warp',
                                        'inverse_warp')]),
        (normalize_struct, outputspec, [('outputspec.unwarped_brain',
                                        'unwarped_brain')]),
        (normalize_struct, outputspec, [('outputspec.warped_brain',
                                        'warped_brain')]),
        (normalize_post_struct, outputspec, [('outputspec.warped_image',
                                        'warped_image')])])

    return combined_workflow
