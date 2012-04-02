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
from QA_utils import plot_ADnorm, tsdiffana, tsnr_roi, combine_table, art_output
import sys
sys.path.insert(0,'../../utils/')
from reportsink.io import ReportSink
import argparse

totable = lambda x: [[x]]
to1table = lambda x: [x]
pickfirst = lambda x: x[0]

def get_config_params(subject_id, table):
        table.insert(0,['subject_id',subject_id])
        return table

def preproc_datagrabber(name='preproc_datagrabber'):
    # create a node to obtain the preproc files
    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id','fwhm'],
                                                   outfields=['noise_components',
                                                              'motion_parameters',
                                                               'outlier_files',
                                                               'art_norm',
                                                               'tsnr',
                                                               'tsnr_detrended',
                                                               'tsnr_stddev',
                                                               'reg_file',
                                                               'motion_plots']),
                         name = name)
    datasource.inputs.base_directory = os.path.join(c.sink_dir,'analyses','func')
    datasource.inputs.template ='*'
    datasource.inputs.field_template = dict(motion_parameters='%s/preproc/motion/*.par',
                                            outlier_files='%s/preproc/art/*_outliers.txt',
                                            art_norm='%s/preproc/art/norm.*.txt',
                                            tsnr='%s/preproc/tsnr/*_tsnr.nii.gz',
                                            tsnr_detrended='%s/preproc/tsnr/*_detrended.nii.gz',
                                            tsnr_stddev='%s/preproc/tsnr/*tsnr_stddev.nii.gz',
                                            reg_file='%s/preproc/bbreg/*.dat',
                                            motion_plots='%s/preproc/motion/*.png')
    datasource.inputs.template_args = dict(motion_parameters=[['subject_id']],
                                           outlier_files=[['subject_id']],
                                           art_norm=[['subject_id']],
                                           tsnr=[['subject_id']],
                                           tsnr_stddev=[['subject_id']],
                                           reg_file=[['subject_id']],
                                           motion_plots=[['subject_id']])
    return datasource


def start_config_table():
    table = []
    table.append(['TR',str(c.TR)])
    table.append(['Slice Order',str(c.SliceOrder)])
    table.append(['Interleaved',str(c.Interleaved)])
    if c.use_fieldmap:
        table.append(['Echo Spacing',str(c.echospacing)])
        table.append(['Fieldmap Smoothing',str(c.sigma)])
        table.append(['TE difference',str(c.TE_diff)])
    table.append(['Art: norm thresh',str(c.norm_thresh)])
    table.append(['Art: z thresh',str(c.z_thresh)])
    table.append(['fwhm',str(c.fwhm)])
    try:
        table.append(['Highpass cutoff',str(c.hpcutoff)])
    except:
        table.append(['highpass sigma',str(c.highpass_sigma)])
        table.append(['lowpass sigma',str(c.lowpass_sigma)])
    return table

