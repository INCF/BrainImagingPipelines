from .base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits
from .flexible_datagrabber import Data, DataBase
import os
from.scripts.u0a14c5b5899911e1bca80023dfa375f2.QA_utils import tsnr_roi as segstats


"""
MetaWorkflow
"""
desc = """
Seg Stats Workflow
==================

"""
mwf = MetaWorkflow()
mwf.uuid = '2c594ed4cb9e11e1a600001e4fb1404c'
mwf.tags = ['seg','stats']
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
    surf_dir = Directory(desc="freesurfer directory. subject id's should be the same")

    # Execution
    run_using_plugin = Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.Enum("PBS", "MultiProc", "SGE", "Condor",
        usedefault=True,
        desc="plugin to use, if run_using_plugin=True")
    plugin_args = traits.Dict({"qsub_args": "-q many"},
        usedefault=True, desc='Plugin arguments.')
    test_mode = Bool(False, mandatory=False, usedefault=True,
        desc='Affects whether where and if the workflow keeps its \
                            intermediary files. True to keep intermediary files. ')
    # DataGrabber
    datagrabber = datagrabber = traits.Instance(Data, ())
    

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.datagrabber = create_datagrabber_config()
    return c

mwf.config_ui = create_config

def create_datagrabber_config():
    dg = Data(['in_files','reg_file'])
    foo = DataBase()
    foo.name="subject_id"
    foo.iterable = True
    foo.values=["sub01","sub02"]
    dg.fields = [foo]
    return dg


"""
View
"""

def create_view():
    from traitsui.api import View, Item, Group, CSVListEditor, TupleEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='working_dir'),
        Item(name='sink_dir'),
        Item(name='crash_dir'), Item(name='surf_dir'),
        label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),
            label='Data', show_border=True),
        buttons=[OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Construct Workflow
"""

def segstats_workflow(c, name='segstats'):
    import nipype.interfaces.fsl as fsl
    import nipype.interfaces.io as nio
    import nipype.pipeline.engine as pe
    workflow = segstats(name='segstats')
    plot = workflow.get_node('roiplotter')
    workflow.remove_nodes([plot])
    inputspec = workflow.get_node('inputspec')
    # merge files grabbed

    merge = pe.Node(fsl.Merge(),name='merge_files')
    datagrabber = c.datagrabber.create_dataflow()

    workflow.connect(datagrabber,'datagrabber.in_files',merge,'in_files')
    workflow.connect(merge,'merged_file',inputspec,'tsnr_file')
    workflow.connect(datagrabber,'datagrabber.reg_file',inputspec,'reg_file')
    workflow.inputs.inputspec.sd = c.surf_dir
    workflow.connect(datagrabber,'subject_id_iterable', inputspec, 'subject')

    sinker = pe.Node(nio.DataSink(),name='sinker')
    sinker.inputs.base_directory = c.sink_dir
    workflow.connect(datagrabber,'subject_id_iterable', sinker, 'container')
    def get_subs(subject_id):
        subs = [('_subject_id_%s'%subject_id,'')]
        return subs
    workflow.connect(datagrabber,('subject_id_iterable',get_subs),sinker,'substitutions')
    outputspec = workflow.get_node('outputspec')
    workflow.connect(outputspec,'roi_file',sinker,'segstat.@roi')

    return workflow

mwf.workflow_function = segstats_workflow

"""
Main
"""
def main(config_file):
    c = load_config(config_file,config)
    wk = segstats_workflow(c)
    if c.test_mode:
        wk.write_graph()
    if c.run_using_plugin:
        wk.run(plugin=c.plugin,plugin_args=c.plugin_args)
    else:
        wk.run()

mwf.workflow_main_function = main
"""
Register Workflow
"""
register_workflow(mwf)
