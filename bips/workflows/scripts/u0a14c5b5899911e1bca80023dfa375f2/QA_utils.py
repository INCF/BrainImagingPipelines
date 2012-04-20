import matplotlib
matplotlib.use('Agg')
import os
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
from nipype.interfaces.freesurfer import ApplyVolTransform
from nipype.workflows.smri.freesurfer.utils import create_get_stats_flow

def art_output(art_file):
    import numpy as np
    try:
        out=np.asarray(np.genfromtxt(art_file))
    except:
        out=np.asarray([])
    table=[["file",art_file],["num outliers", str(out.shape)],["timepoints",str(out)]]
    return table, [out]
        

def plot_ADnorm(ADnorm,TR,norm_thresh,out):
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
    out = out[0]
    plot = os.path.abspath('plot_'+os.path.split(ADnorm)[1]+'.png')
    
    data = np.genfromtxt(ADnorm)
    plt.figure(1,figsize = (8,3))
    X = np.array(range(data.shape[0]))*TR
    plt.plot(X,data)
    plt.xlabel('Time (s)')
    plt.ylabel('Composite Norm')
    
    if norm_thresh > max(data):
        plt.axis([0,TR*data.shape[0],0,norm_thresh*1.1])
        plt.plot(X,np.ones(X.shape)*norm_thresh)
        for o in out:
            plt.plot(o*TR*np.ones(2),[0,norm_thresh*1.1],'r-')
    else:
        plt.axis([0,TR*data.shape[0],0,max(data)*1.1])
        plt.plot(X,np.ones(X.shape)*norm_thresh)
        for o in out:
            plt.plot(o*TR*np.ones(2),[0,max(data)*1.1],'r-')
    
    plt.savefig(plot,bbox_inches='tight')
    plt.close()
    return plot
    
def tsnr_roi(roi=[1021],name='roi_flow',plot=False, onsets=False):
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
                                                                 'aparc_aseg',
                                                                 'subject',
                                                                 'onsets']),name='inputspec')
    
    voltransform = pe.MapNode(interface=ApplyVolTransform(inverse=True, interp='nearest'),name='applyreg', iterfield=['source_file'])
    
    preproc.connect(inputspec,'tsnr_file',voltransform,'source_file')
    
    preproc.connect(inputspec,'reg_file',voltransform,'reg_file')
    
    preproc.connect(inputspec,'aparc_aseg',voltransform,'target_file')
    
    statsflow = create_get_stats_flow()
    preproc.connect(voltransform,'transformed_file',statsflow,'inputspec.label_file')
    preproc.connect(inputspec,'tsnr_file',statsflow,'inputspec.source_file')
    
    statsflow.inputs.segstats.avgwf_txt_file = True

    def strip_ids(subject_id, summary_file, roi_file):
        import numpy as np
        import os
        roi_idx = np.genfromtxt(summary_file)[:,1].astype(int)
        roi_vals = np.genfromtxt(roi_file)
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

    roistripper = pe.MapNode(util.Function(input_names=['subject_id', 'summary_file', 'roi_file'],
                                       output_names=['roi_file'],
                                       function=strip_ids),
                          name='roistripper', iterfield=['summary_file','roi_file'])
    
    preproc.connect(inputspec,'subject',roistripper,'subject_id')
    
    preproc.connect(statsflow, 'segstats.avgwf_txt_file', roistripper, 'roi_file')
    preproc.connect(statsflow, 'segstats.summary_file', roistripper, 'summary_file')

    roiplotter = pe.MapNode(util.Function(input_names=['statsfile', 'roi','TR','plot','onsets'],
                                       output_names=['Fname','AvgRoi'],
                                       function=plot_timeseries),
                          name='roiplotter', iterfield=['statsfile'])
    roiplotter.inputs.roi = roi
    preproc.connect(inputspec,'TR',roiplotter,'TR')
    roiplotter.inputs.plot = plot
    if onsets:
        preproc.connect(inputspec,'onsets',roiplotter,'onsets')
    else:
        roiplotter.inputs.onsets = None

    preproc.connect(roistripper,'roi_file',roiplotter,'statsfile')
    outputspec = pe.Node(interface=util.IdentityInterface(fields=['out_file','roi_table']),name='outputspec')
    preproc.connect(roiplotter,'Fname',outputspec,'out_file')
    preproc.connect(roiplotter,'AvgRoi',outputspec,'roi_table')

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
    plt.close()
    return out_file

