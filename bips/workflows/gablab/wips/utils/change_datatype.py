__author__ = 'keshavan'
from ....base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from ....flexible_datagrabber import Data, DataBase
"""
Part 1: Define a MetaWorkflow
"""

desc = """
Change datatype
======================

This workflow will chagne datatype of your input files
"""
mwf = MetaWorkflow()
mwf.uuid = '30f9ae2281d611e2b67900259080ab1a'
mwf.tags = ['utils','datatype']
mwf.help = desc

"""
Part 2: Define the config class & create_config function
"""

# config_ui
class config(HasTraits):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc='Workflow description')
    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")
    save_script_only = traits.Bool(False)
    # Execution

    run_using_plugin = Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.Enum("PBS", "PBSGraph","MultiProc", "SGE", "Condor",
        usedefault=True,
        desc="plugin to use, if run_using_plugin=True")
    plugin_args = traits.Dict({"qsub_args": "-q many"},
        usedefault=True, desc='Plugin arguments.')
    # Subjects

    datagrabber = traits.Instance(Data, ())
    dtype = traits.Enum('float','short','bool','int')
    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    c.datagrabber = Data(['input_files'])
    sub = DataBase()
    sub.name="subject_id"
    sub.values=[]
    sub.iterable=True
    c.datagrabber.fields.append(sub)
    c.datagrabber.field_template = dict(input_files='%s/preproc/mean/*')
    c.datagrabber.template_args = dict(input_files=[['subject_id']])
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
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin',enabled_when='not save_script_only'),Item('save_script_only'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),Item('dtype'),
            label='Subjects', show_border=True),
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

def convert(img,dtype):
    import os
    from nipype.utils.filemanip import fname_presuffix

    outfile = fname_presuffix(img,'','_%s'%dtype)

    cmd = 'fslmaths %s %s -odt %s'%(img,outfile,dtype)

    print cmd
    os.system(cmd)
    return outfile

def quick_transform(c):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu

    datagrabber = c.datagrabber.create_dataflow()
    xform = pe.MapNode(niu.Function(input_names=['img','dtype'],
        output_names=['outfile'],function=convert),name='convert',iterfield=['img'])

    wf = pe.Workflow(name='convert_datatype')

    wf.connect(datagrabber,'datagrabber.input_files',xform,'img')
    xform.inputs.dtype = c.dtype

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

