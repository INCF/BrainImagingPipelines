#Imports ---------------------------------------------------------------------
import sys
sys.path.insert(0,'/mindhive/gablab/users/keshavan/lib/python/nipype/nipype/interfaces/nipy') # Use Anisha's nipype
import nipype.interfaces.fsl as fsl         # fsl
import nipype.interfaces.utility as util    # utility
import nipype.pipeline.engine as pe         # pypeline engine
import os
import numpy as np
import nipype.algorithms.rapidart as ra     # rapid artifact detection
import nipype.interfaces.io as nio          # input/output
import array
from config import *
from nipype.algorithms.modelgen import SpecifyModel
from nipype.algorithms.misc import TSNR
from nibabel import load
from glob import glob
from nipype.workflows.freesurfer.utils import create_getmask_flow
from nipype.interfaces.base import Bunch
from copy import deepcopy
#from nipype.interfaces.nipy.preprocess import FmriRealign4d
from preprocess import FmriRealign4d
from nipype.utils.config import config
config.enable_debug_mode()

# Utility Functions ---------------------------------------------------------
def getthreshop(thresh):
    return ['-thr %.10f -Tmin -bin'%(0.1*val[1]) for val in thresh]

def pickfirst(files):
    if isinstance(files, list):
        return files[0]
    else:
        return files

def pickmiddlerun(files):
# selects the middle run, defined as the floor of the number of runs divided by two.
    if isinstance(files, list):
        return files[int(len(files)/2)]
    else:
        return files

def returnmiddlevalue(files):
    if isinstance(files,list):
        return int(len(files)/2)

def getbtthresh(medianvals):
    return [0.75*val for val in medianvals]

def chooseindex(fwhm):
    if fwhm<1:
        return [0]
    else:
        return [1]

def getmeanscale(medianvals):
    return ['-mul %.10f'%(10000./val) for val in medianvals]

def getusans(x):
    return [[tuple([val[0],0.75*val[1]])] for val in x]

def extract_noise_components(realigned_file, noise_mask_file, num_components):
    """Derive components most reflective of physiological noise
    """
    import os
    from nibabel import load
    import numpy as np
    import scipy as sp
    from scipy.signal import detrend
    imgseries = load(realigned_file)
    noise_mask = load(noise_mask_file)
    voxel_timecourses = imgseries.get_data()[np.nonzero(noise_mask.get_data())]
    for timecourse in voxel_timecourses:
        timecourse[:] = detrend(timecourse, type='constant')
    
    voxel_timecourses = voxel_timecourses.byteswap().newbyteorder() 
    u,s,v = sp.linalg.svd(voxel_timecourses, full_matrices=False)
    components_file = os.path.join(os.getcwd(), 'noise_components.txt')
    np.savetxt(components_file, v[:,:num_components])
    return components_file

def fslcpgeom(in_file,dest_file):
    from nipype.interfaces.base import CommandLine
    import os
    from glob import glob
    cmd2 = 'cp '+dest_file+' .'
    cli = CommandLine(command=cmd2)
    cli.run()
    dest_file = os.path.join(os.getcwd(),os.path.split(dest_file)[1])
    cmd1 = '''fslcpgeom '''+in_file+' '+dest_file+' -d'
    cli = CommandLine(command=cmd1)
    cli.run()
    return dest_file

def pickvol(filenames, fileidx, which):
    from nibabel import load
    import numpy as np
    if which.lower() == 'first':
        idx = 0
    elif which.lower() == 'middle':
        idx = int(np.ceil(load(filenames[fileidx]).get_shape()[3]/2))
    else:
        raise Exception('unknown value for volume selection : %s'%which)
    return idx

def trad_mot(subinfo,files):
    # modified to work with only one regressor at a time...
    motion_params = []
    mot_par_names = ['Pitch (rad)','Roll (rad)','Yaw (rad)','Tx (mm)','Ty (mm)','Tz (mm)']
    for j,i in enumerate(files):
        motion_params.append([[],[],[],[],[],[]])
        k = map(lambda x: float(x), filter(lambda y: y!='',open(i,'r').read().replace('\n','').split(' ')))
        for z in range(6):
            motion_params[j][z] = k[z:len(k):6]
    for j,i in enumerate(subinfo):
        if i.regressor_names == None: i.regressor_names = []
        if i.regressors == None: i.regressors = []
        for j3, i3 in enumerate(motion_params[j]):
            i.regressor_names.append(mot_par_names[j3])
            i.regressors.append(i3)
    return subinfo