def plot_timeseries(roi,statsfile,TR,plot,onsets):
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
            title = roiname[roinum==str(np.int_(R))][0]
            if plot:
                nums = list(stats[i])[1:]
                X = np.array(range(len(nums)))*TR
                plt.figure(1)
                p1 = plt.plot(X,nums)
                
                if onsets:
                    # onsets is a Bunch with "names", "onsets" and "durations".
                    for B in onsets:
                        p = []*len(B.onsets)
                        for i, ons in enumerate(B.onsets):
                            p[i] = plt.plot(ons,nums[ons])
                
                plt.title(title)
                plt.xlabel('time (s)')
                plt.ylabel('signal')
                fname = os.path.join(os.getcwd(),os.path.split(statsfile)[1][:-4]+'_'+title+'.png')
                plt.savefig(fname,dpi=200)
                plt.close()
                Fname.append(fname)
            else:
                AvgRoi.append([title,np.mean(list(stats[i])[1])])
        else:
            print "roi %s not found!"%R
    return Fname, AvgRoi


def combine_table(roidev,roisnr):
    if len(roisnr) == len(roidev):
        for i, roi in enumerate(roisnr):
            # merge mean and stddev table
            roi.append(roidev[i][1]*roisnr[i][1])
            roi.append(roidev[i][1])
            
        roisnr.sort(key=lambda x:x[1])
        roisnr.insert(0,['ROI','TSNR',
                         'Mean','Standard Deviation'])
    else:
        roisnr.sort(key=lambda x:x[1])
        roisnr.insert(0,['ROI','TSNR'])     
    return roisnr
    
def plot_motion(motion_parameters):
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')
    import numpy as np
    import os
    fname_t=os.path.abspath('translations.png')
    plt.figure(1,figsize = (8,3))
    plt.plot(np.genfromtxt(motion_parameters)[:,3:])
    plt.legend(['x','y','z'])
    plt.title("Estimated Translations (mm)")
    plt.savefig(fname_t)
    plt.close()
    
    fname_r = os.path.abspath('rotations.png')
    plt.figure(2,figsize = (8,3))
    plt.plot(np.genfromtxt(motion_parameters)[:,:3])
    plt.title("Estimated Rotations (rad)")
    plt.legend(['roll','pitch','yaw'])
    plt.savefig(fname_r)
    plt.close()
    fname = [fname_t, fname_r]
    return fname_t, fname_r
    
def plot_ribbon(Brain):
    import os.path
    import pylab as pl
    from nibabel import load
    from nipy.labs import viz   
    images = []
    
    for brain in Brain:
        if os.path.split(brain)[1] == 'ribbon.mgz':
            img = load(brain)
            data = img.get_data()*100
            affine = img.get_affine() 
            viz.plot_anat(anat=data, anat_affine=affine, draw_cross=False, slicer='x', cmap=viz.cm.black_green)
            
            x_view = os.path.abspath('x_view.png')
            y_view = os.path.abspath('y_view.png')
            z_view = os.path.abspath('z_view.png')
            
            pl.savefig(x_view,bbox_inches='tight')
            
            viz.plot_anat(anat=data, anat_affine=affine, draw_cross=False, slicer='y', cmap=viz.cm.black_green)
            pl.savefig(y_view,bbox_inches='tight')
            
            viz.plot_anat(anat=data, anat_affine=affine, draw_cross=False, slicer='z', cmap=viz.cm.black_green)
            pl.savefig(z_view,bbox_inches='tight')
            
            images = [x_view, y_view, z_view]
            pl.close()
    return images
    
