import matplotlib
matplotlib.use('Agg')
import os
import matplotlib.pyplot as plt
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio
from time import ctime
from glob import glob
from nipype.interfaces.freesurfer import ApplyVolTransform
from nipype.workflows.smri.freesurfer.utils import create_get_stats_flow
from nipype.interfaces import freesurfer as fs
from nipype.interfaces.io import FreeSurferSource
from nipype.interfaces import fsl
#from nipype.utils.config import config
#config.enable_debug_mode()
from QA_utils import plot_ADnorm, tsdiffana
import sys
sys.path.insert(0,'../../utils/')
from reportsink.io import ReportSink

totable = lambda x: [[x]]

def reporter(in_file,art_file,config_params,motion_plots,tsdiffana,
             ADnorm, overlayMean):
             #roiplot,tsnr_roi_table, ADnorm, overlayMean):
    from write_report import report # This is located in ~keshavan/lib/python
    import numpy as np
    import os
    # first some handy functions
    def count_outs(art_file):   
        try:
            a = np.genfromtxt(art_file)
            if a.shape ==():
                num_arts = 1
                arts = [a]
            else:
                num_arts = a.shape[0]
                arts = a
        except:
            num_arts = 0
            arts = []
        return arts, num_arts
    
    rep = report(os.path.abspath('QA_Report.pdf'),'Quality Assurance Report')
    rep.add_text('<b>In files: </b>')
    for f in in_file:
        rep.add_text(f)
       
    # config
    rep.add_text('<b>Configuration</b>:')  
    rep.add_table(config_params)
          
    # Artifact Detection    
    rep.add_text('<b>Artifact Detection: </b>')
    arts, num_arts = count_outs(art_file)
    rep.add_text('Number of artifacts: %s'%str(num_arts))
    rep.add_text('Timepoints: %s'%str(arts))
    
    # Motion plots
    rep.add_text('<b>Motion Plots: </b>')
    for m in motion_plots:
        rep.add_image(m)
    
    # Composite Norm plot
    rep.add_text('<b>Composite Norm Plot: </b>')
    rep.add_image(ADnorm,scale=1)
    
    # TSNR overlay
    rep.add_text('<b>TSNR Overlay: </b>')
    rep.add_image(overlayMean,scale=0.8)
    
    #tsdiffana
    rep.add_pagebreak()
    rep.add_text('<b>Time Series Diagnostics: </b>')
    for tsdiff in tsdiffana:
        rep.add_image(tsdiff[0])
        
    # ROI mean table
    #rep.add_text('<b>TSNR Mean and Standard Deviation: </b>')
    #rep.add_table(tsnr_roi_table)
    
    # ROI plots
    #rep.add_text('<b>ROI plots: </b>')
    #for pl in roiplot:
    #    rep.add_image(pl,scale=0.6)
        
    fname = rep.write()
    return fname
    
    