def noise_mot(subinfo,files,num_noise_components):
    noi_reg_names = map(lambda x: 'noise_comp_'+str(x+1),range(num_noise_components))
    noise_regressors = []
    for j,i in enumerate(files):
        noise_regressors.append([[],[],[],[],[]])
        k = map(lambda x: float(x), filter(lambda y: y!='',open(i,'r').read().replace('\n',' ').split(' ')))
        for z in range(num_noise_components):
            noise_regressors[j][z] = k[z:len(k):num_noise_components]
    for j,i in enumerate(subinfo):
        if i.regressor_names == None: i.regressor_names = []
        if i.regressors == None: i.regressors = []
        for j3,i3 in enumerate(noise_regressors[j]):
            i.regressor_names.append(noi_reg_names[j3])
            i.regressors.append(i3)
    return subinfo

def add_outliers(outlier_file, noise_comp_file):
    import numpy as np
    import os
    b = np.genfromtxt(noise_comp_file[0])
    noise_outlier_file = os.path.abspath('outliers+'+os.path.split(noise_comp_file[0])[1])
    try:
        a = np.genfromtxt(outlier_file)
        if a.shape ==():
            z = np.zeros((b.shape[0],1))
            z[np.int_(a)-1,0] = 1
            out = np.hstack((b,z))
        else:
            z = np.zeros((b.shape[0],a.shape[0]))
            for i,t in enumerate(a):
                z[np.int_(t)-1,i] = 1
            out = np.hstack((b,z))
    except:
        out = b
    np.savetxt(noise_outlier_file,out)
    return noise_outlier_file

tolist = lambda x: [x]
takefirst = lambda x: x[0]
highpass_operand = lambda x:'-bptf %.10f -1'%x

# Preprocessing
# -------------------------------------------------------------

def create_compcorr(name='compcorr'):
    compproc = pe.Workflow(name=name)
    # extract the principal components of the noise
    tsnr = pe.MapNode(TSNR(regress_poly=2),
                      name='tsnr',
                      iterfield=['in_file'])
    
    # additional information for the noise prin comps
    getthresh = pe.MapNode(interface=fsl.ImageStats(op_string='-p 98'),
                            name='getthreshold',
                            iterfield=['in_file'])

    # and a bit more...
    threshold_stddev = pe.MapNode(fsl.Threshold(),
                                  name='threshold',
                                  iterfield=['in_file','thresh'])
    
    # compcor actually extracts the components
    compcor = pe.MapNode(util.Function(input_names=['realigned_file',
                                                    'noise_mask_file',
                                                    'num_components'],
                                       output_names=['noise_components'],
                                       function=extract_noise_components),
                                       name='compcor',
                                       iterfield=['realigned_file',
                                                  'noise_mask_file'])

    compproc.connect(getthresh,'out_stat',threshold_stddev,'thresh')
    compproc.connect(threshold_stddev,'out_file', compcor, 'noise_mask_file')
    compproc.connect(tsnr, 'stddev_file', threshold_stddev,'in_file')
    compproc.connect(tsnr, 'stddev_file', getthresh, 'in_file')
    return compproc



