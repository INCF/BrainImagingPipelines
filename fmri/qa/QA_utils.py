import matplotlib
matplotlib.use('Agg')
import os
import matplotlib.pyplot as plt
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio
from nipype.interfaces.freesurfer import ApplyVolTransform
from nipype.workflows.smri.freesurfer.utils import create_get_stats_flow
from nipype.interfaces import freesurfer as fs
from nipype.interfaces.io import FreeSurferSource
from nipype.interfaces import fsl

def plot_ADnorm(ADnorm,TR):
    """ Returns a plot of the composite_norm file output from art
    
    Parameters
    ----------
    ADnorm : File
             Text file output from art
    TR : Float
         TR of scan
         
    Returns
    -------
    File : Filename of plot image
    
    """
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
    
def tsnr_roi(roi=[1021],name='roi_flow',plot=False):
    """ Return a workflow that outputs either a graph of the average \
        
    timseries of each roi specified OR a table of average value across \
    all timeseries for each voxel in each ROI.
    
    Parameters
    ----------
    roi : List of Integers or ['all']
          Specify a list of ROI number corresponding to the Freesurfer LUT.
          Default = 1021 (lh-pericalcarine)
    name : String
           Name of workflow. 
           Default = 'roi_flow'
    plot : Boolean
           True if workflow should output timeseries plots/ROI
           False if workflow should output a table of avg.value/ROI
           Default = False
           
    Inputs
    ------
    inputspec.reg_file :
    inputspec.tsnr_file :
    inputspec.TR :
    inputspec.subject :
    inputspec.sd :
    
    Outputs
    -------
    outputspec.out_file :
    
    
    """
    preproc = pe.Workflow(name=name)
    
    inputspec = pe.Node(interface=util.IdentityInterface(fields=['reg_file',
                                                                 'tsnr_file',
                                                                 'TR',
                                                                 'subject',
                                                                 'sd']),name='inputspec')
    
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

    roiplotter = pe.Node(util.Function(input_names=['statsfile', 'roi','TR','plot'],
                                       output_names=['Fname','AvgRoi'],
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
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
   

    axes = tdp.plot_tsdiffs_image(img, axes=None, show=False)
    out_file = []
    
    of = os.path.abspath("tsdiffana_"+os.path.split(img)[1]+".png")
    x = plt.sca(axes[0])
    plt.savefig(of,dpi=300)
    out_file.append(of)
    
    return out_file

def plot_timeseries(roi,statsfile,TR,plot):
    """ Returns a plot of an averaged timeseries across an roi
    
    Parameters
    ----------
    roi : List of ints
          List of integers corresponding to roi's in the Freesurfer LUT
    statsfile : File
                File output of segstats workflow
    TR : Float
         TR of scan
    plot : Boolean
           True to return plot
           
    Returns
    -------
    File : Filename of plot image, if plot=True 
    List : List of average ROI value if plot=False

    """
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
    AvgRoi = []
    
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
                AvgRoi.append([title,np.mean(list(stats[i])[1])])
        else:
            print "roi %s not found!"%R
  
    return Fname, AvgRoi


def combine_table(roimean,roidev,roisnr):
    if len(roimean) == len(roidev) and len(roimean) == len(roisnr):
        for i, roi in enumerate(roisnr):
            # merge mean and stddev table
            roi.append(roimean[i][1])
            roi.append(roidev[i][1])
            
        roisnr.sort(key=lambda x:x[1])
        roisnr.insert(0,['ROI','TSNR',
                         'Mean','Standard Deviation'])
    else:
        roisnr.sort(key=lambda x:x[1])
        roisnr.insert(0,['ROI','TSNR'])     
    return roisnr
