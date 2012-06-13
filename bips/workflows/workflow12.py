from .scripts.u0a14c5b5899911e1bca80023dfa375f2.modified_nipype_workflows import create_eddy_correct_pipeline, get_flirt_motion_parameters
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
from .scripts.u0a14c5b5899911e1bca80023dfa375f2.QA_utils import plot_motion
import bips.utils.reportsink.io as io

"""
Part 1: MetaWorkflow
"""

mwf = MetaWorkflow()
mwf.help = """
Diffusion pre-processing workflow
================================

"""
mwf.uuid = 'd9bee4cc987611e19b9b001e4fb1404c'
mwf.tags = ['diffusion','dti','pre-processing']
mwf.script_dir = 'u0a14c5b5899911e1bca80023dfa375f2'


"""
Part 2: Config
"""

class config(HasTraits):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc='Workflow description')
    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    base_dir = Directory(os.path.abspath('.'),mandatory=True, desc='Base directory of data. (Should be subject-independent)')
    sink_dir = Directory(os.path.abspath('.'),mandatory=True, desc="Location where the BIP will store the results")
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

mwf.config_ui = create_config

"""
Part 3: View
"""

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

mwf.config_view = create_view

"""
Part 4: Construct Workflow
"""


def tolist(x):
    x = [x]
    return x

