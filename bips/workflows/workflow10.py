# Import Stuff
from .scripts.u0a14c5b5899911e1bca80023dfa375f2.base import create_first
import os
from .base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from .flexible_datagrabber import Data, DataBase

"""
Part 1: Define a MetaWorkflow
"""

mwf = MetaWorkflow()
mwf.uuid = '8efdb2a08f1711e1b160001e4fb1404c'
mwf.help="""
First-Level Workflow
====================

 """
mwf.tags=['fMRI','First Level']

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
    json_sink = Directory(mandatory=False, desc= "Location to store json_files")
    surf_dir = Directory(mandatory=True, desc= "Freesurfer subjects directory")

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
    # Subjects

    #subjects= traits.List(traits.Str, mandatory=True, usedefault=True,
    #    desc="Subject id's. Note: These MUST match the subject id's in the \
    #                            Freesurfer directory. For simplicity, the subject id's should \
    #                            also match with the location of individual functional files.")

    datagrabber = traits.Instance(Data, ())
    # First Level

    subjectinfo = traits.Code()
    contrasts = traits.Code()
    interscan_interval = traits.Float()
    film_threshold = traits.Float()
    input_units = traits.Enum('scans','secs')
    is_sparse = traits.Bool(False)
    model_hrf = traits.Bool(True)
    stimuli_as_impulses = traits.Bool(True)
    use_temporal_deriv = traits.Bool(True)
    volumes_in_cluster = traits.Int(1)
    ta = traits.Float()
    tr = traits.Float()
    hpcutoff = traits.Float()
    scan_onset = traits.Int(0)
    scale_regressors = traits.Bool(True)
    #bases = traits.Dict({'dgamma':{'derivs': False}},use_default=True)
    bases = traits.Dict({'dgamma':{'derivs': False}}, 
                        traits.Enum('dgamma','gamma','none'), traits.Dict(traits.Enum('derivs',None), traits.Bool),
                        desc="name of basis function and options e.g., {'dgamma': {'derivs': True}}")

    # preprocessing info
    preproc_config = traits.File(desc="preproc config file")
    use_compcor = traits.Bool(desc="use noise components from CompCor")
    #advanced_options
    use_advanced_options = Bool(False)
    advanced_options = traits.Code()

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    c.datagrabber = create_datagrabber_config()
    return c

def create_datagrabber_config():
    dg = Data(['noise_components',
               'motion_parameters',
               'highpassed_files',
               'outlier_files'])
    foo = DataBase()
    foo.name="subject_id"
    foo.iterable = True
    foo.values=["sub01","sub02"]
    bar = DataBase()
    bar.name = 'fwhm'
    bar.iterable =True
    bar.values = ['0', '6.0']
    dg.template= '*'
    dg.field_template = dict(noise_components='%s/preproc/noise_components/*noise_components.txt',
        motion_parameters='%s/preproc/motion/*.par',
        highpassed_files='%s/preproc/output/bandpassed/fwhm_%s/*.nii*',
        outlier_files='%s/preproc/art/*_outliers.txt')
    dg.template_args = dict(noise_components=[['subject_id']],
        motion_parameters=[['subject_id']],
        highpassed_files=[['subject_id','fwhm']],
        outlier_files=[['subject_id']])
    dg.fields = [foo, bar]
    return dg

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
            Item(name='json_sink'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'), Item(name="timeout"),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),
            label='Subjects', show_border=True),
        Group(Item(name='interscan_interval'),
            Item(name='film_threshold'),
            Item(name='input_units'),
            Item(name='subjectinfo'),
            Item(name='contrasts'),Item("is_sparse"),
            Item("ta",enabled_when="is_sparse"),
            Item("tr"),
            Item("hpcutoff"),
            Item("model_hrf",enabled_when="is_sparse"),
            Item("stimuli_as_impulses",enabled_when="is_sparse"),
            Item("use_temporal_deriv",enabled_when="is_sparse"),
            Item("volumes_in_cluster",enabled_when="is_sparse"),
            Item("scan_onset",enabled_when="is_sparse"),
            Item("scale_regressors",enabled_when="is_sparse"),
            Item("bases"),
            label = 'First Level'),
        Group(Item(name='preproc_config'),
              Item(name="use_compcor"),
            label = 'Preprocessing Info'),
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

