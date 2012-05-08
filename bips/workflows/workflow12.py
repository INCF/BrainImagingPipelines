from nipype.workflows.dmri.fsl.dti import create_eddy_correct_pipeline
from nipype.workflows.dmri.fsl.tbss import create_tbss_non_FA, create_tbss_all
import nipype.interfaces.io as nio
from nipype.workflows.smri.freesurfer import create_getmask_flow
import nipype.interfaces.fsl as fsl          # fsl
import nipype.interfaces.utility as util     # utility
import nipype.pipeline.engine as pe          # pypeline engine
import os                                    # system functions
fsl.FSLCommand.set_default_output_type('NIFTI')
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits
from .scripts.u0a14c5b5899911e1bca80023dfa375f2.utils import pickfirst
from .base import MetaWorkflow, load_config, register_workflow

mwf = MetaWorkflow()
mwf.help = """
Diffusion pre-processing workflow
================================

"""
mwf.uuid = 'd9bee4cc987611e19b9b001e4fb1404c'
mwf.tags = ['diffusion','dti','pre-processing']
mwf.script_dir = 'u0a14c5b5899911e1bca80023dfa375f2'


def tolist(x):
    x = [x]
    return x

def rotate_bvecs(bvecs, motion_vecs, rotate):
    if not rotate:
        rotated_bvecs = bvecs
    else:
        import numpy as np
        import os
        bvecs = np.genfromtxt(bvecs)
        rotated_bvecs = open(os.path.abspath('rotated_bvecs.txt'),'w')
        for i,r in enumerate(motion_vecs):
            mat = np.genfromtxt(r)
            rot = np.dot(mat,np.hstack((bvecs[i,:],1)))
            for point in rot[:-1]:
                rotated_bvecs.write('%f '%point)
            rotated_bvecs.write('\n')
        rotated_bvecs.close()
        rotated_bvecs = os.path.abspath('rotated_bvecs.txt')
    return rotated_bvecs

# Workflow -------------------------------------------------------------------
def create_prep(use_fieldmap):
        
    inputspec = pe.Node(interface=util.IdentityInterface(fields=['dwi',
                                                                 'bvec',
                                                                 'bval',
                                                                 'subject_id',
                                                                 'subjects_dir',
                                                                 'magnitude_image',
                                                                 'phase_image',
                                                                 'echo_spacing',
                                                                 'TE_diff',
                                                                 'sigma',
                                                                 'rotate']),
                        name='inputspec')
    
    gen_fa = pe.Workflow(name="gen_fa")

    eddy_correct = create_eddy_correct_pipeline()
    eddy_correct.inputs.inputnode.ref_num = 0
    gen_fa.connect(inputspec, 'dwi', eddy_correct, 'inputnode.in_file')


    getmask = create_getmask_flow()
    gen_fa.connect(inputspec,'subject_id',getmask,'inputspec.subject_id')
    gen_fa.connect(inputspec,'subjects_dir',getmask,'inputspec.subjects_dir')
    getmask.inputs.inputspec.contrast_type = 't2'

    if use_fieldmap:
        fieldmap = pe.Node(interface=fsl.utils.EPIDeWarp(), name='fieldmap_unwarp')
        dewarper = pe.MapNode(interface=fsl.FUGUE(),iterfield=['in_file'],name='dewarper')
        gen_fa.connect(inputspec,'TE_diff',
            fieldmap, 'tediff')
        gen_fa.connect(inputspec,'echo_spacing',
            fieldmap,'esp')
        gen_fa.connect(inputspec,'sigma',
            fieldmap, 'sigma')
        gen_fa.connect(eddy_correct, 'outputnode.eddy_corrected',
            dewarper, 'in_file')
        gen_fa.connect(fieldmap, 'exf_mask',
            dewarper, 'mask_file')
        gen_fa.connect(fieldmap, 'vsm_file',
            dewarper, 'shift_in_file')
        gen_fa.connect(eddy_correct, 'pick_ref.out',
            fieldmap, 'exf_file')
        gen_fa.connect(inputspec, 'phase_file',
            fieldmap, 'dph_file')
        gen_fa.connect(inputspec, 'magnitude_file',
            fieldmap, 'mag_file')
        gen_fa.connect(fieldmap, 'exfdw',
            getmask, 'inputspec.source_file')

    else:
        gen_fa.connect(eddy_correct,'pick_ref.out',
            getmask,'inputspec.source_file')


    dtifit = pe.Node(interface=fsl.DTIFit(), name='dtifit')
    gen_fa.connect(eddy_correct, 'outputnode.eddy_corrected', dtifit, 'dwi')


    gen_fa.connect(inputspec,'subject_id',dtifit,'base_name')

    gen_fa.connect(getmask,('outputspec.mask_file',pickfirst), dtifit, 'mask')

    rotate = pe.Node(util.Function(input_names=['bvecs','motion_vecs','rotate'],
                                      output_names=['rotated_bvecs'],
                                      function=rotate_bvecs),
        name='rotate_bvecs')

    gen_fa.connect(inputspec,'bvec', rotate, 'bvecs')
    gen_fa.connect(eddy_correct,'coregistration.out_matrix_file',rotate,'motion_vecs')
    gen_fa.connect(inputspec,'rotate', rotate, 'rotate')
    gen_fa.connect(rotate,'rotated_bvecs', dtifit, 'bvecs')

    gen_fa.connect(inputspec, 'bval', dtifit, 'bvals')

    outputnode = pe.Node(interface=util.IdentityInterface(fields=['FA',
                                                                  'MD',
                                                                  'reg_file']),
        name='outputspec')

    gen_fa.connect(getmask,'outputspec.reg_file',
        outputnode, 'reg_file')
    gen_fa.connect(dtifit, 'FA', outputnode, 'FA')
    gen_fa.connect(dtifit, 'MD', outputnode, 'MD')
    return gen_fa


