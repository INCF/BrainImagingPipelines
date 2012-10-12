from .base import MetaWorkflow, load_config, register_workflow, debug_workflow
import os
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from .flexible_datagrabber import Data, DataBase
"""
Part 1: Define a MetaWorkflow
"""

desc = """
Task/Resting fMRI QA json
============================================
"""
mwf = MetaWorkflow()
mwf.uuid = '8a22aff8fc3411e18bcf00259080ab1a'
mwf.tags = ['task','fMRI','preprocessing','QA', 'resting']
mwf.uses_outputs_of = ['63fcbb0a890211e183d30023dfa375f2','7757e3168af611e1b9d5001e4fb1404c']
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
    field_dir = Directory(exists=True, desc="Base directory of field-map data (Should be subject-independent) \
                                                 Set this value to None if you don't want fieldmap distortion correction")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")
    json_sink = Directory(mandatory=False, desc= "Location to store json_files")
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
    # Subjects

    datagrabber = traits.Instance(Data, ())
    TR = traits.Float(6.0)
    preproc_config = traits.File(desc="preproc config file")
    debug = traits.Bool(True)
    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    c.datagrabber = Data([ 'motion_parameters',
                           'outlier_files',
                           'art_norm',
                           'art_intensity',
                           'art_stats',
                           'tsnr',
                           'tsnr_stddev',
                           'reg_file',
                           'mean_image',
                           'mincost'])
    sub = DataBase()
    sub.name="subject_id"
    sub.value=['sub01','sub02']
    sub.iterable=True
    c.datagrabber.fields.append(sub)
    c.datagrabber.field_template = dict(motion_parameters='%s/preproc/motion/*.par',
                                            outlier_files='%s/preproc/art/*_outliers.txt',
                                            art_norm='%s/preproc/art/norm.*.txt',
                                            art_stats='%s/preproc/art/stats.*.txt',
                                            art_intensity='%s/preproc/art/global_intensity.*.txt',
                                            tsnr='%s/preproc/tsnr/*_tsnr.nii*',
                                            tsnr_stddev='%s/preproc/tsnr/*tsnr_stddev.nii*',
                                            reg_file='%s/preproc/bbreg/*.dat',
                                            mean_image='%s/preproc/mean*/*.nii*',
                                            mincost='%s/preproc/bbreg/*mincost*')
    c.datagrabber.template_args = dict(motion_parameters=[['subject_id']],
                                           outlier_files=[['subject_id']],
                                           art_norm=[['subject_id']],
                                           art_stats=[['subject_id']],
                                           art_intensity=[['subject_id']],
                                           tsnr=[['subject_id']],
                                           tsnr_stddev=[['subject_id']],
                                           reg_file=[['subject_id']],
                                           mean_image=[['subject_id']],
                                           mincost=[['subject_id']])

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
            Item(name='json_sink'), Item('surf_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'), Item(name='debug'),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),
            label='Subjects', show_border=True),
        Group(Item(name='preproc_config'),
            label = 'Preprocessing Info'),
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
totable = lambda x: [[x]]
to1table = lambda x: [x]
pickfirst = lambda x: x[0]
def pickaparc(x):
    print x
    for l in x:
        if "aparc+aseg.mgz" in x:
            return x
    raise Exception("can't find aparc+aseg.mgz")

def myfssource(subject_id,subjects_dir):
    import os
    if os.path.exists(os.path.join(subjects_dir,subject_id,"mri","aparc+aseg.mgz")):
        return os.path.join(subjects_dir,subject_id,"mri","aparc+aseg.mgz")
    else:
        raise Exception("Can't find aparc+aseg!!!! %s"%os.path.join(subjects_dir,subject_id,"mri","aparc+aseg.mgz"))

def getmincost(infile):
    import numpy as np
    return np.genfromtxt(infile).tolist()

def sort(x):
    """Sorts list, if input is a list

Parameters
----------

x : List

Outputs
-------

Sorted list

"""
    if isinstance(x,list):
        return sorted(x)
    else:
        return x

def combine_table(roidev,roisnr):
    if len(roisnr) == len(roidev):
        for i, roi in enumerate(roisnr):
            # merge mean and stddev table
            roi.append(roidev[i][1]*roisnr[i][1])
            roi.append(roidev[i][1])
            
        roisnr.sort(key=lambda x:x[1])
        roisnr.insert(0,['ROI','TSNR',
                         'Mean','Standard Deviation'])
    else:
        roisnr.sort(key=lambda x:x[1])
        roisnr.insert(0,['ROI','TSNR'])     
    return roisnr

