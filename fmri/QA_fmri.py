import matplotlib
matplotlib.use('Agg')
import os
import matplotlib.pyplot as plt
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio
from write_report import report
from config import *
from time import ctime
from glob import glob
from nipype.interfaces.freesurfer import ApplyVolTransform
from nipype.workflows.smri.freesurfer.utils import create_get_stats_flow
from nipype.interfaces import freesurfer as fs
from nipype.interfaces.io import FreeSurferSource
from nipype.interfaces import fsl
from nipype.utils.config import config
config.enable_debug_mode()


def plot_ADnorm(ADnorm,TR):
    # plots the AD norm file
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import os
    import numpy as np
    
    plot = os.path.abspath('plot_'+os.path.split(ADnorm)[1]+'.png')
    
    data = np.genfromtxt(ADnorm)
    print data.shape    
    plt.figure(1,figsize = (8,3))
    X = np.array(range(data.shape[0]))*TR
    plt.plot(X,data)
    plt.xlabel('Time (s)')
    plt.ylabel('Composite Norm')
    plt.savefig(plot)
    return plot

def tsnr_roi(sd,subject,TR,roi=[1021],name='tsnr_roi',plot=False):
    preproc = pe.Workflow(name=name)
    
    inputspec = pe.Node(interface=util.IdentityInterface(fields=['reg_file','tsnr_file']),name='inputspec')
    
    voltransform = pe.Node(interface=ApplyVolTransform(inverse=True, interp='nearest'),name='applyreg')
    
    preproc.connect(inputspec,'tsnr_file',voltransform,'source_file')
    
    preproc.connect(inputspec,'reg_file',voltransform,'reg_file')
    
    voltransform.inputs.target_file = os.path.join(sd,subject,'mri/aparc+aseg.mgz')
    
    
    statsflow = create_get_stats_flow()
    preproc.connect(voltransform,'transformed_file',statsflow,'inputspec.label_file')
    preproc.connect(inputspec,'tsnr_file',statsflow,'inputspec.source_file')
    
    statsflow.inputs.segstats.avgwf_txt_file = True

    def strip_ids(subject_id, summary_file, roi_file):
        import numpy as np
        import os
        roi_idx = np.genfromtxt(summary_file[0])[:,1].astype(int)
        roi_vals = np.genfromtxt(roi_file[0])
        rois2skip = [0, 2, 4, 5, 7, 14, 15, 24, 30, 31, 41, 43, 44, 46,
                     62, 63, 77, 80, 85, 1000, 2000]
        ids2remove = []
        for roi in rois2skip:
            idx, = np.nonzero(roi_idx==roi)
            ids2remove.extend(idx)
        ids2keep = np.setdiff1d(range(roi_idx.shape[0]), ids2remove)
        filename = os.path.join(os.getcwd(), subject_id+'.csv')
        newvals = np.vstack((roi_idx[ids2keep], roi_vals[:, np.array(ids2keep)])).T
        np.savetxt(filename, newvals, '%.4f', delimiter=',')
        return filename

    roistripper = pe.Node(util.Function(input_names=['subject_id', 'summary_file', 'roi_file'],
                                       output_names=['roi_file'],
                                       function=strip_ids),
                          name='roistripper')
    roistripper.inputs.subject_id = subject

    preproc.connect(statsflow, 'segstats.avgwf_txt_file', roistripper, 'roi_file')
    preproc.connect(statsflow, 'segstats.summary_file', roistripper, 'summary_file')

    def plot_timeseries(roi,statsfile,TR,plot):
        import numpy as np
        import os
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        stats = np.recfromcsv(statsfile)     
        
        LUT = np.genfromtxt('/software/Freesurfer/current/FreeSurferColorLUT.txt',dtype = str)
        roinum = LUT[:,0]
        roiname = LUT[:,1]
        Fname = []
        
        if roi == ['all']:
            roi = []
            for i, r in enumerate(stats):
                roi.append(list(r)[0]) 
        
        for R in roi:
            temp = False
            #ghetto for loop: find index of roi in stats list
            for i, r in enumerate(stats):
                if list(r)[0] == R:
                    temp = True
                    break    
            
            if temp:
                #find roi name for plot title
                print roinum.shape
                print R, roiname[roinum==str(np.int_(R))]
                title = roiname[roinum==str(np.int_(R))][0]
                if plot:
                    nums = list(stats[i])[1:]
                    X = np.array(range(len(nums)))*TR
                    plt.figure(1)
                    p1 = plt.plot(X,nums)
                        
                    plt.title(title)
                    plt.xlabel('time (s)')
                    plt.ylabel('signal')
                    fname = os.path.join(os.getcwd(),os.path.split(statsfile)[1][:-4]+'_'+title+'.png')
                    plt.savefig(fname,dpi=200)
                    plt.close()
                    print fname
                    Fname.append(fname)
                else:
                    Fname.append([title,list(stats[i])[1]])
            else:
                print "roi %s not found!"%R
        print Fname        
        return Fname

    roiplotter = pe.Node(util.Function(input_names=['statsfile', 'roi','TR','plot'],
                                       output_names=['Fname'],
                                       function=plot_timeseries),
                          name='roiplotter')
    roiplotter.inputs.roi = roi
    roiplotter.inputs.TR = TR
    roiplotter.inputs.plot = plot

    preproc.connect(roistripper,'roi_file',roiplotter,'statsfile')
    outputspec = pe.Node(interface=util.IdentityInterface(fields=['out_file']),name='outputspec')
    preproc.connect(roiplotter,'Fname',outputspec,'out_file')

    return preproc
    
