# Import Stuff
import os
from .base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from .flexible_datagrabber import Data, DataBase

"""
Part 1: Define a MetaWorkflow
"""

mwf = MetaWorkflow()
mwf.uuid = 'f6ac883016fe11e28310d4bed9336269'
mwf.help="""
One Sample T Test on Surface
============================

 """
mwf.tags=['fMRI','surface','one-sample']

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
    surface_template = traits.Enum("fsaverage","fsaverage5","fsaverage6","fsaverage4")
    # First Level
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
    dg = Data(['copes',
               'reg_files'])
    foo = DataBase()
    foo.name="subject_id"
    foo.iterable = False
    foo.values=["sub01","sub02"]
    dg.template= '*'
    dg.field_template = dict(copes='%s/modelfit/contrasts/_estimate_contrast0/cope01*.nii.gz',
        reg_files='%s/preproc/bbreg/*.dat')
    dg.template_args = dict(copes=[['subject_id']],
        reg_files=[['subject_id']])
    dg.fields = [foo]
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
            Item(name='surf_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'), Item(name="timeout"),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),Item(name="surface_template"),
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

def do_format(copes,regfiles):
    out = []
    if not len(copes) == len(regfiles):
        raise Exception("mismatch in number of copes and regfiles")
    for i, c in enumerate(copes):
        out.append((c,regfiles[i]))
    return out
    

def get_surface_workflow(name='surface_1sample'):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.freesurfer as fs
    import nipype.interfaces.io as nio
    import nipype.interfaces.utility as niu

    wf = pe.Workflow(name=name)
    inputspec = pe.Node(niu.IdentityInterface(fields=["copes","regfiles","surf_template","subjects_dir"]),name='inputspec')
    formatter = pe.Node(niu.Function(input_names=['copes','regfiles'],output_names=['out'],function=do_format),name='formatter')    
    preproc = pe.MapNode(fs.MRISPreproc(),name='preproc',iterfield=['hemi'])
    preproc.inputs.hemi = ['lh','rh']
    glmfit = pe.MapNode(fs.GLMFit(one_sample=True,surf=True),name='glmfit',iterfield=['hemi','in_file'])
    glmfit.inputs.hemi = ['lh','rh']
    outputspec = pe.Node(niu.IdentityInterface(fields=["beta_file",
                                                       "dof_file",
                                                       "error_file",
                                                       "error_stddev_file",
                                                       "error_var_file",
                                                       "estimate_file",
                                                       "frame_eigenvectors",
                                                       "ftest_file",
                                                       "fwhm_file",
                                                       "gamma_file",
                                                       "gamma_var_file",
                                                       "mask_file",
                                                       "sig_file"]),name='outputspec')
    #connections
    wf.connect(inputspec,'copes',formatter,'copes')
    wf.connect(inputspec,'regfiles',formatter,'regfiles')
    wf.connect(inputspec,'surf_template',preproc,'target')
    wf.connect(inputspec,'surf_template',glmfit,'subject_id')
    wf.connect(inputspec,'subjects_dir',preproc,'subjects_dir')
    wf.connect(inputspec,'subjects_dir',glmfit,'subjects_dir')

    wf.connect(formatter,'out',preproc,'vol_measure_file')
   
    wf.connect(preproc,'out_file',glmfit,'in_file')

    wf.connect([(glmfit,outputspec,[('beta_file','beta_file'),
                                    ('dof_file','dof_file'),
                                    ('error_file','error_file'),
                                    ('error_stddev_file','error_stddev_file'),
                                    ('error_var_file','error_var_file'),
                                    ('estimate_file','estimate_file'),
                                    ('frame_eigenvectors','frame_eigenvectors'),
                                    ('ftest_file','ftest_file'),
                                    ('fwhm_file','fwhm_file'),
                                    ('gamma_file','gamma_file'),
                                    ('gamma_var_file','gamma_var_file'),
                                    ('mask_file','mask_file'),
                                    ('sig_file','sig_file')])])
    return wf

def connect_wf(c):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio
    import nipype.interfaces.utility as niu

    wf = get_surface_workflow()
    dg = c.datagrabber.create_dataflow()
    sink = pe.Node(nio.DataSink(),name='sinker')
    sink.inputs.base_directory = c.sink_dir
    inputspec = wf.get_node('inputspec')
    outputspec = wf.get_node('outputspec')

    wf.inputs.inputspec.surf_template = c.surface_template
    wf.inputs.inputspec.subjects_dir = c.surf_dir

    wf.connect(dg,'datagrabber.copes',inputspec,'copes')
    wf.connect(dg,'datagrabber.reg_files',inputspec,'regfiles')

    wf.connect([(outputspec,sink,[('beta_file','beta_file'),
                                    ('dof_file','dof_file'),
                                    ('error_file','error_file'),
                                    ('error_stddev_file','error_stddev_file'),
                                    ('error_var_file','error_var_file'),
                                    ('estimate_file','estimate_file'),
                                    ('frame_eigenvectors','frame_eigenvectors'),
                                    ('ftest_file','ftest_file'),
                                    ('fwhm_file','fwhm_file'),
                                    ('gamma_file','gamma_file'),
                                    ('gamma_var_file','gamma_var_file'),
                                    ('mask_file','mask_file'),
                                    ('sig_file','sig_file')])])
    return wf

mwf.workflow_function = connect_wf

def main(config_file):
    c = load_config(config_file, create_config)

    wf = connect_wf(c)
    wf.base_dir = c.working_dir
    wf.config = {"execution":{"crashdump_dir": c.crash_dir, "job_finished_timeout": c.timeout}}
    if c.run_using_plugin:
        wf.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        wf.run()

mwf.workflow_main_function = main

"""
Part 6: Register the Workflow
"""

register_workflow(mwf) 