def create_prep(name='preproc'):
    preproc = pe.Workflow(name=name)
    from nipype.workflows.freesurfer.utils import create_getmask_flow
    from nipype.workflows.fsl.preprocess import create_susan_smooth
    compcor = create_compcorr()
    
    inputnode = pe.Node(interface=util.IdentityInterface(fields=['subjid',
                                                                 'func',
                                                                 'fwhm',
                                                                 'highpass',
                                                                 'num_noise_components']),
                        name='inputspec')

    #add outliers and noise components
    addoutliers = pe.Node(util.Function(input_names=['outlier_file','noise_comp_file'],output_names=['noise_outlier_file'],function=add_outliers),name='add_outliers')

    
    # convert BOLD images to float
    img2float = pe.MapNode(interface=fsl.ImageMaths(out_data_type='float',
                                                    op_string = '',
                                                    suffix='_dtype'),
                           iterfield=['in_file'],
                           name='img2float')
    
    # define the motion correction node
    motion_correct = pe.MapNode(interface=FmriRealign4d(),
                                name='realign',iterfield=['in_file']) 
    motion_correct.inputs.tr = TR
    motion_correct.inputs.interleaved = Interleaved
    motion_correct.inputs.slice_order = SliceOrder
    
    # construct motion plots
    plot_motion = pe.MapNode(interface=fsl.PlotMotionParams(in_source='fsl'),
                             name='plot_motion',
                             iterfield=['in_file'])

    # rapidArt for artifactual timepoint detection 
    ad = pe.Node(ra.ArtifactDetect(),
                 name='artifactdetect')

    # extract the mean volume if the first functional run
    meanfunc = pe.Node(interface=fsl.ImageMaths(op_string = '-Tmean',
                                                suffix='_mean'),
                       name='meanfunc')

    # generate a freesurfer workflow that will return the mask
    getmask = create_getmask_flow()


    # create a SUSAN smoothing workflow, and smooth each run with 
    # 75% of the median value for each run as the brightness 
    # threshold.
    smooth = create_susan_smooth(name="susan_smooth", separate_masks=False)

    # scale the median value of each run to 10,000
    meanscale = pe.MapNode(interface=fsl.ImageMaths(suffix='_gms'),
                           iterfield=['in_file',
                                      'op_string'],
                           name='meanscale')
                                        
    # determine the median value of the MASKED functional runs  
    medianval = pe.MapNode(interface=fsl.ImageStats(op_string='-k %s -p 50'),
                           iterfield = ['in_file'],
                           name='medianval')

    # temporal highpass filtering
    highpass = pe.MapNode(interface=fsl.ImageMaths(suffix='_tempfilt'),
                          iterfield=['in_file'],
                          name='highpass')

    remove_noise = pe.Node(fsl.FilterRegressor(filter_all=True),
                       name='remove_noise')
                       
    bandpass_filter = pe.Node(fsl.TemporalFilter(),
                              name='bandpass_filter')


    # make one last mean functional image
