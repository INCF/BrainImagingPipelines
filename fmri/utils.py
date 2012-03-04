# Utility Functions ---------------------------------------------------------
import nipype.pipeline.engine as pe         # pypeline engine
import nipype.interfaces.io as nio          # input/output
import os
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.freesurfer as fs

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

def extract_noise_components(realigned_file, noise_mask_file, num_components, anat_mask_file, selector):
    """Derive components most reflective of physiological noise
    """
    import os
    from nibabel import load
    import numpy as np
    import scipy as sp
    from scipy.signal import detrend
    
    options = np.array([noise_mask_file, anat_mask_file])
    selector = np.array(selector)
    imgseries = load(realigned_file)
    
    if selector.all(): # both values of selector are true, need to concatenate
        tcomp = load(noise_mask_file)
        acomp = load(anat_mask_file)
        voxel_timecourses = imgseries.get_data()[np.nonzero(tcomp.get_data()+acomp.get_data())]
        
    else:
        noise_mask_file = options[selector][0]
        noise_mask = load(noise_mask_file)
        voxel_timecourses = imgseries.get_data()[np.nonzero(noise_mask.get_data())]
    
    
    for timecourse in voxel_timecourses:
        timecourse[:] = detrend(timecourse, type='constant')
    
    voxel_timecourses = voxel_timecourses.byteswap().newbyteorder() 
    u,s,v = sp.linalg.svd(voxel_timecourses, full_matrices=False)
    components_file = os.path.join(os.getcwd(), 'noise_components.txt')
    np.savetxt(components_file, v[:,:num_components])
    return components_file
    
def extract_anat_mask():
    
    anat = pe.Workflow(name='extract_anat')
    
    inputspec = pe.Node(interface=util.IdentityInterface(fields=['realigned_file','reg_file','anat_file']),name='inputspec') 
    
    bin = pe.Node(interface = fs.Binarize(), name = 'binarize')
    
    anat.connect(inputspec, ('anat_file',pickfirst), bin, "in_file")
    
    bin.inputs.ventricles = True
    
    unvoltransform = pe.Node(interface=fs.ApplyVolTransform(inverse=True),name='unapplyreg')
    
    anat.connect(bin, 'binary_file', unvoltransform, 'target_file')
    anat.connect(inputspec,('reg_file',pickfirst),unvoltransform,'reg_file')
    anat.connect(inputspec,('realigned_file',pickfirst),unvoltransform,'source_file')
    outputspec = pe.Node(interface=util.IdentityInterface(fields=['anat_mask']),name='outputspec')
    
    anat.connect(unvoltransform,'transformed_file',outputspec,'anat_mask')
       
    return anat
        

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

def create_compcorr(name='compcorr'):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    import nipype.interfaces.io as nio
    from nipype.algorithms.misc import TSNR
    import nipype.interfaces.fsl as fsl         
    compproc = pe.Workflow(name=name)
    inputspec = pe.Node(interface=util.IdentityInterface(fields=['num_components','realigned_file', 'in_file','reg_file','anat_file','selector']),name='inputspec')
    # selector input is bool list [True,True] where first is referring to t compcorr and second refers to a compcorr
    outputspec = pe.Node(interface=util.IdentityInterface(fields=['noise_components','stddev_file','tsnr_file','anat_mask']),name='outputspec')
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
    
    acomp = extract_anat_mask()
    
    # compcor actually extracts the components
    compcor = pe.MapNode(util.Function(input_names=['realigned_file',
                                                    'noise_mask_file',
                                                    'num_components',
                                                    'anat_mask_file',
                                                    'selector'],
                                       output_names=['noise_components'],
                                       function=extract_noise_components),
                                       name='compcor',
                                       iterfield=['realigned_file',
                                                  'noise_mask_file'])
    
    compproc.connect(inputspec,'realigned_file',acomp,'inputspec.realigned_file')
    compproc.connect(inputspec,'reg_file',acomp,'inputspec.reg_file')
    compproc.connect(inputspec,'anat_file',acomp,'inputspec.anat_file')
    compproc.connect(inputspec,'selector', compcor, 'selector')
    compproc.connect(acomp,'outputspec.anat_mask',compcor,'anat_mask_file')
    compproc.connect(inputspec,'in_file',tsnr,'in_file')
    compproc.connect(inputspec,'num_components',compcor,'num_components')
    compproc.connect(inputspec,'realigned_file',compcor,'realigned_file')
    compproc.connect(getthresh,'out_stat',threshold_stddev,'thresh')
    compproc.connect(threshold_stddev,'out_file', compcor, 'noise_mask_file')
    compproc.connect(tsnr, 'stddev_file', threshold_stddev,'in_file')
    compproc.connect(tsnr, 'stddev_file', getthresh, 'in_file')
    compproc.connect(tsnr, 'stddev_file', outputspec, 'stddev_file')
    compproc.connect(tsnr, 'tsnr_file', outputspec, 'tsnr_file')
    compproc.connect(compcor,'noise_components',outputspec, 'noise_components')
    
    
    return compproc

def choose_susan(fwhm,motion_files,smoothed_files):
    cor_smoothed_files = []
    if fwhm == 0:
        cor_smoothed_files = motion_files
    else:
        cor_smoothed_files = smoothed_files
    return cor_smoothed_files

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

def get_datasink(subj,root_dir,fwhm):
    sinkd = pe.Node(nio.DataSink(), name='sinkd')
    sinkd.inputs.base_directory = os.path.join(root_dir,'analyses','func')
    sinkd.inputs.container = subj
    sinkd.inputs.substitutions = getsubs(subj)
    sinkd.inputs.regexp_substitutions = [('mask/fwhm_%d/_threshold([0-9]*)/.*nii'%x,'mask/fwhm_%d/funcmask.nii'%x) for x in fwhm]
    sinkd.inputs.regexp_substitutions.append(('realigned/fwhm_([0-9])/_copy_geom([0-9]*)/','realigned/'))
    sinkd.inputs.regexp_substitutions.append(('motion/fwhm_([0-9])/','motion/'))
    sinkd.inputs.regexp_substitutions.append(('bbreg/fwhm_([0-9])/','bbreg/'))
    return sinkd


    
tolist = lambda x: [x]
highpass_operand = lambda x:'-bptf %.10f -1'%x
