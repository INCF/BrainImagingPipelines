from .base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits
from .flexible_datagrabber import Data, DataBase
import os


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
    timeout = traits.Float(30.0)
    # DataGrabber
    datagrabber = datagrabber = traits.Instance(Data, ())

    # segstats
    use_reg = traits.Bool(True)
    inverse_reg = traits.Bool(True)
    use_standard_label = traits.Bool(False,desc="use same label file for all subjects")
    label_file = traits.File()
    use_annotation = traits.Bool(False,desc="use same annotation file for all subjects (will warp to subject space")
    annot_space = traits.String("fsaverage5",desc="subject space of annot file")
    lh_annotation = traits.File()
    rh_annotation = traits.File()
    color_table_file = traits.Enum("Default","Color_Table","GCA_color_table","None")
    color_file = traits.File()
    proj = traits.BaseTuple(("frac",0,1,0.1),traits.Enum("abs","frac"),traits.Float(),traits.Float(),traits.Float())

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.datagrabber = create_datagrabber_config()
    return c

mwf.config_ui = create_config

def create_datagrabber_config():
    dg = Data(['in_files','reg_file','label_file'])
    foo = DataBase()
    foo.name="subject_id"
    foo.iterable = True
    foo.values=["sub01","sub02"]
    dg.fields = [foo]
    dg.field_template = dict(in_files='%s/preproc/output/bandpassed/fwhm_6.0/*.nii*',
                             reg_file='%s/preproc/bbreg/*.dat',
                             label_file='%s/mri/aparc+aseg.mgz')
    dg.template_args = dict(in_files=[['subject_id']],
                            reg_file=[['subject_id']],
                            label_file=[['subject_id']])
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
            Item(name='test_mode'),Item('timeout'),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),
              Item('use_reg'),
              Item("use_annotation"),Item(name='annot_space'),
              Item('lh_annotation',enabled_when='use_annotation'),
              Item('rh_annotation',enabled_when='use_annotation'),
              Item('inverse_reg',enabled_when="use_reg or use_annotation"),
              Item('use_standard_label'),
              Item('label_file',enabled_when="use_standard_label"),
              Item('color_table_file'),
              Item("color_file"),Item('proj'),
            label='Data', show_border=True),
        buttons=[OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Construct Workflow
"""

def aparc2aseg(subject_id,annot):
    import os
    outfile = os.path.abspath(os.path.split(annot)[1]+'_aparc2aseg.nii.gz')
    os.system("mri_aparc2aseg --s %s --o %s --annot %s" % (subject_id,outfile,annot))

def segstats_workflow(c, name='segstats'):
    import nipype.interfaces.fsl as fsl
    import nipype.interfaces.freesurfer as fs
    import nipype.interfaces.io as nio
    import nipype.pipeline.engine as pe
    from .scripts.u0a14c5b5899911e1bca80023dfa375f2.modified_nipype_workflows import create_get_stats_flow
    from .scripts.u0a14c5b5899911e1bca80023dfa375f2.utils import tolist, pickidx
    if not c.use_annotation:
        workflow = create_get_stats_flow(name='segstats',withreg=c.use_reg)
    else:
        workflow = create_get_stats_flow(name='segstats')

    workflow.inputs.segstats.avgwf_txt_file = True
    datagrabber = c.datagrabber.create_dataflow()
    merge = pe.Node(fsl.Merge(dimension='t'),name='merge_files')
    inputspec = workflow.get_node('inputspec')
    subject_iterable = datagrabber.get_node("subject_id_iterable")
    # merge files grabbed
    stats = workflow.get_node('segstats')
    print "colortablefile:", c.color_table_file
    if c.color_table_file == "Default":
        stats.inputs.default_color_table=True
    elif c.color_table_file == "Color_Table":
        stats.inputs.color_table_file = c.color_file
    elif c.color_table_file == "GCA_color_table":
        stats.inputs.gca_color_table = c.color_file

    workflow.connect(datagrabber,('datagrabber.in_files',tolist),merge,'in_files')


    if c.use_annotation:

        surf2surf = pe.MapNode(fs.SurfaceTransform(source_subject=c.annot_space,
                                                subjects_dir=c.surf_dir),
                            name="surf2surf",
                            iterfield=['hemi','source_annot_file'])
        surf2surf.inputs.source_annot_file = [c.lh_annotation,c.rh_annotation]
        workflow.connect(subject_iterable,"subject_id",surf2surf,"target_subject")
        surf2surf.inputs.hemi=['lh','rh']

        add = pe.Node(fsl.BinaryMaths(operation='add'),name="add")
        workflow.connect(add,'out_file',inputspec,"label_file")
        label2vol = pe.MapNode(fs.Label2Vol(subjects_dir=c.surf_dir, proj=c.proj),name='label2vol',iterfield=["hemi","annot_file"])
        workflow.connect(surf2surf,"out_file",label2vol,"annot_file")
        workflow.connect(subject_iterable,"subject_id",label2vol,"subject_id")
        #fssource = pe.Node(nio.FreeSurferSource(subjects_dir = c.surf_dir),name='fssource')
        #workflow.connect(subject_iterable,"subject_id",fssource,"subject_id")
        #workflow.connect(subject_iterable,"subject_id",label2vol,"reg_header")
        #workflow.connect(fssource,"orig",label2vol,"template_file")
        workflow.connect(merge,"merged_file",label2vol,"template_file")
        label2vol.inputs.hemi=['lh','rh']
        workflow.connect(datagrabber,'datagrabber.reg_file',label2vol,'reg_file')
        if c.inverse_reg:
            label2vol.inputs.invert_mtx = c.inverse_reg
        workflow.connect(label2vol,('vol_label_file',pickidx,0),add,'in_file')
        workflow.connect(label2vol,('vol_label_file',pickidx,1),add,'operand_file')

    workflow.connect(merge,'merged_file',inputspec,'source_file')

    if c.use_reg and not c.use_annotation:
        workflow.connect(datagrabber,'datagrabber.reg_file',inputspec,'reg_file')
        workflow.inputs.inputspec.subjects_dir = c.surf_dir
        workflow.inputs.inputspec.inverse = c.inverse_reg

    if c.use_standard_label and not c.use_annotation:
        workflow.inputs.inputspec.label_file = c.label_file
    elif not c.use_standard_label and not c.use_annotation:
        workflow.connect(datagrabber,'datagrabber.label_file',inputspec,"label_file")

    sinker = pe.Node(nio.DataSink(),name='sinker')
    sinker.inputs.base_directory = c.sink_dir


    workflow.connect(subject_iterable,'subject_id', sinker, 'container')
    def get_subs(subject_id):
        subs = [('_subject_id_%s'%subject_id,'')]
        return subs
    workflow.connect(subject_iterable,('subject_id',get_subs),sinker,'substitutions')
    outputspec = workflow.get_node('outputspec')
    workflow.connect(outputspec,'stats_file',sinker,'segstats.@stats')
    workflow.connect(stats,"avgwf_txt_file",sinker,'segstats.@avg')

    return workflow

mwf.workflow_function = segstats_workflow

"""
Main
"""
def main(config_file):
    c = load_config(config_file,config)
    wk = segstats_workflow(c)
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