def plot_anat(brain):
    import os.path
    import pylab as pl
    from nibabel import load
    from nipy.labs import viz   
    
    img = load(brain)
    data = img.get_data()
    affine = img.get_affine() 
    viz.plot_anat(anat=data, anat_affine=affine, draw_cross=False, slicer='x')
    
    x_view = os.path.abspath('x_view.png')
    y_view = os.path.abspath('y_view.png')
    z_view = os.path.abspath('z_view.png')
    
    pl.savefig(x_view,bbox_inches='tight')
    
    viz.plot_anat(anat=data, anat_affine=affine, draw_cross=False, slicer='y')
    pl.savefig(y_view,bbox_inches='tight')
    
    viz.plot_anat(anat=data, anat_affine=affine, draw_cross=False, slicer='z')
    pl.savefig(z_view,bbox_inches='tight')
    
    images = [x_view, y_view, z_view]
    pl.close()
    return images
    
def overlay_dB(stat_image,background_image,threshold,dB):
    import os.path
    import pylab as pl
    from nibabel import load
    from nipy.labs import viz
    from pylab import colorbar, gca, axes
    import numpy as np
    # Second example, with a given anatomical image slicing in the Z
    # direction
    
    fnames = [os.path.abspath('z_view.png'),
             os.path.abspath('x_view.png'),
             os.path.abspath('y_view.png')]
            
    formatter='%.2f'
    img = load(stat_image)
    data, affine = img.get_data(), img.get_affine()
    if dB:
        data[data > 1] = 20*np.log10(np.asarray(data[data > 1]))

    anat_img = load(background_image)
    anat = anat_img.get_data()
    anat_affine = anat_img.get_affine()

    viz.plot_map(data, affine, anat=anat, anat_affine=anat_affine,
                 slicer='z', threshold=threshold, cmap=viz.cm._cm.hot)
    cb = colorbar(gca().get_images()[1], cax=axes([0.3, 0.00, 0.4, 0.07]),
                         orientation='horizontal', format=formatter)
    cb.set_ticks([cb._values.min(), cb._values.max()])
    pl.savefig(fnames[0],bbox_inches='tight')

    viz.plot_map(data, affine, anat=anat, anat_affine=anat_affine,
                 slicer='x', threshold=threshold, cmap=viz.cm._cm.hot)
    cb = colorbar(gca().get_images()[1], cax=axes([0.3, -0.06, 0.4, 0.07]), 
                         orientation='horizontal', format=formatter)
    cb.set_ticks([cb._values.min(), cb._values.max()])
    pl.savefig(fnames[1],bbox_inches='tight')

    viz.plot_map(data, affine, anat=anat, anat_affine=anat_affine,
                 slicer='y', threshold=threshold, cmap=viz.cm._cm.hot)
    cb = colorbar(gca().get_images()[1], cax=axes([0.3, -0.08, 0.4, 0.07]), 
                         orientation='horizontal', format=formatter)
    cb.set_ticks([cb._values.min(), cb._values.max()])
    pl.savefig(fnames[2],bbox_inches='tight')
    
    return fnames


