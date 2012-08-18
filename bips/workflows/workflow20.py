import os
from .base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits
from .scripts.u0a14c5b5899911e1bca80023dfa375f2.QA_utils import cluster_image
from .flexible_datagrabber import Data, DataBase

"""
MetaWorkflow
"""
desc = """
Group Analysis: Multiple Regression
=====================================

"""
mwf = MetaWorkflow()
mwf.uuid = '51ef1decba6711e18fda001e4fb1404c'
mwf.tags = ['FSL', 'second level', 'multiple regression']

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
    #subjects = traits.List(traits.Str, mandatory=True, usedefault=True,
    #    desc="Subject id's. Note: These MUST match the subject id's in the \
    #                            Freesurfer directory. For simplicity, the subject id's should \
    #                            also match with the location of individual functional files.")
    #fwhm=traits.List(traits.Float())
    #copes_template = traits.String('%s/preproc/output/fwhm_%s/cope*.nii.gz')
    #varcopes_template = traits.String('%s/preproc/output/fwhm_%s/varcope*.nii.gz')
    #contrasts = traits.List(traits.Str,desc="contrasts")

    datagrabber = traits.Instance(Data, ())

    # Regression
    design_csv = traits.File(desc="design .csv file")
    reg_contrasts = traits.Code(desc="function named reg_contrasts which takes in 0 args and returns contrasts")

    #Normalization
    norm_template = traits.File(mandatory=True,desc='Template of files')

    #Correction:
    run_correction = traits.Bool(False)
    z_threshold = traits.Float(2.3)
    connectivity = traits.Int(25)
    do_randomize = traits.Bool(False)
    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()

    # Buttons
    check_func_datagrabber = Button("Check")

def create_config():
    c = config()
    c.uuid = mwf.uuid

    c.datagrabber = Data(['copes','varcopes'])
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
    c.datagrabber.field_template = dict(copes='%s/preproc/output/fwhm_%s/cope*.nii.gz',
        varcopes='%s/preproc/output/fwhm_%s/varcope*.nii.gz')
    c.datagrabber.template_args = dict(copes=[['fwhm',"contrast","subject_id"]],
        varcopes=[['fwhm',"contrast","subject_id"]])

    return c

mwf.config_ui = create_config

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
            Item(name='test_mode'),Item("timeout"),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),
            label='Datagrabber', show_border=True),
        Group(Item(name='norm_template'),
            Item(name='design_csv'),
            Item(name="reg_contrasts"),
            label='Second Level', show_border=True),
        Group(Item("run_correction",enabled_when='not do_randomize'),
            Item("z_threshold",enabled_when='not do_randomize'),
            Item("connectivity",enabled_when='not do_randomize'), 
            Item('do_randomize',enabled_when='not do_correction'),
        label='Correction', show_border=True),
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

def create_2lvl(name="group"):
    import nipype.interfaces.fsl as fsl
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu

    wk = pe.Workflow(name=name)

    inputspec = pe.Node(niu.IdentityInterface(fields=['copes','varcopes',
                                                      'template', "contrasts",
                                                      "regressors"]),name='inputspec')

    model = pe.Node(fsl.MultipleRegressDesign(),name='l2model')

    #wk.connect(inputspec,('copes',get_len),model,'num_copes')
    wk.connect(inputspec, 'contrasts', model, "contrasts")
    wk.connect(inputspec, 'regressors', model, "regressors")

    mergecopes = pe.Node(fsl.Merge(dimension='t'),name='merge_copes')
    mergevarcopes = pe.Node(fsl.Merge(dimension='t'),name='merge_varcopes')

    flame = pe.Node(fsl.FLAMEO(run_mode='ols'),name='flameo')
    wk.connect(inputspec,'copes',mergecopes,'in_files')
    wk.connect(inputspec,'varcopes',mergevarcopes,'in_files')
    wk.connect(model,'design_mat',flame,'design_file')
    wk.connect(model,'design_con',flame, 't_con_file')
    wk.connect(mergecopes, 'merged_file', flame, 'cope_file')
    wk.connect(mergevarcopes,'merged_file',flame,'var_cope_file')
    wk.connect(model,'design_grp',flame,'cov_split_file')

    bet = pe.Node(fsl.BET(mask=True,frac=0.3),name="template_brainmask")
    wk.connect(inputspec,'template',bet,'in_file')
    wk.connect(bet,'mask_file',flame,'mask_file')

    outputspec = pe.Node(niu.IdentityInterface(fields=['zstat','tstat','cope',
                                                       'varcope','mrefvars',
                                                       'pes','res4d','mask',
                                                       'tdof','weights','pstat']),
        name='outputspec')

    wk.connect(flame,'copes',outputspec,'cope')
    wk.connect(flame,'var_copes',outputspec,'varcope')
    wk.connect(flame,'mrefvars',outputspec,'mrefvars')
    wk.connect(flame,'pes',outputspec,'pes')
    wk.connect(flame,'res4d',outputspec,'res4d')
    wk.connect(flame,'weights',outputspec,'weights')
    wk.connect(flame,'zstats',outputspec,'zstat')
    wk.connect(flame,'tstats',outputspec,'tstat')
    wk.connect(flame,'tdof',outputspec,'tdof')
    wk.connect(bet,'mask_file',outputspec,'mask')

    ztopval = pe.MapNode(interface=fsl.ImageMaths(op_string='-ztop',
        suffix='_pval'),
        name='z2pval',
        iterfield=['in_file'])

    wk.connect(flame,'zstats',ztopval,'in_file')
    wk.connect(ztopval,'out_file',outputspec,'pstat')

    return wk

