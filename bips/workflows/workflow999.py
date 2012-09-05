__author__ = 'keshavan'
from .base import MetaWorkflow, load_config, register_workflow, debug_workflow
import os
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from .flexible_datagrabber import Data, DataBase

mwf = MetaWorkflow()
mwf.uuid = 'FIRonly'
mwf.tags = ['FIR']
mwf.uses_outputs_of = ['63fcbb0a890211e183d30023dfa375f2','7757e3168af611e1b9d5001e4fb1404c']
mwf.script_dir = 'u0a14c5b5899911e1bca80023dfa375f2'
mwf.help="""
Filtering workflow
===================

"""

class config(HasTraits):
    uuid = traits.Str(desc="UUID")

    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")

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

    # filter
    highpass_freq = traits.Float()
    lowpass_freq = traits.Float()
    filtering_algorithm = traits.Enum("fsl","IIR","FIR","Fourier")
    tr = traits.Float()

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.datagrabber = create_datagrabber_config()
    return c

mwf.config_ui = create_config

def create_datagrabber_config():
    dg = Data(['in_files'])
    foo = DataBase()
    foo.name="subject_id"
    foo.iterable = True
    foo.values=["sub01","sub02"]
    dg.fields = [foo]
    dg.field_template = dict(in_files='%s/preproc/output/fullspectrum/fwhm_6.0/*.nii*')
    dg.template_args = dict(in_files=[['subject_id']])
    return dg


"""
View
"""

def create_view():
    from traitsui.api import View, Item, Group, CSVListEditor, TupleEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='working_dir'),
        Item(name='sink_dir'),
        Item(name='crash_dir'),
        label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),
            label='Data', show_border=True),
        Group(Item(name='highpass_freq'),
            Item(name='lowpass_freq'),
            Item(name='filtering_algorithm'),Item('tr'),
            label='Bandpass Filter',show_border=True),
        buttons=[OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

def run_filt(c):
    import nipype.interfaces.io as nio
    import nipype.interfaces.utility as niu
    import nipype.pipeline.engine as pe
    from .scripts.u0a14c5b5899911e1bca80023dfa375f2.modular_nodes import mod_filter
    workflow = pe.Workflow(name='Filter')
    datagrabber = c.datagrabber.create_dataflow()
    filt = pe.Node(niu.Function(input_names=['in_file',
                                             'algorithm',
                                             'lowpass_freq',
                                             'highpass_freq',
                                             'tr'],
                                output_names=['out_file'],function=mod_filter),name='FIR_filt')
    sink = pe.Node(nio.DataSink(),name='sinker')
    sink.inputs.base_directory = c.sink_dir
    subjects = datagrabber.get_node('subject_id_iterable')
    workflow.connect(subjects,'subject_id',sink,'container')
    filt.inputs.tr = c.tr
    filt.inputs.lowpass_freq = c.lowpass_freq
    filt.inputs.highpass_freq = c.highpass_freq
    filt.inputs.algorithm = c.filtering_algorithm
    workflow.connect(datagrabber,'datagrabber.in_files',filt,"in_file")
    workflow.connect(filt,'out_file',sink,'bandpassed.@file')
    workflow.base_dir = c.working_dir
    return workflow

mwf.workflow_function = run_filt

def main(config_file):
    """Runs the fMRI preprocessing workflow

Parameters
----------

config_file : JSON file with configuration parameters

"""
    c = load_config(config_file, create_config)
    wf = run_filt(c)
    wf.config = {'execution': {'crashdump_dir': c.crash_dir, 'job_finished_timeout' : 14}}

    if c.run_using_plugin:
        wf.run(plugin=c.plugin, plugin_args = c.plugin_args)
    else:
        wf.run()

mwf.workflow_main_function = main

"""
Part 6: Register the Workflow
"""
register_workflow(mwf)
