import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio
import argparse
from nipype.interfaces.nipy import FmriRealign4d
import nipype.interfaces.fsl as fsl
import nipype.interfaces.spm as spm
import sys
sys.path.append('../../utils')
from reportsink.io import ReportSink
import os
import matplotlib
matplotlib.use('Agg')
from nipype import config
config.set('execution', 'remove_unnecessary_outputs', 'false')

def pickfirst(files):
    """Return first file from a list of files

    Parameters
    ----------
    files : list of filenames

    Returns
    -------
    file : returns the filename corresponding to the middle run
    """
    if isinstance(files, list):
        return files[0]
    else:
        return files

def plot_trans(nipy1,nipy2,fsl,spm):
    import matplotlib.pyplot as plt
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

def compare_workflow(name='compare_realignments'):
    
    workflow =pe.Workflow(name=name)
    
    datagrabber = c.create_dataflow()
    datagrabber.inputs.subject_id = c.subjects[0]
    
    realign_nipy = pe.Node(interface=FmriRealign4d(), name='realign_nipy')
    realign_nipy.inputs.tr = c.TR
    realign_nipy.inputs.slice_order = c.SliceOrder
    realign_nipy.inputs.interleaved = c.Interleaved
    
    realign_nipy_no_t = pe.Node(interface=FmriRealign4d(time_interp=False), name='realign_nipy_no_t')
    realign_nipy_no_t.inputs.tr = c.TR
    realign_nipy_no_t.inputs.slice_order = c.SliceOrder
    realign_nipy_no_t.inputs.interleaved = c.Interleaved
    
    
    realign_mflirt = pe.Node(interface=fsl.MCFLIRT(save_plots=True), name='mcflirt')
    
    realign_spm = pe.Node(interface=spm.Realign(), name='spm')
    
    report = pe.Node(interface=ReportSink(orderfields=['Introduction','Translations','Rotations','Correlation_Matrix']), name='write_report')
    report.inputs.Introduction = 'Comparing realignment nodes for subject %s'%c.subjects[0]
    report.inputs.base_directory= '.'
    
    rot = pe.Node(util.Function(input_names=['nipy1','nipy2','fsl','spm'],output_names=['fname'],function=plot_rot),name='plot_rot')
    
    trans = pe.Node(util.Function(input_names=['nipy1','nipy2','fsl','spm'],output_names=['fname'],function=plot_trans),name='plot_trans')

    coef = pe.Node(util.Function(input_names=['nipy1','nipy2','fsl','spm'],output_names=['fname'],function=corr_mat),name='cor_mat')
    
    workflow.connect(datagrabber, ('func',pickfirst), realign_nipy, 'in_file')
    workflow.connect(datagrabber, ('func',pickfirst), realign_nipy_no_t, 'in_file')
    workflow.connect(datagrabber, ('func',pickfirst), realign_mflirt, 'in_file')
    workflow.connect(datagrabber, ('func',pickfirst), realign_spm, 'in_files')
    
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

    return workflow

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="example: \
                        run resting_preproc.py -c config.py")
    parser.add_argument('-c','--config',
                        dest='config',
                        required=True,
                        help='location of config file'
                        )
    args = parser.parse_args()
    path, fname = os.path.split(os.path.realpath(args.config))
    sys.path.append(path)
    c = __import__(fname.split('.')[0])
    
    compare = compare_workflow(name='compare_sad_task')
    compare.base_dir = os.getcwd()
    compare.run(plugin='PBS')