def QA_workflow(name='QA'):
    """ Workflow that generates a Quality Assurance Report
    
    Parameters
    ----------
    name : name of workflow
    
    Inputs
    ------
    inputspec.subject_id :
    inputspec.config_params :
    inputspec.in_file :
    inputspec.art_file :
    inputspec.motion_plots :
    inputspec.reg_file :
    inputspec.tsnr_detrended :
    inputspec.tsnr :
    inputspec.tsnr_mean :
    inputspec.tsnr_stddev :
    inputspec.ADnorm :
    inputspec.TR :
    inputspec.sd : freesurfer subjects directory
    
    """
    
    # Define Workflow
        
    workflow =pe.Workflow(name=name)
    
    # Define Nodes
    
    inputspec = pe.Node(interface=util.IdentityInterface(fields=['subject_id',
                                                                 'config_params',
                                                                 'in_file',
                                                                 'art_file',
                                                                 'motion_plots',
                                                                 'reg_file',
                                                                 'tsnr_detrended',
                                                                 'tsnr',
                                                                 'tsnr_mean',
                                                                 'tsnr_stddev',
                                                                 'ADnorm',
                                                                 'TR',
                                                                 'sd']),
                        name='inputspec')
    """                    
    write_rep = pe.Node(util.Function(input_names=['in_file',
                                                   'art_file',
                                                   'config_params',
                                                   'motion_plots',
                                                   'tsdiffana',
                                                   'roiplot',
                                                   'tsnr_roi_table',
                                                   'ADnorm',
                                                   'overlayMean'],
                                      output_names=['fname'],
                                      function=reporter),
                        name='write_report')
    """
    tsdiff = pe.MapNode(util.Function(input_names = ['img'], 
                                      output_names = ['out_file'], 
                                      function=tsdiffana), 
                        name='tsdiffana', iterfield=["img"])
    
    #roiplot = tsnr_roi(sd=surf_dir,subject=subjects[0],TR=TR,plot=True)
    
    #tablecombine = pe.Node(util.Function(input_names = ['roimean',
    #                                                    'roidev',
    #                                                    'roisnr'],
    #                                     output_names = ['roisnr'], 
    #                                     function = combine_table),
    #                       name='combinetable')
    
    #roiavgplot = tsnr_roi(plot=False,name='tsnr_mean_roi',roi=['all'])
    
    #roidevplot = tsnr_roi(plot=False,name='tsnr_stddev_roi',roi=['all'])
    
    #roisnrplot = tsnr_roi(plot=False,name='SNR_roi',roi=['all'])
    
    adnormplot = pe.MapNode(util.Function(input_names = ['ADnorm','TR'], 
                                       output_names = ['plot'], 
                                       function=plot_ADnorm), 
                         name='ADnormplot', iterfield=['ADnorm'])
    
    fssource = pe.Node(interface = FreeSurferSource(),name='fssource')
    
    convert = pe.Node(interface=fs.MRIConvert(),name='converter')
    
    voltransform = pe.MapNode(interface=ApplyVolTransform(),name='register',iterfield=['source_file'])
    
    overlay = pe.MapNode(interface = fsl.Overlay(),name ='overlay',iterfield=['stat_image'])
    
    convert2 = pe.MapNode(interface=fsl.SwapDimensions(),name='converter2',iterfield=["in_file"])
    
    slicer = pe.MapNode(interface=fsl.Slicer(),name='slicer',iterfield=['in_file'])
    
    write_rep = pe.Node(interface=ReportSink(),name='report_sink')
    write_rep.inputs.Introduction = "Quality Assurance Report for fMRI preprocessing."
    
    # Define Inputs
    
    convert.inputs.out_type = 'niigz'
    convert.inputs.in_type = 'mgz'
    overlay.inputs.full_bg_range = True
    overlay.inputs.stat_thresh = (0.0,100.0)
    convert2.inputs.new_dims = ('RL','PA','IS')
    slicer.inputs.middle_slices = True
    
    # Define Connections
    workflow.connect(inputspec,'TR',adnormplot,'TR')
    workflow.connect(inputspec,'subject_id',fssource,'subject_id')
    workflow.connect(inputspec,'sd',fssource,'subjects_dir')
    workflow.connect(inputspec,'in_file',write_rep,'in_file')
    workflow.connect(inputspec,'art_file',write_rep,'art_file')
    workflow.connect(inputspec,'motion_plots',write_rep,'motion_plots')
    workflow.connect(inputspec,'in_file',tsdiff,'img')
    workflow.connect(tsdiff,"out_file",write_rep,"tsdiffana")
    workflow.connect(inputspec,('config_params',totable), write_rep,'config_params')
    #workflow.connect(inputspec,'reg_file',roiplot,'inputspec.reg_file')
    #workflow.connect(inputspec,'tsnr_detrended',roiplot,'inputspec.tsnr_file')
    #workflow.connect(roiplot,'outputspec.out_file',write_rep,'roiplot')
    #workflow.connect(inputspec,'reg_file',roiavgplot,'inputspec.reg_file')
    #workflow.connect(inputspec,'tsnr_mean',roiavgplot,'inputspec.tsnr_file')
    #workflow.connect(roiavgplot,'outputspec.out_file',tablecombine,'roimean')
    #workflow.connect(inputspec,'reg_file',roidevplot,'inputspec.reg_file')
    #workflow.connect(inputspec,'tsnr_stddev',roidevplot,'inputspec.tsnr_file')
    #workflow.connect(roidevplot,'outputspec.out_file',tablecombine,'roidev')
    #workflow.connect(inputspec,'reg_file',roisnrplot,'inputspec.reg_file')
    #workflow.connect(inputspec,'tsnr',roisnrplot,'inputspec.tsnr_file')
    #workflow.connect(roisnrplot,'outputspec.out_file',tablecombine,'roisnr')
    #workflow.connect(tablecombine, 'roisnr', write_rep, 'tsnr_roi_table')
    workflow.connect(inputspec,'ADnorm',adnormplot,'ADnorm')
    workflow.connect(adnormplot,'plot',write_rep,'ADnorm')
    workflow.connect(fssource,'orig',convert,'in_file')
    workflow.connect(convert,'out_file',voltransform,'target_file') 
    workflow.connect(inputspec,'reg_file',voltransform,'reg_file')
    workflow.connect(inputspec,'tsnr',voltransform, 'source_file')
    workflow.connect(voltransform,'transformed_file', overlay,'stat_image')
    workflow.connect(convert,'out_file', overlay,'background_image')
    workflow.connect(overlay,'out_file',convert2,'in_file')
    workflow.connect(convert2,'out_file',slicer,'in_file') 
    workflow.connect(slicer,'out_file',write_rep,'overlayMean')
    
    workflow.write_graph()
    return workflow
    
