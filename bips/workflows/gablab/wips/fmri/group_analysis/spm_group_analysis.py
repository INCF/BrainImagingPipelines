import os
from .....base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits
from .....flexible_datagrabber import Data, DataBase

"""
MetaWorkflow
"""
desc = """
SPM Group Analysis
=====================================

"""
mwf = MetaWorkflow()
mwf.uuid = '2d12af2264d811e2be7a00259080ab1a'
mwf.tags = ['SPM', 'second level', 'multiple regression']

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
    datagrabber = traits.Instance(Data, ())

    # Regression
    run_one_sample_T_test = traits.Bool(True)
    run_regression = traits.Bool()
    design_csv = traits.File(desc="design .csv file")
    reg_contrasts = traits.Code(desc="function named reg_contrasts which takes in 0 args and returns contrasts")
    use_regressors = traits.Bool()
    estimation_method = traits.Enum('Classical','Bayesian','Bayesian2')

    #Normalization

    norm_template = traits.File(desc='Template of files')
    use_mask = traits.Bool(False)
    mask_file = traits.File(desc='already binarized mask file to use')
    
    #Correction:
    p_threshold = traits.Float(0.05)
    height_threshold = traits.Float(0.05)
    min_cluster_size = traits.Int(25)
    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()

    # Buttons
    check_func_datagrabber = Button("Check")

def create_config():
    c = config()
    c.uuid = mwf.uuid

    c.datagrabber = Data(['con_images'])
    c.datagrabber.fields = []
    subs = DataBase()
    subs.name = 'subject_id'
    subs.values = ['sub01','sub02','sub03']
    subs.iterable = False
    fwhm = DataBase()
    fwhm.name='fwhm'
    fwhm.values=['0','6.0']
    fwhm.iterable = True
    con = DataBase()
    con.name='contrast'
    con.values=['con01','con02','con03']
    con.iterable=True
    c.datagrabber.fields.append(subs)
    c.datagrabber.fields.append(fwhm)
    c.datagrabber.fields.append(con)
    c.datagrabber.field_template = dict(con_images='%s/smri/fwhm_%s/con*.nii')
    c.datagrabber.template_args = dict(con_images=[['fwhm',"contrast","subject_id"]])

    return c

mwf.config_ui = create_config

"""
View
"""

