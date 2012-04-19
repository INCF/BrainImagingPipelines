from base import MetaWorkflow
from enthought.traits.api import HasTraits, Directory, Bool, Button
import enthought.traits.api as traits
from enthought.traits.ui.api import Handler, View, Item, UItem, HGroup, Group
from traitsui.menu import OKButton, CancelButton
from nipype.utils.filemanip import load_json, save_json
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import os

desc = """
Task preprocessing workflow
===========================

"""
mwf = MetaWorkflow()
mwf.inputs.uuid = '63fcbb0a-8902-11e1-83d3-0023dfa375f2'

# create gui
class config_ui(HasTraits):
    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    base_dir = Directory(mandatory=True,desc='Base directory of data. (Should be subject-independent)')
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")
    field_dir = Directory(mandatory=False, desc="Base directory of field-map data (Should be subject-independent) \
                                                 Set this value to None if you don't want fieldmap distortion correction")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")
    json_sink = Directory(mandatory=False, desc= "Location to store json_files")
    surf_dir = Directory(mandatory=True, desc= "Freesurfer subjects directory")
    
    # Execution
    
    run_on_grid = Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.String("PBS", usedefault=True, desc="plugin to use, if run_on_grid=True")
    plugin_args = traits.Dict({"qsub_args":"-q many"}, usedefault=True,desc='Plugin arguments.')
    test_mode = Bool(False, mandatory=False, usedefault=True,
                            desc='Affects whether where and if the workflow keeps its \
                            intermediary files. True to keep intermediary files. ')
    # Subjects
    
    subjects= traits.String('sub01,sub02,sub03',mandatory=True,usedefault=True,
                          desc="Subject id's. Note: These MUST match the subject id's in the \
                                Freesurfer directory. For simplicity, the subject id's should \
                                also match with the location of individual functional files.")
    func_template = traits.String('%s/functional.nii.gz')
    
    # Fieldmap
    
    use_fieldmap = Bool(False, mandatory=False, usedefault=True,
                               desc='True to include fieldmap distortion correction. Note: field_dir \
                                     must be specified')
    magnitude_template = traits.String('%s/magnitude.nii.gz')
    phase_template = traits.String('%s/phase.nii.gz')
    TE_diff = traits.Float(desc='difference in B0 field map TEs')
    sigma = traits.Int(2, desc='2D spatial gaussing smoothing stdev (default = 2mm)')
    echospacing = traits.Float(desc="EPI echo spacing")
    
    # Motion Correction
    
    Interleaved = Bool(mandatory=True,desc='True for Interleaved')
    SliceOrder = traits.String("ascending", usedefault=True)
    TR = traits.Float(mandatory=True, desc = "TR of functional")    
    
    # Artifact Detection
    
    norm_thresh = traits.Float(2, usedefault=True, desc="norm thresh for art")
    z_thresh = traits.Float(3, usedefault=True, desc="z thresh for art")
    
    # Smoothing
    fwhm = traits.List([0,5],traits.Float(), mandatory=True, usedefault=True, 
                       desc="Full width at half max. The data will be smoothed at all values \
                             specified in this list.")
                             
    # CompCor
    compcor_select = traits.List(traits.Bool(), mandatory=True, 
                                 desc="The first value in the list corresponds to applying \
                                       t-compcor, and the second value to a-compcor. Note: \
                                       both can be true")
    num_noise_components = traits.Int(6, usedefault=True, 
                                      desc="number of principle components of the noise to use")
    # Highpass Filter
    hpcutoff = traits.Float(128., desc="highpass cutoff", usedefault=True)
    
    # First Level
    input_units = traits.Enum("secs","scans", desc="units of onsets/durations")
    film_threshold = traits.Float(2000, usedefault=True,desc="film threshold")
    interscan_interval = traits.Float(desc="interscan_interval")
    #overlay_thresh = traits.Tuple(traits.Float(),(3.09,10.0), usedefault=True,
    #                              desc="the min and max z-scores to threshold the image at. \
    #                                    In the sliced and overlayed images, voxels will show \
    #                                    up if for their value x the following is true: \
    #                                    overlaythresh[0] < x < overlaythresh[1] or \
    #                                    -1*overlaythresh[0] > x > -1*overlaythresh[0]")
    is_block_design = Bool(False, usedefault=True, desc="True for block design")
    subjectinfo = traits.Code("""def subjectinfo(subject_id):
    from nipype.interfaces.base import Bunch
    output = []
    names = ['cond1','cond2']
    onsets = [[0,20,40],[10,30,50]]
    durations = [[10],[10]]
    runs=2
    for r in runs:
        output.insert(r,Bunch(conditions=names,
        onsets=deepcopy(onsets),
        durations=deepcopy(durations),
        amplitudes=None,
        tmod=None,
        pmod=None,
        regressor_names=None,
        regressors=None)))
    return output""")
    getcontrasts = traits.Code("""def getcontrasts(subject_id):
    con1 = ['cond1_cond2','T', ['cond1','cond2'],[1,-1]]
    con2 = ['cond2_cond1','T', ['cond1','cond2'],[-1,1]]
    contrasts = [con1, con2]
    return contrasts""")
    
    # Buttons
    check_func_datagrabber = Button("Check")
    check_field_datagrabber = Button("Check")
    
    def _check_func_datagrabber_fired(self):
        subs = self.subjects.split(',')
        
        for s in subs:
            if not os.path.exists(os.path.join(self.base_dir,self.func_template % s)):
                print "ERROR", os.path.join(self.base_dir,self.func_template % s), "does NOT exist!"
                break
            else:
                print os.path.join(self.base_dir,self.func_template % s), "exists!"

    def _check_field_datagrabber_fired(self):
        subs = self.subjects.split(',')
        
        for s in subs:
            if not os.path.exists(os.path.join(self.field_dir,self.magnitude_template % s)):
                print "ERROR:", os.path.join(self.field_dir,self.magnitude_template % s), "does NOT exist!"
                break
            else:
                print os.path.join(self.base_dir,self.magnitude_template % s), "exists!"
            if not os.path.exists(os.path.join(self.field_dir,self.phase_template % s)):
                print "ERROR:", os.path.join(self.field_dir,self.phase_template % s), "does NOT exist!"
                break
            else:
                print os.path.join(self.base_dir,self.phase_template % s), "exists!"
