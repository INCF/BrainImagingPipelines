from .base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from .workflow13 import config as prep_config
from .scripts.u0a14c5b5899911e1bca80023dfa375f2.matlab_utils import ConnImport
from .flexible_datagrabber import Data, DataBase

"""
Part 1: MetaWorkflow
"""

mwf = MetaWorkflow()
mwf.help = """
Import files to Conn
=====================

"""

mwf.uuid = '19d774a8a36111e1b495001e4fb1404c'
mwf.tags = ['SPM','conn','import']
mwf.script_dir = 'u0a14c5b5899911e1bca80023dfa375f2'
mwf.uses_outputs_of = ['731520e29b6911e1bd2d001e4fb1404c']

"""
Part 2: Config
"""

class config(HasTraits):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc='Workflow description')

    datagrabber = traits.Instance(Data, ())

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
    run_datagrabber_without_submitting = Bool(True)
    # Subjects

    #prep_config = traits.File()
    tr = traits.Float()
    n_subjects= traits.Int()
    project_name=traits.Str()


def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    c.datagrabber = Data(['func',
                      'struct',
                      'csf',
                      'grey',
                      'white',
                      'realignment',
                      'norm',
                      'out'])
    c.datagrabber.fields = []
    subs = DataBase()
    subs.name = 'subject_id'
    subs.values = ['sub01','sub02','sub03']
    subs.iterable = True
    c.datagrabber.fields.append(subs)
    c.datagrabber.field_template = dict(func='%s/spm_preproc/smoothed_outputs/*.nii',
        struct='%s/spm_preproc/normalized_struct/*.nii',
        csf='%s/spm_preproc/segment/mod/mwc3*.nii',
        grey='%s/spm_preproc/segment/mod/mwc2*.nii',
        white='%s/spm_preproc/segment/mod/mwc1*.nii',
        realignment='%s/spm_preproc/realignment_parameters/*.par',
        norm='%s/spm_preproc/art/*norm*',
        out='%s/spm_preproc/art/*outlier*')
    c.datagrabber.template_args = dict(func=[["subject_id"]],
        struct=[["subject_id"]],
        csf=[["subject_id"]],
        grey=[["subject_id"]],
        white=[["subject_id"]],
        realignment=[["subject_id"]],
        norm=[["subject_id"]],
        out=[["subject_id"]])
    return c

mwf.config_ui = create_config

"""
Part 3: View
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
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'),
            Item(name='run_datagrabber_without_submitting'),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber', enabled_when="1"),
              Item(name='n_subjects'),
              Item(name='project_name'),
              Item('tr'),
            label='Data', show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Part 4: Construct Workflow
"""

def get_datagrabber(c):
    import nipype.interfaces.io as nio
    import nipype.pipeline.engine as pe
    dataflow = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
        outfields=['func','struct','csf','grey','white','realignment','norm','out']),
        name = "preproc_dataflow",
        run_without_submitting=c.run_datagrabber_without_submitting)
    dataflow.inputs.base_directory = c.sink_dir
    dataflow.inputs.template ='*'
    dataflow.inputs.sort_filelist = True
    if c.used_spm_workflow:
        dataflow.inputs.field_template = dict(func='%s/spm_preproc/smoothed_outputs/*.nii',
                                            struct='%s/spm_preproc/normalized_struct/*.nii',
                                            csf='%s/spm_preproc/segment/mod/mwc3*.nii',
                                            grey='%s/spm_preproc/segment/mod/mwc2*.nii',
                                            white='%s/spm_preproc/segment/mod/mwc1*.nii',
                                            realignment='%s/spm_preproc/realignment_parameters/*.par',
                                            norm='%s/spm_preproc/art/*norm*',
                                            out='%s/spm_preproc/art/*outlier*')
    else:
        dataflow.inputs.field_template = dict(func='%s/spm_preproc/smoothed_outputs/*.nii',
                                              struct='%s/spm_preproc/normalized_struct/*.nii',
                                              csf='%s/spm_preproc/segment/mod/mwc3*.nii',
                                              grey='%s/spm_preproc/segment/mod/mwc2*.nii',
                                              white='%s/spm_preproc/segment/mod/mwc1*.nii',
                                              realignment='%s/spm_preproc/realignment_parameters/*.par',
                                              norm='%s/spm_preproc/art/*norm*',
                                              out='%s/spm_preproc/art/*outlier*')

    dataflow.inputs.template_args = dict(func=[["subject_id"]],
                                        struct=[["subject_id"]],
                                        csf=[["subject_id"]],
                                        grey=[["subject_id"]],
                                        white=[["subject_id"]],
                                        realignment=[["subject_id"]],
                                        norm=[["subject_id"]],
                                        out=[["subject_id"]])
    return dataflow

