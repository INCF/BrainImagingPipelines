import os
from nipype.interfaces import fsl
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio
from .base import MetaWorkflow, load_json, register_workflow
from nipype.interfaces.io import FreeSurferSource
from .scripts.u0a14c5b5899911e1bca80023dfa375f2.utils import pickfirst
from .scripts.u0a14c5b5899911e1bca80023dfa375f2.QA_utils import tsnr_roi, \
                                                               make_surface_plots, \
                                                               write_report, \
                                                               show_slices, \
                                                               get_labels,\
                                                               get_coords
from .workflow1 import config_ui
from traitsui.menu import OKButton, CancelButton
from enthought.traits.ui.api import View, Item, Group

desc = """
fMRI First Level QA workflow
=====================================

"""
mwf = MetaWorkflow()
mwf.uuid = '9ecc82228b1d11e1b99a001e4fb1404c'
mwf.tags = ['QA','first-level','activation','constrast images']
mwf.config_ui = lambda : config_ui
mwf.help = desc
mwf.config_view = View(Group(Item(name='working_dir'),
    Item(name='sink_dir'),
    Item(name='crash_dir'),
    Item(name='json_sink'),
    Item(name='surf_dir'),
    label='Directories',show_border=True),
    Group(Item(name='run_on_grid'),
        Item(name='plugin',enabled_when="run_on_grid"),
        Item(name='plugin_args',enabled_when="run_on_grid"),
        Item(name='test_mode'),
        label='Execution Options',show_border=True),
    Group(Item(name='subjects'),
        Item(name='base_dir'),
        Item(name='func_template'),
        Item(name='check_func_datagrabber'),
        label='Subjects',show_border=True),
    Group(Item(name='use_fieldmap'),
        Item(name='field_dir',enabled_when="use_fieldmap"),
        Item(name='magnitude_template',enabled_when="use_fieldmap"),
        Item(name='phase_template',enabled_when="use_fieldmap"),
        Item(name='check_field_datagrabber',enabled_when="use_fieldmap"),
        Item(name='echospacing',enabled_when="use_fieldmap"),
        Item(name='TE_diff',enabled_when="use_fieldmap"),
        Item(name='sigma',enabled_when="use_fieldmap"),
        label='Fieldmap',show_border=True),
    Group(Item(name='TR'),
        Item(name='Interleaved'),
        Item(name='SliceOrder'),
        label='Motion Correction',show_border=True),
    Group(Item(name='norm_thresh'),
        Item(name='z_thresh'),
        label='Artifact Detection',show_border=True),
    Group(Item(name='compcor_select'),
        Item(name='num_noise_components'),
        label='CompCor',show_border=True),
    Group(Item(name='fwhm'),
        label='Smoothing',show_border=True),
    Group(Item(name='hpcutoff'),
        label='Highpass Filter',show_border=True),
    Group(Item(name='is_block_design'),
        Item(name='input_units'),
        Item(name='interscan_interval'),
        Item(name='film_threshold'),
        Item(name='subjectinfo'),
        Item(name='getcontrasts'),
        label='First Level',show_border=True),
    Group(Item(name='fx'),
          Item(name='thr'),
          Item(name='csize'),
          label='First Level QA',show_border=True),
    buttons = [OKButton, CancelButton],
    resizable=True,
    width=1050)