if __name__ == "__main__":
    a = QA_workflow()
    a.base_dir = './'
    a.write_graph()
    a.inputs.inputspec.subject_id = 'SAD_018'
    a.inputs.inputspec.TR = 2.5
    a.inputs.inputspec.sd = '/mindhive/xnat/surfaces/sad'
    a.inputs.inputspec.in_file = ['/mindhive/gablab/sad/PY_STUDY_DIR/Block/data/SAD_018/f3.nii']
    a.inputs.inputspec.art_file = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/analyses/func/SAD_018/preproc/art/fwhm_5/art.corr_f3_dtype.nii_outliers.txt'
    a.inputs.inputspec.motion_plots = glob('/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/analyses/func/SAD_018/preproc/motion/*.png')
    a.inputs.inputspec.reg_file = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/analyses/func/SAD_018/preproc/bbreg/_register0/corr_f3_dtype_mean_bbreg_SAD_018.dat'
    a.inputs.inputspec.tsnr_detrended = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/work_dir/SAD_018/preproc/preproc/compcorr/_fwhm_5/tsnr/mapflow/_tsnr0/corr_f3_dtype_detrended.nii.gz'
    a.inputs.inputspec.tsnr_mean = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/work_dir/SAD_018/preproc/preproc/compcorr/_fwhm_5/tsnr/mapflow/_tsnr0/corr_f3_dtype_tsnr_mean.nii.gz'
    a.inputs.inputspec.tsnr = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/work_dir/SAD_018/preproc/preproc/compcorr/_fwhm_5/tsnr/mapflow/_tsnr0/corr_f3_dtype_tsnr.nii.gz'
    a.inputs.inputspec.tsnr_stddev = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/work_dir/SAD_018/preproc/preproc/compcorr/_fwhm_5/tsnr/mapflow/_tsnr0/corr_f3_dtype_tsnr_stddev.nii.gz'
    a.inputs.inputspec.ADnorm = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/analyses/func/SAD_018/preproc/art/norm.corr_f3_dtype.nii.txt'
    a.inputs.inputspec.config_params = [['Subject','TR'],['SAD_018',2.5]]
    a.run()
    
