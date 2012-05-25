from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from .scripts.u0a14c5b5899911e1bca80023dfa375f2.diffusion_base import create_workflow
from .base import MetaWorkflow, load_config, register_workflow
import nipype.interfaces.io as nio
import nipype.interfaces.utility as niu
from .workflow12 import config as pconfig
import nipype.pipeline.engine as pe

mwf = MetaWorkflow()
mwf.help = """
Diffusion tracking workflow
===========================

"""
mwf.uuid = 'fda82554a43511e1b507001e4fb1404c'
mwf.tags = ['diffusion','dti','tracking']
mwf.script_dir = 'u0a14c5b5899911e1bca80023dfa375f2'

class config(HasTraits):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc='Workflow description')
    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")

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
    # Subjects

    subjects= traits.List(traits.Str, mandatory=True, usedefault=True,
        desc="Subject id's. Note: These MUST match the subject id's in the \
                                Freesurfer directory. For simplicity, the subject id's should \
                                also match with the location of individual functional files.")
    # Preprocessing info
    preproc_config = traits.File(desc="preproc json file")

    #Track
    seed = traits.File()

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    return c

def create_view():
    from traitsui.api import View, Item, Group, CSVListEditor, TupleEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='uuid', style='readonly'),
        Item(name='desc', style='readonly'),
        label='Description', show_border=True),
        Group(Item(name='working_dir'),
            Item(name='sink_dir'),
            Item(name='crash_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'),
            label='Execution Options', show_border=True),
        Group(Item(name='subjects', editor=CSVListEditor()),
            label='Subjects', show_border=True),
        Group(Item(name='preproc_config'), Item(name='seed'),
            label='Track', show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

def get_dataflow(c):
    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
        outfields=['dwi','mask']),
        name='datasource')
    # create a node to obtain the functional images
    datasource.inputs.base_directory = c.sink_dir
    datasource.inputs.template ='*'
    datasource.inputs.field_template = dict(dwi='%s/preproc/outputs/dwi/*',
        mask='%s/preproc/outputs/mask/*')
    datasource.inputs.template_args = dict(dwi=[['subject_id']],
        mask=[['subject_id']])
    return datasource

def main(config_file):
    c = load_config(config_file,config)

    prep_c = load_config(c.preproc_config, pconfig)

    workflow = create_workflow()
    datagrabber = get_dataflow(prep_c)
    inputspec = workflow.get_node('inputspec')
    workflow.connect(datagrabber,'mask',inputspec,'mask')
    workflow.connect(datagrabber,'dwi',inputspec,'dwi')
    infosource = pe.Node(niu.IdentityInterface(fields=["subject_id"]),name='subject_names')
    workflow.connect(infosource,"subject_id",datagrabber, 'subject_id')
    workflow.base_dir = c.working_dir
    if c.test_mode:
        infosource.iterables=("subject_id", [c.subjects[0]])
        workflow.write_graph()
    else:
        infosource.iterables=("subject_id", c.subjects)

    if c.run_using_plugin:
        workflow.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        workflow.run()

    return 1

mwf.workflow_main_function = main
mwf.config_ui = create_config
mwf.config_view = create_view

register_workflow(mwf)