#    meanfunc3 = pe.Node(interface=fsl.ImageMaths(op_string='-Tmean',
#                                                 suffix='_mean'),
#                        iterfield=['in_file'],
#                        name='meanfunc3')


    # declare some node inputs...
    plot_motion.iterables = ('plot_type', ['rotations', 'translations'])
    ad.inputs.norm_threshold = norm_thresh
    ad.inputs.parameter_source = 'FSL'
    ad.inputs.zintensity_threshold = z_thresh
    ad.inputs.mask_type = 'file'
    ad.inputs.use_differences = [True, False]
    getmask.inputs.inputspec.subjects_dir = surf_dir
    getmask.inputs.inputspec.contrast_type = 't2'
    bandpass_filter.inputs.highpass_sigma = highpass_sigma
    bandpass_filter.inputs.lowpass_sigma = lowpass_sigma
    #motion_correct.inputs.args = '-spline_final'

    # make connections...
    preproc.connect(inputnode, 'subjid', getmask, 'inputspec.subject_id')
    preproc.connect(inputnode, 'func', img2float, 'in_file')
    preproc.connect(img2float,('out_file',tolist),motion_correct,'in_file')
    preproc.connect(motion_correct, 'par_file', plot_motion, 'in_file')
    preproc.connect(motion_correct, ('out_file', pickfirst), meanfunc,'in_file')
    preproc.connect(meanfunc, 'out_file', getmask, 'inputspec.source_file')
    preproc.connect(inputnode,'num_noise_components',compcor, 'compcor.num_components')
    preproc.connect(motion_correct,'out_file',compcor, 'compcor.realigned_file')
    preproc.connect(motion_correct,'out_file',compcor, 'tsnr.in_file')
    preproc.connect(motion_correct,'out_file',ad,'realigned_files')
    preproc.connect(motion_correct,'par_file',ad,'realignment_parameters')
    preproc.connect(getmask,('outputspec.mask_file',pickfirst),ad,'mask_file')
    preproc.connect(smooth,'outputnode.smoothed_files',medianval,'in_file')
    preproc.connect(getmask,('outputspec.mask_file',pickfirst),medianval,'mask_file')
    preproc.connect(inputnode, 'fwhm', smooth, 'inputnode.fwhm')
    #preproc.connect(motion_correct, 'out_file', smooth, 'inputnode.in_files')
    preproc.connect(bandpass_filter,'out_file',smooth,'inputnode.in_files')
    preproc.connect(getmask, ('outputspec.mask_file',pickfirst), smooth, 'inputnode.mask_file')
    preproc.connect(smooth, 'outputnode.smoothed_files', meanscale, 'in_file')
    preproc.connect(medianval, ('out_stat', getmeanscale), meanscale, 'op_string')
    preproc.connect(inputnode, ('highpass', highpass_operand), highpass, 'op_string')
    preproc.connect(meanscale, 'out_file', highpass, 'in_file')
    ## CHANGE ##
    # this file needs to have art outlier in it as well
    #preproc.connect(compcor, 'compcor.noise_components', remove_noise, 'design_file') 
    preproc.connect(ad,'outlier_files',addoutliers,'outlier_file')
    preproc.connect(compcor,'compcor.noise_components',addoutliers,'noise_comp_file')
    preproc.connect(addoutliers,'noise_outlier_file',remove_noise,'design_file')
    ## CHANGE ##
    preproc.connect(remove_noise, 'out_file', bandpass_filter, 'in_file')
    preproc.connect(compcor, ('tsnr.detrended_file',takefirst),remove_noise, 'in_file')
    # create output node
    outputnode = pe.Node(interface=util.IdentityInterface(
        fields=['reference',
                'motion_parameters',
                'realigned_files',
                'mask',
                'smoothed_files',
                'highpassed_files',
                'mean',
                'combined_motion',
                'outlier_files',
                'mask',
                'reg_cost',
                'reg_file',
                'noise_components']),
                        name='outputspec')

    # make output connection
    preproc.connect(meanfunc,'out_file',outputnode,'reference')
    preproc.connect(motion_correct,'par_file',outputnode,'motion_parameters')
    preproc.connect(motion_correct,'out_file',outputnode,'realigned_files')
    preproc.connect(highpass, 'out_file', outputnode, 'highpassed_files')
    preproc.connect(meanfunc, 'out_file', outputnode, 'mean')
    preproc.connect(ad,'norm_files', outputnode,'combined_motion')
    preproc.connect(ad,'outlier_files', outputnode,'outlier_files')
    preproc.connect(compcor, 'compcor.noise_components', outputnode,'noise_components')
    preproc.connect(getmask, ('outputspec.mask_file',pickfirst), outputnode,'mask')
    preproc.connect(getmask, 'outputspec.reg_file', outputnode,'reg_file')
    preproc.connect(getmask, 'outputspec.reg_cost', outputnode, 'reg_cost')

    return preproc

def prep_workflow(subj):
    
    def getsubs(subject_id):
        subs = [('_subject_id_%s/'%subject_id,''),
                ('_plot_type_',''),
                ('_fwhm','fwhm'),
                ('_dtype_mcf_mask_mean','_mean'),
                ('_dtype_mcf_mask_smooth_mask_gms_tempfilt','_smoothed_preprocessed'),
                ('_dtype_mcf_mask_gms_tempfilt','_unsmoothed_preprocessed'),
                ('_dtype_mcf','_mcf')]
        
        for i in range(4):
            subs.append(('_plot_motion%d'%i, ''))
            subs.append(('_highpass%d/'%i, ''))
            subs.append(('_realign%d/'%i, ''))
            subs.append(('_meanfunc2%d/'%i, ''))
        return subs

    modelflow = pe.Workflow(name='preproc')