def img_wkflw(thr, csize, name='slice_image_generator'):
    inputspec = pe.Node(util.IdentityInterface(fields=['in_file',
                                                       'mask_file',
                                                       'anat_file',
                                                       'reg_file',
                                                       'subject_id',
                                                       'fsdir']),
                        name='inputspec')
    workflow = pe.Workflow(name=name)

    applymask = pe.MapNode(interface=fsl.ApplyMask(),
                           name='applymask',
                           iterfield=['in_file'])
    workflow.connect(inputspec,'in_file',applymask,'in_file')
    workflow.connect(inputspec,'mask_file',applymask,'mask_file')
    
    getlabels = pe.MapNode(util.Function( input_names = ["in_file",
                                                         "thr",
                                                         "csize"],
                                          output_names =["labels"],
                                          function = get_labels),
                           iterfield=['in_file'],
                           name = "getlabels")
    getlabels.inputs.csize = csize
    getlabels.inputs.thr = thr
                           
    workflow.connect(applymask,'out_file',getlabels,'in_file')
    
    getcoords = pe.MapNode(util.Function(input_names=["labels",
                                                      "in_file",
                                                      'subsess',
                                                      'fsdir'],
                                          output_names = ["coordinates",
                                                          "cs",
                                                          'locations',
                                                          'percents',
                                                          'meanval'],
                                          function= get_coords),
                                          iterfield=['labels','in_file'],
                           name="get_coords")
    
    
    workflow.connect(inputspec, 'subject_id', getcoords, 'subsess')
    workflow.connect(inputspec, 'fsdir', getcoords, 'fsdir')
    
    
    workflow.connect(getlabels,'labels', getcoords, 'labels')
    workflow.connect(applymask,'out_file',getcoords,'in_file')  
    
   
    showslices = pe.MapNode(util.Function(input_names=['image_in',
                                                       'anat_file',
                                                       'coordinates',
                                                       'thr'],
                                          output_names = ["outfiles"],
                                          function=show_slices),
                            iterfield= ['image_in','coordinates'],
                            name='showslices')  

    showslices.inputs.thr = thr
    
    workflow.connect(inputspec,'anat_file',showslices,'anat_file')
    workflow.connect(getcoords,'coordinates',showslices,'coordinates') 
    workflow.connect(applymask,'out_file',showslices,'image_in')
    
    outputspec = pe.Node(util.IdentityInterface(fields=['coordinates',
                                                        'cs',
                                                        'locations',
                                                        'percents',
                                                        'meanval',
                                                        'imagefiles']),
                         name='outputspec')
    workflow.connect(getcoords,'coordinates',outputspec,'coordinates')
    workflow.connect(getcoords,'cs',outputspec,'cs')
    workflow.connect(getcoords,'locations',outputspec,'locations')
    workflow.connect(getcoords,'percents',outputspec,'percents')
    workflow.connect(getcoords,'meanval',outputspec,'meanval')
    
    
    workflow.connect(showslices,'outfiles',outputspec,'imagefiles')
    
    return workflow               
    
def get_data(c,name='first_level_datagrab'):
    
    datasource = pe.Node(nio.DataGrabber(infields=['subject_id',
                                                   'fwhm'],
                                        outfields=['func',
                                                   'mask',
                                                   'reg',
                                                   'des_mat',
                                                   'des_mat_cov',
                                                   'detrended']),
                         name=name)

    datasource.inputs.template = '*'
    
    datasource.inputs.base_directory = os.path.join(c["sink_dir"],'analyses','func')
    
    datasource.inputs.field_template = dict(func='%s/modelfit/contrasts/fwhm_'+'%1d'+'/*/*zstat*',
                                            mask = '%s/preproc/mask/'+'*.nii',
                                            reg = '%s/preproc/bbreg/*.dat',
                                            detrended = '%s/preproc/tsnr/*detrended.nii.gz',
                                            des_mat = '%s/modelfit/design/fwhm_%1d/*/run?.png',
                                            des_mat_cov = '%s/modelfit/design/fwhm_%1d/*/*cov.png')
    
    datasource.inputs.template_args = dict(func=[['subject_id','fwhm']],
                                           mask=[['subject_id']], 
                                           reg = [['subject_id']],
                                           detrended = [['subject_id']],
                                           des_mat = [['subject_id','fwhm']],
                                           des_mat_cov = [['subject_id','fwhm']])
    return datasource
    