def overlay_new(stat_image,background_image):
    import os.path
    import pylab as pl
    from nibabel import load
    from nipy.labs import viz
    from pylab import colorbar, gca, axes
    # Second example, with a given anatomical image slicing in the Z
    # direction
    
    fnames = [os.path.abspath('z_view.png'),
             os.path.abspath('x_view.png'),
             os.path.abspath('y_view.png')]
            
    formatter='%.2f'
    img = load(stat_image)
    data, affine = img.get_data(), img.get_affine()
    
    anat_img = load(background_image)
    anat = anat_img.get_data()
    anat_affine = anat_img.get_affine()

    viz.plot_map(data, affine, anat=anat, anat_affine=anat_affine,
                 slicer='z', threshold=10, cmap=viz.cm._cm.hot)
    cb = colorbar(gca().get_images()[1], cax=axes([0.3, 0.00, 0.4, 0.07]),
                         orientation='horizontal', format=formatter)
    cb.set_ticks([cb._values.min(), cb._values.max()])
    pl.savefig(fnames[0],bbox_inches='tight')

    viz.plot_map(data, affine, anat=anat, anat_affine=anat_affine,
                 slicer='x', threshold=10, cmap=viz.cm._cm.hot)
    cb = colorbar(gca().get_images()[1], cax=axes([0.3, -0.06, 0.4, 0.07]), 
                         orientation='horizontal', format=formatter)
    cb.set_ticks([cb._values.min(), cb._values.max()])
    pl.savefig(fnames[1],bbox_inches='tight')

    viz.plot_map(data, affine, anat=anat, anat_affine=anat_affine,
                 slicer='y', threshold=10, cmap=viz.cm._cm.hot)
    cb = colorbar(gca().get_images()[1], cax=axes([0.3, -0.08, 0.4, 0.07]), 
                         orientation='horizontal', format=formatter)
    cb.set_ticks([cb._values.min(), cb._values.max()])
    pl.savefig(fnames[2],bbox_inches='tight')
    
    return fnames

    

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
    
    inputspec = pe.Node(interface=util.IdentityInterface(fields=['subject_id',
                                                                 'config_params',
                                                                 'in_file',
                                                                 'art_file',
                                                                 'motion_plots',
                                                                 'reg_file',
                                                                 'tsnr',
                                                                 'tsnr_mean',
                                                                 'tsnr_stddev',
                                                                 'ADnorm',
                                                                 'TR',
                                                                 'sd']),
                        name='inputspec')
    
    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
                         name='subject_names')
    infosource.iterables = ('subject_id', c.subjects)
    
    datagrabber = preproc_datagrabber()
    
    datagrabber.inputs.fwhm = c.fwhm
    
    orig_datagrabber = c.create_dataflow()
    
    workflow.connect(infosource, 'subject_id',
                     datagrabber, 'subject_id')
    
    workflow.connect(infosource, 'subject_id', orig_datagrabber, 'subject_id')
    
    workflow.connect(orig_datagrabber, 'func', inputspec, 'in_file')
    workflow.connect(infosource, 'subject_id', inputspec, 'subject_id')
    workflow.connect(datagrabber, 'outlier_files', inputspec, 'art_file')
    workflow.connect(datagrabber, 'motion_plots', inputspec, 'motion_plots')
    workflow.connect(datagrabber, 'reg_file', inputspec, 'reg_file')
    workflow.connect(datagrabber, 'tsnr', inputspec, 'tsnr')
    workflow.connect(datagrabber, 'tsnr_stddev', inputspec, 'tsnr_stddev')
    workflow.connect(datagrabber, 'art_norm', inputspec, 'ADnorm')
    
    inputspec.inputs.TR = c.TR
    inputspec.inputs.sd = c.surf_dir
    
    # Define Nodes

    tsdiff = pe.MapNode(util.Function(input_names = ['img'], 
                                      output_names = ['out_file'], 
                                      function=tsdiffana), 
                        name='tsdiffana', iterfield=["img"])
                        
    art_info = pe.MapNode(util.Function(input_names = ['art_file'], 
                                      output_names = ['table'], 
                                      function=art_output), 
                        name='art_output', iterfield=["art_file"])
    
    fssource = pe.Node(interface = FreeSurferSource(),name='fssource')
        
    roidevplot = tsnr_roi(plot=False,name='tsnr_stddev_roi',roi=['all'])
    roidevplot.inputs.inputspec.TR = c.TR
    roisnrplot = tsnr_roi(plot=False,name='SNR_roi',roi=['all'])
    roisnrplot.inputs.inputspec.TR = c.TR
    
    workflow.connect(fssource, ('aparc_aseg', pickfirst), roisnrplot, 'inputspec.aparc_aseg')
    workflow.connect(fssource, ('aparc_aseg', pickfirst), roidevplot, 'inputspec.aparc_aseg')
    
    workflow.connect(infosource, 'subject_id', roidevplot, 'inputspec.subject')
    workflow.connect(infosource, 'subject_id', roisnrplot, 'inputspec.subject')
    
    tablecombine = pe.MapNode(util.Function(input_names = ['roidev',
                                                        'roisnr'],
                                         output_names = ['roisnr'], 
                                         function = combine_table),
                           name='combinetable', iterfield=['roidev','roisnr'])
    
    
    
    adnormplot = pe.MapNode(util.Function(input_names = ['ADnorm','TR'], 
                                       output_names = ['plot'], 
                                       function=plot_ADnorm), 
                         name='ADnormplot', iterfield=['ADnorm'])
    
    
    
    convert = pe.Node(interface=fs.MRIConvert(),name='converter')
    
    voltransform = pe.MapNode(interface=ApplyVolTransform(),name='register',iterfield=['source_file'])
    
    overlaynew = pe.MapNode(util.Function(input_names=['stat_image','background_image'],
                                          output_names=['fnames'], function=overlay_new), 
                                          name='overlay_new', iterfield=['stat_image'])
    
    
    write_rep = pe.Node(interface=ReportSink(orderfields=['Introduction',
                                                          'in_file',
                                                          'config_params',
                                                          'Art_Detect',
                                                          'motion_plots',
                                                          'tsdiffana',
                                                          'ADnorm',
                                                          'TSNR_Images',
                                                          'tsnr_roi_table']),
                                             name='report_sink')
    write_rep.inputs.Introduction = "Quality Assurance Report for fMRI preprocessing."
    write_rep.inputs.base_directory = os.path.join(c.sink_dir,'analyses','func')
    workflow.connect(infosource,'subject_id',write_rep,'container')
    
    # Define Inputs
    
    convert.inputs.out_type = 'niigz'
    convert.inputs.in_type = 'mgz'
    
    # Define Connections
    workflow.connect(inputspec,'TR',adnormplot,'TR')
    workflow.connect(inputspec,'subject_id',fssource,'subject_id')
    workflow.connect(inputspec,'sd',fssource,'subjects_dir')
    workflow.connect(inputspec,'in_file',write_rep,'in_file')
    workflow.connect(inputspec,'art_file',art_info,'art_file')
    workflow.connect(art_info,('table',to1table), write_rep,'Art_Detect')
    workflow.connect(inputspec,'motion_plots',write_rep,'motion_plots')
    workflow.connect(inputspec,'in_file',tsdiff,'img')
    workflow.connect(tsdiff,"out_file",write_rep,"tsdiffana")
    workflow.connect(inputspec,('config_params',totable), write_rep,'config_params')
    workflow.connect(inputspec,'reg_file',roidevplot,'inputspec.reg_file')
    workflow.connect(inputspec,'tsnr_stddev',roidevplot,'inputspec.tsnr_file')
    workflow.connect(roidevplot,'outputspec.roi_table',tablecombine,'roidev')
    workflow.connect(inputspec,'reg_file',roisnrplot,'inputspec.reg_file')
    workflow.connect(inputspec,'tsnr',roisnrplot,'inputspec.tsnr_file')
    workflow.connect(roisnrplot,'outputspec.roi_table',tablecombine,'roisnr')
    workflow.connect(tablecombine, ('roisnr',to1table), write_rep, 'tsnr_roi_table')
    workflow.connect(inputspec,'ADnorm',adnormplot,'ADnorm')
    workflow.connect(adnormplot,'plot',write_rep,'ADnorm')
    workflow.connect(fssource,'orig',convert,'in_file')
    workflow.connect(convert,'out_file',voltransform,'target_file') 
    workflow.connect(inputspec,'reg_file',voltransform,'reg_file')
    workflow.connect(inputspec,'tsnr',voltransform, 'source_file')
    
    workflow.connect(voltransform,'transformed_file', overlaynew,'stat_image')
    workflow.connect(convert,'out_file', overlaynew,'background_image')
    
    workflow.connect(overlaynew, 'fnames', write_rep, 'TSNR_Images')
    
    workflow.write_graph()
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
    
    a = QA_workflow()
    a.base_dir = c.working_dir
    a.write_graph()
    a.inputs.inputspec.config_params = start_config_table()
    
    if c.run_on_grid:
        a.run(plugin=c.plugin,plugin_args=c.plugin_args)
    else:
        a.run()
    
