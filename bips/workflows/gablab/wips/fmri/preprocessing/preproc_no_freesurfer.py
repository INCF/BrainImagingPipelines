import os
import traits.api as traits
from .....base import MetaWorkflow, load_config, register_workflow, debug_workflow

"""
Part 1: Define a MetaWorkflow
        - help (description)
        - uuid
        - tags
"""

mwf = MetaWorkflow()
mwf.help = """
fMRI preprocessing workflow - NO RECON ALL
===========================================

"""

mwf.uuid = '8b5b551442fc11e284a600259080ab1a'
mwf.tags = ['resting','fMRI','preprocessing','fsl','nipy','task']
mwf.script_dir = 'u0a14c5b5899911e1bca80023dfa375f2'

"""
Part 2: Define the config class & create_config function
        - The config_ui attribute of MetaWorkflow is defined as the create_config function
"""

# create_gui
from ...scripts.workflow1 import config as baseconfig
from .....flexible_datagrabber import Data, DataBase

class config(baseconfig):
    highpass_freq = traits.Float()
    lowpass_freq = traits.Float()
    filtering_algorithm = traits.Enum("fsl","IIR","FIR","Fourier")
    reg_params = traits.BaseTuple(traits.Bool(desc="motion parameters"),
        traits.Bool(desc="norm components"),
        traits.Bool(desc="noise components (CompCor)"),
        traits.Bool(desc='gloabl signal (NOT RECOMMENDED!)'),
        traits.Bool(desc="art_outliers"),
        traits.Bool(desc="motion derivatives"))
    do_despike = traits.Bool(False,usedefault=True)
    do_whitening = traits.Bool(False, usedefault=True)
    use_metadata = traits.Bool(True)
    update_hash = traits.Bool(False)
    datagrabber = traits.Instance(Data, ())
    segmentation_type = traits.Enum('FAST','Atropos')
    save_script_only = traits.Bool(False)

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    dg = Data(['functionals',
               'structural'])
    foo = DataBase()
    foo.name="subject_id"
    foo.iterable = True
    foo.values=["sub01","sub02"]

    dg.template= '*'
    dg.field_template =  dict(functionals='%s/functional.nii.gz',
        structural='%s/structural.nii.gz')
    dg.template_args = dict(functionals=[['subject_id']],
        structural=[['subject_id']])
    dg.fields = [foo]

    c.datagrabber = dg

    return c

mwf.config_ui = create_config

"""
Part 3: Create a View
        - MetaWorkflow.config_view is a function that returns a View object
        - Make sure the View is organized into Groups
"""

