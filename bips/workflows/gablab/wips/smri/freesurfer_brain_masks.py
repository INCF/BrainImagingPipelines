import os
from ....base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from bips.workflows.base import BaseWorkflowConfig

"""
MetaWorkflow
"""

desc = """
Create FS Brainmasks
===========================

"""
mwf = MetaWorkflow()
mwf.uuid = '04a4dc102aa711e2a14700259080ab1a'
mwf.tags = ['masks', 'freesurfer']

mwf.help = desc

"""
Config
"""

class config(BaseWorkflowConfig):
    uuid = traits.Str(desc="UUID")

    # Directories
    base_dir = Directory(os.path.abspath('.'),mandatory=True, desc='Base directory of data. (Should be subject-independent)')
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")
    surf_dir = Directory(os.environ['SUBJECTS_DIR'],desc='Freesurfer subjects dir')
    save_script_only = traits.Bool(False)
    
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
    for s in files:
        if 'aparc+aseg.mgz' in s:
            aparcs.append(s)
    if aparcs == []:
        raise Exception("can't find aparc")
    return aparcs[0]


def create_custom_template(c):
    import nipype.pipeline.engine as pe
    #from nipype.interfaces.ants import BuildTemplate
    import nipype.interfaces.io as nio
    import nipype.interfaces.utility as niu
    import nipype.interfaces.freesurfer as fs

    wf = pe.Workflow(name='create_fs_masked_brains')
    #temp = pe.Node(BuildTemplate(parallelization=1), name='create_template')
    fssource = pe.Node(nio.FreeSurferSource(subjects_dir = c.surf_dir),name='fssource')
    infosource = pe.Node(niu.IdentityInterface(fields=["subject_id"]),name="subject_names")
    infosource.iterables = ("subject_id", c.subjects)
    wf.connect(infosource,"subject_id",fssource,"subject_id")
    sink = pe.Node(nio.DataSink(base_directory=c.sink_dir),name='sinker')
    applymask = pe.Node(fs.ApplyMask(mask_thresh=0.5),name='applymask')   
    binarize = pe.Node(fs.Binarize(dilate=1,min=0.5,subjects_dir=c.surf_dir),name='binarize') 
    convert = pe.Node(fs.MRIConvert(out_type='niigz'),name='convert')
    wf.connect(fssource,'orig',applymask,'in_file')
    wf.connect(fssource,('aparc_aseg',pickaparc),binarize,'in_file')
    wf.connect(binarize,'binary_file',applymask,'mask_file')
    wf.connect(applymask,'out_file',convert,'in_file')
    wf.connect(convert,"out_file",sink,"masked_images")

    def getsubs(subject_id):
        subs = []
        subs.append(('_subject_id_%s/'%subject_id, '%s_'%subject_id))
        return subs
    wf.connect(infosource, ("subject_id", getsubs), sink, "substitutions")
    #wf.connect(convert,'out_file',temp,'in_files')
    #wf.connect(temp,'final_template_file',sink,'custom_template.final_template_file')
    #wf.connect(temp,'subject_outfiles',sink,'custom_template.subject_outfiles')
    #wf.connect(temp,'template_files',sink,'template_files')
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

    from nipype.utils.filemanip import fname_presuffix
    workflow.export(fname_presuffix(config_file,'','_script_').replace('.json',''))

    if c.run_using_plugin:
        workflow.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        workflow.run()


mwf.workflow_main_function = main

"""
Register
"""

register_workflow(mwf)
