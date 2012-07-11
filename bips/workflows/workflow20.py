import os
import nipype.interfaces.fsl as fsl
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as niu
import nipype.interfaces.io as nio
from .base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits

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
    # Subjects
    subjects = traits.List(traits.Str, mandatory=True, usedefault=True,
        desc="Subject id's. Note: These MUST match the subject id's in the \
                                Freesurfer directory. For simplicity, the subject id's should \
                                also match with the location of individual functional files.")
    fwhm=traits.List(traits.Float())
    copes_template = traits.String('%s/preproc/output/fwhm_%s/cope*.nii.gz')
    varcopes_template = traits.String('%s/preproc/output/fwhm_%s/varcope*.nii.gz')
    contrasts = traits.List(traits.Str,desc="contrasts")
    # Regression
    design_csv = traits.File(desc="design .csv file")
    reg_contrasts = traits.Code(desc="function named reg_contrasts which takes in 0 args and returns contrasts")

    #Normalization
    norm_template = traits.File(mandatory=True,desc='Template of files')

    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()

    # Buttons
    check_func_datagrabber = Button("Check")

def create_config():
    c = config()
    c.uuid = mwf.uuid
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
            Item(name='test_mode'),
            label='Execution Options', show_border=True),
        Group(Item(name='subjects', editor=CSVListEditor()),
            Item(name='base_dir'),
            Item(name='fwhm', editor=CSVListEditor()),
            Item(name="contrasts", editor=CSVListEditor()),
            Item(name='copes_template'),
            Item(name='varcopes_template'),
            Item(name='check_func_datagrabber'),
            label='Subjects', show_border=True),
        Group(Item(name='norm_template'),
            Item(name='design_csv'),
            Item(name="reg_contrasts"),
            Item(name="contrasts"),
            label='Second Level', show_border=True),
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
                                                       'tdof','weights']),
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

    return wk

def get_datagrabber(c):
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

def get_substitutions(contrast):
    subs = [('_fwhm','fwhm'),
        ('_contrast_%s'%contrast,''),
        ('output','')]
    return subs

def get_regressors(csv,ids):
    import numpy as np
    reg = {}
    design = np.recfromcsv(csv)
    design_str = np.recfromcsv(csv,dtype=str)
    print design_str.id
    names = design.dtype.names
    for n in names:
        if not n=="id":
            reg[n] = []
    for sub in ids:
        if sub in design_str["id"]:
            for key in reg.keys():
                reg[key].append(design[key][design_str["id"]==sub][0])
        else:
            raise Exception("%s is missing from the CSV file!"%sub)
    return reg


def connect_to_config(c):
    wk = create_2lvl()
    wk.base_dir = c.working_dir
    datagrabber = get_datagrabber(c)
    infosourcecon = pe.Node(niu.IdentityInterface(fields=["contrast"]),name="contrasts")
    infosourcecon.iterables = ("contrast",c.contrasts)
    wk.connect(infosourcecon,'contrast',datagrabber,"contrast")
    sinkd = pe.Node(nio.DataSink(),name='sinker')
    sinkd.inputs.base_directory = c.sink_dir
    wk.connect(infosourcecon,("contrast",get_substitutions),sinkd,"substitutions")
    wk.connect(infosourcecon,"contrast",sinkd,"container")
    inputspec = wk.get_node('inputspec')
    outputspec = wk.get_node('outputspec')
    datagrabber.inputs.subject_id = c.subjects
    infosource = pe.Node(niu.IdentityInterface(fields=['fwhm']),name='fwhm_infosource')
    infosource.iterables = ('fwhm',c.fwhm)
    wk.connect(infosource,'fwhm',datagrabber,'fwhm')
    wk.connect(datagrabber,'copes', inputspec, 'copes')
    wk.connect(datagrabber,'varcopes', inputspec, 'varcopes')
    wk.inputs.inputspec.template = c.norm_template

    cons = pe.Node(niu.Function(input_names=[],output_names=["contrasts"]),name="get_contrasts")
    cons.inputs.function_str = c.reg_contrasts
    #wk.inputs.inputspec.contrasts = c.reg_contrasts
    wk.connect(cons, "contrasts", inputspec,"contrasts")
    wk.inputs.inputspec.regressors = get_regressors(c.design_csv,c.subjects)

    wk.connect(outputspec,'cope',sinkd,'output.@cope')
    wk.connect(outputspec,'varcope',sinkd,'output.@varcope')
    wk.connect(outputspec,'mrefvars',sinkd,'output.@mrefvars')
    wk.connect(outputspec,'pes',sinkd,'output.@pes')
    wk.connect(outputspec,'res4d',sinkd,'output.@res4d')
    wk.connect(outputspec,'weights',sinkd,'output.@weights')
    wk.connect(outputspec,'zstat',sinkd,'output.@zstat')
    wk.connect(outputspec,'tstat',sinkd,'output.@tstat')
    wk.connect(outputspec,'tdof',sinkd,'output.@tdof')
    wk.connect(outputspec,'mask',sinkd,'output.@bet_mask')
    wk.connect(inputspec,'template',sinkd,'output.@template')
    return wk

mwf.workflow_function = connect_to_config

"""
Main
"""

def main(config_file):
    c = load_config(config_file, config)
    wk = connect_to_config(c)
    wk.config = {'execution': {'crashdump_dir': c.crash_dir}}

    if c.test_mode:
        wk.write_graph()
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

