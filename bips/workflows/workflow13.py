import nipype.algorithms.rapidart as ra
import nipype.interfaces.spm as spm
import nipype.interfaces.utility as niu
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio
from .scripts.u0a14c5b5899911e1bca80023dfa375f2.modular_nodes import mod_realign
from .scripts.u0a14c5b5899911e1bca80023dfa375f2.utils import art_mean_workflow, pickfirst
logger = pe.logger
import os
from nipype.workflows.smri.freesurfer.utils import create_getmask_flow

from .base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits

mwf = MetaWorkflow()
mwf.help = """
SPM preprocessing workflow
===========================

"""
mwf.uuid = '731520e29b6911e1bd2d001e4fb1404c'
mwf.tags = ['task','fMRI','preprocessing','SPM','freesurfer']
mwf.script_dir = 'u0a14c5b5899911e1bca80023dfa375f2'

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
    func_template = traits.String('%s/functional.nii.gz')
    run_datagrabber_without_submitting = traits.Bool(desc="Run the datagrabber without \
    submitting to the cluster")
    timepoints_to_remove = traits.Int(0,usedefault=True)

    do_slicetiming = Bool(True, usedefault=True, desc="Perform slice timing correction")
    SliceOrder = traits.List(traits.Int)
    TR = traits.Float(mandatory=True, desc = "TR of functional")
    motion_correct_node = traits.Enum('nipy','fsl','spm','afni',
        desc="motion correction algorithm to use",
        usedefault=True,)

    csf_prob = traits.File(desc='CSF_prob_map') 
    grey_prob = traits.File(desc='grey_prob_map')
    white_prob = traits.File(desc='white_prob_map')
    # Artifact Detection

    norm_thresh = traits.Float(1, min=0, usedefault=True, desc="norm thresh for art")
    z_thresh = traits.Float(3, min=0, usedefault=True, desc="z thresh for art")

    # Smoothing
    fwhm = traits.Float(6.0,usedefault=True)

    check_func_datagrabber = Button("Check")

    def _check_func_datagrabber_fired(self):
        subs = self.subjects

        for s in subs:
            if not os.path.exists(os.path.join(self.base_dir,self.func_template % s)):
                print "ERROR", os.path.join(self.base_dir,self.func_template % s), "does NOT exist!"
                break
            else:
                print os.path.join(self.base_dir,self.func_template % s), "exists!"

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    return c

def get_dataflow(c):
    dataflow = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
        outfields=['func']),
        name = "preproc_dataflow",
        run_without_submitting=c.run_datagrabber_without_submitting)
    dataflow.inputs.base_directory = c.base_dir
    dataflow.inputs.template ='*'
    dataflow.inputs.sort_filelist = True
    dataflow.inputs.field_template = dict(func=c.func_template)
    dataflow.inputs.template_args = dict(func=[['subject_id']])
    return dataflow

def do_symlink(in_file):
    import os
    import shutil

    if not isinstance(in_file, list):
        out_link=os.path.abspath(os.path.split(in_file)[1])
        #os.symlink(in_file,out_link)
        shutil.copy2(in_file,out_link)
    else:
        out_links = []
        for f in in_file:
            out_link=os.path.abspath(os.path.split(f)[1])
            #os.symlink(f,out_link)
            shutil.copy2(f,out_link)
            out_links.append(out_link)
        out_link = out_links	
    return out_link