def overlay_new(stat_image,background_image,threshold):
    import os.path
    import pylab as pl
    from nibabel import load
    from nipy.labs import viz
    from pylab import colorbar, gca, axes
    import numpy as np
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
    anat = np.ones(anat.shape) - anat
    
    viz.plot_map(data, affine, anat=anat, anat_affine=anat_affine,
                 slicer='z', threshold=threshold, cmap=viz.cm._cm.hot)
    cb = colorbar(gca().get_images()[1], cax=axes([0.3, 0.00, 0.4, 0.07]),
                         orientation='horizontal', format=formatter)
    cb.set_ticks([cb._values.min(), cb._values.max()])
    pl.savefig(fnames[0],bbox_inches='tight')

    viz.plot_map(data, affine, anat=anat, anat_affine=anat_affine,
                 slicer='x', threshold=threshold, cmap=viz.cm._cm.hot)
    cb = colorbar(gca().get_images()[1], cax=axes([0.3, -0.06, 0.4, 0.07]), 
                         orientation='horizontal', format=formatter)
    cb.set_ticks([cb._values.min(), cb._values.max()])
    pl.savefig(fnames[1],bbox_inches='tight')

    viz.plot_map(data, affine, anat=anat, anat_affine=anat_affine,
                 slicer='y', threshold=threshold, cmap=viz.cm._cm.hot)
    cb = colorbar(gca().get_images()[1], cax=axes([0.3, -0.08, 0.4, 0.07]), 
                         orientation='horizontal', format=formatter)
    cb.set_ticks([cb._values.min(), cb._values.max()])
    pl.savefig(fnames[2],bbox_inches='tight')
    
    return fnames

def corr_image(resting_image,fwhm):
    """This function makes correlation image on brain surface"""
    import numpy as np
    import nibabel as nb
    import matplotlib.pyplot as plt
    from surfer import Brain, Surface
    import os

    img = nb.load(resting_image)
    corrmat = np.corrcoef(np.squeeze(img.get_data()))
    corrmat[np.isnan(corrmat)] = 0
    corrmat_npz = os.path.abspath('corrmat.npz')
    np.savez(corrmat_npz,corrmat=corrmat)

    br = Brain('fsaverage5', 'lh', 'smoothwm')

    #br.add_overlay(corrmat[0,:], min=0.2, name=0, visible=True)
    values = nb.freesurfer.read_annot('/software/Freesurfer/5.1.0/subjects/fsaverage5/label/lh.aparc.annot')

    #br.add_overlay(np.mean(corrmat[values[0]==5,:], axis=0), min=0.8, name='mean', visible=True)


    data = img.get_data()

    data = np.squeeze(img.get_data())

    #
    precuneus_signal = np.mean(data[values[0]==np.nonzero(np.array(values[2])=='precuneus')[0][0],:], axis=0)
    precuneus = np.corrcoef(precuneus_signal, data)
    #precuneus.shape

    #br.add_overlay(precuneus[0,1:], min=0.3, sign='pos', name='mean', visible=True)

    br.add_overlay(precuneus[0,1:], name='mean', visible=True)
    plt.hist(precuneus[0,1:], 128)
    plt.savefig(os.path.abspath("histogram.png"))
    plt.close()

    corr_image = os.path.abspath("corr_image%s.png"%fwhm)
    br.save_montage(corr_image)
    ims = br.save_imageset(prefix=os.path.abspath('fwhm_%s'%str(fwhm)),views=['medial','lateral','caudal','rostral','dorsal','ventral'])
    br.close()
    print ims
    #precuneus[np.isnan(precuneus)] = 0
    #plt.hist(precuneus[0,1:])

    roitable = [['Region','Mean Correlation']]
    for i, roi in enumerate(np.unique(values[2])):
        roitable.append([roi,np.mean(precuneus[values[0]==np.nonzero(np.array(values[2])==roi)[0][0]])])

        #images = [corr_image]+ims+[os.path.abspath("histogram.png"), roitable]
    roitable=[roitable]
    histogram = os.path.abspath("histogram.png")

    return corr_image, ims, roitable, histogram, corrmat_npz

def vol2surf(input_volume,ref_volume,reg_file,trg,hemi):
    import os
    out_file = os.path.abspath("surface.nii")
    os.system("mri_vol2surf --mov %s --ref %s --reg %s --trgsubject %s \
              --hemi %s --out_type nii --out %s --interp trilinear \
              --projfrac 0.5" % (input_volume, ref_volume, reg_file,
                                 trg, hemi, out_file))
    return out_file