#    # create a node to obtain the functional images
#    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
#                                                   outfields=['func']),
#                         name = 'datasource')
#    datasource.inputs.base_directory = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/data/'
#    datasource.inputs.template ='*'
#    datasource.inputs.field_template = dict(func='%s/f%s.nii')
#    datasource.inputs.subject_id = subj
#    datasource.inputs.template_args = dict(func=[['subject_id',['3']]])#,'2','3','4','5','6']]])
    
    # generate preprocessing workflow
    dataflow =                                          create_dataflow(subj)
    #recon =                                             create_recon()
    preproc =                                           create_prep()
    #preproc.inputs.inputspec.func =                     bolds
    preproc.get_node('inputspec').iterables =           ('fwhm',fwhm)
    preproc.inputs.inputspec.highpass =                 hpcutoff/(2*2.5)
    preproc.inputs.inputspec.num_noise_components =     num_noise_components
    preproc.crash_dir =                                 crash_dir
    preproc.inputs.inputspec.subjid =                   subj
    

    # make a data sink
    sinkd = pe.Node(nio.DataSink(), name='sinkd')
    sinkd.inputs.base_directory = os.path.join(root_dir,'analyses','func')
    sinkd.inputs.container = subj
    sinkd.inputs.substitutions = getsubs(subj)
    sinkd.inputs.regexp_substitutions = [('mask/fwhm_%d/_threshold([0-9]*)/.*nii'%x,'mask/fwhm_%d/funcmask.nii'%x) for x in fwhm]
    sinkd.inputs.regexp_substitutions.append(('realigned/fwhm_([0-9])/_copy_geom([0-9]*)/','realigned/'))
    sinkd.inputs.regexp_substitutions.append(('motion/fwhm_([0-9])/','motion/'))
    sinkd.inputs.regexp_substitutions.append(('bbreg/fwhm_([0-9])/','bbreg/'))
    
    # make connections
        
    modelflow.connect(dataflow,'func',preproc,'inputspec.func')
      
    modelflow.connect(preproc, 'outputspec.reference',              sinkd,      'preproc.motion.reference')
    modelflow.connect(preproc, 'outputspec.motion_parameters',      sinkd,      'preproc.motion')
    modelflow.connect(preproc, 'outputspec.realigned_files',        sinkd,      'preproc.motion.realigned')
    modelflow.connect(preproc, 'outputspec.mean',                   sinkd,      'preproc.meanfunc')
    modelflow.connect(preproc, 'plot_motion.out_file',              sinkd,      'preproc.motion.@plots')
    modelflow.connect(preproc, 'outputspec.mask',                   sinkd,      'preproc.mask')
    modelflow.connect(preproc, 'outputspec.outlier_files',          sinkd,      'preproc.art')
    modelflow.connect(preproc, 'outputspec.combined_motion',        sinkd,      'preproc.art.@stats')
    modelflow.connect(preproc, 'outputspec.reg_file',               sinkd,      'preproc.bbreg')
    modelflow.connect(preproc, 'outputspec.reg_cost',               sinkd,      'preproc.bbreg.@reg_cost')
    modelflow.connect(preproc, 'outputspec.highpassed_files',       sinkd,      'preproc.highpass')
    
    # create output node
    outputnode = pe.Node(interface=util.IdentityInterface(
        fields=['reference',
                'motion_parameters',
                'realigned_files',
                'mask',
                'smoothed_files',
                'highpassed_files',
                'mean',
                'combined_motion',
                'outlier_files',
                'mask',
                'reg_cost',
                'reg_file',
                'noise_components']),
                        name='outputspec')
    
    #Make more connections    
    
    modelflow.connect(preproc, 'outputspec.reference',              outputnode,      'reference')
    modelflow.connect(preproc, 'outputspec.motion_parameters',      outputnode,      'motion_parameters')
    modelflow.connect(preproc, 'outputspec.realigned_files',        outputnode,      'realigned_files')
    modelflow.connect(preproc, 'outputspec.smoothed_files',         outputnode,      'smoothed_files')
    modelflow.connect(preproc, 'outputspec.noise_components',       outputnode,      'noise_components')
    modelflow.connect(preproc, 'outputspec.mean',                   outputnode,      'mean')
    modelflow.connect(preproc, 'outputspec.mask',                   outputnode,      'mask')
    modelflow.connect(preproc, 'outputspec.outlier_files',          outputnode,      'outlier_files')
    modelflow.connect(preproc, 'outputspec.combined_motion',        outputnode,      'combined_motion')
    modelflow.connect(preproc, 'outputspec.reg_file',               outputnode,      'reg_file')
    modelflow.connect(preproc, 'outputspec.reg_cost',               outputnode,      'reg_cost')
    modelflow.connect(preproc, 'outputspec.highpassed_files',       outputnode,      'highpassed_files')
    
    
    modelflow.base_dir = os.path.join(root_dir,'work_dir',subj)
    return modelflow

if __name__ == "__main__":
    preprocess = prep_workflow(subjects[0])
    preprocess.run()

