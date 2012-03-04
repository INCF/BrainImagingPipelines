# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

# imports --------------------------------------------------------------------
import sys
sys.path.insert(0,'/mindhive/gablab/users/keshavan/lib/python/nipype') # use Anisha's nipype
from nipype.workflows.dmri.fsl.dti import create_eddy_correct_pipeline
from nipype.workflows.dmri.fsl.tbss import create_tbss_non_FA, create_tbss_all
import nipype.interfaces.io as nio           # Data i/o
import nipype.interfaces.fsl as fsl          # fsl
import nipype.interfaces.utility as util     # utility
import nipype.pipeline.engine as pe          # pypeline engine
import os                                    # system functions
from config import *                         # config file
fsl.FSLCommand.set_default_output_type('NIFTI')
from nipype.utils.config import config
config.enable_debug_mode()

# Utils ----------------------------------------------------------------------

# tolist has to be made into a function node, otherwise Nipype complains. :(

def tolist(x):
    x = [x]
    return x

# Workflow -------------------------------------------------------------------
def create_prep(subj):
        
    inputspec = pe.Node(interface=util.IdentityInterface(fields=['dwi','bvec','bval']),
                        name='inputspec')
    
    gen_fa = pe.Workflow(name="gen_fa")
    gen_fa.base_dir = os.path.join(os.path.abspath(workingdir), 'l1')

    eddy_correct = create_eddy_correct_pipeline()
    eddy_correct.inputs.inputnode.ref_num = 0
    gen_fa.connect(inputspec, 'dwi', eddy_correct, 'inputnode.in_file')

    bet = pe.Node(interface=fsl.BET(), name='bet')
    bet.inputs.mask = True
    bet.inputs.frac = frac
    gen_fa.connect(eddy_correct, 'pick_ref.out', bet, 'in_file')

    dtifit = pe.Node(interface=fsl.DTIFit(), name='dtifit')
    gen_fa.connect(eddy_correct, 'outputnode.eddy_corrected', dtifit, 'dwi')
    
    dtifit.inputs.base_name = subj
    
    gen_fa.connect(bet, 'mask_file', dtifit, 'mask')
    gen_fa.connect(inputspec, 'bvec', dtifit, 'bvecs')
    gen_fa.connect(inputspec, 'bval', dtifit, 'bvals')

    outputnode = pe.Node(interface=util.IdentityInterface(fields=['FA','MD']), name='outputspec')
    
    gen_fa.connect(dtifit, 'FA', outputnode, 'FA')
    gen_fa.connect(dtifit, 'MD', outputnode, 'MD')
    return gen_fa

def create_tbss():
    """
    TBSS analysis
    """
    #tbss_source = get_tbss_source()
    inputnode = pe.Node(interface=util.IdentityInterface(fields=['fa_list','md_list']),
                        name='inputspec')
                        
    tbss_all = create_tbss_all()
    tbss_all.inputs.inputnode.skeleton_thresh = skeleton_thresh

    tbssproc = pe.Workflow(name="tbssproc")
    tbssproc.base_dir = os.path.join(os.path.abspath(workingdir), 'l2')
    
    tbssproc.connect(inputnode, 'fa_list', tbss_all, 'inputnode.fa_list')

    tbss_MD = create_tbss_non_FA(name='tbss_MD')
    tbss_MD.inputs.inputnode.skeleton_thresh = tbss_all.inputs.inputnode.skeleton_thresh

    tbssproc.connect([(tbss_all, tbss_MD, [('tbss2.outputnode.field_list',
                                            'inputnode.field_list'),
                                           ('tbss3.outputnode.groupmask',
                                            'inputnode.groupmask'),
                                           ('tbss3.outputnode.meanfa_file',
                                            'inputnode.meanfa_file'),
                                           ('tbss4.outputnode.distance_map',
                                            'inputnode.distance_map')]),
                      (inputnode, tbss_MD, [('md_list',
                                               'inputnode.file_list')]),
                ])
    return tbssproc

def combine_prep(subj):
    
    modelflow = pe.Workflow(name='preproc')
    
    datasource = get_datasource()
    datasource.inputs.subject_id = subj
    
    prep = create_prep(subj)
    tbss = create_tbss()
    
    lister1 = pe.Node(util.Function(input_names = ['x'],output_names = ['x'],function=tolist),name='to_list1')
    lister2 = pe.Node(util.Function(input_names = ['x'],output_names = ['x'],function=tolist),name='to_list2')
    
    modelflow.connect(datasource,   'dwi',              prep,   'inputspec.dwi')
    modelflow.connect(datasource,   'bvec',             prep,   'inputspec.bvec')
    modelflow.connect(datasource,   'bval',             prep,   'inputspec.bval')
    
    modelflow.connect(prep,         'outputspec.FA',    lister1,   'x')
    modelflow.connect(lister1,         'x',    tbss,   'inputspec.fa_list')
    modelflow.connect(prep,         'outputspec.MD',    lister2,   'x')
    modelflow.connect(lister2,         'x',    tbss,   'inputspec.md_list')
    
    modelflow.base_dir = os.path.join(workingdir,'work_dir',subj)
    return modelflow
    
    

if __name__ == '__main__':
    workflow = combine_prep(subjects[0])
    workflow.write_graph()
    workflow.run()

