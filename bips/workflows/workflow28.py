import os
from .base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from .flexible_datagrabber import Data, DataBase

"""
Part 1: Define a MetaWorkflow
"""

mwf = MetaWorkflow()
mwf.uuid = '9ce580861d2a11e2907600259080ab1a'
mwf.help="""
Divide Parcellation
====================

 """
mwf.tags=['mris_divide_parcellation']

"""
Part 2: Define the config class & create_config function
"""

class config(HasTraits):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc="Workflow Description")
    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    sink_dir = Directory(os.path.abspath('.'), mandatory=True, desc="Location where the BIP will store the results")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")
    surf_dir = Directory(mandatory=True, desc= "Freesurfer subjects directory")
    save_script_only = traits.Bool(False)
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
    timeout = traits.Float(14.0)
    subjects = traits.List(desc="subjects")
    split_files = traits.List(traits.File(),desc="""list of split files""")
    # First Level
    #advanced_options
    use_advanced_options = Bool(False)
    advanced_options = traits.Code()

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
            Item(name='surf_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'), Item(name="timeout"),
            label='Execution Options', show_border=True),
        Group(Item(name='subjects', editor=CSVListEditor()),Item(name="split_files"),
            label='Subjects', show_border=True),
        Group(Item(name='use_advanced_options'),
            Item(name="advanced_options", enabled_when="use_advanced_options"),
            label="Advanced Options", show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Part 4: Workflow Construction
"""

def divide_parcellations(subject,hemi,in_annot,split_file,subjects_dir,iter=0):
    import os
    os.environ["SUBJECTS_DIR"] = subjects_dir
    out_annot = os.path.abspath("%s.%s.%d.annot"%(subject,hemi,iter))
    cmd = "mris_divide_parcellation %s %s %s %s %s"%(subject, hemi, in_annot, split_file,out_annot)
    print cmd
    os.system(cmd)
    return out_annot

def pickaparcannot(files):
    """Return the aparc+aseg.mgz file"""
    aparcs = []
    for s in files:
        if 'lh.aparc.annot' in s:
            aparcs.append(s)
        elif 'rh.aparc.annot' in s:
            aparcs.append(s)
    aparcs = sorted(aparcs)
    return aparcs

def divide_wf(c):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio
    import nipype.interfaces.utility as niu

    wf = pe.Workflow(name="divider")
    inputnode = pe.Node(niu.IdentityInterface(fields=["subject_id"]),name="subject_names")
    inputnode.iterables = ("subject_id",c.subjects)
    fssource = pe.Node(nio.FreeSurferSource(),name='fssource')
    fssource.inputs.subjects_dir = c.surf_dir
    wf.connect(inputnode,"subject_id",fssource,"subject_id")


    divide0 = pe.MapNode(niu.Function(input_names=['subject','hemi',
                                                'in_annot','split_file',
                                                'subjects_dir','iter'],
        output_names=['out_annot'], function=divide_parcellations),
        name='divide0',iterfield=['hemi','in_annot'])
    divide0.inputs.hemi = ['lh','rh']
    divide0.inputs.subjects_dir = c.surf_dir
    wf.connect(inputnode,"subject_id", divide0,"subject")

    def clone(name):
        dividen = pe.MapNode(niu.Function(input_names=['subject','hemi',
                                                       'in_annot','split_file',
                                                       'subjects_dir','iter'],
            output_names=['out_annot'], function=divide_parcellations),
            name=name,iterfield=['hemi','in_annot'])
        dividen.inputs.hemi = ['lh','rh']
        dividen.inputs.subjects_dir = c.surf_dir
        return dividen

    for i,f in enumerate(c.split_files):
        if i==0:
            wf.connect(fssource,('annot',pickaparcannot),divide0,'in_annot')
            divide0.inputs.split_file = f
            divide0.inputs.iter = 0
            divide_n = divide0

        else:
            divide_n = clone('divide_%d'%i)
            divide_n.inputs.iter = i
            divide_n.inputs.split_file = f
            if not i==1:
                divide_n1 = wf.get_node("divide_%d"%(i-1))
            else:
                divide_n1 = wf.get_node("divide0")
            wf.connect(divide_n1,"out_annot", divide_n,"in_annot")
            wf.connect(inputnode,"subject_id", divide_n,"subject")



    sinker = pe.Node(nio.DataSink(),name='sinker')
    sinker.inputs.base_directory = c.sink_dir
    wf.connect(inputnode,"subject_id",sinker,"container")

    def get_subs(subject_id):
        subs = []
        subs.append(("_subject_id_%s"%subject_id,""))
        for max in xrange(10):
            subs.append(("_divide_%d0"%(max-1), ""))
            subs.append(("_divide_%d1"%(max-1), ""))
        subs.append(("_divide00", ""))
        subs.append(("_divide01", ""))
        return subs

    wf.connect(inputnode,("subject_id",get_subs),sinker,"substitutions")

    wf.connect(divide_n,"out_annot",sinker,"divided_annotations")

    return wf

mwf.workflow_function = divide_wf

"""
Main
"""

def main(config_file):
    c = load_config(config_file, create_config)

    workflow = divide_wf(c)
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