def create_view():
    from traitsui.api import View, Item, Group, CSVListEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='uuid', style='readonly'),
        Item(name='desc', style='readonly'),
        label='Description', show_border=True),
        Group(Item(name='working_dir'),
            Item(name='sink_dir'),
            Item(name='crash_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin',enabled_when='save_script_only'),Item('save_script_only'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'),Item('update_hash'),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),
            Item(name='timepoints_to_remove'),
            label='Subjects', show_border=True),
        Group(Item(name='use_fieldmap'),
            Item(name='field_dir', enabled_when="use_fieldmap"),
            Item(name='magnitude_template',
                enabled_when="use_fieldmap"),
            Item(name='phase_template', enabled_when="use_fieldmap"),
            Item(name='check_field_datagrabber',
                enabled_when="use_fieldmap"),
            Item(name='echospacing',enabled_when="use_fieldmap"),
            Item(name='TE_diff',enabled_when="use_fieldmap"),
            Item(name='sigma',enabled_when="use_fieldmap"),
            label='Fieldmap',show_border=True),
        Group(Item('segmentation_type'),label='Structural',show_border=True),
        Group(Item(name="do_despike"),
            Item(name="motion_correct_node"),
            Item(name='TR', enabled_when="not use_metadata"),
            Item(name='do_slicetiming'),
            Item(name="use_metadata"),
            Item(name='SliceOrder',editor=CSVListEditor(),enabled_when="not use_metadata or not do_slicetiming"),
            Item(name='loops',enabled_when="motion_correct_node=='nipy' ", editor=CSVListEditor()),
            Item(name='speedup',enabled_when="motion_correct_node=='nipy' ", editor=CSVListEditor()),
            label='Motion Correction', show_border=True),
        Group(Item(name='norm_thresh'),
            Item(name='z_thresh'),
            label='Artifact Detection',show_border=True),
        Group(Item(name='compcor_select'),
            Item(name='num_noise_components'),
            Item(name='regress_before_PCA'),
            label='CompCor',show_border=True),
        Group(Item(name='reg_params'),
            label='Nuisance Filtering',show_border=True),
        Group(Item(name='smooth_type'),
            Item(name='fwhm', editor=CSVListEditor()),
            Item(name='surface_fwhm'),
            label='Smoothing',show_border=True),
        Group(Item(name='highpass_freq'),
            Item(name='lowpass_freq'),
            Item(name='filtering_algorithm'),
            Item(name='do_whitening'),
            label='Bandpass Filter',show_border=True),
        Group(Item(name='do_zscore'),
            Item(name='use_advanced_options'),
            Item(name='advanced_script',enabled_when='use_advanced_options'),
            Item(name='debug'),
            label='Advanced',show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Part 4: Workflow Construction
        - Write a function that returns the workflow
        - The workflow should take a config object as the first argument
"""

# create_workflow



def prep_workflow(c=create_config()):
    """Creates a project-specific fMRI preprocessing workflow

Parameters
----------

c : Config objects

Returns
-------

Preprocessing nipype workflow

"""
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    import nipype.interfaces.io as nio
    from ...scripts.base import create_rest_NoFS
    from ...scripts.utils import get_datasink, get_substitutions, get_regexp_substitutions
    from fmri_preprocessing import extract_meta

    fieldmap = c.use_fieldmap
    if fieldmap:
        modelflow = pe.Workflow(name='preprocfm')
    else:
        modelflow = pe.Workflow(name='preproc')

    datagrabber = c.datagrabber.create_dataflow()
    infosource = datagrabber.get_node('subject_id_iterable')

    # generate datagrabber

        # generate preprocessing workflow
    preproc = create_rest_NoFS(use_fieldmap=fieldmap,segmentation_type=c.segmentation_type)

    if not c.do_zscore:
        z_score = preproc.get_node('z_score')
        preproc.remove_nodes([z_score])

    # make a data sink
    sinkd = get_datasink(c.sink_dir, c.fwhm)

    if fieldmap:
        datasource_fieldmap = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
            outfields=['mag','phase']),
            name = "fieldmap_datagrabber")
        datasource_fieldmap.inputs.base_directory = c.field_dir
        datasource_fieldmap.inputs.template ='*'
        datasource_fieldmap.inputs.sort_filelist = True
        datasource_fieldmap.inputs.field_template = dict(mag=c.magnitude_template,
            phase=c.phase_template)
        datasource_fieldmap.inputs.template_args = dict(mag=[['subject_id']],
            phase=[['subject_id']])

        preproc.inputs.inputspec.FM_Echo_spacing = c.echospacing
        preproc.inputs.inputspec.FM_TEdiff = c.TE_diff
        preproc.inputs.inputspec.FM_sigma = c.sigma
        modelflow.connect(infosource, 'subject_id',
            datasource_fieldmap, 'subject_id')
        modelflow.connect(datasource_fieldmap,'mag',
            preproc,'fieldmap_input.magnitude_file')
        modelflow.connect(datasource_fieldmap,'phase',
            preproc,'fieldmap_input.phase_file')
        modelflow.connect(preproc, 'outputspec.vsm_file',
            sinkd, 'preproc.fieldmap')
        modelflow.connect(preproc, 'outputspec.FM_unwarped_mean',
            sinkd, 'preproc.mean')
    else:
        modelflow.connect(preproc, 'outputspec.mean',
            sinkd, 'preproc.mean')

    if c.use_metadata:
        get_meta = pe.Node(util.Function(input_names=['func'],output_names=['so','tr'],function=extract_meta),name="get_metadata")
        modelflow.connect(datagrabber,'datagrabber.functionals',get_meta, 'func')
        modelflow.connect(get_meta,'so',preproc,"inputspec.sliceorder")
        modelflow.connect(get_meta,'tr',preproc,"inputspec.tr")
    else:
        preproc.inputs.inputspec.sliceorder = c.SliceOrder
        preproc.inputs.inputspec.tr = c.TR

    # inputs
    preproc.inputs.inputspec.motion_correct_node = c.motion_correct_node
    preproc.inputs.inputspec.realign_parameters = {"loops":c.loops,
                                                   "speedup":c.speedup}
    preproc.inputs.inputspec.do_whitening = c.do_whitening
    preproc.inputs.inputspec.timepoints_to_remove = c.timepoints_to_remove
    preproc.inputs.inputspec.smooth_type = c.smooth_type
    preproc.inputs.inputspec.do_despike = c.do_despike
    preproc.inputs.inputspec.surface_fwhm = c.surface_fwhm
    preproc.inputs.inputspec.num_noise_components = c.num_noise_components
    preproc.inputs.inputspec.regress_before_PCA = c.regress_before_PCA
    preproc.crash_dir = c.crash_dir

    preproc.get_node('fwhm_input').iterables = ('fwhm', c.fwhm)
    preproc.get_node('take_mean_art').get_node('strict_artifact_detect').inputs.save_plot = False
    preproc.inputs.inputspec.ad_normthresh = c.norm_thresh
    preproc.inputs.inputspec.ad_zthresh = c.z_thresh
    preproc.inputs.inputspec.tr = c.TR
    preproc.inputs.inputspec.do_slicetime = c.do_slicetiming


    preproc.inputs.inputspec.compcor_select = c.compcor_select

    preproc.inputs.inputspec.filter_type = c.filtering_algorithm
    preproc.inputs.inputspec.highpass_freq = c.highpass_freq
    preproc.inputs.inputspec.lowpass_freq = c.lowpass_freq

    preproc.inputs.inputspec.reg_params = c.reg_params


    modelflow.connect(infosource, 'subject_id', sinkd, 'container')
    modelflow.connect(infosource, ('subject_id', get_substitutions, fieldmap),
        sinkd, 'substitutions')
    modelflow.connect(infosource, ('subject_id', get_regexp_substitutions,
                                   fieldmap),
        sinkd, 'regexp_substitutions')

    # make connections

    modelflow.connect(datagrabber,'datagrabber.functionals',
        preproc,'inputspec.func')
    modelflow.connect(datagrabber,'datagrabber.structural',
        preproc,'inputspec.anatomical')
    modelflow.connect(preproc, 'outputspec.motion_parameters',
        sinkd, 'preproc.motion')
    #modelflow.connect(preproc, 'plot_motion.out_file',
    #                  sinkd, 'preproc.motion.@plots')
    modelflow.connect(preproc, 'outputspec.mask',
        sinkd, 'preproc.mask')
    modelflow.connect(preproc, 'outputspec.outlier_files',
        sinkd, 'preproc.art')
    modelflow.connect(preproc, 'outputspec.outlier_stat_files',
        sinkd, 'preproc.art.@stats')
    modelflow.connect(preproc, 'outputspec.intensity_files',
        sinkd, 'preproc.art.@intensity')
    modelflow.connect(preproc, 'outputspec.combined_motion',
        sinkd, 'preproc.art.@norm')
    modelflow.connect(preproc, 'outputspec.reg_file',
        sinkd, 'preproc.flirtreg')
    modelflow.connect(preproc, 'mask_segment_register.outputspec.warped_struct',
        sinkd, 'preproc.flirtreg.@flirtstruct')
    modelflow.connect(preproc, 'mask_segment_register.outputspec.bet_struct',
        sinkd, 'bet')
    modelflow.connect(preproc, 'mask_segment_register.outputspec.inverse_reg',
        sinkd, 'flirtreg.func2struct')
    modelflow.connect(preproc, 'outputspec.highpassed_files',
        sinkd, 'preproc.highpass')
    modelflow.connect(preproc, 'outputspec.tsnr_file',
        sinkd, 'preproc.tsnr')
    modelflow.connect(preproc, 'outputspec.stddev_file',
        sinkd, 'preproc.tsnr.@stddev')
    modelflow.connect(preproc, 'outputspec.tsnr_detrended',
        sinkd, 'preproc.tsnr.@detrended')
    modelflow.connect(preproc, 'outputspec.filter_file',
        sinkd, 'preproc.regressors')
    modelflow.connect(preproc, 'outputspec.csf_mask',
        sinkd, 'preproc.compcor.@acompcor')
    modelflow.connect(preproc, 'outputspec.noise_mask',
        sinkd, 'preproc.compcor.@tcompcor')
    modelflow.connect(preproc, 'outputspec.noise_components',
        sinkd, 'preproc.noise_components')

    if c.do_zscore:
        modelflow.connect(preproc, 'outputspec.z_img',
            sinkd, 'preproc.output.zscored')
    modelflow.connect(preproc, 'outputspec.scaled_files',
        sinkd, 'preproc.output.fullspectrum')
    modelflow.connect(preproc, 'outputspec.bandpassed_file',
        sinkd, 'preproc.output.bandpassed')

    modelflow.base_dir = os.path.abspath(c.working_dir)
    return modelflow

mwf.workflow_function = prep_workflow

"""
Part 5: Define the main function
        - In the main function the path to a json file is passed as the only argument
        - The json file is loaded into a config instance, c
        - The workflow function is called with c and runs
"""

def main(config_file):
    """Runs the fMRI preprocessing workflow

Parameters
----------

config_file : JSON file with configuration parameters

"""
    c = load_config(config_file, create_config)
    preprocess = prep_workflow(c)
    preprocess.config = {'execution': {'crashdump_dir': c.crash_dir, 'job_finished_timeout' : 14}}

    if len(c.subjects) == 1:
        preprocess.write_graph(graph2use='exec',
            dotfilename='single_subject_exec.dot')

    if c.debug:
        preprocess = debug_workflow(preprocess)

    if c.use_advanced_options:
        exec c.advanced_script

    preprocess.export(os.path.join(c.base_dir,'bips_'))
    if c.save_script_only:
        return 0

    if c.run_using_plugin:
        preprocess.run(plugin=c.plugin, plugin_args = c.plugin_args)
    else:
        preprocess.run()

mwf.workflow_main_function = main

"""
Part 6: Register the Workflow
"""
register_workflow(mwf)