def rotate_bvecs(bvecs, motion_vecs, rotate):
    if not rotate:
        rotated_bvecs = bvecs
    else:
        import numpy as np
        import os
        from nipype.interfaces.fsl.utils import AvScale
        bvecs = np.genfromtxt(bvecs)
        rotated_bvecs = open(os.path.abspath('rotated_bvecs.txt'),'w')

        for i,r in enumerate(motion_vecs):
            avscale = AvScale()
            avscale.inputs.mat_file = r
            res = avscale.run()
            mat = np.asarray(res.outputs.rotation_translation_matrix)
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
                                                                 'rotate',
                                                                 'report_directory']),
                        name='inputspec')
    
    gen_fa = pe.Workflow(name="gen_fa")

    eddy_correct = create_eddy_correct_pipeline()
    gen_fa.connect(inputspec, 'dwi', eddy_correct, 'inputnode.in_file')
    gen_fa.connect(inputspec,'bval', eddy_correct, 'inputnode.bvals')

    getmask = create_getmask_flow()
    gen_fa.connect(inputspec,'subject_id',getmask,'inputspec.subject_id')
    gen_fa.connect(inputspec,'subjects_dir',getmask,'inputspec.subjects_dir')
    getmask.inputs.inputspec.contrast_type = 't2'

    outputnode = pe.Node(interface=util.IdentityInterface(fields=['FA',
                                                                  'MD',
                                                                  'reg_file',
                                                                  'FM_unwarped_mean',
                                                                  'FM_unwarped_epi',
                                                                  'eddy_corrected',
                                                                  'mask']),
        name='outputspec')
    dtifit = pe.MapNode(interface=fsl.DTIFit(), name='dtifit', iterfield=['dwi',"mask","bvecs","bvals"])

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
        gen_fa.connect(eddy_correct, 'outputnode.mean_image',
            fieldmap, 'exf_file')
        gen_fa.connect(inputspec, 'phase_image',
            fieldmap, 'dph_file')
        gen_fa.connect(inputspec, 'magnitude_image',
            fieldmap, 'mag_file')
        gen_fa.connect(fieldmap, 'exfdw',
            getmask, 'inputspec.source_file')
        gen_fa.connect(fieldmap, 'exfdw',
            outputnode, 'FM_unwarped_mean')
        gen_fa.connect(dewarper,'unwarped_file',dtifit,'dwi')
        gen_fa.connect(dewarper, 'unwarped_file',
            outputnode, 'FM_unwarped_epi')
        #gen_fa.connect(fieldmap,'exf_mask',dtifit,'mask')

    else:
        gen_fa.connect(eddy_correct,'outputnode.mean_image',
            getmask,'inputspec.source_file')
        gen_fa.connect(eddy_correct, 'outputnode.eddy_corrected', dtifit, 'dwi')
        gen_fa.connect(eddy_correct, 'outputnode.eddy_corrected', outputspec, 'eddy_corrected')

    gen_fa.connect(getmask,('outputspec.mask_file',pickfirst), dtifit, 'mask')
    gen_fa.connect(getmask,('outputspec.mask_file',pickfirst), outputnode, 'mask')

    gen_fa.connect(inputspec,'subject_id',dtifit,'base_name')

    rotate = pe.MapNode(util.Function(input_names=['bvecs','motion_vecs','rotate'],
                                      output_names=['rotated_bvecs'],
                                      function=rotate_bvecs),
        name='rotate_bvecs', iterfield=["bvecs", "motion_vecs"])

    gen_fa.connect(inputspec,'bvec', rotate, 'bvecs')
    gen_fa.connect(eddy_correct,'outputnode.coreg_mat_files',rotate,'motion_vecs')
    gen_fa.connect(inputspec,'rotate', rotate, 'rotate')
    gen_fa.connect(rotate,'rotated_bvecs', dtifit, 'bvecs')

    gen_fa.connect(inputspec, 'bval', dtifit, 'bvals')

    getmotion = pe.MapNode(util.Function(input_names=["flirt_out_mats"],
        output_names=["motion_params"],
        function=get_flirt_motion_parameters),
        name="get_motion_parameters",iterfield="flirt_out_mats")

    plotmotion = pe.MapNode(util.Function(input_names=["motion_parameters"],
                                          output_names=["fname_t","fname_r"],
                                          function=plot_motion),
        name="plot_motion",iterfield="motion_parameters")

    gen_fa.connect(eddy_correct,'outputnode.coreg_mat_files',getmotion,'flirt_out_mats')
    gen_fa.connect(getmotion,"motion_params", plotmotion, "motion_parameters")

    reportnode = pe.Node(io.ReportSink(orderfields=["Introduction",
                                                    "In_Files",
                                                    "Translations",
                                                    "Rotations"]),name="Diffusion_Preprocessing_Report")
    reportnode.inputs.Introduction = "Quality Assurance Report for Diffusion preprocessing."
    reportnode.inputs.report_name = "Diffusion_Preprocessing_Report"

    gen_fa.connect(getmask,'outputspec.reg_file',
        outputnode, 'reg_file')

    gen_fa.connect(plotmotion, "fname_t", reportnode, "Translations")
    gen_fa.connect(plotmotion, "fname_r", reportnode, "Rotations")
    gen_fa.connect(inputspec, "dwi", reportnode, "In_Files")
    gen_fa.connect(inputspec,"subject_id", reportnode, "container")
    gen_fa.connect(inputspec,"report_directory", reportnode,"base_directory")

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
    if c.use_fieldmap:
        datasource_fieldmap = pe.Node(nio.DataGrabber(infields=['subject_id'],
            outfields=['mag',
                       'phase']),
            name = "fieldmap_datagrabber")
        datasource_fieldmap.inputs.base_directory = c.field_dir
        datasource_fieldmap.inputs.sort_filelist = True
        datasource_fieldmap.inputs.template ='*'
        datasource_fieldmap.inputs.field_template = dict(mag=c.magnitude_template,
            phase=c.phase_template)
        datasource_fieldmap.inputs.template_args = dict(mag=[['subject_id']],
            phase=[['subject_id']])
        prep.inputs.inputspec.echo_spacing = c.echospacing
        prep.inputs.inputspec.TE_diff = c.TE_diff
        prep.inputs.inputspec.sigma = c.sigma
        modelflow.connect(infosource, 'subject_id',
            datasource_fieldmap, 'subject_id')
        modelflow.connect(datasource_fieldmap,'mag',
            prep,'inputspec.magnitude_image')
        modelflow.connect(datasource_fieldmap,'phase',
            prep,'inputspec.phase_image')

    modelflow.connect(infosource,'subject_id', prep, 'inputspec.subject_id')
    modelflow.connect(datasource,   'dwi',              prep,   'inputspec.dwi')
    modelflow.connect(datasource,   'bvec',             prep,   'inputspec.bvec')
    modelflow.connect(datasource,   'bval',             prep,   'inputspec.bval')

    prep.inputs.inputspec.rotate = c.do_rotate_bvecs

    sinker = pe.Node(nio.DataSink(),name='sinker')
    sinker.inputs.base_directory = c.sink_dir

    def getsubs(subject_id):
        subs = [('_subject_id_%s'%subject_id,''),
            ('_threshold20/aparc+aseg_thresh_warped_dil_thresh',
             '%s_brainmask' % subject_id),
            ('_register0','')]
        for i in range(0,20):
            subs.append(('_dewarper%d/vol0000_flirt_merged_unwarped.nii'%i,'dwi%d.nii'%i))
        return subs

    def get_regexpsubs(subject_id):
        subs=[]
        for i in range(0,20):
            subs.append(('_dewarper%d/vol0000*.nii'%i,'dwi%d.nii'%i))
        print subs
        return subs

    modelflow.connect(infosource,'subject_id', sinker, 'container')
    modelflow.connect(prep,'outputspec.reg_file',sinker,'preproc.bbreg')
    modelflow.connect(prep, 'outputspec.FA', sinker, 'preproc.FA')
    modelflow.connect(prep,'outputspec.MD',sinker,'preproc.MD')
    if c.use_fieldmap:
        modelflow.connect(prep, 'outputspec.FM_unwarped_mean',
            sinker, 'preproc.fieldmap.@unwarped_mean')
        modelflow.connect(prep, 'outputspec.FM_unwarped_epi',
            sinker, 'preproc.fieldmap.@unwarped_epi')
        modelflow.connect(prep, 'outputspec.FM_unwarped_epi',
            sinker, 'preproc.outputs.dwi')
    else:
        modelflow.connect(prep, 'outputspec.eddy_corrected', sinker, 'preproc.outputs.dwi')
    modelflow.connect(prep, 'outputspec.mask', sinker, 'preproc.outputs.mask')
    modelflow.connect(infosource,('subject_id',getsubs),sinker,'substitutions')
    modelflow.connect(infosource,('subject_id',get_regexpsubs),sinker,'regexp_substitutions')
    return modelflow


mwf.workflow_function = combine_prep

"""
Part 5: Main
"""

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

mwf.workflow_main_function = main

"""
Part 6: Register
"""

register_workflow(mwf)