# run workflow

from scripts.u0a14c5b5899911e1bca80023dfa375f2.base import create_prep, create_prep_fieldmap
from scripts.u0a14c5b5899911e1bca80023dfa375f2.utils import get_datasink, get_substitutions

def prep_workflow(c,fieldmap):
    
    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
                         name='subject_names')
    infosource.iterables = ('subject_id', c["subjects"].split(","))

    modelflow = pe.Workflow(name='preproc')
    
    # make a data sink
    sinkd = get_datasink(c["sink_dir"],c["fwhm"])
    
    # generate preprocessing workflow
    #dataflow = c.create_dataflow()
    
    import nipype.interfaces.io as nio 
    # create a node to obtain the functional images
    dataflow = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
                                                   outfields=['func']),
                         name = "preproc_dataflow")
    dataflow.inputs.base_directory = c["base_dir"]
    dataflow.inputs.template ='*'
    dataflow.inputs.field_template = dict(func=c["func_template"])
    dataflow.inputs.template_args = dict(func=[['subject_id']])

    if fieldmap:
        preproc = create_prep_fieldmap()
        preproc.inputs.inputspec.FM_Echo_spacing = c["echospacing"]
        preproc.inputs.inputspec.FM_TEdiff = c["TE_diff"]
        preproc.inputs.inputspec.FM_sigma = c["sigma"]
        
        #datasource_fieldmap = c.create_fieldmap_dataflow()
        datasource_fieldmap = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
                                                   outfields=['mag','phase']),
                         name = "fieldmap_datagrabber")
        datasource_fieldmap.inputs.base_directory = c["field_dir"]
        datasource_fieldmap.inputs.template ='*'
        datasource_fieldmap.inputs.field_template = dict(mag=c["magnitude_template"],
                                                phase=c["phase_template"])
        datasource_fieldmap.inputs.template_args = dict(mag=[['subject_id']],
                                               phase=[['subject_id']])
        
        
        modelflow.connect(infosource, 'subject_id',
                          datasource_fieldmap, 'subject_id')
        modelflow.connect(datasource_fieldmap,'mag',
                          preproc,'fieldmap_input.magnitude_file')
        modelflow.connect(datasource_fieldmap,'phase',
                          preproc,'fieldmap_input.phase_file')
        modelflow.connect(preproc, 'outputspec.FM_unwarped_mean',
                          sinkd, 'preproc.fieldmap.@unwarped_mean')
        modelflow.connect(preproc, 'outputspec.FM_unwarped_epi',
                          sinkd, 'preproc.fieldmap.@unwarped_epi')
    else:
        preproc = create_prep()
    
    preproc.inputs.inputspec.fssubject_dir = c["surf_dir"]
    preproc.get_node('fwhm_input').iterables = ('fwhm',c["fwhm"])
    preproc.inputs.inputspec.highpass = c["hpcutoff"]/(2*c["TR"])
    preproc.inputs.inputspec.num_noise_components = c["num_noise_components"]
    preproc.crash_dir = c["crash_dir"]
    preproc.inputs.inputspec.ad_normthresh = c["norm_thresh"]
    preproc.inputs.inputspec.ad_zthresh = c["z_thresh"]
    preproc.inputs.inputspec.tr = c["TR"]
    preproc.inputs.inputspec.interleaved = c["Interleaved"]
    preproc.inputs.inputspec.sliceorder = c["SliceOrder"]
    preproc.inputs.inputspec.compcor_select = c["compcor_select"]
    
    # make connections
    modelflow.connect(infosource, 'subject_id',
                      sinkd, 'container')
    modelflow.connect(infosource, ('subject_id', get_substitutions, c["use_fieldmap"]),
                      sinkd, 'substitutions')
    modelflow.connect(infosource, 'subject_id',
                      dataflow, 'subject_id')
    modelflow.connect(infosource, 'subject_id', 
                      preproc, 'inputspec.fssubject_id')
    modelflow.connect(dataflow,'func',
                      preproc, 'inputspec.func')
    modelflow.connect(preproc, 'outputspec.mean',
                      sinkd, 'preproc.motion.reference')
    modelflow.connect(preproc, 'outputspec.motion_parameters',
                      sinkd, 'preproc.motion')
    modelflow.connect(preproc, 'outputspec.realigned_files',
                      sinkd, 'preproc.motion.realigned')
    modelflow.connect(preproc, 'outputspec.mean',
                      sinkd, 'preproc.meanfunc')
    modelflow.connect(preproc, 'plot_motion.out_file',
                      sinkd, 'preproc.motion.@plots')
    modelflow.connect(preproc, 'outputspec.mask',
                      sinkd, 'preproc.mask')
    modelflow.connect(preproc, 'outputspec.outlier_files',
                      sinkd, 'preproc.art')
    modelflow.connect(preproc, 'outputspec.combined_motion',
                      sinkd, 'preproc.art.@stats')
    modelflow.connect(preproc, 'outputspec.reg_file',
                      sinkd, 'preproc.bbreg')
    modelflow.connect(preproc, 'outputspec.reg_cost',
                      sinkd, 'preproc.bbreg.@reg_cost')
    modelflow.connect(preproc, 'outputspec.highpassed_files',
                      sinkd, 'preproc.highpass')
    modelflow.connect(preproc, 'outputspec.smoothed_files',
                      sinkd, 'preproc.smooth')
    modelflow.connect(preproc, 'outputspec.tsnr_file',
                      sinkd, 'preproc.tsnr')
    modelflow.connect(preproc, 'outputspec.tsnr_detrended',
                      sinkd, 'preproc.tsnr.@detrended')
    modelflow.connect(preproc, 'outputspec.stddev_file',
                      sinkd, 'preproc.tsnr.@stddev')
    modelflow.connect(preproc, 'outputspec.z_img', 
                      sinkd, 'preproc.z_image')
    modelflow.connect(preproc, 'outputspec.noise_components',
                      sinkd, 'preproc.noise_components')
    

    modelflow.base_dir = os.path.join(c["working_dir"],'work_dir')
    return modelflow