def create_spm_preproc(name='preproc'):
    """Create an spm preprocessing workflow with freesurfer registration and
artifact detection.

The workflow realigns and smooths and registers the functional images with
the subject's freesurfer space.

Example
-------

>>> preproc = create_spm_preproc()
>>> preproc.base_dir = '.'
>>> preproc.inputs.inputspec.fwhm = 6
>>> preproc.inputs.inputspec.subject_id = 's1'
>>> preproc.inputs.inputspec.subjects_dir = '.'
>>> preproc.inputs.inputspec.functionals = ['f3.nii', 'f5.nii']
>>> preproc.inputs.inputspec.norm_threshold = 1
>>> preproc.inputs.inputspec.zintensity_threshold = 3

Inputs::

inputspec.functionals : functional runs use 4d nifti
inputspec.subject_id : freesurfer subject id
inputspec.subjects_dir : freesurfer subjects dir
inputspec.fwhm : smoothing fwhm
inputspec.norm_threshold : norm threshold for outliers
inputspec.zintensity_threshold : intensity threshold in z-score

Outputs::

outputspec.realignment_parameters : realignment parameter files
outputspec.smoothed_files : smoothed functional files
outputspec.outlier_files : list of outliers
outputspec.outlier_stats : statistics of outliers
outputspec.outlier_plots : images of outliers
outputspec.mask_file : binary mask file in reference image space
outputspec.reg_file : registration file that maps reference image to
freesurfer space
outputspec.reg_cost : cost of registration (useful for detecting misalignment)
"""

    """
Initialize the workflow
"""

    workflow = pe.Workflow(name=name)

    """
Define the inputs to this workflow
"""

    inputnode = pe.Node(niu.IdentityInterface(fields=['functionals',
                                                      'subject_id',
                                                      'subjects_dir',
                                                      'fwhm',
                                                      'norm_threshold',
                                                      'zintensity_threshold',
                                                      'tr',
                                                      'do_slicetime',
                                                      'sliceorder',
                                                      'node',
                                                      'csf_prob','wm_prob','gm_prob']),
        name='inputspec')

    """
Setup the processing nodes and create the mask generation and coregistration
workflow
"""

    poplist = lambda x: x.pop()
    #realign = pe.Node(spm.Realign(), name='realign')
    
    sym_func = pe.Node(niu.Function(input_names=['in_file'],output_names=['out_link'],function=do_symlink),name='func_symlink')

    realign = pe.Node(niu.Function(input_names=['node','in_file','tr','do_slicetime','sliceorder'],
        output_names=['out_file','par_file'],
        function=mod_realign),
        name="mod_realign")

    mean = art_mean_workflow()
    workflow.connect(realign,'out_file', mean, 'inputspec.realigned_files')
    workflow.connect(realign,'par_file', mean, 'inputspec.realignment_parameters')
    mean.inputs.inputspec.parameter_source='FSL' # Modular realign puts it in FSL format for consistency

    #workflow.connect(inputnode, 'functionals', realign, 'in_file')
    workflow.connect(inputnode,'functionals', sym_func, 'in_file')
    workflow.connect(sym_func,'out_link',realign,'in_file')

    workflow.connect(inputnode, 'tr',
        realign, 'tr')
    workflow.connect(inputnode, 'do_slicetime',
        realign, 'do_slicetime')
    workflow.connect(inputnode, 'sliceorder',
        realign, 'sliceorder')
    workflow.connect(inputnode, 'node',
        realign, 'node')

    maskflow = create_getmask_flow()
    workflow.connect([(inputnode, maskflow, [('subject_id','inputspec.subject_id'),
        ('subjects_dir', 'inputspec.subjects_dir')])])
    maskflow.inputs.inputspec.contrast_type = 't2'
    workflow.connect(mean, 'outputspec.mean_image', maskflow, 'inputspec.source_file')
    smooth = pe.Node(spm.Smooth(), name='smooth')

    normalize = pe.Node(spm.Normalize(jobtype='write'),name='normalize')
    normalize_struct = normalize.clone('normalize_struct')
    segment = pe.Node(spm.Segment(csf_output_type=[True,True,False],
                                  gm_output_type=[True,True,False],
                                  wm_output_type=[True,True,False]),name='segment')

    mergefunc = lambda in1,in2,in3:[in1,in2,in3]

    # merge = pe.Node(niu.Merge(),name='merge')
    merge = pe.Node(niu.Function(input_names=['in1','in2','in3'],output_names=['out'],function=mergefunc),name='merge')
    workflow.connect(inputnode,'csf_prob',merge,'in3')
    workflow.connect(inputnode,'wm_prob',merge,'in2')
    workflow.connect(inputnode,'gm_prob',merge,'in1')

    #workflow.connect(merge,'out', segment,'tissue_prob_maps')

    sym_prob = sym_func.clone('sym_prob')
    workflow.connect(merge,'out',sym_prob,'in_file')
    workflow.connect(sym_prob,'out_link',segment,'tissue_prob_maps')

    workflow.connect(maskflow,('outputspec.mask_file',pickfirst),segment,'mask_image')
    workflow.connect(inputnode, 'fwhm', smooth, 'fwhm')

    #sym_brain = sym_func.clone('sym_brain')
    #workflow.connect(realign, 'mean_image', normalize, 'source')
    #workflow.connect(maskflow,'fssource.brain',segment,'data')
    fssource = maskflow.get_node('fssource')
    import nipype.interfaces.freesurfer as fs
    convert_brain = pe.Node(interface=fs.ApplyVolTransform(inverse=True),name='convert')
    workflow.connect(fssource,'brain',convert_brain,'target_file')
    workflow.connect(maskflow,('outputspec.reg_file',pickfirst),convert_brain,'reg_file')
    workflow.connect(mean,'outputspec.mean_image',convert_brain,'source_file')
    convert2nii = pe.Node(fs.MRIConvert(in_type='mgz',out_type='nii'),name='convert2nii')
    workflow.connect(convert_brain,'transformed_file',convert2nii,'in_file')
    workflow.connect(convert2nii,'out_file',segment,'data')    

    workflow.connect(segment, 'transformation_mat', normalize, 'parameter_file')
    workflow.connect(segment, 'transformation_mat', normalize_struct, 'parameter_file')
    workflow.connect(convert2nii,'out_file',normalize_struct, 'apply_to_files')
    workflow.connect(realign,'out_file',normalize, 'apply_to_files')
    #normalize.inputs.template='/software/spm8/templates/EPI.nii'
    workflow.connect(normalize,'normalized_files',smooth,'in_files')
    #workflow.connect(realign, 'realigned_files', smooth, 'in_files')

    artdetect = pe.Node(ra.ArtifactDetect(mask_type='file',
        parameter_source='FSL',
        use_differences=[True,False],
        use_norm=True,
        save_plot=True),
        name='artdetect')
    workflow.connect([(inputnode, artdetect,[('norm_threshold', 'norm_threshold'),
        ('zintensity_threshold',
         'zintensity_threshold')])])
    workflow.connect([(realign, artdetect, [('out_file', 'realigned_files'),
        ('par_file',
         'realignment_parameters')])])
    workflow.connect(maskflow, ('outputspec.mask_file', poplist), artdetect, 'mask_file')

    """
Define the outputs of the workflow and connect the nodes to the outputnode
"""

    outputnode = pe.Node(niu.IdentityInterface(fields=["realignment_parameters",
                                                       "smoothed_files",
                                                       "mask_file",
                                                       "mean_image",
                                                       "reg_file",
                                                       "reg_cost",
                                                       'outlier_files',
                                                       'outlier_stats',
                                                       'outlier_plots',
                                                       'norm_components',
                                                       'mod_csf',
                                                       'unmod_csf',
                                                       'mod_wm',
                                                       'unmod_wm',
                                                       'mod_gm',
                                                       'unmod_gm',
                                                       'mean',
                                                       'normalized_struct',
                                                       'struct_in_functional_space',
                                                       'normalization_parameters',
                                                       'reverse_normalize_parameters'
    ]),
        name="outputspec")
    workflow.connect([
        (maskflow, outputnode, [("outputspec.reg_file", "reg_file")]),
        (maskflow, outputnode, [("outputspec.reg_cost", "reg_cost")]),
        (maskflow, outputnode, [(("outputspec.mask_file", poplist), "mask_file")]),
        (realign, outputnode, [('par_file', 'realignment_parameters')]),
        (smooth, outputnode, [('smoothed_files', 'smoothed_files')]),
        (artdetect, outputnode,[('outlier_files', 'outlier_files'),
            ('statistic_files','outlier_stats'),
            ('plot_files','outlier_plots'),
            ('norm_files','norm_components')])
    ])
    workflow.connect(segment,'modulated_csf_image',outputnode,'mod_csf')
    workflow.connect(segment,'modulated_wm_image',outputnode,'mod_wm')
    workflow.connect(segment,'modulated_gm_image',outputnode,'mod_gm')
    workflow.connect(segment,'normalized_csf_image',outputnode,'unmod_csf')
    workflow.connect(segment,'normalized_wm_image',outputnode,'unmod_wm')
    workflow.connect(segment,'normalized_gm_image',outputnode,'unmod_gm')
    workflow.connect(mean,'outputspec.mean_image',outputnode, 'mean')
    workflow.connect(normalize_struct, 'normalized_files', outputnode, 'normalized_struct')
    workflow.connect(segment,'transformation_mat', outputnode,'normalization_parameters')
    workflow.connect(segment,'inverse_transformation_mat',outputnode,'reverse_normalize_parameters')
    workflow.connect(convert2nii,'out_file',outputnode,'struct_in_functional_space')
    return workflow