# Workflow construction function should only take in 1 arg.
# Create a dummy config for the second arg
def QA_workflow(c, prep_c,name='QA'):
    """ Workflow that generates a Quality Assurance json
   
    """
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    from nipype.interfaces.freesurfer import ApplyVolTransform
    from nipype.interfaces import freesurfer as fs
    from nipype.interfaces.io import FreeSurferSource
    from scripts.u0a14c5b5899911e1bca80023dfa375f2.QA_utils import (tsnr_roi,
                                                                    art_output)
    from ..utils.reportsink.io import JSONSink
    # Define Workflow
        
    workflow =pe.Workflow(name=name)
    datagrabber = c.datagrabber.create_dataflow()
    infosource = datagrabber.get_node('subject_id_iterable')
    
    #workflow.connect(infosource, 'subject_id', inputspec, 'subject_id')
   
    art_info = pe.MapNode(util.Function(input_names = ['art_file','intensity_file','stats_file'],
                                      output_names = ['table','out','intensity_plot'],
                                      function=art_output), 
                        name='art_output', iterfield=["art_file","intensity_file","stats_file"])
    
    #fssource = pe.Node(interface = FreeSurferSource(),name='fssource')
    #fssource.inputs.subjects_dir = c.surf_dir
    
    roidevplot = tsnr_roi(plot=False,name='tsnr_stddev_roi',roi=['all'],onsets=False)
    roidevplot.inputs.inputspec.TR = c.TR
    roisnrplot = tsnr_roi(plot=False,name='SNR_roi',roi=['all'],onsets=False)
    roisnrplot.inputs.inputspec.TR = c.TR
    
    #workflow.connect(fssource, ('aparc_aseg', pickaparc), roisnrplot, 'inputspec.aparc_aseg')
    #workflow.connect(fssource, ('aparc_aseg', pickaparc), roidevplot, 'inputspec.aparc_aseg')
    
    workflow.connect(infosource, 'subject_id', roidevplot, 'inputspec.subject')
    workflow.connect(infosource, 'subject_id', roisnrplot, 'inputspec.subject')
    workflow.connect(infosource,("subject_id", myfssource, c.surf_dir),roisnrplot,"inputspec.aparc_aseg")
    workflow.connect(infosource,("subject_id", myfssource, c.surf_dir),roidevplot,"inputspec.aparc_aseg")
    tablecombine = pe.MapNode(util.Function(input_names = ['roidev',
                                                           'roisnr'],
                                         output_names = ['combined_table'],
                                         function = combine_table),
                           name='combinetable', iterfield=['roidev','roisnr'])
    
    #workflow.connect(infosource,'subject_id',fssource,'subject_id')
    #workflow.connect(inputspec,'sd',fssource,'subjects_dir')
    #fssource.inputs.subjects_dir = c.surf_dir
    roisnrplot.inputs.inputspec.sd = c.surf_dir
    roidevplot.inputs.inputspec.sd = c.surf_dir
    workflow.connect(datagrabber,'datagrabber.art_intensity',art_info,'intensity_file')
    workflow.connect(datagrabber,'datagrabber.art_stats',art_info,'stats_file')
    workflow.connect(datagrabber,'datagrabber.outlier_files',art_info,'art_file')
    workflow.connect(datagrabber,'datagrabber.reg_file',roidevplot,'inputspec.reg_file')
    workflow.connect(datagrabber,'datagrabber.tsnr_stddev',roidevplot,'inputspec.tsnr_file')
    #workflow.connect(fssource,('aparc_aseg',pickaparc),roidevplot,'inputspec.aparc_aseg')
    workflow.connect(roidevplot,'outputspec.roi_table',tablecombine,'roidev')
    workflow.connect(datagrabber,'datagrabber.reg_file',roisnrplot,'inputspec.reg_file')
    workflow.connect(datagrabber,'datagrabber.tsnr',roisnrplot,'inputspec.tsnr_file')
    workflow.connect(roisnrplot,'outputspec.roi_table',tablecombine,'roisnr')
   
    js = pe.Node(interface=JSONSink(),name="jsoner")
    workflow.connect(tablecombine,"combined_table",js,"SNR_table")
    workflow.connect(art_info,"table",js,"art")
    workflow.connect(art_info,"out",js,"outliers")
    workflow.connect(datagrabber,("datagrabber.mincost",getmincost),js,"mincost")
    js.inputs.norm_thresh = prep_c.norm_thresh
    js.inputs.z_thresh = prep_c.z_thresh
    return workflow

mwf.workflow_function = QA_workflow

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
    QA_config = load_config(config_file, create_config)
    from .workflow2 import create_config as prep_config
    prep_c = load_config(QA_config.preproc_config,prep_config)
    a = QA_workflow(QA_config,prep_c)
    a.base_dir = QA_config.working_dir

    if QA_config.test_mode:
        a.write_graph()

    a.config = {'execution' : {'crashdump_dir' : QA_config.crash_dir, 'job_finished_timeout' : 14}}

    if QA_config.use_advanced_options:
        exec QA_config.advanced_script

    if QA_config.run_using_plugin:
        a.run(plugin=QA_config.plugin,plugin_args=QA_config.plugin_args)
    else:
        a.run()

mwf.workflow_main_function = main

"""
Part 6: Register the Workflow
"""

register_workflow(mwf)
