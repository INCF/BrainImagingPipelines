from .base import MetaWorkflow, load_config, register_workflow
from .workflow1 import config_ui
from workflow1 import config as baseconfig
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits
from scripts.u0a14c5b5899911e1bca80023dfa375f2.base import create_rest_prep


mwf = MetaWorkflow()
mwf.uuid = 'f7165f208e1511e19bee0019b9f22493'
mwf.tags = ['ants', 'normalize', 'warp', 'struct']
mwf.help = """ Base structural workflow for normalization

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

class config(baseconfig):
    highpass_freq = traits.Float()
    lowpass_freq = traits.Float()
    reg_params = traits.BaseTuple(traits.Bool, traits.Bool, traits.Bool,
                                  traits.Bool, traits.Bool)

def create_config():
    c = config()
    c.uuid = mwf.uuid
    return c

mwf.config_ui = create_config


def get_struct_norm_workflow(name='normalize_struct'):
    #inputs to workflow
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


def main(config):
    c = load_config(config)
    workflow = get_struct_norm_workflow()
    workflow.base_dir = c["working_dir"]

    if not os.environ['SUBJECTS_DIR'] == c["surf_dir"]:
        print "Your SUBJECTS_DIR is incorrect!"
        print "export SUBJECTS_DIR=%s"%c["surf_dir"]
        
    else:
        if c["run_on_grid"]:
            workflow.run(plugin=c["plugin"], plugin_args=c["plugin_args"])
        else:
            workflow.run()
        
mwf.workflow_main_function = main
register_workflow(mwf)
