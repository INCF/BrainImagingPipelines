import os
from .base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits

"""
MetaWorkflow
"""

desc = """
Create ANTS custom template
===========================

"""
mwf = MetaWorkflow()
mwf.uuid = 'ants_custom_template'
mwf.tags = ['ants', 'template']

mwf.help = desc

"""
Config
"""

class config(HasTraits):
    uuid = traits.Str(desc="UUID")

    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    base_dir = Directory(os.path.abspath('.'),mandatory=True, desc='Base directory of data. (Should be subject-independent)')
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")
    surf_dir = Directory(desc='Freesurfer subjects dir')
    # Execution
    run_using_plugin = Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.Enum("PBS", "MultiProc", "SGE", "Condor",
                         usedefault=True,
                         desc="plugin to use, if run_using_plugin=True")
    plugin_args = traits.Dict({"qsub_args": "-q max10"},
                                                      usedefault=True, desc='Plugin arguments.')
    test_mode = Bool(False, mandatory=False, usedefault=True,
                     desc='Affects whether where and if the workflow keeps its \
                            intermediary files. True to keep intermediary files. ')
    # Subjects
    subjects = traits.List(traits.Str, mandatory=True, usedefault=True,
                          desc="Subject id's. Note: These MUST match the subject id's in the \
                                Freesurfer directory. For simplicity, the subject id's should \
                                also match with the location of individual functional files.")
   # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()


def create_config():
    c = config()
    c.uuid = mwf.uuid
    return c

mwf.config_ui = create_config

"""
View
"""

def create_view():
    from traitsui.api import View, Item, Group, CSVListEditor, TupleEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='working_dir'),
                      Item(name='sink_dir'),
                      Item(name='crash_dir'),
                      Item(name='surf_dir'),
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
                buttons=[OKButton, CancelButton],
                resizable=True,
                width=1050)
    return view

mwf.config_view = create_view

"""
Construct Workflow
"""

def pickaparc(files):
    """Return the aparc+aseg.mgz file"""
    aparcs = []
    for sets in files:
        for s in sets:
            if 'aparc+aseg.mgz' in s:
                aparcs.append(s)
    return aparcs


def create_custom_template(c):
    import nipype.pipeline.engine as pe
    from nipype.interfaces.ants import BuildTemplate
    import nipype.interfaces.io as nio
    import nipype.interfaces.utility as niu
    import nipype.interfaces.freesurfer as fs

    wf = pe.Workflow(name='create_custom_template')
    temp = pe.Node(BuildTemplate(parallelization=1), name='create_template')
    fssource = pe.MapNode(nio.FreeSurferSource(subjects_dir = c.surf_dir),name='fssource',iterfield='subject_id')
    fssource.inputs.subject_id = c.subjects
    sink = pe.Node(nio.DataSink(base_directory=c.sink_dir),name='sinker')
    applymask = pe.MapNode(fs.ApplyMask(mask_thresh=0.5),name='applymask',iterfield=['in_file','mask_file'])   
    binarize = pe.MapNode(fs.Binarize(dilate=1,min=0.5,subjects_dir=c.surf_dir),name='binarize',iterfield=['in_file']) 
    convert = pe.MapNode(fs.MRIConvert(out_type='niigz'),iterfield=['in_file'],name='convert')
    wf.connect(fssource,'orig',applymask,'in_file')
    wf.connect(fssource,('aparc_aseg',pickaparc),binarize,'in_file')
    wf.connect(binarize,'binary_file',applymask,'mask_file')
    wf.connect(applymask,'out_file',convert,'in_file')
    wf.connect(convert,'out_file',temp,'in_files')
    wf.connect(temp,'final_template_file',sink,'custom_template.final_template_file')
    wf.connect(temp,'subject_outfiles',sink,'custom_template.subject_outfiles')
    wf.connect(temp,'template_files',sink,'template_files')
    return wf

mwf.workflow_function = create_custom_template

"""
Main
"""

def main(config_file):
    c = load_config(config_file, create_config)

    workflow = create_custom_template(c)
    workflow.base_dir = c.working_dir
    workflow.config = {'execution': {'crashdump_dir': c.crash_dir}}
    
    if c.test_mode:
        workflow.write_graph()
    
    if c.use_advanced_options:
        exec c.advanced_script
    if c.run_using_plugin:
        workflow.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        workflow.run()


mwf.workflow_main_function = main

"""
Register
"""

register_workflow(mwf)