def get_fx_data(c, name='fixedfx_datagrab'):
    
    datasource = pe.Node(nio.DataGrabber(infields=['subject_id',
                                                   'fwhm'],
                                         outfields=['func',
                                                    'mask',
                                                    'reg',
                                                    'des_mat',
                                                    'des_mat_cov',
                                                    'detrended']),
                         name=name)

    datasource.inputs.template = '*'
    
    datasource.inputs.base_directory = os.path.join(c["sink_dir"],'analyses','func')
    
    datasource.inputs.field_template = dict(func='%s/fixedfx/fwhm_'+'%s'+'*zstat*',
                                            mask = '%s/preproc/mask/'+'*.nii',
                                            reg = '%s/preproc/bbreg/*.dat',
                                            detrended = '%s/preproc/tsnr/*detrended.nii.gz',
                                            des_mat = '%s/modelfit/design/fwhm_%s/*/run?.png',
                                            des_mat_cov = '%s/modelfit/design/fwhm_%s/*/*cov.png')
    
    datasource.inputs.template_args = dict(func=[['subject_id','fwhm']],
                                           mask=[['subject_id']], 
                                           reg = [['subject_id']],
                                           detrended = [['subject_id']],
                                           des_mat = [['subject_id','fwhm']],
                                           des_mat_cov = [['subject_id','fwhm']])
    return datasource
    