def get_datasource(c):
    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
        outfields=['dwi', 'bvec',
                   'bval']),
        name='datasource')
    # create a node to obtain the functional images
    datasource.inputs.base_directory = c.base_dir
    datasource.inputs.template ='*'
    datasource.inputs.field_template = dict(dwi=c.dwi_template,
                                            bvec=c.bvec_template,
                                            bval = c.bval_template)
    datasource.inputs.template_args = dict(dwi=[['subject_id']],
                                           bvec=[['subject_id']],
                                           bval=[['subject_id']])
    return datasource


def combine_prep(c):
    
    modelflow = pe.Workflow(name='preproc')
    
    datasource = get_datasource(c)

    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),name='subject_names')

    if c.test_mode:
        infosource.iterables = ('subject_id',[c.subjects[0]])
    else:
        infosource.iterables = ('subject_id',c.subjects)

    modelflow.connect(infosource,'subject_id', datasource, 'subject_id')

    prep = create_prep(c.use_fieldmap)
    prep.inputs.inputspec.subjects_dir = c.surf_dir

    modelflow.connect(infosource,'subject_id', prep, 'inputspec.subject_id')
    modelflow.connect(datasource,   'dwi',              prep,   'inputspec.dwi')
    modelflow.connect(datasource,   'bvec',             prep,   'inputspec.bvec')
    modelflow.connect(datasource,   'bval',             prep,   'inputspec.bval')

    prep.inputs.inputspec.rotate = c.do_rotate_bvecs

    sinker = pe.Node(nio.DataSink(),name='sinker')
    sinker.inputs.base_directory = c.sink_dir

    modelflow.connect(infosource,'subject_id', sinker, 'container')
    modelflow.connect(prep,'outputspec.reg_file',sinker,'preproc.bbreg')
    modelflow.connect(prep, 'outputspec.FA', sinker, 'preproc.FA')
    modelflow.connect(prep,'outputspec.MD',sinker,'preproc.MD')

    return modelflow

def main(config_file):
    c = load_config(config_file, create_config)
    workflow = combine_prep(c)
    workflow.base_dir = c.working_dir
    if c.test_mode:
        workflow.write_graph()
    if c.run_using_plugin:
        workflow.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        workflow.run()
    return 0

