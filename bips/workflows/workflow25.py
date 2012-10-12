from .base import MetaWorkflow, load_config, register_workflow, debug_workflow
import os
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from .scripts.ua780b1988e1c11e1baf80019b9f22493.utils import fs_segment

"""
Part 1: Define a MetaWorkflow
"""

desc = """
Kelly Kapowski
================
"""
mwf = MetaWorkflow()
mwf.uuid = '3c274ab2fc4c11e1a04700259080ab1a'
mwf.tags = ['ANTS','cortical thickness']
mwf.script_dir = 'u0a14c5b5899911e1bca80023dfa375f2'
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
    base_dir = Directory(exists=True, desc='Base directory of data. (Should be subject-independent)')
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")
    surf_dir = Directory(mandatory=True, desc= "Freesurfer subjects directory")

    # Execution

    run_using_plugin = Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.Enum("PBS", "PBSGraph","MultiProc", "SGE", "Condor",
        usedefault=True,
        desc="plugin to use, if run_using_plugin=True")
    plugin_args = traits.Dict({"qsub_args": "-q many"},
        usedefault=True, desc='Plugin arguments.')
    test_mode = Bool(False, mandatory=False, usedefault=True,
        desc='Affects whether where and if the workflow keeps its \
                            intermediary files. True to keep intermediary files. ')
    # Sub
    subjects = traits.List(traits.Str)
    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
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
            Item(name='sink_dir'),
            Item(name='crash_dir'),
            Item('surf_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'),
            label='Execution Options', show_border=True),
        Group(Item(name='subjects', editor=CSVListEditor()),
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

tolist = lambda x: [x]

def kellyk(c):
    import nipype.interfaces.io as nio
    import nipype.interfaces.utility as niu
    import nipype.pipeline.engine as pe
    import nipype.interfaces.fsl as fsl
    import nipype.interfaces.freesurfer as fs

    wf = pe.Workflow(name="KellyKapowski")

    infosource  = pe.Node(niu.IdentityInterface(fields=["subject_id"]),name="subjects")
    infosource.iterables = ("subject_id", c.subjects)

    seg = fs_segment()
    wf.connect(infosource,"subject_id",seg,"inputspec.subject_id")
    seg.inputs.inputspec.subjects_dir = c.surf_dir

    combine = pe.Node(fsl.MultiImageMaths(op_string='-mul 1.5 -add %s -mul 2'),name="add23")
    wf.connect(seg,'outputspec.wm', combine,'in_file')
    wf.connect(seg,('outputspec.gm',tolist), combine, 'operand_files')

    sink = pe.Node(nio.DataSink(),name="sinker")
    wf.connect(infosource,"subject_id",sink,"container")
    sink.inputs.base_directory = c.sink_dir
    wf.connect(combine,"out_file",sink,"kellykapowski.segment")

    return wf

mwf.workflow_function = kellyk

"""
Part 5: Define the main function
"""

def main(config_file):
    """Runs preprocessing QA workflow

Parameters
----------

config_file : String
              Filename to .json file of configuration parameters for the workflow

"""
    c = load_config(config_file, create_config)

    a = kellyk(c)
    a.base_dir = c.working_dir

    if c.test_mode:
        a.write_graph()

    a.config = {'execution' : {'crashdump_dir' : c.crash_dir, 'job_finished_timeout' : 14}}

    if c.use_advanced_options:
        exec c.advanced_script

    if c.run_using_plugin:
        a.run(plugin=c.plugin,plugin_args=c.plugin_args)
    else:
        a.run()

mwf.workflow_main_function = main

"""
Part 6: Register the Workflow
"""

register_workflow(mwf)