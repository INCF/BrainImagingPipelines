from .base import MetaWorkflow, load_json, register_workflow
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
from nipype.interfaces.nipy import FmriRealign4d
import nipype.interfaces.fsl as fsl
import nipype.interfaces.spm as spm
from bips.utils.reportsink.io import ReportSink
import os
from nipype import config
config.set('execution', 'remove_unnecessary_outputs', 'false')
from workflow2 import r_config, view
from workflow1 import get_dataflow


desc = """
Compare Realignment Nodes workflow
=====================================

"""
mwf = MetaWorkflow()
mwf.uuid = '79755b1e8b1a11e1a2ae001e4fb1404c'
mwf.tags = ['motion_correction', 'test', 'nipy', 'fsl', 'spm']
mwf.config_ui = lambda : r_config
mwf.config_view = view
mwf.help = desc

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
    infosource.iterables = ('subject_id', c["subjects"].split(','))
    
    datagrabber = get_dataflow(c)
    workflow.connect(infosource, 'subject_id', datagrabber, 'subject_id')
    
    realign_nipy = pe.Node(interface=FmriRealign4d(), name='realign_nipy')
    realign_nipy.inputs.tr = c["TR"]
    realign_nipy.inputs.slice_order = c["SliceOrder"]
    realign_nipy.inputs.interleaved = c["Interleaved"]
    
    realign_nipy_no_t = pe.Node(interface=FmriRealign4d(time_interp=False), name='realign_nipy_no_t')
    realign_nipy_no_t.inputs.tr = c["TR"]
    realign_nipy_no_t.inputs.slice_order = c["SliceOrder"]
    realign_nipy_no_t.inputs.interleaved = c["Interleaved"]
    
    
    realign_mflirt = pe.MapNode(interface=fsl.MCFLIRT(save_plots=True), name='mcflirt', iterfield=['in_file'])
    
    realign_spm = pe.MapNode(interface=spm.Realign(), name='spm', iterfield=['in_files'])
    
    report = pe.Node(interface=ReportSink(orderfields=['Introduction','Translations','Rotations','Correlation_Matrix']), name='write_report')
    report.inputs.Introduction = 'Comparing realignment nodes'
    report.inputs.base_directory= os.path.join(c["sink_dir"],'analyses','func')
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

def main(config):

    c = load_json(config)
    
    compare = compare_workflow(c)
    compare.base_dir = c["working_dir"]
    if c["run_on_grid"]:
        compare.run(plugin=c["plugin"], plugin_args=c["plugin_args"])
    else:
        compare.run()

mwf.workflow_main_function = main
register_workflow(mwf)