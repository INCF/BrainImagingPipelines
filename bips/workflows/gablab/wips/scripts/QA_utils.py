import os

def art_output(art_file,intensity_file,stats_file):
    import numpy as np
    from nipype.utils.filemanip import load_json
    import os
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    try:
        out=np.asarray(np.genfromtxt(art_file))
    except:
        out=np.asarray([])
    table=[["file",art_file],["num outliers", str(out.shape)],["timepoints",str(out)]]
    stats = load_json(stats_file)
    for s in stats:
        for key, item in s.iteritems():
            if isinstance(item,dict):
                table.append(['+'+key,''])
                for sub_key,sub_item in item.iteritems():
                    table.append(['  '+sub_key,str(sub_item)])
            elif isinstance(item, list):
                table.append(['+'+key,''])
                for s_item in item:
                    for sub_key, sub_item in s_item.iteritems():
                        table.append(['  '+sub_key,str(sub_item)])
            else:
                table.append([key,str(item)])
    print table
    intensity = np.genfromtxt(intensity_file)
    intensity_plot = os.path.abspath('global_intensity.png')
    plt.figure(1,figsize = (8,3))
    plt.xlabel('Volume')
    plt.ylabel("Global Intensity")
    plt.plot(intensity)
    plt.savefig(intensity_plot,bbox_inches='tight')
    plt.close()
    return table, out.tolist(), intensity_plot


def plot_spectrum(Timeseries, tr):
    from nitime.timeseries import TimeSeries
    from nitime.analysis import SpectralAnalyzer
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import os
    import numpy as np
    figure= []
    for i, timeseries in enumerate(Timeseries):
        #T = io.time_series_from_file(in_file,TR=tr)
        title = os.path.abspath('spectra')
        timeseries = np.asarray(timeseries[1:])
        timeseries = timeseries-np.mean(timeseries)*np.ones(timeseries.shape)
        T = TimeSeries(timeseries,sampling_interval=tr)
        S_original = SpectralAnalyzer(T)
        # Initialize a figure to put the results into:
        fig01 = plt.figure(figsize = (8,3))
        ax01 = fig01.add_subplot(1, 1, 1)
        ax01.plot(S_original.psd[0],
            S_original.psd[1],
            label='Welch PSD')

        ax01.plot(S_original.spectrum_fourier[0],
            S_original.spectrum_fourier[1],
            label='FFT')

        ax01.plot(S_original.periodogram[0],
            S_original.periodogram[1],
            label='Periodogram')

        ax01.plot(S_original.spectrum_multi_taper[0],
            S_original.spectrum_multi_taper[1],
            label='Multi-taper')

        ax01.set_xlabel('Frequency (Hz)')
        ax01.set_ylabel('Power')

        ax01.legend()
        Figure = title+'%02d.png'%i
        plt.savefig(Figure, bbox_inches='tight')
        figure.append(Figure)
        plt.close()
    return figure

def plot_simple_timeseries(Timeseries):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import os
    title=[]
    for i, timeseries in enumerate(Timeseries):
        Title = os.path.abspath('timeseries%02d.png'%i)
        plt.figure(figsize=(8,3))
        plt.plot(timeseries[1:])
        plt.xlabel('Volume')
        plt.ylabel('Signal')
        plt.savefig(Title,bbox_inches='tight')
        title.append(Title)
        plt.close()
    return title