def create_view():
    from traitsui.api import View, Item, Group
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='working_dir'),
        Item(name='sink_dir'),
        Item(name='crash_dir'),
        label='Directories', show_border=True),
        Group(Item(name='run_using_plugin',enabled_when='save_script_only'),Item('save_script_only'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'),Item("timeout"),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),
            label='Datagrabber', show_border=True),
        Group(Item(name='norm_template',enabled_when='not use_mask'),Item(name='use_mask'),Item('mask_file',enabled_when='use_mask'),
            Item(name='run_one_sample_T_test'),
            Item('run_regression'),
            Item('estimation_method'),
            Item('use_regressors'),
            Item(name='design_csv',enabled_when='use_regressors'),
            Item(name="reg_contrasts"),
            Item("p_threshold"),Item('height_threshold'),
            Item("min_cluster_size"), 
        label='Second_Level', show_border=True),
        Group(Item(name='use_advanced_options'),
            Item(name='advanced_script',enabled_when='use_advanced_options'),
            label='Advanced',show_border=True),
        buttons=[OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Construct Workflow
"""

get_len = lambda x: len(x)

def create_2lvl(do_one_sample,name="group",mask=None):
    import nipype.interfaces.fsl as fsl
    import nipype.interfaces.spm as spm
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu

    wk = pe.Workflow(name=name)

    inputspec = pe.Node(niu.IdentityInterface(fields=['copes','estimation_method',
                                                      'template', "contrasts",
                                                      "regressors","p_thresh","height_thresh",'min_cluster_size']),name='inputspec')

    if do_one_sample:
        model = pe.Node(spm.OneSampleTTestDesign(),name='onesample')
    else:
        model = pe.Node(spm.MultipleRegressionDesign(),name='l2model')
        wk.connect(inputspec, 'regressors', model, "user_covariates")

    est_model = pe.Node(spm.EstimateModel(),name='estimate_model')
    wk.connect(inputspec,'copes',model,'in_files')
    wk.connect(inputspec,'estimation_method',est_model,'estimation_method')
    wk.connect(model,'spm_mat_file',est_model,'spm_mat_file')

    if mask==None:
        bet = pe.Node(fsl.BET(mask=True,frac=0.3,output_type='NIFTI'),name="template_brainmask")
        wk.connect(inputspec,'template',bet,'in_file')
        wk.connect(bet,'mask_file',model,'explicit_mask_file')

    else:
        wk.connect(inputspec,'template',model,'explicit_mask_file')    

    est_cont = pe.Node(spm.EstimateContrast(group_contrast=True),name='estimate_contrast')

    wk.connect(inputspec, 'contrasts', est_cont, "contrasts")
    wk.connect(est_model,'spm_mat_file', est_cont,"spm_mat_file")
    wk.connect(est_model,'residual_image',est_cont,"residual_image")
    wk.connect(est_model,'beta_images', est_cont,"beta_images")

    thresh = pe.MapNode(spm.Threshold(use_fwe_correction=False,use_topo_fdr=True,height_threshold_type='p-value'),name='fdr',iterfield=['stat_image','contrast_index'])
    wk.connect(est_cont,'spm_mat_file',thresh,'spm_mat_file')
    wk.connect(est_cont,'spmT_images',thresh,'stat_image')
    wk.connect(inputspec,'min_cluster_size',thresh,'extent_threshold')
    count = lambda x: range(1,len(x)+1)

    wk.connect(inputspec,('contrasts',count),thresh,'contrast_index')
    wk.connect(inputspec,'p_thresh',thresh,'extent_fdr_p_threshold')
    wk.connect(inputspec,'height_thresh',thresh,'height_threshold')

    outputspec = pe.Node(niu.IdentityInterface(fields=['RPVimage',
                                                        'beta_images',
                                                        'mask_image',
                                                        'residual_image',
                                                        'con_images',
                                                        'ess_images',
                                                        'spmF_images',
                                                        'spmT_images',
                                                        'spm_mat_file',
                                                        'pre_topo_fdr_map',
                                                        'thresholded_map']),
                         name='outputspec')


    wk.connect(est_model,'RPVimage',outputspec,'RPVimage')
    wk.connect(est_model,'beta_images',outputspec,'beta_images')
    wk.connect(est_model,'mask_image',outputspec,'mask_image')
    wk.connect(est_model,'residual_image',outputspec,'residual_image')
    wk.connect(est_cont,'con_images',outputspec,'con_images')
    wk.connect(est_cont,'ess_images',outputspec,'ess_images')
    wk.connect(est_cont,'spmF_images',outputspec,'spmF_images')
    wk.connect(est_cont,'spmT_images',outputspec,'spmT_images')
    wk.connect(est_cont,'spm_mat_file',outputspec,'spm_mat_file')
    wk.connect(thresh,'pre_topo_fdr_map',outputspec,'pre_topo_fdr_map')
    wk.connect(thresh,'thresholded_map',outputspec,'thresholded_map')
    return wk


def get_datagrabber(c):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio
    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id',
                                                             'fwhm',"contrast"],
        outfields=['con_images']),
        name="datagrabber")
    datasource.inputs.base_directory = c.base_dir
    datasource.inputs.template = '*'
    datasource.inputs.field_template = dict(
        con_images=c.copes_template)
    datasource.inputs.template_args = dict(copes=[['fwhm',"contrast","subject_id"]],
        varcopes=[['fwhm',"contrast","subject_id"]])
    return datasource


from fsl_one_sample_t_test import get_substitutions

def get_regressors(csv,ids):
    import numpy as np
    if csv == '':
        return None
    reg = {}
    design = np.recfromcsv(csv)
    design_str = np.recfromcsv(csv,dtype=str)
    names = design_str.dtype.names
    csv_ids = []
    for i in design_str["id"]:
        csv_ids.append(str(i))
    csv_ids = np.asarray(csv_ids)
    for n in names:
        if not n=="id":
            reg[n] = []
    for sub in ids:
        if sub in csv_ids:
            for key in reg.keys():
                reg[key].append(design[key][csv_ids==sub][0])
        else:
            raise Exception("%s is missing from the CSV file!"%sub)
    cov = []
    for key,item in reg.iteritems():
        cov.append({'name':key,'vector':item})
    print cov
    return cov


def connect_to_config(c):

    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu
    import nipype.interfaces.io as nio
    if c.use_mask: 
        wk = create_2lvl(c.run_one_sample_T_test,mask=c.mask_file)
    else:
        wk = create_2lvl(c.run_one_sample_T_test)
        
    wk.base_dir = c.working_dir
    datagrabber = c.datagrabber.create_dataflow()  #get_datagrabber(c)
    #infosourcecon = pe.Node(niu.IdentityInterface(fields=["contrast"]),name="contrasts")
    #infosourcecon.iterables = ("contrast",c.contrasts)
    #wk.connect(infosourcecon,'contrast',datagrabber,"contrast")
    sinkd = pe.Node(nio.DataSink(),name='sinker')
    sinkd.inputs.base_directory = c.sink_dir
    
    infosourcecon = datagrabber.get_node('contrast_iterable')
    
    if infosourcecon:

        wk.connect(infosourcecon,("contrast",get_substitutions),sinkd,"substitutions")
        wk.connect(infosourcecon,"contrast",sinkd,"container")
    
    inputspec = wk.get_node('inputspec')
    outputspec = wk.get_node('outputspec')
    #datagrabber.inputs.subject_id = c.subjects
    #infosource = pe.Node(niu.IdentityInterface(fields=['fwhm']),name='fwhm_infosource')
    #infosource.iterables = ('fwhm',c.fwhm)

    #wk.connect(infosource,'fwhm',datagrabber,'fwhm')
    wk.connect(datagrabber,'datagrabber.con_images', inputspec, 'copes')
    if not c.use_mask:
        wk.inputs.inputspec.template = c.norm_template
    else: 
        wk.inputs.inputspec.template = c.mask_file
    wk.inputs.inputspec.p_thresh = c.p_threshold
    wk.inputs.inputspec.min_cluster_size = c.min_cluster_size
    wk.inputs.inputspec.height_thresh = c.height_threshold
    wk.inputs.inputspec.estimation_method = {c.estimation_method:1}
    cons = pe.Node(niu.Function(input_names=[],output_names=["contrasts"]),name="get_contrasts")
    cons.inputs.function_str = c.reg_contrasts
    #wk.inputs.inputspec.contrasts = c.reg_contrasts
    wk.connect(cons, "contrasts", inputspec,"contrasts")

    def get_val(datagrabber,field='subject_id'):
        for f in datagrabber.fields:
            if f.name==field:
                return f.values
        return None

    subjects = get_val(c.datagrabber,'subject_id')

    if c.use_regressors:
        wk.inputs.inputspec.regressors = get_regressors(c.design_csv,subjects)
    
    wk.connect(outputspec,'RPVimage',sinkd,'output.@RPVimage')
    wk.connect(outputspec,'beta_images',sinkd,'output.@beta_images')
    wk.connect(outputspec,'mask_image',sinkd,'output.@mask_image')
    wk.connect(outputspec,'residual_image',sinkd,'output.@residual_image')
    wk.connect(outputspec,'con_images',sinkd,'output.@con_images')
    wk.connect(outputspec,'ess_images',sinkd,'output.@ess_images')
    wk.connect(outputspec,'spmF_images',sinkd,'output.@spmF_images')
    wk.connect(outputspec,'spmT_images',sinkd,'output.@spmT_images')
    wk.connect(outputspec,'spm_mat_file',sinkd,'output.@spm_mat_file')
    wk.connect(outputspec,'pre_topo_fdr_map',sinkd,'output.fdr.@pretopo')
    wk.connect(outputspec,'thresholded_map',sinkd,'output.fdr.@thresh')
    return wk

mwf.workflow_function = connect_to_config

"""
Main
"""

def main(config_file):
    c = load_config(config_file, config)
    wk = connect_to_config(c)
    wk.config = {'execution': {'crashdump_dir': c.crash_dir,"job_finished_timeout":c.timeout}}

    if c.test_mode:
        wk.write_graph()
    if c.use_advanced_options:
        exec c.advanced_script
    try:
        from nipype.utils.filemanip import fname_presuffix
        wk.export(fname_presuffix(config_file,'','_script_').replace('.json',''))
    except:
        print "ERROR in exporting workflow"
    if c.save_script_only:
        return 0

    if c.run_using_plugin:
        wk.run(plugin=c.plugin,plugin_args=c.plugin_args)
    else:
        wk.run()
    return 1

mwf.workflow_main_function = main

"""
Register
"""

register_workflow(mwf)

