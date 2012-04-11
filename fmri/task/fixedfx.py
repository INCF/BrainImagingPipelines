# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
A pipeline example that intergrates spm, fsl freesurfer modules to perform a
comparative volume and surface based first level analysis.

This tutorial uses the nipype-tutorial data and hence should be run from the
directory containing tutorial data

    python freesurfer_tutorial.py

"""

import argparse
import os                                    # system functions
import sys
#from nipype.utils.config import config
#config.enable_debug_mode()

#from config import (subjects, root_dir, getcontrasts, auto_fixedfx, fwhm, run_on_grid, overlaythresh, subjectinfo, test_mode)
from copy import deepcopy
from glob import glob
from nipype.workflows.fmri.fsl.estimate import create_fixed_effects_flow

import numpy as np
import nipype.interfaces.io as nio           # i/o routines
import nipype.interfaces.fsl as fsl          # fsl
import nipype.interfaces.utility as util     # utility
import nipype.pipeline.engine as pe          # pypeline engine
import argparse
fsl.FSLCommand.set_default_output_type('NIFTI_GZ')


def getinfo(subject_id,getcontrasts,subjectinfo):
    numruns = len(subjectinfo(subject_id))
    print numruns
    numcon = len(getcontrasts(subject_id))
    info = dict(copes=[['subject_id', 'fwhm',range(1,numcon+1)]],
                varcopes=[['subject_id', 'fwhm', range(1,numcon+1)]],
                dof_files=[['subject_id', 'fwhm']],
                mask_file=[['subject_id']]) 
    return info

def num_copes(files):
    if type(files[0]) is list:
        return len(files[0])
    else:
        return len(files)

def getsubs(subject_id,getcontrasts):
    
    subs = [('_subject_id_%s/'%subject_id,''),
            ('_runs', '/runs'),
            ('_fwhm', 'fwhm')]
    cons = getcontrasts(subject_id)
    for i, con in enumerate(cons):
        subs.append(('_flameo%d/cope1'%i, 'cope_%s'%(con[0])))
        subs.append(('_flameo%d/varcope1'%(i), 'varcope_%s'%(con[0])))
        subs.append(('_flameo%d/tstat1'%(i), 'tstat_%s'%(con[0])))
        subs.append(('_flameo%d/zstat1'%(i), 'zstat_%s'%(con[0])))
        subs.append(('_flameo%d/res4d'%(i), 'res4d_%s'%(con[0])))
        subs.append(('_ztop%d/zstat1_pval'%(i), 'pval_%s'%(con[0])))
        subs.append(('_slicestats%d/zstat1_overlay.png'%(i),'zstat_overlay%d_%s.png'%(i,con[0])))
    return subs

def create_overlay_workflow(name='overlay'):
    # Setup overlay workflow

    overlay = pe.Workflow(name='overlay')
    
    inputspec = pe.Node(interface=util.IdentityInterface(fields=['subject_id',
                                                                 'fwhm',
                                                                 'stat_image']),
                        name='inputspec')
    
    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
                                                   outfields=['meanfunc']),
                         name='datasource')
    
    datasource.inputs.base_directory = os.path.join(c.sink_dir,'analyses','func')
    datasource.inputs.template = '*'
    datasource.inputs.sort_filelist = True
    datasource.inputs.field_template = dict(meanfunc='%s/preproc/meanfunc/*.nii.gz')
    datasource.inputs.template_args = dict(meanfunc = [['subject_id']])

    overlaystats = pe.MapNode(interface=fsl.Overlay(), 
                              name="overlaystats",
                              iterfield=['stat_image'])
    
    slicestats = pe.MapNode(interface=fsl.Slicer(), 
                            name="slicestats",
                            iterfield=['in_file'])
    
    slicestats.inputs.all_axial = True
    slicestats.inputs.image_width = 512
    overlaystats.inputs.show_negative_stats=True
    overlaystats.inputs.auto_thresh_bg=True
    overlaystats.inputs.stat_thresh = c.overlaythresh

    overlay.connect(inputspec, 'subject_id', datasource, 'subject_id')
    #overlay.connect(inputspec, 'fwhm', datasource, 'fwhm')
    overlay.connect(inputspec, 'stat_image', overlaystats, 'stat_image')
    overlay.connect(datasource, 'meanfunc', overlaystats, 'background_image')
    overlay.connect(overlaystats, 'out_file', slicestats, 'in_file')

    return overlay
"""
lab_dir = os.path.join(root_dir, 'analyses/func')
lab_modelfit_out_dir = lab_dir
lab_fixedfx_work_dir = os.path.join(root_dir,'work_dir','fixedfx')
lab_fixedfx_out_dir = lab_dir
lab_crash_dir = os.path.join(lab_dir, 'crash')
"""


# these are command-line arguments
"""
parser = argparse.ArgumentParser()
parser.add_argument('-s','--subjects',dest='subjects',nargs="+",
                    help='A space-delimited list of subjects')
args = parser.parse_args()
if args.subjects:
    subject_list = args.subjects