def spectrum_ts_table():
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    import numpy as np
    import os

    LUT = np.genfromtxt(os.path.join(os.environ["FREESURFER_HOME"],'FreeSurferColorLUT.txt'),dtype = str)
    roinum = LUT[:,0]
    roiname = LUT[:,1]

    wf = pe.Workflow(name="spectra_and_timeseries")
    inputspec = pe.Node(util.IdentityInterface(fields=['stats_file',
                                                       'tr']),name='inputspec')
    spectra = pe.MapNode(util.Function(input_names=['Timeseries',
                                                 'tr'],
                                    output_names=['figure'],
                                    function= plot_spectrum),
                         name='spectra', iterfield=['Timeseries'])
    timeseries = pe.MapNode(util.Function(input_names=['Timeseries'],
                                       output_names=['title'],
                                       function=plot_simple_timeseries),
                         name='timeseries', iterfield=['Timeseries'])


    def stats(stats_file):
        import numpy as np
        Stats = []
        for stat in stats_file:
            Stats.append(np.recfromcsv(stat).tolist())
        return Stats

    def make_table(roiname, roinum,spectra,timeseries,stats):
        import numpy as np
        imagetable=[['ROI','Timeseries','Spectra']]

        for i, R in enumerate(stats):
            title = roiname[roinum==str(np.int_(R[0]))][0]
            imagetable.append([title,timeseries[i],spectra[i]])
        return imagetable

    table = pe.MapNode(util.Function(input_names=['roiname',
                                               'roinum',
                                               'spectra',
                                               'timeseries',
                                               'stats'],
                                  output_names=['imagetable'],
                                  function=make_table),
                    name='maketable', iterfield=['spectra','stats','timeseries'])

    wf.connect(inputspec,('stats_file', stats),spectra,'Timeseries')
    wf.connect(inputspec,('stats_file', stats),timeseries,'Timeseries')
    wf.connect(inputspec,('stats_file', stats),table,'stats')
    wf.connect(inputspec,'tr', spectra,'tr')
    wf.connect(spectra,'figure', table,'spectra')
    wf.connect(timeseries,'title',table,'timeseries')
    table.inputs.roiname=roiname
    table.inputs.roinum = roinum

    outputspec = pe.Node(util.IdentityInterface(fields=['imagetable']),name='outputspec')
    wf.connect(table,'imagetable',outputspec,'imagetable')

    return wf

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

    if not isinstance(out,list):
        out = [out]

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
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    from nipype.interfaces.freesurfer import ApplyVolTransform
    from nipype.workflows.smri.freesurfer.utils import create_get_stats_flow

    preproc = pe.Workflow(name=name)
    
    inputspec = pe.Node(interface=util.IdentityInterface(fields=['reg_file',
                                                                 'tsnr_file',
                                                                 'TR',
                                                                 'aparc_aseg',
                                                                 'subject',
                                                                 'onsets',
                                                                 'input_units','sd']),name='inputspec')
    
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
        roi_vals = np.atleast_2d(roi_vals)
	rois2skip = [0, 2, 4, 5, 7, 14, 15, 24, 30, 31, 41, 43, 44, 46, 62, 63, 77, 80, 85, 1000, 2000]
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


    if onsets:
        roiplotter = pe.MapNode(util.Function(input_names=['statsfile', 'roi','TR','plot','onsets','units'],
            output_names=['Fname','AvgRoi'],
            function=plot_timeseries),
            name='roiplotter', iterfield=['statsfile','onsets'])
        preproc.connect(inputspec,'onsets',roiplotter,'onsets')
        preproc.connect(inputspec, 'input_units',roiplotter,'units')
    else:
        roiplotter = pe.MapNode(util.Function(input_names=['statsfile', 'roi','TR','plot','onsets','units'],
            output_names=['Fname','AvgRoi'],
            function=plot_timeseries),
            name='roiplotter', iterfield=['statsfile'])
        roiplotter.inputs.onsets = None
        roiplotter.inputs.units = None

    roiplotter.inputs.roi = roi
    preproc.connect(inputspec,'TR',roiplotter,'TR')
    roiplotter.inputs.plot = plot
    preproc.connect(roistripper,'roi_file',roiplotter,'statsfile')

    outputspec = pe.Node(interface=util.IdentityInterface(fields=['out_file','roi_table','roi_file']),name='outputspec')
    preproc.connect(roiplotter,'Fname',outputspec,'out_file')
    preproc.connect(roiplotter,'AvgRoi',outputspec,'roi_table')
    preproc.connect(roistripper,'roi_file', outputspec,'roi_file')

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

