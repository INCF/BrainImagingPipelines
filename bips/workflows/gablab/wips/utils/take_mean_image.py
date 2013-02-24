from ....base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from ....flexible_datagrabber import Data, DataBase
"""
Part 1: Define a MetaWorkflow
"""

desc = """
Take Mean Image
======================

This workflow will take the mean of a list of files 
provided they all have the same affine
"""
mwf = MetaWorkflow()
mwf.uuid = '4032b4be77a511e28b4a00259080ab1a'
mwf.tags = ['mean']
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
    sink_dir = Directory(mandatory=True,desc="Location to store results")
    # Execution

    run_using_plugin = Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.Enum("PBS", "PBSGraph","MultiProc", "SGE", "Condor",
        usedefault=True,
        desc="plugin to use, if run_using_plugin=True")
    plugin_args = traits.Dict({"qsub_args": "-q many"},
        usedefault=True, desc='Plugin arguments.')
    # Subjects
    datagrabber = traits.Instance(Data, ())
    name= traits.String('mean')
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
    c.datagrabber.field_template = dict(input_files='%s/*')
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
            Item(name='crash_dir'),Item('sink_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin',enabled_when='not save_script_only'),Item('save_script_only'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),Item('name'),
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

def mean_image(images):
    import nibabel as nib
    import numpy as np
    import os

    img = nib.load(images[0])
    shape,affine = img.shape,img.get_affine()

    mean = np.zeros((len(images),shape[0],shape[1],shape[2]))

    for i,im in enumerate(images):
        im_ = nib.load(im)
        data, aff = im_.get_data(),im_.get_affine()
        if not np.sum(aff - affine):
            mean[i,:,:,:] = data
        else:
            print np.sum(aff-affine)
            raise Exception("Images are not in the same space!!")

    mean = np.mean(mean,axis=0)
    outfile = os.path.abspath('mean.nii')
    out = nib.Nifti1Image(mean,affine)
    out.to_filename(outfile)
    return outfile

def mean_workflow(c,name='take_mean'):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu
    import nipype.interfaces.io as nio

    wf = pe.Workflow(name=name)
    datagrabber = c.datagrabber.create_dataflow()
    subject_names = datagrabber.get_node('subject_id_iterable')
    sink = pe.Node(nio.DataSink(),name='sinker')
    sink.inputs.base_directory = c.sink_dir
    if subject_names:
        wf.connect(subject_names,'subject_id',sink,'container')
        subs = lambda x: [('_subject_id_%s'%x,'')]
        wf.connect(subject_names,('subject_id',subs),sink,'substitutions')
    mean = pe.Node(niu.Function(input_names=['images'],output_names=['outfile'],
                                function=mean_image),name='take_mean')

    wf.connect(mean,'outfile',sink,'%s.@mean'%c.name)
    wf.connect(datagrabber,'datagrabber.input_files', mean, 'images')
    wf.base_dir = c.working_dir
    return wf

    mwf.workflow_function = mean_workflow

def main(config_file):

    c = load_config(config_file,create_config)
    a = mean_workflow(c)

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