"""
# have to determine the total number of runs.

def create_fixedfx(name='fixedfx'):
    selectnode = pe.Node(interface=util.IdentityInterface(fields=['runs']),
                         name='idselect')

    selectnode.iterables = ('runs', [range(0,len(c.subjectinfo(c.subjects[0])))]) # this is really bad.

    copeselect = pe.MapNode(interface=util.Select(), name='copeselect',
                            iterfield=['inlist'])

    varcopeselect = pe.MapNode(interface=util.Select(), name='varcopeselect',
                               iterfield=['inlist'])

    dofselect = pe.Node(interface=util.Select(), name='dofselect')

    infosource = pe.Node(interface=util.IdentityInterface(fields=['subject_id','fwhm']), name="infosource")
    infosource.iterables = [('subject_id', c.subjects),
                            ('fwhm',c.fwhm)]

    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id','fwhm'],
                                                   outfields=['copes', 
                                                              'varcopes',
                                                              'dof_files',
                                                              'mask_file']),
                         name = 'datasource')

    datasource.inputs.base_directory = os.path.join(c.sink_dir,'analyses','func')
    datasource.inputs.template ='*'
    datasource.inputs.sort_filelist = True
    datasource.inputs.field_template = dict(copes='%s/modelfit/contrasts/fwhm_%d/_estimate_contrast*/cope%02d*.nii.gz',
                                            varcopes='%s/modelfit/contrasts/fwhm_%d/_estimate_contrast*/varcope%02d*.nii.gz',
                                            dof_files='%s/modelfit/dofs/fwhm_%d/*/*',
                                            mask_file='%s/preproc/mask/*.nii')

    fixedfx = create_fixed_effects_flow()

    fixedfxflow = pe.Workflow(name=name)
    fixedfxflow.config = {'execution' : {'crashdump_dir' : c.crash_dir}}

    overlay = create_overlay_workflow(name='overlay')

    fixedfxflow.connect(infosource, 'subject_id',           datasource, 'subject_id')
    fixedfxflow.connect(infosource, ('subject_id',getinfo, c.getcontrasts, c.subjectinfo), datasource, 'template_args')
    fixedfxflow.connect(infosource, 'fwhm',                 datasource, 'fwhm')
    fixedfxflow.connect(datasource,'copes',                 copeselect,'inlist')
    fixedfxflow.connect(selectnode,'runs',                  copeselect,'index')
    fixedfxflow.connect(datasource,'copes',                   fixedfx,'inputspec.copes')
    fixedfxflow.connect(datasource,'varcopes',              varcopeselect,'inlist')
    fixedfxflow.connect(selectnode,'runs',                  varcopeselect,'index')
    fixedfxflow.connect(datasource,'varcopes',                fixedfx,'inputspec.varcopes')
    fixedfxflow.connect(datasource,'dof_files',             dofselect,'inlist')
    fixedfxflow.connect(selectnode,'runs',                  dofselect,'index')
    fixedfxflow.connect(datasource,'dof_files',                    fixedfx,'inputspec.dof_files')
    fixedfxflow.connect(datasource,('copes',num_copes),       fixedfx,'l2model.num_copes')
    fixedfxflow.connect(datasource,'mask_file',             fixedfx,'flameo.mask_file') 
    fixedfxflow.connect(infosource, 'subject_id',           overlay, 'inputspec.subject_id')
    fixedfxflow.connect(infosource, 'fwhm',                 overlay, 'inputspec.fwhm')
    fixedfxflow.connect(fixedfx, 'outputspec.zstats',       overlay, 'inputspec.stat_image')



    datasink = pe.Node(interface=nio.DataSink(), name="datasink")
    datasink.inputs.base_directory = os.path.join(c.sink_dir,'analyses','func')
    # store relevant outputs from various stages of the 1st level analysis
    fixedfxflow.connect([(infosource, datasink,[('subject_id','container'),
                                          (('subject_id', getsubs, c.getcontrasts), 'substitutions')
                                          ]),
                   (fixedfx, datasink,[('outputspec.copes','fixedfx.@copes'),
                                       ('outputspec.varcopes','fixedfx.@varcopes'),
                                       ('outputspec.tstats','fixedfx.@tstats'),
                                       ('outputspec.zstats','fixedfx.@zstats'),
                                       ('outputspec.res4d','fixedfx.@pvals'),
                                       ])
                   ])
    fixedfxflow.connect(overlay, 'slicestats.out_file', datasink, 'overlays')
    return fixedfxflow
    
"""
if test_mode:
    fixedfxflow.base_dir = lab_fixedfx_work_dir
    fixedfxflow.config.update(**{'execution':{'remove_unnecessary_outputs':False,
                                              'crashdump_dir':lab_crash_dir}})"""
"""
Run the analysis pipeline and also create a dot+png (if graphviz is available)
that visually represents the workflow.
"""

if __name__ == '__main__' or auto_fixedfx:
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
    
    fixedfxflow = create_fixedfx()
    fixedfxflow.base_dir = c.working_dir
    
    if c.run_on_grid:
        fixedfxflow.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        fixedfxflow.run()
    #fixedfxflow.write_graph(graph2use='flat')