def main(config):
    c = load_json(config)
    preprocess = prep_workflow(c, c["use_fieldmap"])
    realign = preprocess.get_node('preproc.realign')
    realign.plugin_args = {'qsub_args': '-l nodes=1:ppn=3'}
    realign.inputs.loops = 2
    realign.inputs.speedup = 15
    cc = preprocess.get_node('preproc.CompCor')
    cc.plugin_args = {'qsub_args': '-l nodes=1:ppn=3'}
    preprocess.config = {'execution' : {'crashdump_dir' : c["crash_dir"]}}
    preprocess.write_graph()
    if c["run_on_grid"]:
        preprocess.run(plugin=c["plugin"],plugin_args = c["plugin_args"])
    else:
        preprocess.run()

mwf.inputs.workflow_main_function = main
mwf.inputs.config_ui = lambda : config_ui
mwf.inputs.config_view = View(Group(Item(name='working_dir'),
             Item(name='sink_dir'),
             Item(name='crash_dir'),
             Item(name='json_sink'),
             Item(name='surf_dir'),
             label='Directories',show_border=True),
             Group(Item(name='run_on_grid'),
             Item(name='plugin',enabled_when="run_on_grid"),
             Item(name='plugin_args',enabled_when="run_on_grid"),
             Item(name='test_mode'),
             label='Execution Options',show_border=True),
             Group(Item(name='subjects'),
             Item(name='base_dir'),
             Item(name='func_template'),
             Item(name='check_func_datagrabber'),
             label='Subjects',show_border=True),
             Group(Item(name='use_fieldmap'),
             Item(name='field_dir',enabled_when="use_fieldmap"),
             Item(name='magnitude_template',enabled_when="use_fieldmap"),
             Item(name='phase_template',enabled_when="use_fieldmap"),
             Item(name='check_field_datagrabber',enabled_when="use_fieldmap"),
             Item(name='echospacing',enabled_when="use_fieldmap"),
             Item(name='TE_diff',enabled_when="use_fieldmap"),
             Item(name='sigma',enabled_when="use_fieldmap"),
             label='Fieldmap',show_border=True),
             Group(Item(name='TR'),
             Item(name='Interleaved'),
             Item(name='SliceOrder'),
             label='Motion Correction',show_border=True),
             Group(Item(name='norm_thresh'),
             Item(name='z_thresh'),
             label='Artifact Detection',show_border=True),
             Group(Item(name='compcor_select'),
             Item(name='num_noise_components'),
             label='CompCor',show_border=True),
             Group(Item(name='fwhm'),
             label='Smoothing',show_border=True),
             Group(Item(name='hpcutoff'),
             label='Highpass Filter',show_border=True),
             Group(Item(name='is_block_design'),
             Item(name='input_units'),
             Item(name='interscan_interval'),
             Item(name='film_threshold'),
             Item(name='subjectinfo'),
             Item(name='getcontrasts'),
             label='First Level',show_border=True),
             buttons = [OKButton, CancelButton],
             resizable=True,
             width=1050)