def copytree(tree,out):
    import shutil
    import os
    dst = os.path.join(out,os.path.split(tree)[1])
    shutil.copytree(tree,dst)
    return None

def get_outliers(art_outliers,motion):
    import numpy as np
    import os
    def try_import(fname):
        try:
            a = np.genfromtxt(fname)
            return a
        except:
            return np.array([])

    mot = np.genfromtxt(motion)
    print mot.shape
    len = mot.shape[0]
    outliers = try_import(art_outliers)
    if outliers.shape == ():  # 1 outlier
        art = np.zeros((len, 1))
        art[np.int_(outliers), 0] = 1 #  art outputs 0 based indices

    elif outliers.shape[0] == 0:  # empty art file
        art = np.zeros((len, 1))

    else:  # >1 outlier
        art = np.zeros((len, outliers.shape[0]))
        for j, t in enumerate(outliers):
            art[np.int_(t), j] = 1 #  art outputs 0 based indices

    out_file = os.path.abspath('outliers.txt')
    np.savetxt(out_file,art)

    return out_file

#foo = prep_config()

def import_workflow(c):
    import nipype.interfaces.io as nio
    import nipype.interfaces.utility as niu
    import nipype.pipeline.engine as pe
    workflow = pe.Workflow(name='import_conn')

    datagrabber = c.datagrabber.create_dataflow()

    #datagrabber.inputs.subject_id = c.subjects

    outliers = pe.MapNode(niu.Function(input_names=['art_outliers','motion'],
        output_names=['out_file'], function= get_outliers),
        name='format_outliers',
        iterfield=['art_outliers', 'motion'])

    importer = pe.Node(interface=ConnImport(), name='import_to_conn')
    workflow.connect(datagrabber,'datagrabber.func',importer,'functional_files')
    workflow.connect(datagrabber,'datagrabber.struct',importer,'structural_files')
    workflow.connect(datagrabber,'datagrabber.csf',importer,'csf_mask')
    workflow.connect(datagrabber,'datagrabber.white',importer,'white_mask')
    workflow.connect(datagrabber,'datagrabber.grey',importer,'grey_mask')
    workflow.connect(datagrabber,'datagrabber.realignment',importer,'realignment_parameters')
    workflow.connect(datagrabber,'datagrabber.norm',importer,'norm_components')
    workflow.connect(datagrabber,'datagrabber.out', outliers, 'art_outliers')
    workflow.connect(datagrabber,'datagrabber.realignment', outliers, 'motion')
    workflow.connect(outliers, 'out_file', importer,'outliers')

    importer.inputs.tr = c.tr #c_prep.TR
    importer.inputs.n_subjects = c.n_subjects
    importer.inputs.project_name = c.project_name

    sinker = pe.Node(nio.DataSink(),name='sinker')
    workflow.connect(importer,'conn_batch',sinker,'Conn.@batch')
    workflow.connect(importer,'conn_inputs',sinker,'Conn.@inputs')

    #copier = pe.Node(niu.Function(input_names=['tree','out'],
    #    output_names=['none'],function=copytree),
    #    name='copy_conn_dir')
    #workflow.connect(importer,'conn_directory',copier,'tree')
    sinker.inputs.base_directory = c.sink_dir
    #copier.inputs.out = os.path.join(c.sink_dir,'Conn')
    workflow.base_dir = c.working_dir
    return workflow

mwf.workflow_function = import_workflow

"""
Part 5: Main
"""

def main(config_file):

    c = load_config(config_file,config)
    #c_prep = load_config(c.prep_config,prep_config)

    workflow = import_workflow(c)

    if c.run_using_plugin:
        workflow.run(plugin=c.plugin,plugin_args=c.plugin_args)
    else:
        workflow.run()

    return 1

mwf.workflow_main_function = main

"""
Part 6: Register
"""

register_workflow(mwf)