def preproc_datagrabber(c, name='preproc_datagrabber'):

    import nipype.pipeline.engine as pe         # pypeline engine
    import nipype.interfaces.io as nio          # input/output

    # create a node to obtain the preproc files
    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id','fwhm'],
                                                   outfields=['noise_components',
                                                              'motion_parameters',
                                                               'highpassed_files',
                                                               'outlier_files']),
                         name = name)
    datasource.inputs.base_directory = os.path.join(c.sink_dir)
    datasource.inputs.template ='*'
    datasource.inputs.field_template = dict(noise_components='%s/preproc/noise_components/*noise_components.txt',
                                            motion_parameters='%s/preproc/motion/*.par',
                                            highpassed_files='%s/preproc/output/bandpassed/fwhm_%s/*.nii*',
                                            outlier_files='%s/preproc/art/*_outliers.txt')
    datasource.inputs.template_args = dict(noise_components=[['subject_id']],
                                           motion_parameters=[['subject_id']],
                                           highpassed_files=[['subject_id','fwhm']],
                                           outlier_files=[['subject_id']])
    return datasource

def trad_mot(subinfo,files):
    # modified to work with only one regressor at a time...
    import numpy as np
    motion_params = []
    mot_par_names = ['Pitch (rad)','Roll (rad)','Yaw (rad)','Tx (mm)','Ty (mm)','Tz (mm)']
    if not isinstance(files,list):
        files = [files]
    if not isinstance(subinfo,list):
        subinfo = [subinfo]
    for j,i in enumerate(files):
        motion_params.append([[],[],[],[],[],[]])
        #k = map(lambda x: float(x), filter(lambda y: y!='',open(i,'r').read().replace('\n',' ').split(' ')))
        print i
        a = np.genfromtxt(i)
        for z in range(6):
            motion_params[j][z] = a[:,z].tolist()#k[z:len(k):6]
        
    for j,i in enumerate(subinfo):
        if i.regressor_names == None: i.regressor_names = []
        if i.regressors == None: i.regressors = []
        for j3, i3 in enumerate(motion_params[j]):
            i.regressor_names.append(mot_par_names[j3])
            i.regressors.append(i3)
    return subinfo

def noise_mot(subinfo,files,num_noise_components,use_compcor):
    if use_compcor:
        noi_reg_names = map(lambda x: 'noise_comp_'+str(x+1),range(num_noise_components))
        noise_regressors = []
        if not isinstance(files,list):
            files = [files]
        for j,i in enumerate(files):
            noise_regressors.append([[]]*num_noise_components)
            k = map(lambda x: float(x), filter(lambda y: y!='',open(i,'r').read().replace('\n',' ').split(' ')))
            for z in range(num_noise_components):
                noise_regressors[j][z] = k[z:len(k):num_noise_components]
        for j,i in enumerate(subinfo):
            if i.regressor_names == None: i.regressor_names = []
            if i.regressors == None: i.regressors = []
            for j3,i3 in enumerate(noise_regressors[j]):
                i.regressor_names.append(noi_reg_names[j3])
                i.regressors.append(i3)
    return subinfo

# First level modeling

from .scripts.u0a14c5b5899911e1bca80023dfa375f2.workflow1 import create_config as prep_config
foo = prep_config()