def combine_report(c, thr=2.326,csize=30,fx=False):

    if not fx:
        workflow = pe.Workflow(name='first_level_report')
        dataflow = get_data(c)
    else:
        workflow = pe.Workflow(name='fixedfx_report')
        dataflow =  get_fx_data(c)
    
    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
                         name='subject_names')
    infosource.iterables = ('subject_id', c["subjects"].split(','))
    
    infosource1 = pe.Node(util.IdentityInterface(fields=['fwhm']),
                         name='fwhms')
    infosource1.iterables = ('fwhm', c["fwhm"])
    
    fssource = pe.Node(interface = FreeSurferSource(),name='fssource')
    
    workflow.connect(infosource, 'subject_id', dataflow, 'subject_id')
    workflow.connect(infosource1, 'fwhm', dataflow, 'fwhm')
    
    workflow.connect(infosource, 'subject_id', fssource, 'subject_id')
    fssource.inputs.subjects_dir = c["surf_dir"]
    
    imgflow = img_wkflw(thr=thr,csize=csize)
    
    # adding cluster correction before sending to imgflow
    
    smoothest = pe.MapNode(fsl.SmoothEstimate(), name='smooth_estimate', iterfield=['zstat_file'])
    workflow.connect(dataflow,'func', smoothest, 'zstat_file')
    workflow.connect(dataflow,'mask',smoothest, 'mask_file')
    
    cluster = pe.MapNode(fsl.Cluster(), name='cluster', iterfield=['in_file','dlh','volume'])
    workflow.connect(smoothest,'dlh', cluster, 'dlh')
    workflow.connect(smoothest, 'volume', cluster, 'volume')
    cluster.inputs.connectivity = csize
    cluster.inputs.threshold = thr
    cluster.inputs.out_threshold_file = True
    workflow.connect(dataflow,'func',cluster,'in_file')
    
    workflow.connect(cluster, 'threshold_file',imgflow,'inputspec.in_file')
    #workflow.connect(dataflow,'func',imgflow, 'inputspec.in_file')
    workflow.connect(dataflow,'mask',imgflow, 'inputspec.mask_file')
    workflow.connect(dataflow,'reg',imgflow, 'inputspec.reg_file')
    
    workflow.connect(fssource,'brain',imgflow, 'inputspec.anat_file')
    
    workflow.connect(infosource, 'subject_id', imgflow, 'inputspec.subject_id')
    imgflow.inputs.inputspec.fsdir = c["surf_dir"]
    
    writereport = pe.Node(util.Function( input_names = ["cs",
                                                        "locations",
                                                        "percents",
                                                        "in_files",
                                                        "des_mat_cov",
                                                        "des_mat",
                                                        "subjects",
                                                        "meanval",
                                                        "imagefiles",
                                                        "surface_ims",
                                                        'thr',
                                                        'csize',
                                                        'fwhm',
                                                        'onset_images'],
                                        output_names =["report",
                                                       "elements"],
                                        function = write_report),
                          name = "writereport" )
    
    
    # add plot detrended timeseries with onsets if block
    if c["is_block_design"]:
        plottseries = tsnr_roi(plot=True)
        plottseries.inputs.inputspec.TR = c["TR"]
        workflow.connect(dataflow,'reg',plottseries, 'inputspec.reg_file')
        workflow.connect(fssource, ('aparc_aseg',pickfirst), plottseries, 'inputspec.aparc_aseg')
        workflow.connect(infosource, 'subject_id', plottseries, 'inputspec.subject')
        workflow.connect(dataflow, 'detrended', plottseries,'inputspec.tsnr_file')
        workflow.connect(infosource,('subject_id',c["subjectinfo"]),plottseries,'inputspec.onsets')
        workflow.connect(plottseries,'outputspec.out_file',writereport,'onset_images')
    else:
        writereport.inputs.onset_images = None
    
    
    
    #writereport = pe.Node(interface=ReportSink(),name='reportsink')
    #writereport.inputs.base_directory = os.path.join(c.sink_dir,'analyses','func')
    
    workflow.connect(infosource, 'subject_id', writereport, 'subjects')
    #workflow.connect(infosource, 'subject_id', writereport, 'container')
    workflow.connect(infosource1, 'fwhm', writereport, 'fwhm')
    
    writereport.inputs.thr = thr
    writereport.inputs.csize = csize
    
    makesurfaceplots = pe.Node(util.Function(input_names = ['con_image',
                                                            'reg_file',
                                                            'subject_id',
                                                            'thr',
                                                            'sd'],
                                              output_names = ['surface_ims',
                                                              'surface_mgzs'],
                                              function = make_surface_plots),
                               name = 'make_surface_plots')
    
    workflow.connect(infosource, 'subject_id', makesurfaceplots, 'subject_id')
    
    makesurfaceplots.inputs.thr = thr
    makesurfaceplots.inputs.sd = c["surf_dir"]
    
    sinker = pe.Node(nio.DataSink(), name='sinker')
    sinker.inputs.base_directory = os.path.join(c["sink_dir"],'analyses','func')
    
    workflow.connect(infosource,'subject_id',sinker,'container')
    workflow.connect(dataflow,'func',makesurfaceplots,'con_image')
    workflow.connect(dataflow,'reg',makesurfaceplots,'reg_file')
    
    workflow.connect(dataflow, 'des_mat', writereport, 'des_mat')
    workflow.connect(dataflow, 'des_mat_cov', writereport, 'des_mat_cov')
    workflow.connect(imgflow, 'outputspec.cs', writereport, 'cs')
    workflow.connect(imgflow, 'outputspec.locations', writereport, 'locations')
    workflow.connect(imgflow, 'outputspec.percents', writereport, 'percents')
    workflow.connect(imgflow, 'outputspec.meanval', writereport, 'meanval')
    workflow.connect(imgflow,'outputspec.imagefiles', writereport, 'imagefiles')
    
    workflow.connect(dataflow, 'func', writereport, 'in_files')
    workflow.connect(makesurfaceplots,'surface_ims', writereport, 'surface_ims')
    if not fx:
        workflow.connect(writereport,"report",sinker,"first_level_report")
    else:
        workflow.connect(writereport,"report",sinker,"fixed_fx_report")
    
    
    return workflow


def main(config):
    c = load_json(config)
    workflow = combine_report(c, fx=c["fx"],csize=c["csize"],thr=c["thr"])
    workflow.base_dir = c["working_dir"]

    if not os.environ['SUBJECTS_DIR'] == c["surf_dir"]:
        print "Your SUBJECTS_DIR is incorrect!"
        print "export SUBJECTS_DIR=%s"%c["surf_dir"]
        
    else:
        if c["run_on_grid"]:
            workflow.run(plugin=c["plugin"], plugin_args=c["plugin_args"])
        else:
            workflow.run()
        
mwf.workflow_main_function = main
register_workflow(mwf)