class config(HasTraits):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc='Workflow description')
    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    base_dir = Directory(mandatory=True, desc='Base directory of data. (Should be subject-independent)')
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")
    field_dir = Directory(desc="Base directory of field-map data (Should be subject-independent) \
                                                 Set this value to None if you don't want fieldmap distortion correction")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")
    json_sink = Directory(mandatory=False, desc= "Location to store json_files")
    surf_dir = Directory(mandatory=True, desc= "Freesurfer subjects directory")

    # Execution

    run_using_plugin = Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.Enum("PBS", "PBSGraph","MultiProc", "SGE", "Condor",
        usedefault=True,
        desc="plugin to use, if run_using_plugin=True")
    plugin_args = traits.Dict({"qsub_args": "-q many"},
        usedefault=True, desc='Plugin arguments.')
    test_mode = Bool(False, mandatory=False, usedefault=True,
        desc='Affects whether where and if the workflow keeps its \
                            intermediary files. True to keep intermediary files. ')
    # Subjects

    subjects= traits.List(traits.Str, mandatory=True, usedefault=True,
        desc="Subject id's. Note: These MUST match the subject id's in the \
                                Freesurfer directory. For simplicity, the subject id's should \
                                also match with the location of individual functional files.")
    dwi_template = traits.String('%s/functional.nii.gz')
    bval_template = traits.String('%s/bval')
    bvec_template = traits.String('%s/fbvec')
    run_datagrabber_without_submitting = traits.Bool(desc="Run the datagrabber without \
    submitting to the cluster")
    timepoints_to_remove = traits.Int(0,usedefault=True)

    # Fieldmap

    use_fieldmap = Bool(False, mandatory=False, usedefault=True,
        desc='True to include fieldmap distortion correction. Note: field_dir \
                                     must be specified')
    magnitude_template = traits.String('%s/magnitude.nii.gz')
    phase_template = traits.String('%s/phase.nii.gz')
    TE_diff = traits.Float(desc='difference in B0 field map TEs')
    sigma = traits.Int(2, desc='2D spatial gaussing smoothing stdev (default = 2mm)')
    echospacing = traits.Float(desc="EPI echo spacing")

    # Bvecs
    do_rotate_bvecs = traits.Bool(True, usedefault=True)

    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()

    # Buttons
    check_func_datagrabber = Button("Check")
    check_field_datagrabber = Button("Check")

    def _check_func_datagrabber_fired(self):
        subs = self.subjects

        for s in subs:
            if not os.path.exists(os.path.join(self.base_dir,self.dwi_template % s)):
                print "ERROR", os.path.join(self.base_dir,self.dwi_template % s), "does NOT exist!"
                break
            else:
                print os.path.join(self.base_dir,self.dwi_template % s), "exists!"

    def _check_field_datagrabber_fired(self):
        subs = self.subjects

        for s in subs:
            if not os.path.exists(os.path.join(self.field_dir,self.magnitude_template % s)):
                print "ERROR:", os.path.join(self.field_dir,self.magnitude_template % s), "does NOT exist!"
                break
            else:
                print os.path.join(self.base_dir,self.magnitude_template % s), "exists!"
            if not os.path.exists(os.path.join(self.field_dir,self.phase_template % s)):
                print "ERROR:", os.path.join(self.field_dir,self.phase_template % s), "does NOT exist!"
                break
            else:
                print os.path.join(self.base_dir,self.phase_template % s), "exists!"


def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    return c

def create_view():
    from traitsui.api import View, Item, Group, CSVListEditor, TupleEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='uuid', style='readonly'),
        Item(name='desc', style='readonly'),
        label='Description', show_border=True),
        Group(Item(name='working_dir'),
            Item(name='sink_dir'),
            Item(name='crash_dir'),
            Item(name='json_sink'),
            Item(name='surf_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'),
            label='Execution Options', show_border=True),
        Group(Item(name='subjects', editor=CSVListEditor()),
            Item(name='base_dir'),
            Item(name='dwi_template'),
            Item(name='bval_template'),
            Item(name='bvec_template'),
            Item(name='check_func_datagrabber'),
            Item(name='run_datagrabber_without_submitting'),
            Item(name='timepoints_to_remove'),
            label='Subjects', show_border=True),
        Group(Item(name='use_fieldmap'),
            Item(name='field_dir', enabled_when="use_fieldmap"),
            Item(name='magnitude_template',
                enabled_when="use_fieldmap"),
            Item(name='phase_template', enabled_when="use_fieldmap"),
            Item(name='check_field_datagrabber',
                enabled_when="use_fieldmap"),
            Item(name='echospacing',enabled_when="use_fieldmap"),
            Item(name='TE_diff',enabled_when="use_fieldmap"),
            Item(name='sigma',enabled_when="use_fieldmap"),
            label='Fieldmap',show_border=True),
        Group(Item('do_rotate_bvecs'),
            label='Diffusion_Options',show_border=True),
        Group(Item(name='use_advanced_options'),
            Item(name='advanced_script',enabled_when='use_advanced_options'),
            label='Advanced',show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.workflow_main_function = main
mwf.config_ui = create_config
mwf.config_view = create_view

register_workflow(mwf)