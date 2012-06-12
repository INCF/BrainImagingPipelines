import os

import traits.api as traits
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio

from .base import MetaWorkflow, load_config, register_workflow, debug_workflow

mwf = MetaWorkflow()
mwf.help = """
Resting State preprocessing workflow
====================================

"""

mwf.uuid = '7757e3168af611e1b9d5001e4fb1404c'
mwf.tags = ['resting-state','fMRI','preprocessing','fsl','freesurfer','nipy']
mwf.script_dir = 'u0a14c5b5899911e1bca80023dfa375f2'

# create_gui
from workflow1 import config as baseconfig
from workflow1 import get_dataflow

class config(baseconfig):
    highpass_freq = traits.Float()
    lowpass_freq = traits.Float()
    filtering_algorithm = traits.Enum("fsl","IIR","FIR")
    reg_params = traits.BaseTuple(traits.Bool, traits.Bool, traits.Bool,
                                  traits.Bool, traits.Bool)
    do_whitening = traits.Bool(False, usedefault=True)

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    return c

# create_workflow

from scripts.u0a14c5b5899911e1bca80023dfa375f2.base import create_rest_prep
from scripts.u0a14c5b5899911e1bca80023dfa375f2.utils import get_datasink, get_substitutions, get_regexp_substitutions

def prep_workflow(c, fieldmap):

    if fieldmap:
        modelflow = pe.Workflow(name='preprocfm')
    else:
        modelflow = pe.Workflow(name='preproc')


    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
                         name='subject_names')
    if not c.test_mode:
        infosource.iterables = ('subject_id', c.subjects)
    else:
        infosource.iterables = ('subject_id', c.subjects[:1])

    # generate datagrabber
    
    dataflow = get_dataflow(c)
    
    modelflow.connect(infosource, 'subject_id',
                      dataflow, 'subject_id')
    
    # generate preprocessing workflow
    preproc = create_rest_prep(fieldmap=fieldmap)

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

    # inputs
    preproc.inputs.inputspec.motion_correct_node = c.motion_correct_node
    preproc.inputs.inputspec.do_whitening = c.do_whitening
    preproc.inputs.inputspec.timepoints_to_remove = c.timepoints_to_remove
    preproc.inputs.inputspec.smooth_type = c.smooth_type
    preproc.inputs.inputspec.surface_fwhm = c.surface_fwhm
    preproc.inputs.inputspec.num_noise_components = c.num_noise_components
    preproc.inputs.inputspec.regress_before_PCA = c.regress_before_PCA
    preproc.crash_dir = c.crash_dir
    modelflow.connect(infosource, 'subject_id', preproc, 'inputspec.fssubject_id')
    preproc.inputs.inputspec.fssubject_dir = c.surf_dir
    preproc.get_node('fwhm_input').iterables = ('fwhm', c.fwhm)
    preproc.get_node('take_mean_art').get_node('strict_artifact_detect').inputs.save_plot = False
    preproc.inputs.inputspec.ad_normthresh = c.norm_thresh
    preproc.inputs.inputspec.ad_zthresh = c.z_thresh
    preproc.inputs.inputspec.tr = c.TR
    preproc.inputs.inputspec.do_slicetime = c.do_slicetiming
    if c.do_slicetiming:
        preproc.inputs.inputspec.sliceorder = c.SliceOrder
    else:
        preproc.inputs.inputspec.sliceorder = None

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

    modelflow.connect(dataflow,'func',
                      preproc,'inputspec.func')
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
                      sinkd, 'preproc.bbreg')
    modelflow.connect(preproc, 'outputspec.reg_fsl_file',
                      sinkd, 'preproc.bbreg.@fsl')
    modelflow.connect(preproc, 'outputspec.reg_cost',
                      sinkd, 'preproc.bbreg.@reg_cost')
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

    if c.do_zscore:
        modelflow.connect(preproc, 'outputspec.z_img',
                          sinkd, 'preproc.output.@zscored')
    modelflow.connect(preproc, 'outputspec.scaled_files',
                      sinkd, 'preproc.output.@fullspectrum')
    modelflow.connect(preproc, 'outputspec.bandpassed_file',
                      sinkd, 'preproc.output.@bandpassed')

    modelflow.base_dir = os.path.abspath(c.working_dir)
    return modelflow
    
def main(config_file):
    c = load_config(config_file, create_config)
    preprocess = prep_workflow(c, c.use_fieldmap)
    preprocess.config = {'execution': {'crashdump_dir': c.crash_dir}}
    
    if len(c.subjects) == 1:
        preprocess.write_graph(graph2use='exec',
                               dotfilename='single_subject_exec.dot')

    if c.debug:
        preprocess = debug_workflow(preprocess)

    if c.use_advanced_options:
        exec c.advanced_script

    if c.run_using_plugin:
        preprocess.run(plugin=c.plugin, plugin_args = c.plugin_args)
    else:
        preprocess.run()

def create_view():
    from traitsui.api import View, Item, Group, CSVListEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='uuid', style='readonly'),
                      Item(name='desc', style='readonly'),
                      label='Description', show_border=True),
                Group(Item(name='working_dir'),
                      Item(name='sink_dir'),
                      Item(name='crash_dir'),
                      Item(name='json_sink'),
                      Item(name='surf_dir'),
                      label='Directories', show_border=True),
                Group(Item(name='run_using_plugin'),
                      Item(name='plugin', enabled_when="run_using_plugin"),
                      Item(name='plugin_args', enabled_when="run_using_plugin"),
                      Item(name='test_mode'),
                      label='Execution Options', show_border=True),
                Group(Item(name='subjects', editor=CSVListEditor()),
                      Item(name='base_dir', ),
                      Item(name='func_template'),
                      Item(name='check_func_datagrabber'),
                      Item(name='run_datagrabber_without_submitting'),
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
                Group(Item(name="motion_correct_node"),
                      Item(name='TR'),
                      Item(name='do_slicetiming'),
                      Item(name='SliceOrder',editor=CSVListEditor()),
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

mwf.workflow_main_function = main
mwf.config_ui = create_config
mwf.config_view = create_view
register_workflow(mwf)