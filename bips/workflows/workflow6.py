import os
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
from nipype.interfaces.nipy import FmriRealign4d
import nipype.interfaces.fsl as fsl
import nipype.interfaces.spm as spm
from .base import MetaWorkflow, load_config, register_workflow
from ..utils.reportsink.io import ReportSink
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits
from workflow1 import get_dataflow

"""
Part 1: Define a MetaWorkflow
"""

desc = """
Compare Realignment Nodes workflow
=====================================

"""
mwf = MetaWorkflow()
mwf.uuid = '79755b1e8b1a11e1a2ae001e4fb1404c'
mwf.tags = ['motion_correction', 'test', 'nipy', 'fsl', 'spm']
mwf.help = desc

"""
Part 2: Define the config class & create_config function
"""

class config(HasTraits):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc='Workflow description')
    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    base_dir = Directory(os.path.abspath('.'),exists=True, desc='Base directory of data. (Should be subject-independent)')
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

    subjects= traits.List(traits.Str, mandatory=True, usedefault=True,
        desc="Subject id's. Note: These MUST match the subject id's in the \
                                    Freesurfer directory. For simplicity, the subject id's should \
                                    also match with the location of individual functional files.")
    func_template = traits.String('%s/functional.nii.gz')
    run_datagrabber_without_submitting = Bool(True, usedefault=True)
    # Motion Correction

    do_slicetiming = Bool(True, usedefault=True, desc="Perform slice timing correction")
    SliceOrder = traits.List(traits.Int)
    TR = traits.Float(mandatory=True, desc = "TR of functional")

    # Buttons
    check_func_datagrabber = Button("Check")
    def _check_func_datagrabber_fired(self):
        subs = self.subjects

        for s in subs:
            if not os.path.exists(os.path.join(self.base_dir,self.func_template % s)):
                print "ERROR", os.path.join(self.base_dir,self.func_template % s), "does NOT exist!"
                break
            else:
                print os.path.join(self.base_dir,self.func_template % s), "exists!"

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
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
            Item(name='json_sink'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'),
            label='Execution Options', show_border=True),
        Group(Item(name='subjects', editor=CSVListEditor()),
            Item(name='base_dir', ),
            Item(name='func_template'),
            Item(name='check_func_datagrabber'),
            Item(name='run_datagrabber_without_submitting'),
            label='Subjects', show_border=True),
        Group(Item(name='TR'),
            Item(name='SliceOrder', editor=CSVListEditor()),
            label='Motion Correction', show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Part 4: Workflow Construction
"""

def plot_trans(nipy1,nipy2,fsl,spm):
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')
    import numpy as np
    import os
    fname=os.path.abspath('translations.png')
    plt.subplot(411);plt.plot(np.genfromtxt(nipy1)[:,3:])
    plt.ylabel('nipy')
    plt.subplot(412);plt.plot(np.genfromtxt(nipy2)[:,3:])
    plt.ylabel('nipy_no_t')
    plt.subplot(413);plt.plot(np.genfromtxt(fsl)[:,3:])
    plt.ylabel('fsl')
    plt.subplot(414);plt.plot(np.genfromtxt(spm)[:,:3])
    plt.ylabel('spm')
    plt.savefig(fname)
    plt.close()
    return fname
  
    
def plot_rot(nipy1,nipy2,fsl,spm):
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')
    import numpy as np
    import os
    fname=os.path.abspath('rotations.png')
    plt.subplot(411);plt.plot(np.genfromtxt(nipy1)[:,:3])
    plt.ylabel('nipy')
    plt.subplot(412);plt.plot(np.genfromtxt(nipy2)[:,:3])
    plt.ylabel('nipy_no_t')
    plt.subplot(413);plt.plot(np.genfromtxt(nipy2)[:,:3])
    plt.ylabel('fsl')
    plt.subplot(414);plt.plot(np.genfromtxt(spm)[:,3:])
    plt.ylabel('spm')
    plt.savefig(fname)
    plt.close()
    return fname
    
    
def corr_mat(nipy1,nipy2,fsl,spm):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import os
    fname=os.path.abspath('correlation.png')
    allparams = np.hstack((np.genfromtxt(nipy1),
                    np.genfromtxt(nipy2),
                    np.genfromtxt(spm)[:,[3,4,5,0,1,2]]))
    plt.imshow(abs(np.corrcoef(allparams.T)), interpolation='nearest'); plt.colorbar()
    plt.savefig(fname)
    plt.close()
    return fname

def compare_workflow(c, name='compare_realignments'):
    import nipype.interfaces.matlab as mlab
    mlab.MatlabCommand.set_default_matlab_cmd("matlab -nodesktop -nosplash")
    mlab.MatlabCommand.set_default_paths('/software/spm8_4290')

    workflow =pe.Workflow(name=name)
    
    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
                         name='subject_names')
    if c.test_mode:
        infosource.iterables = ('subject_id', [c.subjects[0]])
    else:
        infosource.iterables = ('subject_id', c.subjects)
    
    datagrabber = get_dataflow(c)
    workflow.connect(infosource, 'subject_id', datagrabber, 'subject_id')
    
    realign_nipy = pe.Node(interface=FmriRealign4d(), name='realign_nipy')
    realign_nipy.inputs.tr = c.TR
    realign_nipy.inputs.slice_order = c.SliceOrder
    realign_nipy.inputs.time_interp=True

    realign_nipy_no_t = pe.Node(interface=FmriRealign4d(), name='realign_nipy_no_t')
    realign_nipy_no_t.inputs.tr = c.TR
    #realign_nipy_no_t.inputs.slice_order = c.SliceOrder

    
    realign_mflirt = pe.MapNode(interface=fsl.MCFLIRT(save_plots=True), name='mcflirt', iterfield=['in_file'])
    
    realign_spm = pe.MapNode(interface=spm.Realign(), name='spm', iterfield=['in_files'])
    
    report = pe.Node(interface=ReportSink(orderfields=['Introduction','Translations','Rotations','Correlation_Matrix']), name='write_report')
    report.inputs.Introduction = 'Comparing realignment nodes'
    report.inputs.base_directory= os.path.join(c.sink_dir)
    report.inputs.report_name = 'Comparing_Motion'
    
    rot = pe.MapNode(util.Function(input_names=['nipy1','nipy2','fsl','spm'],output_names=['fname'],function=plot_rot),name='plot_rot',
                     iterfield=['nipy1','nipy2','fsl','spm'])
    
    trans = pe.MapNode(util.Function(input_names=['nipy1','nipy2','fsl','spm'],output_names=['fname'],function=plot_trans),name='plot_trans',
                       iterfield=['nipy1','nipy2','fsl','spm'])

    coef = pe.MapNode(util.Function(input_names=['nipy1','nipy2','fsl','spm'],output_names=['fname'],function=corr_mat),name='cor_mat',
                      iterfield=['nipy1','nipy2','fsl','spm'])
    
    workflow.connect(datagrabber, 'func', realign_nipy, 'in_file')
    workflow.connect(datagrabber, 'func', realign_nipy_no_t, 'in_file')
    workflow.connect(datagrabber, 'func', realign_mflirt, 'in_file')
    workflow.connect(datagrabber, 'func', realign_spm, 'in_files')
    
    workflow.connect(realign_nipy, 'par_file', rot, 'nipy1')
    workflow.connect(realign_nipy_no_t, 'par_file', rot, 'nipy2')
    workflow.connect(realign_spm, 'realignment_parameters', rot, 'spm')
    workflow.connect(realign_mflirt, 'par_file', rot, 'fsl')
    
    workflow.connect(realign_nipy, 'par_file', trans, 'nipy1')
    workflow.connect(realign_nipy_no_t, 'par_file', trans, 'nipy2')
    workflow.connect(realign_spm, 'realignment_parameters', trans, 'spm')
    workflow.connect(realign_mflirt, 'par_file', trans, 'fsl')
    
    workflow.connect(realign_nipy, 'par_file', coef, 'nipy1')
    workflow.connect(realign_nipy_no_t, 'par_file', coef, 'nipy2')
    workflow.connect(realign_spm, 'realignment_parameters', coef, 'spm')
    workflow.connect(realign_mflirt, 'par_file', coef, 'fsl')
    
    workflow.connect(trans, 'fname', report, 'Translations')
    workflow.connect(rot, 'fname', report, 'Rotations')
    workflow.connect(coef, 'fname', report, 'Correlation_Matrix')
    workflow.connect(infosource,'subject_id',report,'container')
    
    return workflow

mwf.workflow_function = compare_workflow

"""
Part 5: Define the main function
"""

def main(config_file):

    c = load_config(config_file, create_config)
    
    compare = compare_workflow(c)
    compare.base_dir = c.working_dir
    if c.run_using_plugin:
        compare.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        compare.run()

mwf.workflow_main_function = main

"""
Part 6: Register the Workflow
"""

register_workflow(mwf)