def tsdiffana(img):
    # Should be a nipype wrapper, but for now a function node.
    from nipy.algorithms.diagnostics import tsdiffplot as tdp
    import os
    import matplotlib.pyplot as plt

    axes = tdp.plot_tsdiffs_image(img, axes=None, show=False)
    out_file = []
    
    of = os.path.abspath("tsdiffana_"+os.path.split(img)[1]+".png")
    x = plt.sca(axes[0])
    plt.savefig(of,dpi=300)
    out_file.append(of)
    
    return out_file
    
def reporter(in_file,art_file,config_params,motion_plots,tsdiffana,roiplot,tsnr_roi_table, ADnorm, overlayMean):
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
    rep.add_text('<b>TSNR Mean and Standard Deviation: </b>')
    rep.add_table(tsnr_roi_table)
    
    # ROI plots
    rep.add_text('<b>ROI plots: </b>')
    for pl in roiplot:
        rep.add_image(pl,scale=0.6)
        
    fname = rep.write()
    return fname
    
    

def QA_workflow(sub, name='QA'):
    """
    This QA workflow needs to show:
    - ArtifactDetection - num outliers, outlier indices, images
    - tsdiffana (nipy)
    - TSNR, Mean, StdDev image (by region) 
    - Motion parameters (+ Composite norm)
    - Image smoothness estimate (?)
    - FD, DVARS - Power et al.
    - brain mask
    """
    # handy defs:
    def config_params():
        runs = get_run_numbers(sub)
        cfg = [['Subject',sub],
               ['Runs',str(len(runs))],
               ['Run Numbers', str(runs)],
               ['Date',ctime()],
               ['Art Thresh Norm',str(norm_thresh)],
               ['Art Thresh Z',str(z_thresh)],
               ['FWHM',str(fwhm)],
               ['Film Threshold',str(film_threshold)],
               ['TR',str(TR)],
               ['Highpass Cutoff',str(hpcutoff)],
               ['Number of noise components',str(num_noise_components)]] 
        return cfg
        
    def combine_table(roimean,roidev,roisnr):
        if len(roimean) == len(roidev) and len(roimean) == len(roisnr):
            for i, roi in enumerate(roisnr):
                # merge mean and stddev table
                roi.append(roimean[i][1])
                roi.append(roidev[i][1])
                
            roisnr.sort(key=lambda x:x[1])
            roisnr.insert(0,['<b>ROI</b>','<b> TSNR </b>','<b>Mean</b>','<b>Standard Deviation</b>'])
        else:
            roisnr.sort(key=lambda x:x[1])
            roisnr.insert(0,['ROI','TSNR'])     
        return roisnr
        
    workflow =pe.Workflow(name=name)
    inputspec = pe.Node(interface=util.IdentityInterface(fields=['in_file','art_file','motion_plots','reg_file','tsnr_detrended','tsnr','tsnr_mean','tsnr_stddev','ADnorm']),name='inputspec')
    write_rep = pe.Node(util.Function(input_names=['in_file','art_file','config_params','motion_plots','tsdiffana','roiplot','tsnr_roi_table','ADnorm','overlayMean'],output_names=['fname'],function=reporter),name='write_report')
    
    workflow.connect(inputspec,'in_file',write_rep,'in_file')
    workflow.connect(inputspec,'art_file',write_rep,'art_file')
    workflow.connect(inputspec,'motion_plots',write_rep,'motion_plots')
    
    tsdiff = pe.MapNode(util.Function(input_names = ['img'], output_names = ['out_file'], function=tsdiffana), name='tsdiffana', iterfield=["img"])
    workflow.connect(inputspec,'in_file',tsdiff,'img')
    workflow.connect(tsdiff,"out_file",write_rep,"tsdiffana")
    
    write_rep.inputs.config_params = config_params()
    
    # ROI-related nodes and connections
    
    # plots roi timeseries of detrended SNR
    roiplot = tsnr_roi(sd=surf_dir,subject=subjects[0],TR=TR,plot=True)
    workflow.connect(inputspec,'reg_file',roiplot,'inputspec.reg_file')
    workflow.connect(inputspec,'tsnr_detrended',roiplot,'inputspec.tsnr_file')
    workflow.connect(roiplot,'outputspec.out_file',write_rep,'roiplot')
    
    tablecombine = pe.Node(util.Function(input_names = ['roimean','roidev','roisnr'], output_names = ['roisnr'], function = combine_table), name='combinetable')
    
    # outputs list of mean / roi
    roiavgplot = tsnr_roi(sd=surf_dir,subject=subjects[0],TR=TR,plot=False,name='tsnr_mean_roi',roi=['all'])
    workflow.connect(inputspec,'reg_file',roiavgplot,'inputspec.reg_file')
    workflow.connect(inputspec,'tsnr_mean',roiavgplot,'inputspec.tsnr_file')
    workflow.connect(roiavgplot,'outputspec.out_file',tablecombine,'roimean')
    
    #outputs list of standard dev / roi
    roidevplot = tsnr_roi(sd=surf_dir,subject=subjects[0],TR=TR,plot=False,name='tsnr_stddev_roi',roi=['all'])
    workflow.connect(inputspec,'reg_file',roidevplot,'inputspec.reg_file')
    workflow.connect(inputspec,'tsnr_stddev',roidevplot,'inputspec.tsnr_file')
    workflow.connect(roidevplot,'outputspec.out_file',tablecombine,'roidev')
    
    # outputs list of SNR / roi
    roisnrplot = tsnr_roi(sd=surf_dir,subject=subjects[0],TR=TR,plot=False,name='SNR_roi',roi=['all'])
    workflow.connect(inputspec,'reg_file',roisnrplot,'inputspec.reg_file')
    workflow.connect(inputspec,'tsnr',roisnrplot,'inputspec.tsnr_file')
    workflow.connect(roisnrplot,'outputspec.out_file',tablecombine,'roisnr')
    
    workflow.connect(tablecombine, 'roisnr', write_rep, 'tsnr_roi_table')
    
    adnormplot = pe.Node(util.Function(input_names = ['ADnorm','TR'], output_names = ['plot'], function=plot_ADnorm), name='ADnormplot')
    adnormplot.inputs.TR = TR
    workflow.connect(inputspec,'ADnorm',adnormplot,'ADnorm')
    workflow.connect(adnormplot,'plot',write_rep,'ADnorm')
    
    fssource = pe.Node(interface = FreeSurferSource(),name='fssource')
    fssource.inputs.subject_id = sub
    fssource.inputs.subjects_dir = surf_dir
        
    # need to convert .gz to .nii.gz for fsl
    convert = pe.Node(interface=fs.MRIConvert(),name='converter')
    workflow.connect(fssource,'orig',convert,'in_file')
    convert.inputs.out_type = 'niigz'
    convert.inputs.in_type = 'mgz'
    #convert.inputs.out_orientation = 'LAS'
    
    # crap need to register fmri and struct. wah.
    voltransform = pe.Node(interface=ApplyVolTransform(),name='register')
    overlay = pe.Node(interface = fsl.Overlay(),name ='overlay')
    # Source file: file to transform
    # Target file: Output template volume
    # inverse samples target to source
    #workflow.connect(fssource,'brainmask',voltransform,'target_file')
    workflow.connect(convert,'out_file',voltransform,'target_file') 
    workflow.connect(inputspec,'reg_file',voltransform,'reg_file')
    workflow.connect(inputspec,'tsnr',voltransform, 'source_file')
    #workflow.connect(inputspec,'tsnr_mean',voltransform, 'source_file')
    
   
    workflow.connect(voltransform,'transformed_file', overlay,'stat_image')
    workflow.connect(convert,'out_file', overlay,'background_image')
    
    overlay.inputs.full_bg_range = True
    overlay.inputs.stat_thresh = (0.0,100.0)
    """
    convert2 = pe.Node(interface=fs.MRIConvert(),name='converter2')
    workflow.connect(overlay,'out_file',convert2,'in_file')
    convert2.inputs.out_type = 'niigz'
    convert2.inputs.out_orientation = 'LAS'
    """
    
    convert2 = pe.Node(interface=fsl.SwapDimensions(),name='converter2')
    workflow.connect(overlay,'out_file',convert2,'in_file')
    convert2.inputs.new_dims = ('RL','PA','IS')
    # use fsl slicer to see all axial images
    
    slicer = pe.Node(interface=fsl.Slicer(),name='slicer')
    workflow.connect(convert2,'out_file',slicer,'in_file') #This isn't nice
    #workflow.connect(inputspec,'tsnr_mean',slicer,'in_file') This is nice
    #workflow.connect(convert,'out_file',slicer,'in_file')
    slicer.inputs.middle_slices = True
    workflow.connect(slicer,'out_file',write_rep,'overlayMean')
    
    
    return workflow
    