def combine_wkflw(c,prep_c=foo, name='work_dir'):
    import nipype.interfaces.utility as util    # utility
    import nipype.pipeline.engine as pe         # pypeline engine
    import nipype.interfaces.io as nio          # input/output
    from nipype.algorithms.modelgen import SpecifyModel, SpecifySparseModel
    import numpy as np
    modelflow = pe.Workflow(name=name)
    modelflow.base_dir = os.path.join(c.working_dir)
    
    preproc = c.datagrabber.create_dataflow()#preproc_datagrabber(prep_c)
    
    #infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
    #                     name='subject_names')

    #if c.test_mode:
    #    infosource.iterables = ('subject_id', [c.subjects[0]])
    #else:
    #    infosource.iterables = ('subject_id', c.subjects)

    infosource = preproc.get_node('subject_id_iterable')
    #modelflow.connect(infosource,'subject_id',preproc,'subject_id')
    #preproc.iterables = ('fwhm', prep_c.fwhm)

    subjectinfo = pe.Node(util.Function(input_names=['subject_id'], output_names=['output']), name='subjectinfo')
    subjectinfo.inputs.function_str = c.subjectinfo

    def getsubs(subject_id,cons,info,fwhm):
        #from config import getcontrasts, get_run_numbers, subjectinfo, fwhm
        subs = [('_subject_id_%s/'%subject_id,''),
                ('_plot_type_',''),
                ('_fwhm','fwhm'),
                ('_dtype_mcf_mask_mean','_mean'),
                ('_dtype_mcf_mask_smooth_mask_gms_tempfilt','_smoothed_preprocessed'),
                ('_dtype_mcf_mask_gms_tempfilt','_unsmoothed_preprocessed'),
                ('_dtype_mcf','_mcf')]
        
        for i in range(4):
            subs.append(('_plot_motion%d'%i, ''))
            subs.append(('_highpass%d/'%i, ''))
            subs.append(('_realign%d/'%i, ''))
            subs.append(('_meanfunc2%d/'%i, ''))
        runs = range(len(info))
        for i, run in enumerate(runs):
            subs.append(('_modelestimate%d/'%i, '_run_%d_%02d_'%(i,run)))
            subs.append(('_modelgen%d/'%i, '_run_%d_%02d_'%(i,run)))
            subs.append(('_conestimate%d/'%i,'_run_%d_%02d_'%(i,run)))
        for i, con in enumerate(cons):
            subs.append(('cope%d.'%(i+1), 'cope%02d_%s.'%(i+1,con[0])))
            subs.append(('varcope%d.'%(i+1), 'varcope%02d_%s.'%(i+1,con[0])))
            subs.append(('zstat%d.'%(i+1), 'zstat%02d_%s.'%(i+1,con[0])))
            subs.append(('tstat%d.'%(i+1), 'tstat%02d_%s.'%(i+1,con[0])))
        for i, name in enumerate(info[0].conditions):
            subs.append(('pe%d.'%(i+1), 'pe%02d_%s.'%(i+1,name)))
        for i in range(len(info[0].conditions), 256):
            subs.append(('pe%d.'%(i+1), 'others/pe%02d.'%(i+1)))
        for i in fwhm:
            subs.append(('_register%d/'%(i),''))
        
        return subs

    get_substitutions = pe.Node(util.Function(input_names=['subject_id',
                                                           'cons',
                                                           'info',
                                                           'fwhm'],
        output_names=['subs'], function=getsubs), name='getsubs')

    # create a node to create the subject info
    if not c.is_sparse:
        s = pe.Node(SpecifyModel(),name='s')
    else:
        s = pe.Node(SpecifySparseModel(model_hrf=c.model_hrf,
                                       stimuli_as_impulses=c.stimuli_as_impulses,
                                       use_temporal_deriv=c.use_temporal_deriv,
                                       volumes_in_cluster=c.volumes_in_cluster, 
                                       scan_onset=c.scan_onset,scale_regressors=c.scale_regressors),
            name='s')
        s.inputs.time_acquisition = c.ta
    s.inputs.input_units =                              c.input_units
    s.inputs.time_repetition =                          c.tr
    if c.hpcutoff < 0:
        c.hpcutoff = np.inf
    s.inputs.high_pass_filter_cutoff =                  c.hpcutoff
    #subjinfo =                                          subjectinfo(subj)
    
    
    # create a node to add the traditional (MCFLIRT-derived) motion regressors to 
    # the subject info
    trad_motn = pe.Node(util.Function(input_names=['subinfo',
                                                   'files'],
                                      output_names=['subinfo'],
                                      function=trad_mot),
                        name='trad_motn')

    
    #subjinfo = pe.Node(interface=util.Function(input_names=['subject_id','get_run_numbers'], output_names=['output'], function = c.subjectinfo), name='subjectinfo')
    #subjinfo.inputs.get_run_numbers = c.get_run_numbers
    #modelflow.connect(infosource,'subject_id', 
    #                  subjinfo,'subject_id' )
    #modelflow.connect(subjinfo, 'output',
    #                  trad_motn, 'subinfo')
    
    #modelflow.connect(infosource, ('subject_id',subjectinfo), trad_motn, 'subinfo')
    modelflow.connect(infosource,'subject_id', subjectinfo, 'subject_id')
    modelflow.connect(subjectinfo, 'output', trad_motn, 'subinfo')


    # create a node to add the principle components of the noise regressors to 
    # the subject info
    noise_motn = pe.Node(util.Function(input_names=['subinfo',
                                                    'files',
                                                    'num_noise_components',
                                                    "use_compcor"],
                                       output_names=['subinfo'],
                                       function=noise_mot),
                         name='noise_motn')
    noise_motn.inputs.use_compcor=c.use_compcor
    # generate first level analysis workflow
    modelfit =                                          create_first()
    modelfit.inputs.inputspec.interscan_interval =      c.interscan_interval
    modelfit.inputs.inputspec.film_threshold =          c.film_threshold
    
    
    contrasts = pe.Node(util.Function(input_names=['subject_id'], output_names=['contrasts']), name='getcontrasts')
    contrasts.inputs.function_str = c.contrasts

    modelflow.connect(infosource,'subject_id', 
                     contrasts, 'subject_id')
    modelflow.connect(contrasts,'contrasts', modelfit, 'inputspec.contrasts')
    
    modelfit.inputs.inputspec.bases =                   c.bases
    modelfit.inputs.inputspec.model_serial_correlations = True
    noise_motn.inputs.num_noise_components =           prep_c.num_noise_components
    
    # make a data sink
    sinkd = pe.Node(nio.DataSink(), name='sinkd')
    sinkd.inputs.base_directory = os.path.join(c.sink_dir)
        
    modelflow.connect(infosource, 'subject_id', sinkd, 'container')
    #modelflow.connect(infosource, ('subject_id',getsubs, getcontrasts, subjectinfo, prep_c.fwhm), sinkd, 'substitutions')
    modelflow.connect(infosource, 'subject_id', get_substitutions, 'subject_id')
    modelflow.connect(contrasts, 'contrasts', get_substitutions, 'cons')
    modelflow.connect(subjectinfo,'output',get_substitutions,'info')
    get_substitutions.inputs.fwhm = prep_c.fwhm
    modelflow.connect(get_substitutions,'subs', sinkd, 'substitutions')


    sinkd.inputs.regexp_substitutions = [('mask/fwhm_%d/_threshold([0-9]*)/.*nii'%x,'mask/fwhm_%d/funcmask.nii'%x) for x in prep_c.fwhm]
    sinkd.inputs.regexp_substitutions.append(('realigned/fwhm_([0-9])/_copy_geom([0-9]*)/','realigned/'))
    sinkd.inputs.regexp_substitutions.append(('motion/fwhm_([0-9])/','motion/'))
    sinkd.inputs.regexp_substitutions.append(('bbreg/fwhm_([0-9])/','bbreg/'))
     
    # make connections
    modelflow.connect(preproc, 'datagrabber.motion_parameters',      trad_motn,  'files')
    modelflow.connect(preproc, 'datagrabber.noise_components',       noise_motn, 'files')
    modelflow.connect(preproc, 'datagrabber.highpassed_files',       s,          'functional_runs')
    modelflow.connect(preproc, 'datagrabber.highpassed_files',       modelfit,   'inputspec.functional_data')
    modelflow.connect(preproc, 'datagrabber.outlier_files',          s,          'outlier_files')
    modelflow.connect(trad_motn,'subinfo',                          noise_motn, 'subinfo')
    modelflow.connect(noise_motn,'subinfo',                         s,          'subject_info')
    modelflow.connect(s,'session_info',                             modelfit,   'inputspec.session_info')
    modelflow.connect(modelfit, 'outputspec.parameter_estimates',   sinkd,      'modelfit.estimates')
    modelflow.connect(modelfit, 'outputspec.dof_file',              sinkd,      'modelfit.dofs')
    modelflow.connect(modelfit, 'outputspec.copes',                 sinkd,      'modelfit.contrasts.@copes')
    modelflow.connect(modelfit, 'outputspec.varcopes',              sinkd,      'modelfit.contrasts.@varcopes')
    modelflow.connect(modelfit, 'outputspec.zstats',                sinkd,      'modelfit.contrasts.@zstats')
    modelflow.connect(modelfit, 'outputspec.tstats',                sinkd,      'modelfit.contrasts.@tstats')
    modelflow.connect(modelfit, 'outputspec.design_image',          sinkd,      'modelfit.design')
    modelflow.connect(modelfit, 'outputspec.design_cov',            sinkd,      'modelfit.design.@cov')
    modelflow.connect(modelfit, 'outputspec.design_file',           sinkd,      'modelfit.design.@matrix')
    modelflow.connect(modelfit, 'outputspec.pfiles',                sinkd,      'modelfit.contrasts.@pstats')
    return modelflow

mwf.workflow_function = combine_wkflw

"""
Part 5: Define the main function
"""

def main(config_file):

    c = load_config(config_file, create_config)

    prep_c = load_config(c.preproc_config, prep_config)

    first_level = combine_wkflw(c, prep_c)
    first_level.config = {'execution' : {'crashdump_dir' : c.crash_dir, "job_finished_timeout": c.timeout}}
    first_level.base_dir = c.working_dir

    if c.use_advanced_options:
        exec c.advanced_options

    if c.test_mode:
        first_level.write_graph()

    if c.run_using_plugin:
        first_level.run(plugin=c.plugin, plugin_args = c.plugin_args)
    else:
        first_level.run()


mwf.workflow_main_function = main

"""
Part 6: Register the Workflow
"""

register_workflow(mwf)