def plot_timeseries(roi,statsfile,TR,plot,onsets,units):
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
    
    LUT = np.genfromtxt(os.path.join(os.environ["FREESURFER_HOME"],'FreeSurferColorLUT.txt'),dtype = str)
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
                nums = np.asarray(list(stats[i])[1:])
                X = np.array(range(len(nums)))*TR
                plt.figure(1)
                plt.plot(X,nums)
                if onsets:
                    # onsets is a Bunch with "conditions", "onsets" and "durations".
                    print onsets
                    names = onsets.conditions
                    durations = onsets.durations
                    onsets = onsets.onsets
                    colors1 = [[]]*len(onsets)

                    for i, ons in enumerate(onsets):
                        colors1[i] = [np.random.rand(3)]
                        if units == 'scans':
                            plt.plot(np.asarray(ons)*TR,nums[ons],marker='*',linestyle='None',color=colors1[i][0])
                        else:
                            plt.plot(ons,nums[np.int_(np.asarray(ons)/TR)],marker='*',linestyle='None',color=colors1[i][0])

                    plt.legend(['signal']+names)

                    for i, ons in enumerate(onsets):
                        ons = np.asarray(ons)
                        newX = np.zeros(nums.shape)
                        newX[:] = np.nan
                        for d in xrange(durations[i][0]):
                            if units == 'scans':
                                newX[np.int_(ons+np.ones(ons.shape)*(d))] = nums[np.int_(ons+np.ones(ons.shape)*(d))]
                            else:
                                newX[np.int_(ons/TR)] = nums[np.int_(ons/TR)]
                        plt.plot(X,newX,color=colors1[i][0])


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


def combine_table(roidev,roisnr,imagetable):
    print len(roidev)
    print len(roisnr)
    print len(imagetable)

    def match(List, Value):
        for L in List:
            if L[0]==Value:
                return L[1]
        return 0

    for i, roi in enumerate(imagetable[1:]):
        # merge mean and stddev table
        avg = match(roidev,roi[0])*match(roisnr,roi[0])
        dev = match(roidev,roi[0])
        snr = match(roisnr,roi[0])
        roi[0]+="\nSNR = %f\nMean = %f\nStandard Deviation = %f"%(snr,avg,dev)


    return imagetable



def reduce_table(imagetable,custom_LUT_file):
    import numpy as np
    custom_LUT = np.genfromtxt(custom_LUT_file,dtype = str)
    custom_roinames = custom_LUT[:,1]
    reduced_imagetable = [['ROI','Timeseries','Spectra']]
    for i, roi in enumerate(imagetable[1:]):
        roi_label = imagetable[i+1][0].split("\n")[0]
        if roi_label in custom_roinames:
            reduced_imagetable.append(imagetable[i+1])
    return reduced_imagetable
 
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
            pl.close()

            viz.plot_anat(anat=data, anat_affine=affine, draw_cross=False, slicer='y', cmap=viz.cm.black_green)
            pl.savefig(y_view,bbox_inches='tight')
            pl.close()

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
    import numpy as np

    img = load(brain)
    data = img.get_data()
    data[np.isnan(data)] = 0
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
    pl.close()
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
    pl.close()
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
    lh_aparc_annot_file = os.path.join(os.environ["FREESURFER_HOME"],'/subjects/label/lh.aparc.annot')
    values = nb.freesurfer.read_annot(lh_aparc_annot_file)

    #br.add_overlay(np.mean(corrmat[values[0]==5,:], axis=0), min=0.8, name='mean', visible=True)


    data = img.get_data()

    data = np.squeeze(img.get_data())

    #
    precuneus_signal = np.mean(data[values[0]==np.nonzero(np.array(values[2])=='precuneus')[0][0],:], axis=0)
    precuneus = np.corrcoef(precuneus_signal, data)
    #precuneus.shape

    #br.add_overlay(precuneus[0,1:], min=0.3, sign='pos', name='mean', visible=True)

    br.add_overlay(precuneus[0,1:], min=0.2, name='mean')#, visible=True)
    #br.add_overlay(precuneus[0,1:], min=0.2, name='mean')#, visible=True)
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

        #images = [corr_fimage]+ims+[os.path.abspath("histogram.png"), roitable]
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

