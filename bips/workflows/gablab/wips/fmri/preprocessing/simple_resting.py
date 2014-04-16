from bips.workflows.base import BaseWorkflowConfig
__author__ = 'keshavan'
from .....base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from .....flexible_datagrabber import Data, DataBase
"""
Part 1: Define a MetaWorkflow
"""

desc = """
Simple Preprocessing
====================

This preprocessing just realigns and registers.
Use a different worflow for better preprocessing.

"""
mwf = MetaWorkflow()
mwf.uuid = '303e5cce81c411e29e0900259080ab1a'
mwf.tags = ['fMRI','preprocessing','resting','test']
mwf.help = desc

"""
Part 2: Define the config class & create_config function
"""

# config_ui
class config(BaseWorkflowConfig):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc='Workflow description')
    # Directories
    sink_dir = Directory(mandatory=False, desc="Location to store BIPS results")
    surf_dir = Directory(mandatory=True, desc= "Freesurfer subjects directory")
    save_script_only = traits.Bool(False)
    
    # Subjects
    datagrabber = traits.Instance(Data, ())
    # Motion Correction

    do_slicetiming = Bool(True, usedefault=True, desc="Perform slice timing correction")
    SliceOrder = traits.List(traits.Int)
    TR = traits.Float(1.0,mandatory=True, desc = "TR of functional")
    motion_correct_node = traits.Enum('nipy','fsl','spm','afni',
        desc="motion correction algorithm to use",
        usedefault=True,)
    use_metadata = traits.Bool(True)
    order = traits.Enum('motion_slicetime','slicetime_motion',use_default=True)
    loops = traits.List([5],traits.Int(5),usedefault=True)
    #between_loops = traits.Either("None",traits.List([5]),usedefault=True)
    speedup = traits.List([5],traits.Int(5),usedefault=True)
    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    c.datagrabber = Data(['epi'])
    sub = DataBase()
    sub.name="subject_id"
    sub.values=[]
    sub.iterable=True
    c.datagrabber.fields.append(sub)
    c.datagrabber.field_template = dict(epi='%s/*')
    c.datagrabber.template_args = dict(epi=[['subject_id']])
    return c

mwf.config_ui = create_config

"""
Part 3: Create a View
"""