def create_2lvl_rand(name="group_randomize"):
    import nipype.interfaces.fsl as fsl
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu
    import nipype.interfaces.io as nio
    wk = pe.Workflow(name=name)
    
    inputspec = pe.Node(niu.IdentityInterface(fields=['copes','varcopes',
                                                      'template', "contrasts",
                                                      "regressors"]),name='inputspec')
    
    model = pe.Node(fsl.MultipleRegressDesign(),name='l2model')

    wk.connect(inputspec, 'contrasts', model, "contrasts")
    wk.connect(inputspec, 'regressors', model, "regressors")

    mergecopes = pe.Node(fsl.Merge(dimension='t'),name='merge_copes')
    
    rand = pe.Node(fsl.Randomise(base_name='TwoSampleT', raw_stats_imgs=True, tfce=True),name='randomize')

    wk.connect(inputspec,'copes',mergecopes,'in_files')
    wk.connect(model,'design_mat',rand,'design_mat')
    wk.connect(model,'design_con',rand, 'tcon')
    wk.connect(mergecopes, 'merged_file', rand, 'in_file')
    wk.connect(model,'design_grp',rand,'x_block_labels')
    
    bet = pe.Node(fsl.BET(mask=True,frac=0.3),name="template_brainmask")
    wk.connect(inputspec,'template',bet,'in_file')
    wk.connect(bet,'mask_file',rand,'mask')

    outputspec = pe.Node(niu.IdentityInterface(fields=['f_corrected_p_files',
                                                       'f_p_files',
                                                       'fstat_files',
                                                       't_corrected_p_files',
                                                       't_p_files', 
                                                       'tstat_file','mask']),
                         name='outputspec')
                             
    wk.connect(rand,'f_corrected_p_files',outputspec,'f_corrected_p_files')
    wk.connect(rand,'f_p_files',outputspec,'f_p_files')
    wk.connect(rand,'fstat_files',outputspec,'fstat_files')
    wk.connect(rand,'t_corrected_p_files',outputspec,'t_corrected_p_files')
    wk.connect(rand,'t_p_files',outputspec,'t_p_files')
    wk.connect(rand,'tstat_files',outputspec,'tstat_file')
    wk.connect(bet,'mask_file',outputspec,'mask')

    return wk


def get_datagrabber(c):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio
    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id',
                                                             'fwhm',"contrast"],
        outfields=['copes','varcopes']),
        name="datagrabber")
    datasource.inputs.base_directory = c.base_dir
    datasource.inputs.template = '*'
    datasource.inputs.field_template = dict(
        copes=c.copes_template,
        varcopes=c.varcopes_template)
    datasource.inputs.template_args = dict(copes=[['fwhm',"contrast","subject_id"]],
        varcopes=[['fwhm',"contrast","subject_id"]])
    return datasource


from .workflow18 import get_substitutions

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
    return reg


def connect_to_config(c):

    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu
    import nipype.interfaces.io as nio
    
    if not c.do_randomize:
        wk = create_2lvl()
    else:
        wk  =create_2lvl_rand()
        
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
    wk.connect(datagrabber,'datagrabber.copes', inputspec, 'copes')
    if not c.do_randomize:
        wk.connect(datagrabber,'datagrabber.varcopes', inputspec, 'varcopes')
    wk.inputs.inputspec.template = c.norm_template

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

    wk.inputs.inputspec.regressors = get_regressors(c.design_csv,subjects)
    if not c.do_randomize:
        wk.connect(outputspec,'cope',sinkd,'output.@cope')
        wk.connect(outputspec,'varcope',sinkd,'output.@varcope')
        wk.connect(outputspec,'mrefvars',sinkd,'output.@mrefvars')
        wk.connect(outputspec,'pes',sinkd,'output.@pes')
        wk.connect(outputspec,'res4d',sinkd,'output.@res4d')
        wk.connect(outputspec,'weights',sinkd,'output.@weights')
        wk.connect(outputspec,'zstat',sinkd,'output.@zstat')
        wk.connect(outputspec,'tstat',sinkd,'output.@tstat')
        wk.connect(outputspec,'pstat',sinkd,'output.@pstat')
        wk.connect(outputspec,'tdof',sinkd,'output.@tdof')
        wk.connect(outputspec,'mask',sinkd,'output.@bet_mask')
        wk.connect(inputspec,'template',sinkd,'output.@template')

    if c.run_correction and not c.do_randomize:
        cluster = cluster_image()
        wk.connect(outputspec,"zstat",cluster,'inputspec.zstat')
        wk.connect(outputspec,"mask",cluster,"inputspec.mask")
        wk.connect(inputspec,"template",cluster,"inputspec.anatomical")
        cluster.inputs.inputspec.threshold = c.z_threshold
        cluster.inputs.inputspec.connectivity = c.connectivity
        wk.connect(cluster,'outputspec.corrected_z',sinkd,'output.corrected.@zthresh')
        wk.connect(cluster,'outputspec.slices',sinkd,'output.corrected.clusters')
        wk.connect(cluster,'outputspec.cuts',sinkd,'output.corrected.slices')

    if c.do_randomize:
        wk.connect(outputspec,'t_corrected_p_files',sinkd,'output.@t_corrected_p_files')
        wk.connect(outputspec,'t_p_files',sinkd,'output.@t_p_files')
        wk.connect(outputspec,'tstat_file',sinkd,'output.@tstat_file')

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

