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
FLIRT Registration
==================

This workflow will create a flirt registration matrix
"""
mwf = MetaWorkflow()
mwf.uuid = '65a8a6de7f6311e29d5f00259080ab1a'
mwf.tags = ['flirt','coregistration']
mwf.help = desc

"""
Part 2: Define the config class & create_config function
"""

# config_ui
class config(BaseWorkflowConfig):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc='Workflow description')
    # Directories
    sink_dir = Directory(mandatory=True, desc="Location to store results")
    save_script_only = traits.Bool(False)

    # Subjects
    interpolation = traits.Enum('trilinear','nearestneighbour','sinc',usedefault=True)
    name = traits.String('flirt_output',desc='name of folder to store flirt mats')
    datagrabber_create = traits.Instance(Data, ())
    datagrabber_apply = traits.Instance(Data, ())
    create_transform = traits.Bool(True)
    apply_transform = traits.Bool(False)
    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    c.datagrabber_create = Data(['inputs','template'])
    sub = DataBase()
    sub.name="subject_id"
    sub.values=[]
    sub.iterable=True
    c.datagrabber_create.fields.append(sub)
    c.datagrabber_create.field_template = dict(inputs='%s/preproc/mean/*mean.nii*',template='%s/preproc/mean/*mean_anat/nii*')
    c.datagrabber_create.template_args = dict(inputs=[['subject_id']],template=[['subject_id']])

    c.datagrabber_apply = Data(['inputs','template','reg_mat'])
    sub = DataBase()
    sub.name="subject_id"
    sub.values=[]
    sub.iterable=True
    c.datagrabber_apply.fields.append(sub)
    c.datagrabber_apply.field_template = dict(inputs='%s/preproc/mean/*mean.nii*',
                                              template='%s/preproc/mean/*mean_anat/nii*',
                                              reg_mat='%s/flirt_reg/*/mat')
    c.datagrabber_apply.template_args = dict(inputs=[['subject_id']],
                                             template=[['subject_id']],
                                             reg_mat=[['subject_id']])

    return c

mwf.config_ui = create_config

"""
Part 3: Create a View
"""

def create_view():
    from traitsui.api import View, Item, Group
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='uuid', style='readonly'),
        Item(name='desc', style='readonly'),
        label='Description', show_border=True),
        Group(Item(name='working_dir'),
            Item(name='crash_dir'),
            Item('sink_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin',enabled_when='not save_script_only'),Item('save_script_only'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            label='Execution Options', show_border=True),
        Group(Item('create_transform',enabled_when='not apply_transform'),
            Item(name='datagrabber_create',enabled_when='create_transform'),
            Item('apply_transform', enabled_when='not create_transform'),
            Item(name='datagrabber_apply',enabled_when='apply_transform'),
            Item('interpolation'),Item('name'),
            label='Subjects', show_border=True),
        Group(Item(name='use_advanced_options'),
            Item(name='advanced_script',enabled_when='use_advanced_options'),
            label='Advanced',show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

def quick_transform(c):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio
    import nipype.interfaces.fsl as fsl

    wf = pe.Workflow(name='flirt_transform')
    sink = pe.Node(nio.DataSink(),name='sinker')
    sink.inputs.base_directory = c.sink_dir

    if c.create_transform:
        datagrabber = c.datagrabber_create.create_dataflow()
        infosource = datagrabber.get_node('subject_id_iterable')
        xform = pe.MapNode(fsl.FLIRT(interp=c.interpolation),name='flirt',iterfield=['in_file'])
        wf.connect(xform,'out_matrix_file',sink,'%s.@outmatfile'%c.name)

    elif c.apply_transform:
        datagrabber = c.datagrabber_apply.create_dataflow()
        infosource = datagrabber.get_node('subject_id_iterable')
        xform = pe.MapNode(fsl.FLIRT(interp=c.interpolation,apply_xfm=True),name='flirt',iterfield=['in_file'])
        wf.connect(datagrabber,'datagrabber.reg_mat',xform,'in_matrix_file')

    else:
        raise Exception("Need to either create or apply a flirt transform!!")

    wf.connect(datagrabber,'datagrabber.inputs',xform,'in_file')
    wf.connect(datagrabber,'datagrabber.template',xform,'reference')
    wf.connect(infosource,'subject_id',sink,'container')
    wf.connect(xform,'out_file',sink,'%s.@outfile'%c.name)

    subs = lambda sub_id: [('_subject_id_%s'%sub_id,'')]+[('_flirt%d'%i,'') for i in range(20)]
    wf.connect(infosource,('subject_id', subs),sink,'substitutions')

    return wf

mwf.workflow_function = quick_transform

def main(config_file):

    c = load_config(config_file,create_config)
    a = quick_transform(c)
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