def create_view():
    from traitsui.api import View, Item, Group, CSVListEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='uuid', style='readonly'),
        Item(name='desc', style='readonly'),
        label='Description', show_border=True),
        Group(Item(name='working_dir'),
            Item(name='crash_dir'),Item('sink_dir'),
            Item('surf_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin',enabled_when='not save_script_only'),Item('save_script_only'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),
            label='Subjects', show_border=True),
        Group(Item(name="motion_correct_node"),
            Item(name='TR',enabled_when='not use_metadata'),Item('use_metadata'),
            Item(name='do_slicetiming'),
            Item(name='SliceOrder', editor=CSVListEditor(), enabled_when='do_slicetiming and not use_metadata'),Item('order', enabled_when='do_slicetiming'),
            Item(name='loops',enabled_when="motion_correct_node=='nipy' ", editor=CSVListEditor()),
            Item(name='speedup',enabled_when="motion_correct_node=='nipy' ", editor=CSVListEditor()),
            label='Motion Correction', show_border=True),
        Group(Item(name='use_advanced_options'),
            Item(name='advanced_script',enabled_when='use_advanced_options'),
            label='Advanced',show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Part 4: Workflow Construction
"""

def get_substitutions(subject_id):
    subs = [('_subject_id_%s/' % subject_id, ''),
            ('_fwhm', 'fwhm'),
            ('_register0/', ''),
            ('_threshold20/aparc+aseg_thresh_warped_thresh',
             '%s_brainmask' % subject_id),
            ('st.','.'),
            ]

    for i in range(20):  #SG: assumes max 4 runs
        subs.append(('_tsnr%d/' % i, '%s_r%02d_' % (subject_id, i)))
        subs.append(('_z_score%d/' % i, '%s_r%02d_' % (subject_id, i)))
        subs.append(('_threshold%d/'%i,'%s_r%02d_'%(subject_id, i)))

    return subs

def simple_preproc(c):
    from .fmri_preprocessing import extract_meta
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    from ...scripts.modular_nodes import mod_realign
    from nipype.workflows.smri.freesurfer.utils import create_getmask_flow
    from ...scripts.utils import art_mean_workflow
    from nipype.algorithms.misc import TSNR
    import nipype.interfaces.io as nio
    import nipype.interfaces.fsl as fsl

    wf = pe.Workflow(name='simple_preproc')
    datagrabber = c.datagrabber.create_dataflow()
    infosource = datagrabber.get_node('subject_id_iterable')
    img2float = pe.MapNode(interface=fsl.ImageMaths(out_data_type='float',
        op_string='',
        suffix='_dtype'),
        iterfield=['in_file'],
        name='img2float')
    motion_correct = pe.Node(util.Function(input_names=['node','in_file','tr',
                                                        'do_slicetime','sliceorder',"parameters"],
        output_names=['out_file','par_file','parameter_source'],
        function=mod_realign),
        name="mod_realign")

    meanfunc = art_mean_workflow()
    art = meanfunc.get_node('strict_artifact_detect')
    getmask = create_getmask_flow()

    tsnr = pe.MapNode(TSNR(regress_poly=2),  #SG: advanced parameter
        name='tsnr',
        iterfield=['in_file'])

    if c.use_metadata:
        get_meta = pe.Node(util.Function(input_names=['func'],output_names=['so','tr'],function=extract_meta),name="get_metadata")
        wf.connect(datagrabber,'datagrabber.epi',get_meta, 'func')
        wf.connect(get_meta,'so',motion_correct,"sliceorder")
        wf.connect(get_meta,'tr',motion_correct,"tr")
    else:
        motion_correct.inputs.sliceorder = c.SliceOrder
        motion_correct.inputs.tr = c.TR

    # inputs
    motion_correct.inputs.do_slicetime = c.do_slicetiming
    motion_correct.inputs.node = c.motion_correct_node
    motion_correct.inputs.parameters = {"loops":c.loops,
                                                   "speedup":c.speedup,
                                                   "order": c.order}
    wf.connect(datagrabber,'datagrabber.epi',img2float,'in_file')
    wf.connect(img2float,'out_file', motion_correct,'in_file')
    wf.connect(motion_correct,'out_file',meanfunc,'inputspec.realigned_files')
    wf.connect(motion_correct,'parameter_source',meanfunc,'inputspec.parameter_source')
    wf.connect(motion_correct,'par_file',meanfunc,'inputspec.realignment_parameters')


    wf.connect(motion_correct,'out_file',tsnr,'in_file')

    wf.connect(meanfunc,'outputspec.mean_image',getmask,'inputspec.source_file')
    wf.connect(infosource,'subject_id',getmask,'inputspec.subject_id')
    getmask.inputs.inputspec.subjects_dir = c.surf_dir
    getmask.inputs.inputspec.contrast_type = 't2'

    sink = pe.Node(nio.DataSink(),name='sinker')
    sink.inputs.base_directory = c.sink_dir
    wf.connect(infosource,'subject_id',sink,'container')
    wf.connect(infosource,('subject_id', get_substitutions),sink,'substitutions')
    wf.connect(motion_correct,'out_file',sink,'simple_preproc.output')
    wf.connect(motion_correct,'par_file',sink,'simple_preproc.motion')
    wf.connect(meanfunc,'outputspec.mean_image',sink,'simple_preproc.mean')
    wf.connect(getmask,'outputspec.mask_file',sink,'simple_preproc.mask')
    wf.connect(getmask,'outputspec.reg_file',sink,'simple_preproc.bbreg.@reg')
    wf.connect(getmask,'outputspec.reg_cost',sink,'simple_preproc.bbreg.@regcost')
    wf.connect(tsnr,'tsnr_file',sink,'simple_preproc.tsnr.@tsnr')
    wf.connect(tsnr,'detrended_file',sink,'simple_preproc.tsnr.@detrended')
    wf.connect(tsnr,'stddev_file',sink,'simple_preproc.tsnr.@stddev')
    wf.connect(tsnr,'mean_file',sink,'simple_preproc.tsnr.@mean')
    wf.connect(art,'intensity_files',sink,'simple_preproc.art.@intensity')
    wf.connect(art,'norm_files',sink,'simple_preproc.art.@norm')
    wf.connect(art,'outlier_files',sink,'simple_preproc.art.@outlier')
    wf.connect(art,'statistic_files',sink,'simple_preproc.art.@stats')

    return wf

mwf.workflow_function = simple_preproc

def main(config_file):

    c = load_config(config_file,create_config)
    a = simple_preproc(c)
    a.base_dir = c.working_dir

    a.config = {'execution' : {'crashdump_dir' : c.crash_dir, 'job_finished_timeout' : 14}}

    if c.use_advanced_options:
        exec c.advanced_script

    from nipype.utils.filemanip import fname_presuffix

    a.export(fname_presuffix(config_file,'','_script_').replace('.json',''))

    if c.save_script_only:
        return 0

    if c.run_using_plugin:
        a.run(plugin=c.plugin,plugin_args=c.plugin_args)
    else:
        a.run()

mwf.workflow_main_function = main

register_workflow(mwf)