import os
import traits.api as traits
from .base import MetaWorkflow, load_config, register_workflow, debug_workflow
from .flexible_datagrabber import Data, DataBase
from traits.api import HasTraits

mwf = MetaWorkflow()
mwf.uuid = '31a16ceef77e11e196e800259080ab1a'
mwf.tags = ['Segstats Group']
mwf.script_dir = 'u0a14c5b5899911e1bca80023dfa375f2'
mwf.help="""
Segstats Group
==============

"""

class config(HasTraits):
    uuid = traits.Str(desc="UUID")

    # Directories
    working_dir = traits.Directory(mandatory=True, desc="Location of the Nipype working directory")
    sink_dir = traits.Directory(mandatory=True, desc="Location where the BIP will store the results")
    crash_dir = traits.Directory(mandatory=False, desc="Location to store crash files")

    # Execution
    run_using_plugin = traits.Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.Enum("PBS", "MultiProc", "SGE", "Condor",
        usedefault=True,
        desc="plugin to use, if run_using_plugin=True")
    plugin_args = traits.Dict({"qsub_args": "-q many"},
        usedefault=True, desc='Plugin arguments.')
    test_mode = traits.Bool(False, mandatory=False, usedefault=True,
        desc='Affects whether where and if the workflow keeps its \
                            intermediary files. True to keep intermediary files. ')
    timeout = traits.Float(14.0)
    # DataGrabber
    datagrabber = traits.Instance(Data, ())


def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.datagrabber = create_datagrabber_config()
    return c

mwf.config_ui = create_config

def create_datagrabber_config():
    dg = Data(['summary_files',"timeseries_files"])
    foo = DataBase()
    foo.name="subject_id"
    foo.iterable = False
    foo.values=["sub01","sub02"]
    dg.fields = [foo]
    dg.field_template = dict(summary_files='%s/segstats/_segstats0/*.stats',
                             timeseries_files='%s/segstats/_segstats0/*.txt')
    dg.template_args = dict(summary_files=[['subject_id']],
                             timeseries_files=[['subject_id']])
    return dg

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
            Item(name='test_mode'),Item('timeout'),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),
            label='Data', show_border=True),
        buttons=[OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

def grouper(avgfile,sumfile):
    import numpy as np
    import os
    names = np.genfromtxt(sumfile,dtype=str)[:,4]
    fname = os.path.abspath('segstats_file.csv')
    f = open(fname,"w")
    avg = np.genfromtxt(avgfile)
    f.write("ROI, ")
    for con in range(0,avg.shape[0]):
        if not con == avg.shape[0]-1:
            f.write("con%02d, "%(con+1))
        else:
            f.write("con%02d"%(con+1))
    f.write("\n")
    for i in range(0,avg.shape[1]):
        f.write("%s, "%names[i])
        for con in range(0,avg.shape[0]):
            if not con == avg.shape[0]-1:
                f.write("%2.4f, "%avg[con,i])
            else:
                f.write("%2.4f"%avg[con,i])
        f.write('\n')
        # load first file, find the # of columns = # contrasts
    return fname

def otherfunc(roifiles,subjects):
    import numpy as np
    from matplotlib.mlab import rec2csv
    import os
    first = np.recfromcsv(roifiles[0])
    numcons = len(first.dtype.names)-1
    roinames = ["subject_id"]+first["roi"].tolist()
    formats = ['a10']+['f4' for f in roinames[1:]]
    confiles = []
    for con in range(0,numcons):
        recarray = np.zeros(len(roifiles),dtype={'names':roinames,"formats":formats})
        for i, file in enumerate(roifiles):
            recfile = np.recfromcsv(file)
            recarray["subject_id"][i] = subjects[i]
            for roi in roinames[1:]:
                value = recfile["con%02d"%(con+1)][recfile['roi']==roi]
                if value:
                    recarray[roi][i] = value
                else:
                    recarray[roi][i] = 999
        filename = os.path.abspath("grouped_con%02d.csv"%(con+1))
        rec2csv(recarray,filename)
        confiles.append(filename)
    return confiles

def group_segstats(c):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu
    import nipype.interfaces.io as nio

    wf = pe.Workflow(name="group_segstats")
    datagrabber = c.datagrabber.create_dataflow()
    grouper1 = pe.MapNode(niu.Function(input_names=['avgfile','sumfile'],
        output_names=['fname'],
        function=grouper),
        name="grouper1", iterfield=['avgfile','sumfile'])
    grouper2 = pe.Node(niu.Function(input_names=['roifiles',
                                                 'subjects'],
                                    output_names=['confiles'],
        function=otherfunc),name='grouper2')
    sinker = pe.Node(nio.DataSink(),name='sinker')
    sinker.inputs.base_directory = c.sink_dir
    wf.base_dir = c.working_dir
    wf.connect(datagrabber,"datagrabber.summary_files",grouper1,"sumfile")
    wf.connect(datagrabber,"datagrabber.timeseries_files",grouper1,"avgfile")
    wf.connect(grouper1,"fname",grouper2,"roifiles")
    grouper2.inputs.subjects = datagrabber.inputs.datagrabber.get()['subject_id']
    wf.connect(grouper2,"confiles",sinker,"segstats")
    return wf

mwf.workflow_function = group_segstats

def main(config_file):
    c = load_config(config_file,config)
    wk = group_segstats(c)
    wk.base_dir = c.working_dir
    wk.config = {'execution' : {'crashdump_dir' : c.crash_dir,
                                'job_finished_timeout' : c.timeout}}

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