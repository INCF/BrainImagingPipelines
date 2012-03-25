#Imports ---------------------------------------------------------------------
import sys
sys.path.append('..')

import nipype.interfaces.utility as util    # utility
import nipype.pipeline.engine as pe         # pypeline engine
import os

from base import create_rest_prep
from utils import get_datasink, get_substitutions, get_regexp_substitutions
import argparse

# Preprocessing
# -------------------------------------------------------------

def prep_workflow(subjects, fieldmap):

    if fieldmap:
        modelflow = pe.Workflow(name='preprocfm')
    else:
        modelflow = pe.Workflow(name='preproc')


    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
                         name='subject_names')
    infosource.iterables = ('subject_id', subjects)

    # generate datagrabber
    dataflow = c.create_dataflow()
    modelflow.connect(infosource, 'subject_id',
                      dataflow, 'subject_id')
    
    # generate preprocessing workflow
    preproc = create_rest_prep(fieldmap=fieldmap)
    
    # make a data sink
    sinkd = get_datasink(c.sink_dir, c.fwhm)
    
    if fieldmap:
        datasource_fieldmap = c.create_fieldmap_dataflow()
        preproc.inputs.inputspec.FM_Echo_spacing = c.echospacing
        preproc.inputs.inputspec.FM_TEdiff = c.TE_diff
        preproc.inputs.inputspec.FM_sigma = c.sigma
        modelflow.connect(infosource, 'subject_id',
                          datasource_fieldmap, 'subject_id')
        modelflow.connect(datasource_fieldmap,'mag',
                          preproc,'fieldmap_input.magnitude_file')
        modelflow.connect(datasource_fieldmap,'phase',
                          preproc,'fieldmap_input.phase_file')
        modelflow.connect(preproc, 'outputspec.vsm_file',
                          sinkd, 'preproc.fieldmap')
        modelflow.connect(preproc, 'outputspec.FM_unwarped_mean',
                          sinkd, 'preproc.mean')
    else:
        modelflow.connect(preproc, 'outputspec.mean',
                          sinkd, 'preproc.mean')

    # inputs
    preproc.inputs.fwhm_input.fwhm = c.fwhm
    preproc.inputs.inputspec.num_noise_components = c.num_noise_components
    preproc.crash_dir = c.crash_dir
    modelflow.connect(infosource, 'subject_id', preproc, 'inputspec.fssubject_id')
    preproc.inputs.inputspec.fssubject_dir = c.surf_dir
    preproc.get_node('fwhm_input').iterables = ('fwhm',c.fwhm)
    preproc.inputs.inputspec.ad_normthresh = c.norm_thresh
    preproc.inputs.inputspec.ad_zthresh = c.z_thresh
    preproc.inputs.inputspec.tr = c.TR
    preproc.inputs.inputspec.interleaved = c.Interleaved
    preproc.inputs.inputspec.sliceorder = c.SliceOrder
    preproc.inputs.inputspec.compcor_select = c.compcor_select
    preproc.inputs.inputspec.highpass_sigma = c.highpass_sigma
    preproc.inputs.inputspec.lowpass_sigma = c.lowpass_sigma
    preproc.inputs.inputspec.reg_params = c.reg_params

    
    modelflow.connect(infosource, 'subject_id', sinkd, 'container')
    modelflow.connect(infosource, ('subject_id', get_substitutions, fieldmap),
                      sinkd, 'substitutions')
    modelflow.connect(infosource, ('subject_id', get_regexp_substitutions,
                                   fieldmap),
                      sinkd, 'regexp_substitutions')

    # make connections

    modelflow.connect(dataflow,'func',
                      preproc,'inputspec.func')
    modelflow.connect(preproc, 'outputspec.motion_parameters',
                      sinkd, 'preproc.motion')
    modelflow.connect(preproc, 'plot_motion.out_file',
                      sinkd, 'preproc.motion.@plots')
    modelflow.connect(preproc, 'outputspec.mask',
                      sinkd, 'preproc.mask')
    modelflow.connect(preproc, 'outputspec.outlier_files',
                      sinkd, 'preproc.art')
    modelflow.connect(preproc, 'outputspec.outlier_stat_files',
                      sinkd, 'preproc.art.@stats')
    modelflow.connect(preproc, 'outputspec.combined_motion',
                      sinkd, 'preproc.art.@norm')
    modelflow.connect(preproc, 'outputspec.reg_file',
                      sinkd, 'preproc.bbreg')
    modelflow.connect(preproc, 'outputspec.reg_fsl_file',
                      sinkd, 'preproc.bbreg.@fsl')
    modelflow.connect(preproc, 'outputspec.reg_cost',
                      sinkd, 'preproc.bbreg.@reg_cost')
    modelflow.connect(preproc, 'outputspec.highpassed_files',
                      sinkd, 'preproc.highpass')
    modelflow.connect(preproc, 'outputspec.tsnr_file',
                      sinkd, 'preproc.tsnr')
    modelflow.connect(preproc, 'outputspec.stddev_file',
                      sinkd, 'preproc.tsnr.@stddev')
    modelflow.connect(preproc, 'outputspec.filter_file',
                      sinkd, 'preproc.regressors')
    modelflow.connect(preproc, 'outputspec.z_img', 
                      sinkd, 'preproc.output.@zscored')
    modelflow.connect(preproc, 'outputspec.scaled_files',
                      sinkd, 'preproc.output.@fullspectrum')
    modelflow.connect(preproc, 'outputspec.bandpassed_file',
                      sinkd, 'preproc.output.@bandpassed')

    modelflow.base_dir = os.path.join(c.working_dir,'work_dir')
    return modelflow

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

    #from nipype import config
    #if c.test_mode:
    #    config.enable_debug_mode()
    
    preprocess = prep_workflow(c.subjects, c.use_fieldmap)
    realign = preprocess.get_node('preproc.realign')
    #realign.inputs.loops = 2
    realign.inputs.speedup = 10
    realign.plugin_args = {'qsub_args': '-l nodes=1:ppn=3'}

    if len(c.subjects) == 1:
        preprocess.write_graph(graph2use='exec',
                               dotfilename='single_subject_exec.dot')
    if c.run_on_grid:
        preprocess.run(plugin='PBS', plugin_args = c.plugin_args)
    else:
        preprocess.run()
        #preprocess.run(plugin='MultiProc', plugin_args={'n_procs': 4})

