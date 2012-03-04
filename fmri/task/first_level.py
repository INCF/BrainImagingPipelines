# Import Stuff
import sys
sys.path.insert(0,'/mindhive/gablab/users/keshavan/lib/python/nipype/') # Use Anisha's nipype
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
from nipype.utils.config import config
config.enable_debug_mode()
from preproc_only_AK import * #(preproc = prep_workflow(subject))
from report_first_level import *
from textmake import *

# First level modeling
def create_first(name='modelfit'):
    modelfit = pe.Workflow(name=name)

    inputspec = pe.Node(util.IdentityInterface(fields=['session_info',
                                                       'interscan_interval',
                                                       'contrasts',
                                                       'film_threshold',
                                                       'functional_data',
                                                       'bases',
                                                       'model_serial_correlations']),
                        name='inputspec')
    
    
    
    level1design = pe.Node(interface=fsl.Level1Design(), 
                           name="level1design")

    modelgen = pe.MapNode(interface=fsl.FEATModel(), 
                          name='modelgen',
                          iterfield = ['fsf_file', 
                                       'ev_files'])
    
    modelestimate = pe.MapNode(interface=fsl.FILMGLS(smooth_autocorr=True,
                                                     mask_size=5),
                               name='modelestimate',
                               iterfield = ['design_file',
                                            'in_file'])

    conestimate = pe.MapNode(interface=fsl.ContrastMgr(), 
                             name='conestimate',
                             iterfield = ['tcon_file',
                                          'param_estimates',
                                          'sigmasquareds', 
                                          'corrections',
                                          'dof_file'])

    ztopval = pe.MapNode(interface=fsl.ImageMaths(op_string='-ztop',
                                                  suffix='_pval'),
                         name='ztop',
                         iterfield=['in_file'])
    outputspec = pe.Node(util.IdentityInterface(fields=['copes',
                                                        'varcopes',
                                                        'dof_file', 
                                                        'pfiles',
                                                        'parameter_estimates',
                                                        'zstats',
                                                        'tstats',
                                                        'design_image',
                                                        'design_file',
                                                        'design_cov']),
                         name='outputspec')

    # Utility function

    pop_lambda = lambda x : x[0]

    # Setup the connections

    modelfit.connect([
        (inputspec, level1design,   [('interscan_interval',     'interscan_interval'),
                                     ('session_info',           'session_info'),
                                     ('contrasts',              'contrasts'),
                                     ('bases',                  'bases'),
                                     ('model_serial_correlations',
                                     'model_serial_correlations')]),
        (inputspec, modelestimate,  [('film_threshold',         'threshold'),
                                     ('functional_data',        'in_file')]),
        (level1design,modelgen,     [('fsf_files',              'fsf_file'),
                                     ('ev_files',               'ev_files')]),
        (modelgen, modelestimate,   [('design_file',            'design_file')]),
        (modelgen, conestimate,     [('con_file',               'tcon_file')]),
        (modelestimate, conestimate,[('param_estimates',        'param_estimates'),
                                     ('sigmasquareds',          'sigmasquareds'),
                                     ('corrections',            'corrections'),
                                     ('dof_file',               'dof_file')]),
        (conestimate, ztopval,      [(('zstats', pop_lambda),   'in_file')]),
        (ztopval, outputspec,       [('out_file',               'pfiles')]),
        (modelestimate, outputspec, [('param_estimates',        'parameter_estimates'),
                                     ('dof_file',               'dof_file')]),
        (conestimate, outputspec,   [('copes',                  'copes'),
                                     ('varcopes',               'varcopes'),
                                     ('tstats',                 'tstats'),
                                     ('zstats',                 'zstats')])])
    modelfit.connect(modelgen, 'design_image',          outputspec, 'design_image')
    modelfit.connect(modelgen, 'design_file',           outputspec, 'design_file')
    modelfit.connect(modelgen, 'design_cov',           outputspec, 'design_cov')
    return modelfit