def main(config_file):
    c = load_config(config_file,config)
    workflow = create_spm_preproc('spm_preproc')
    datagrabber = get_dataflow(c)
    inputspec = workflow.get_node('inputspec')
    workflow.connect(datagrabber,'func',inputspec,'functionals')
    workflow.inputs.inputspec.fwhm = c.fwhm
    workflow.inputs.inputspec.subjects_dir = c.surf_dir
    workflow.inputs.inputspec.norm_threshold = c.norm_thresh
    workflow.inputs.inputspec.zintensity_threshold = c.z_thresh
    workflow.inputs.inputspec.node = c.motion_correct_node
    workflow.inputs.inputspec.tr = c.TR
    workflow.inputs.inputspec.do_slicetime = c.do_slicetiming
    workflow.inputs.inputspec.sliceorder = c.SliceOrder
    workflow.inputs.inputspec.csf_prob = c.csf_prob
    workflow.inputs.inputspec.gm_prob = c.grey_prob
    workflow.inputs.inputspec.wm_prob = c.white_prob
    workflow.base_dir = c.working_dir
    workflow.config = {'execution': {'crashdump_dir': c.crash_dir}}
    infosource = pe.Node(niu.IdentityInterface(fields=['subject_id']),
        name='subject_names')
    if not c.test_mode:
        infosource.iterables = ('subject_id', c.subjects)
    else:
        infosource.iterables = ('subject_id', c.subjects[:1])
        workflow.write_graph()

    workflow.connect(infosource,'subject_id',inputspec,'subject_id')
    workflow.connect(infosource,'subject_id',datagrabber,'subject_id')
    sub = lambda x: [('_subject_id_%s'%x,'')]

    sinker = pe.Node(nio.DataSink(),name='sinker')
    workflow.connect(infosource,'subject_id',sinker,'container')
    workflow.connect(infosource,('subject_id',sub),sinker,'substitutions')
    sinker.inputs.base_directory = c.sink_dir
    outputspec = workflow.get_node('outputspec')
    workflow.connect(outputspec,'realignment_parameters',sinker,'spm_preproc.realignment_parameters')
    workflow.connect(outputspec,'smoothed_files',sinker,'spm_preproc.smoothed_outputs')
    workflow.connect(outputspec,'outlier_files',sinker,'spm_preproc.art.@outlier_files')
    workflow.connect(outputspec,'outlier_stats',sinker,'spm_preproc.art.@outlier_stats')
    workflow.connect(outputspec,'outlier_plots',sinker,'spm_preproc.art.@outlier_plots')
    workflow.connect(outputspec,'norm_components',sinker,'spm_preproc.art.@norm')
    workflow.connect(outputspec,'reg_file',sinker,'spm_preproc.bbreg.@reg_file')
    workflow.connect(outputspec,'reg_cost',sinker,'spm_preproc.bbreg.@reg_cost')
    workflow.connect(outputspec,'mask_file',sinker,'spm_preproc.mask.@mask_file')
    workflow.connect(outputspec,'mod_csf',sinker,'spm_preproc.segment.mod.@csf')
    workflow.connect(outputspec,'mod_wm',sinker,'spm_preproc.segment.mod.@wm')
    workflow.connect(outputspec,'mod_gm',sinker,'spm_preproc.segment.mod.@gm')
    workflow.connect(outputspec,'unmod_csf',sinker,'spm_preproc.segment.unmod.@csf')
    workflow.connect(outputspec,'unmod_wm',sinker,'spm_preproc.segment.unmod.@wm')
    workflow.connect(outputspec,'unmod_gm',sinker,'spm_preproc.segment.unmod.@gm')
    workflow.connect(outputspec,'mean',sinker,'spm_preproc.mean')
    workflow.connect(outputspec,'normalized_struct', sinker, 'spm_preproc.normalized_struct')
    workflow.connect(outputspec,'normalization_parameters',sinker,'spm_preproc.normalization_parameters.@forward')
    workflow.connect(outputspec,'reverse_normalize_parameters',sinker,'spm_preproc.normalization_parameters.@reverse')
    workflow.connect(outputspec,'struct_in_functional_space',sinker,'spm_preproc.struct_in_func_space')

    if c.run_using_plugin:
        workflow.run(plugin=c.plugin,plugin_args=c.plugin_args)
    else:
        workflow.run()

    return None