def get_coords(labels, in_file, subsess, fsdir):
    from nibabel import load
    import numpy as np
    import os

    img = labels[0]
    data1 = in_file
    data,affine = load(data1).get_data(), load(data1).get_affine()
    coords = []
    labels = np.setdiff1d(np.unique(img.ravel()), [0])
    cs = []

    brain_dir = os.path.join(fsdir,subsess,'mri')
    lut_file=os.path.join(os.environ["FREESURFER_HOME"],'FreeSurferColorLUT.txt')
    colorfile = np.genfromtxt(lut_file,dtype='string')
    seg_file = os.path.join(brain_dir,'aparc+aseg.mgz')
    data_seg,aff_seg = load(seg_file).get_data(), load(seg_file).get_affine()
    inv_aff_seg = np.linalg.inv(aff_seg)

    def make_chart(coords):
        brain_loc = []

        for co in coords:
            realspace = np.dot(affine,np.hstack((co,1)))
            #segspace = np.dot(inv_aff_seg, np.hstack((co,1)))
            segspace = np.dot(inv_aff_seg, realspace)
            colornum = str(data_seg[segspace[0],segspace[1],segspace[2]])
            brain_loc.append(colorfile[:,1][colorfile[:,0]==colornum][0])

        percents = []

        for loc in np.unique(brain_loc):
            #percents.append(np.mean(loc==brain_loc, dtype=np.float64))
            percents.append(np.mean(loc==np.array(brain_loc), dtype=np.float64))
        return np.unique(brain_loc), percents

    for label in labels:
        cs.append(np.sum(img==label))

    locations = []
    percents = []
    meanval = []
    for label in labels[np.argsort(cs)[::-1]]:
        coordinates = np.asarray(np.nonzero(img==label))
        print coordinates.shape
        locs, pers = make_chart(coordinates.T)
        i =  np.argmax(abs(data[coordinates[0,:],coordinates[1,:],coordinates[2,:]]))
        meanval.append(np.mean(data[coordinates[0,:],coordinates[1,:],coordinates[2,:]]))
        q =  coordinates[:,i]
        locations.append(locs)
        percents.append(pers)
        coords.append(np.dot(affine, np.hstack((q,1)))[:3].tolist())

    return [coords], [cs], locations, percents, meanval


def get_labels(in_file,thr,csize):
    from nibabel import load
    from scipy.ndimage import label
    #from numpy import *
    min_extent=csize
    data = load(in_file).get_data()
    labels, nlabels = label(abs(data)>thr)
    for idx in range(1, nlabels+1):
        if sum(sum(sum(labels==idx)))<min_extent:
            labels[labels==idx] = 0
    return [labels]


def show_slices(image_in, anat_file, coordinates,thr):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import pylab as pl
    import numpy as np
    from nibabel import load
    import os
    from nipy.labs import viz
    anat = anat_file
    img = image_in
    coords = coordinates[0]
    threshold=thr
    cmap=pl.cm.jet
    prefix=None,
    show_colorbar=True
    formatter='%.2f'

    img1 = load(img)
    data, aff = img1.get_data(), img1.get_affine()
    anatimg = load(anat) #load('/usr/share/fsl/data/standard/MNI152_T1_1mm_brain.nii.gz')
    anatdata, anataff = anatimg.get_data(), anatimg.get_affine()
    anatdata = anatdata.astype(np.float)
    anatdata[anatdata<10.] = np.nan
    outfile1 = os.path.split(img)[1][0:-7]
    outfiles = []
    for idx,coord in enumerate(coords):
        outfile = outfile1+'cluster%02d' % idx
        osl = viz.plot_map(np.asarray(data), aff, anat=anatdata, anat_affine=anataff,
            threshold=threshold, cmap=cmap,
            black_bg=False, cut_coords=coord)
        if show_colorbar:
            cb = plt.colorbar(plt.gca().get_images()[1], cax=plt.axes([0.4, 0.075, 0.2, 0.025]),
                orientation='horizontal', format=formatter)
            cb.set_ticks([cb._values.min(), cb._values.max()])

        #osl.frame_axes.figure.savefig(outfile+'.svg', bbox_inches='tight', transparent=True)
        osl.frame_axes.figure.savefig(os.path.join(os.getcwd(),outfile+'.png'), dpi=600, bbox_inches='tight', transparent=True)
        #pl.savefig(os.path.join(os.getcwd(),outfile+'.png'), dpi=600, bbox_inches='tight', transparent=True)
        outfiles.append(os.path.join(os.getcwd(),outfile+'.png'))
    return outfiles