def combine_wkflw(subj,preproc,name='combineworkflow'):
    modelflow = pe.Workflow(name=name)
    modelflow.base_dir = os.path.join(root_dir,'work_dir')
       
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
        cons = getcontrasts(subject_id)
        runs = get_run_numbers(subject_id)
        info = subjectinfo(subject_id)
        for i, run in enumerate(runs):
            subs.append(('_modelestimate%d/'%i, '_run_%d_%02d_'%(i,run)))
            subs.append(('_modelgen%d/'%i, '_run_%d_%02d_'%(i,run)))
            subs.append(('_conestimate%d/'%i,'_run_%d_%02d_'%(i,run)))
        for i, con in enumerate(cons):
            subs.append(('cope%d.'%(i+1), 'cope%02d_%s.'%(i+1,con[0])))
            subs.append(('varcope%d.'%(i+1), 'varcope%02d_%s.'%(i+1,con[0])))
            subs.append(('zstat%d.'%(i+1), 'zstat%02d_%s.'%(i+1,con[0])))
            subs.append(('tstat%d.'%(i+1), 'tstat%02d_%s.'%(i+1,con[0])))
        for i, name in enumerate(info[0].conditions):
            subs.append(('pe%d.'%(i+1), 'pe%02d_%s.'%(i+1,name)))
        for i in range(len(info[0].conditions), 256):
            subs.append(('pe%d.'%(i+1), 'others/pe%02d.'%(i+1)))
        for i in fwhm:
            subs.append(('_register%d/'%(i),''))
        
        return subs
    
    # create a node to create the subject info
    s = pe.Node(SpecifyModel(),name='s')
    s.inputs.input_units =                              'secs'
    s.inputs.time_repetition =                          TR
    s.inputs.high_pass_filter_cutoff =                  hpcutoff
    subjinfo =                                          subjectinfo(subj)
    
    # create a node to add the traditional (MCFLIRT-derived) motion regressors to 
    # the subject info
    trad_motn = pe.Node(util.Function(input_names=['subinfo',
                                                   'files'],
                                      output_names=['subinfo'],
                                      function=trad_mot),
                        name='trad_motn')

    trad_motn.inputs.subinfo = subjinfo

    # create a node to add the principle components of the noise regressors to 
    # the subject info
    noise_motn = pe.Node(util.Function(input_names=['subinfo',
                                                    'files',
                                                    'num_noise_components'],
                                       output_names=['subinfo'],
                                       function=noise_mot),
                         name='noise_motn')
    
    # generate first level analysis workflow
    modelfit =                                          create_first()
    modelfit.inputs.inputspec.interscan_interval =      interscan_interval
    modelfit.inputs.inputspec.film_threshold =          film_threshold
    modelfit.inputs.inputspec.contrasts =               getcontrasts(subj)
    modelfit.inputs.inputspec.bases =                   {'dgamma':{'derivs': False}}
    modelfit.inputs.inputspec.model_serial_correlations = True
    noise_motn.inputs.num_noise_components =            num_noise_components
    
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
    modelflow.connect(preproc, 'outputspec.motion_parameters',      trad_motn,  'files')
    modelflow.connect(preproc, 'outputspec.noise_components',       noise_motn, 'files')
    modelflow.connect(preproc, 'outputspec.highpassed_files',       s,          'functional_runs')
    modelflow.connect(preproc, 'outputspec.highpassed_files',       modelfit,   'inputspec.functional_data')
    modelflow.connect(preproc, 'outputspec.outlier_files',          s,          'outlier_files')
    modelflow.connect(trad_motn,'subinfo',                          noise_motn, 'subinfo')
    modelflow.connect(noise_motn,'subinfo',                         s,          'subject_info')
    modelflow.connect(s,'session_info',                             modelfit,   'inputspec.session_info')
    modelflow.connect(preproc, 'outputspec.reference',              sinkd,      'preproc.motion.reference')
    modelflow.connect(modelfit, 'outputspec.parameter_estimates',   sinkd,      'modelfit.estimates')
    modelflow.connect(modelfit, 'outputspec.dof_file',              sinkd,      'modelfit.dofs')
    modelflow.connect(modelfit, 'outputspec.copes',                 sinkd,      'modelfit.contrasts.@copes')
    modelflow.connect(modelfit, 'outputspec.varcopes',              sinkd,      'modelfit.contrasts.@varcopes')
    modelflow.connect(modelfit, 'outputspec.zstats',                sinkd,      'modelfit.contrasts.@zstats')
    modelflow.connect(modelfit, 'outputspec.tstats',                sinkd,      'modelfit.contrasts.@tstats')
    modelflow.connect(modelfit, 'outputspec.design_image',          sinkd,      'modelfit.design')
    modelflow.connect(modelfit, 'outputspec.design_cov',            sinkd,      'modelfit.design.@cov')
    modelflow.connect(modelfit, 'outputspec.design_file',           sinkd,      'modelfit.design.@matrix')
    return modelflow
    
if __name__ == "__main__":
     preprocess = prep_workflow(subjects[0])
     first_level = combine_wkflw(subjects[0],preprocess,name=subjects[0])
     first_level.run()
     modelflow = combine_report(subjects[0],maindir = root_dir, fsdir = surf_dir, thr = 3.6, csize = 50)
     modelflow.run(plugin='PBS')
     textmake(subjects[0])