def create_view():
    from traitsui.api import View, Item, Group, CSVListEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='uuid', style='readonly'),
        Item(name='desc', style='readonly'),
        label='Description', show_border=True),
        Group(Item(name='working_dir'),
            Item(name='sink_dir'),
            Item(name='crash_dir'),
            Item(name='surf_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'),
            label='Execution Options', show_border=True),
        Group(Item(name='subjects', editor=CSVListEditor()),
            Item(name='base_dir'),
            Item(name='func_template'),
            Item(name='check_func_datagrabber'),
            Item(name='run_datagrabber_without_submitting'),
            Item(name='timepoints_to_remove'),
            label='Subjects', show_border=True),
        Group(Item(name="motion_correct_node"),
            Item(name='TR'),
            Item(name='do_slicetiming'),
            Item(name='SliceOrder', editor=CSVListEditor()),
            label='Motion Correction', show_border=True),
        Group(Item('csf_prob'),
            Item('grey_prob'),
            Item('white_prob'),
            label='normalize', 
            show_border=True),
        Group(Item(name='norm_thresh'),
            Item(name='z_thresh'),
            label='Artifact Detection',show_border=True),
        Group(Item(name='fwhm'),
            label='Smoothing',show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.workflow_main_function = main
mwf.config_ui = create_config
mwf.config_view = create_view

register_workflow(mwf)