def write_report(cs,locations,percents,in_files,
                 des_mat,des_mat_cov,subjects, meanval,
                 imagefiles, surface_ims, thr, csize, fwhm,
                 onset_images):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
    from reportlab.lib.units import inch
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    import time
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from numpy import array
    import os
    from PIL import Image

    def get_and_scale(imagefile,scale=1):
        from reportlab.platypus import Image as Image2
        im1 = scale_im(Image.open(imagefile))
        im = Image2(imagefile, im1.size[0]*scale, im1.size[1]*scale)
        return im

    def scale_im(im):
        # scales an image so that it will fit on the page with various margins...
        width, height = letter
        newsize = array(im.size)/(max(array(im.size)/array([width-(1*inch), height-(2*inch)])))
        newsize = tuple(map(lambda x: int(x), tuple(newsize)))
        return im.resize(newsize)



    fwhm = [fwhm]
    report = os.path.join(os.getcwd(),"slice_tables.pdf")
    doc = SimpleDocTemplate(report, pagesize=letter,
        rightMargin=36,leftMargin=36,
        topMargin=72,bottomMargin=72)
    elements = []
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='RIGHT', alignment=TA_RIGHT))

    formatted_time = time.ctime()

    ptext = '<font size=10>%s</font>' % formatted_time
    elements.append(Paragraph(ptext, styles["Normal"]))
    elements.append(Spacer(1, 12))

    ptext = '<font size=22>%s</font>' %('Subject '+subjects+' Report')
    elements.append(Paragraph(ptext, styles["Normal"]))
    elements.append(Spacer(1, 24))

    ptext = '<font size=10>%s</font>' %("The contrast files are: ")
    elements.append(Paragraph(ptext, styles["Normal"]))
    elements.append(Spacer(1, 12))

    contrasts = []
    for fil in in_files:
        pt = os.path.split(fil)[1]
        contrasts.append(pt)
        ptext = '<font size=10>%s</font>' %pt
        elements.append(Paragraph(ptext, styles["Normal"]))
        elements.append(Spacer(1, 12))

    ptext = '<font size=10>%s</font>' %("The stat images were thresholded at z = %s and min cluster size = %s voxels. FWHM = %d "%(thr,csize,fwhm[0]))
    elements.append(Paragraph(ptext, styles["Normal"]))
    elements.append(Spacer(1, 12))
    elements.append(PageBreak())

    if not isinstance(des_mat,list):
        des_mat = [des_mat]
    if not isinstance(des_mat_cov,list):
        des_mat_cov = [des_mat_cov]

    for i in range(len(des_mat)):
        ptext = '<font size=10>%s</font>' %('Design Matrix:')
        elements.append(Paragraph(ptext, styles["Normal"]))
        elements.append(Spacer(1, 12))
        im = get_and_scale(des_mat[i],.6)
        elements.append(im)
        elements.append(Spacer(1, 12))

        ptext = '<font size=10>%s</font>' %('Covariance Matrix:')
        elements.append(Paragraph(ptext, styles["Normal"]))
        elements.append(Spacer(1, 12))
        im = get_and_scale(des_mat_cov[i],.6)
        elements.append(im)
        elements.append(PageBreak())

    if onset_images:
        for image in onset_images:
            if isinstance(image,list):
                for im0 in image:
                    im = get_and_scale(im0)
                    elements.append(im)
            else:
                im = get_and_scale(image)
                elements.append(im)


    for i, con_cs in enumerate(cs):
        data = [['Size','Location','Ratio','Mean(z)','Image']]
        for j, cluster in enumerate(con_cs[0]):
            data.append([])
            data[j+1].append(cluster)
            locstr = ''
            perstr = ''
            if len(locations[i][j]) <= 50:
                for k, loc in enumerate(locations[i][j]):
                    locstr = locstr + loc + '\n'
                    perstr = perstr+'%.2f\n'%percents[i][j][k]

            data[j+1].append(locstr)
            data[j+1].append(perstr)
            meanstr = '%2.2f'%meanval[i][j]
            data[j+1].append(meanstr)
            im = get_and_scale(imagefiles[i][j],.5)
            data[j+1].append(im)

        print data
        t=Table(data)
        t.setStyle(TableStyle([('ALIGN',(0,0), (-1,-1),'LEFT'),
            ('VALIGN',(0,0), (-1,-1), 'TOP'),
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
            ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))
        t.hAlign='LEFT'
        ptext = '<font size=10>%s</font>' %('Contrast:  %s'%(contrasts[i]))
        elements.append(Paragraph(ptext,styles["Normal"]))
        elements.append(Spacer(1, 12))
        elements.append(get_and_scale(surface_ims[i]))
        elements.append(Spacer(1, 12))
        elements.append(t)
        elements.append(Spacer(1, 12))
        #elements.append(PageBreak())

    doc.build(elements)
    return report, elements

def make_surface_plots(con_image,reg_file,subject_id,thr,sd):
    import matplotlib
    matplotlib.use('Agg')
    import os

    def make_image(zstat_path,bbreg_path):
        name_path = os.path.join(os.getcwd(),os.path.split(zstat_path)[1]+'_reg_surface.mgh')
        systemcommand ='mri_vol2surf --mov %s --reg %s --hemi lh --projfrac-max 0 1 0.1 --o %s --out_type mgh --sd %s'%(zstat_path,bbreg_path,name_path, sd)
        print systemcommand
        os.system(systemcommand)
        return name_path

    def make_brain(subject_id,image_path):
        from surfer import Brain
        hemi = 'lh'
        surface = 'inflated'
        brain = Brain(subject_id, hemi, surface)
        brain.add_overlay(image_path,min=thr)
        outpath = os.path.join(os.getcwd(),os.path.split(image_path)[1]+'_surf.png')
        brain.save_montage(outpath)
        return outpath

    surface_ims = []
    surface_mgzs = []
    for con in con_image:
        surf_mgz = make_image(format(con),reg_file)
        surface_mgzs.append(surf_mgz)
        surface_ims.append(make_brain(subject_id,surf_mgz))

    return surface_ims, surface_mgzs

def get_coords2(in_file,img):
    """Here, img = labels from getlabels!"""
    import numpy as np
    from nibabel import load
    affine = load(in_file).get_affine()
    img=img[0]
    coords = []
    labels = np.setdiff1d(np.unique(img.ravel()), [0])
    cs = []
    for label in labels:
        cs.append(np.sum(img==label))
    for label in labels[np.argsort(cs)[::-1]]:
        coords.append(np.dot(affine,
            np.hstack((np.mean(np.asarray(np.nonzero(img==label)),
                axis = 1),
                       1)))[:3].tolist())
    return [coords]

def fdr(in_file, mask_file, pthresh):
    import os
    import nibabel as nib
    import numpy as np
    from nipype.utils.filemanip import fname_presuffix
 
    qstat = os.path.abspath(os.path.split(in_file)[1])
    qrate = fname_presuffix(os.path.split(qstat)[0],'qrate_',os.path.abspath('.'))
    p = os.popen('fdr -i %s -m %s -q %s -o %s'%(in_file,mask_file,pthresh,qrate))
    qthresh = 1 - float(p.readlines()[1])
    img = nib.load(in_file)
    data, aff = img.get_data(), img.get_affine()
    data = np.ones(data.shape) - data
    ominp = nib.Nifti1Image(data,aff)
    ominp.to_filename(qstat)

    return qstat, qthresh, qrate

def cluster_image2(name="threshold_cluster_makeimages"):
    from nipype.interfaces import fsl
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util

    workflow = pe.Workflow(name=name)
    inputspec = pe.Node(util.IdentityInterface(fields=["pstat","mask","threshold","min_cluster_size",'anatomical']),name="inputspec")

    do_fdr = pe.MapNode(util.Function(input_names=['in_file','mask_file','pthresh'],
                                      output_names=['qstat','qthresh','qrate'],
                                      function=fdr),name='do_fdr',iterfield=['in_file'])

    cluster = pe.MapNode(fsl.Cluster(out_localmax_txt_file=True,
                                     out_index_file=True,
                                     out_localmax_vol_file=True), 
                         name='cluster', iterfield=['in_file','threshold'])

    workflow.connect(inputspec,'pstat',do_fdr,'in_file')
    workflow.connect(inputspec,'mask',do_fdr,'mask_file')
    workflow.connect(inputspec,'threshold', do_fdr,'pthresh')

    workflow.connect(do_fdr,"qthresh",cluster,"threshold")
    #workflow.connect(inputspec,"connectivity",cluster,"connectivity")
    cluster.inputs.out_threshold_file = True
    cluster.inputs.out_pval_file = True
    workflow.connect(do_fdr,'qstat',cluster,'in_file')

    labels = pe.MapNode(util.Function(input_names=['in_file','thr','csize'],
                                   output_names=['labels'],function=get_labels),
        name='labels',iterfield=["in_file","thr"])

    workflow.connect(do_fdr,"qthresh",labels,"thr")
    workflow.connect(inputspec,"min_cluster_size",labels,"csize")
    workflow.connect(cluster,"threshold_file",labels,"in_file")

    showslice=pe.MapNode(util.Function(input_names=['image_in','anat_file','coordinates','thr'],
                                    output_names=["outfiles"],function=show_slices),
              name='showslice',iterfield=["image_in","coordinates",'thr'])

    coords = pe.MapNode(util.Function(input_names=["in_file","img"],
                                   output_names=["coords"],
                                   function=get_coords2),
        name='getcoords', iterfield=["in_file","img"])

    workflow.connect(cluster,'threshold_file',showslice,'image_in')
    workflow.connect(inputspec,'anatomical',showslice,"anat_file")
    workflow.connect(do_fdr,'qthresh',showslice,'thr')
    workflow.connect(labels,'labels',coords,"img")
    workflow.connect(cluster,"threshold_file",coords,"in_file")
    workflow.connect(coords,"coords",showslice,"coordinates")

    overlay = pe.MapNode(util.Function(input_names=["stat_image",
                                                 "background_image",
                                                 "threshold"],
                                       output_names=["fnames"],function=overlay_new),
                         name='overlay', iterfield=["stat_image",'threshold'])
    workflow.connect(inputspec,"anatomical", overlay,"background_image")
    workflow.connect(cluster,"threshold_file",overlay,"stat_image")
    workflow.connect(do_fdr,"qthresh",overlay,"threshold")
    #workflow.connect(cluster, 'threshold_file',imgflow,'inputspec.in_file')
    #workflow.connect(dataflow,'func',imgflow, 'inputspec.in_file')
    #workflow.connect(inputspec,'mask',imgflow, 'inputspec.mask_file')

    outputspec = pe.Node(util.IdentityInterface(fields=["corrected_p","localmax_txt","index_file","localmax_vol","slices","cuts","corrected_p","qrate"]),name='outputspec')
    workflow.connect(cluster,'threshold_file',outputspec,'corrected_p')
    workflow.connect(showslice,"outfiles",outputspec,"slices")
    workflow.connect(overlay,"fnames",outputspec,"cuts")
    workflow.connect(cluster,'localmax_txt_file',outputspec,'localmax_txt')
    workflow.connect(do_fdr,"qrate",outputspec,'qrate')
    #workflow.connect(logp,'out_file',outputspec,"corrected_p")
    return workflow 

def cluster_image(name="threshold_cluster_makeimages"):
    from nipype.interfaces import fsl
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util

    workflow = pe.Workflow(name=name)
    inputspec = pe.Node(util.IdentityInterface(fields=["zstat","mask","zthreshold","pthreshold","connectivity",'anatomical']),name="inputspec")
    smoothest = pe.MapNode(fsl.SmoothEstimate(), name='smooth_estimate', iterfield=['zstat_file'])
    workflow.connect(inputspec,'zstat', smoothest, 'zstat_file')
    workflow.connect(inputspec,'mask',smoothest, 'mask_file')

    cluster = pe.MapNode(fsl.Cluster(out_localmax_txt_file=True,
                                     out_index_file=True,
                                     out_localmax_vol_file=True), 
                         name='cluster', iterfield=['in_file','dlh','volume'])
    workflow.connect(smoothest,'dlh', cluster, 'dlh')
    workflow.connect(smoothest, 'volume', cluster, 'volume')
    workflow.connect(inputspec,"zthreshold",cluster,"threshold")
    workflow.connect(inputspec,"pthreshold",cluster,"pthreshold")
    workflow.connect(inputspec,"connectivity",cluster,"connectivity")
    cluster.inputs.out_threshold_file = True
    cluster.inputs.out_pval_file = True
    workflow.connect(inputspec,'zstat',cluster,'in_file')
    """
    labels = pe.MapNode(util.Function(input_names=['in_file','thr','csize'],
                                   output_names=['labels'],function=get_labels),
        name='labels',iterfield=["in_file"])

    workflow.connect(inputspec,"zthreshold",labels,"thr")
    workflow.connect(inputspec,"connectivity",labels,"csize")
    workflow.connect(cluster,"threshold_file",labels,"in_file")
    showslice=pe.MapNode(util.Function(input_names=['image_in','anat_file','coordinates','thr'],
                                    output_names=["outfiles"],function=show_slices),
              name='showslice',iterfield=["image_in","coordinates"])

    coords = pe.MapNode(util.Function(input_names=["in_file","img"],
                                   output_names=["coords"],
                                   function=get_coords2),
        name='getcoords', iterfield=["in_file","img"])

    workflow.connect(cluster,'threshold_file',showslice,'image_in')
    workflow.connect(inputspec,'anatomical',showslice,"anat_file")
    workflow.connect(inputspec,'zthreshold',showslice,'thr')
    workflow.connect(labels,'labels',coords,"img")
    workflow.connect(cluster,"threshold_file",coords,"in_file")
    workflow.connect(coords,"coords",showslice,"coordinates")

    overlay = pe.MapNode(util.Function(input_names=["stat_image",
                                                 "background_image",
                                                 "threshold"],
                                       output_names=["fnames"],function=overlay_new),
                         name='overlay', iterfield=["stat_image"])
    workflow.connect(inputspec,"anatomical", overlay,"background_image")
    workflow.connect(cluster,"threshold_file",overlay,"stat_image")
    workflow.connect(inputspec,"zthreshold",overlay,"threshold")
    """
    outputspec = pe.Node(util.IdentityInterface(fields=["corrected_z","localmax_txt","index_file","localmax_vol","slices","cuts","corrected_p"]),name='outputspec')
    workflow.connect(cluster,'threshold_file',outputspec,'corrected_z')
    workflow.connect(cluster,'index_file',outputspec,'index_file')
    workflow.connect(cluster,'localmax_vol_file',outputspec,'localmax_vol')
    #workflow.connect(showslice,"outfiles",outputspec,"slices")
    #workflow.connect(overlay,"fnames",outputspec,"cuts")
    workflow.connect(cluster,'localmax_txt_file',outputspec,'localmax_txt')
    return workflow