if __name__ == "__main__":
    a = QA_workflow(subjects[0])
    a.base_dir = root_dir
    datagrab = create_dataflow()
    datagrab.inputs.subject_id = subjects[0]
    inputspec = a.get_node('inputspec')
    tolist = lambda x:[x]
    a.connect(datagrab,('func',tolist),inputspec,'in_file')
    a.inputs.inputspec.art_file = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/analyses/func/SAD_018/preproc/art/fwhm_5/art.corr_f3_dtype.nii_outliers.txt'
    a.inputs.inputspec.motion_plots = glob('/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/analyses/func/SAD_018/preproc/motion/*.png')
    a.inputs.inputspec.reg_file = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/analyses/func/SAD_018/preproc/bbreg/_register0/corr_f3_dtype_mean_bbreg_SAD_018.dat'
    a.inputs.inputspec.tsnr_detrended = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/work_dir/SAD_018/preproc/preproc/compcorr/_fwhm_5/tsnr/mapflow/_tsnr0/corr_f3_dtype_detrended.nii.gz'
    a.inputs.inputspec.tsnr_mean = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/work_dir/SAD_018/preproc/preproc/compcorr/_fwhm_5/tsnr/mapflow/_tsnr0/corr_f3_dtype_tsnr_mean.nii.gz'
    a.inputs.inputspec.tsnr = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/work_dir/SAD_018/preproc/preproc/compcorr/_fwhm_5/tsnr/mapflow/_tsnr0/corr_f3_dtype_tsnr.nii.gz'
    a.inputs.inputspec.tsnr_stddev = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/work_dir/SAD_018/preproc/preproc/compcorr/_fwhm_5/tsnr/mapflow/_tsnr0/corr_f3_dtype_tsnr_stddev.nii.gz'
    a.inputs.inputspec.ADnorm = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/analyses/func/SAD_018/preproc/art/fwhm_5/norm.corr_f3_dtype.nii.txt'
    a.run()
    
