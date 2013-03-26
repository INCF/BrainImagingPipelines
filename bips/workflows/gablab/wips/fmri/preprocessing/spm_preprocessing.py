from ...scripts.modular_nodes import mod_realign
from ...scripts.utils import art_mean_workflow, pickfirst
import os
from .....base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits

"""
Part 1: MetaWorkflow
"""

mwf = MetaWorkflow()
mwf.help = """
SPM preprocessing workflow
===========================

"""
mwf.uuid = '731520e29b6911e1bd2d001e4fb1404c'
mwf.tags = ['task','fMRI','preprocessing','SPM','freesurfer']
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
    order = traits.Enum('motion_slicetime','slicetime_motion',use_default=True)
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
    save_script_only = traits.Bool(False)
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

mwf.config_ui = create_config

"""
Part 3: View
"""

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
        Group(Item(name='run_using_plugin',enabled_when='not save_script_only'),Item('save_script_only'),
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
            Item(name='do_slicetiming'),Item('order'),
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

mwf.config_view = create_view

"""
Part 4: Construct Workflow
"""

def get_dataflow(c):

    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio
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

def create_spm_preproc(c, name='preproc'):
    """
"""

    from nipype.workflows.smri.freesurfer.utils import create_getmask_flow
    import nipype.algorithms.rapidart as ra
    import nipype.interfaces.spm as spm
    import nipype.interfaces.utility as niu
    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio
    import nipype.interfaces.freesurfer as fs


    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(fields=['functionals',
                                                      'subject_id',
                                                      'subjects_dir',
                                                      'fwhm',
                                                      'norm_threshold',
                                                      'zintensity_threshold',
                                                      'tr',
                                                      'do_slicetime',
                                                      'sliceorder',
                                                      'parameters',
                                                      'node',
                                                      'csf_prob','wm_prob','gm_prob']),
        name='inputspec')

    poplist = lambda x: x.pop()
    
    sym_func = pe.Node(niu.Function(input_names=['in_file'],output_names=['out_link'],function=do_symlink),name='func_symlink')

    # REALIGN

    realign = pe.Node(niu.Function(input_names=['node','in_file','tr','do_slicetime','sliceorder','parameters'],
        output_names=['out_file','par_file','parameter_source'],
        function=mod_realign),
        name="mod_realign")
    workflow.connect(inputnode,'parameters',realign,'parameters')
    workflow.connect(inputnode,'functionals', realign, 'in_file')
    workflow.connect(inputnode, 'tr', realign, 'tr')
    workflow.connect(inputnode, 'do_slicetime', realign, 'do_slicetime')
    workflow.connect(inputnode, 'sliceorder', realign, 'sliceorder')
    workflow.connect(inputnode, 'node', realign, 'node')

   # TAKE MEAN IMAGE

    mean = art_mean_workflow()
    workflow.connect(realign,'out_file', mean, 'inputspec.realigned_files')
    workflow.connect(realign,'par_file', mean, 'inputspec.realignment_parameters')
    workflow.connect(realign,'parameter_source', mean, 'inputspec.parameter_source')

    # CREATE BRAIN MASK

    maskflow = create_getmask_flow()
    workflow.connect([(inputnode, maskflow, [('subject_id','inputspec.subject_id'),
        ('subjects_dir', 'inputspec.subjects_dir')])])
    maskflow.inputs.inputspec.contrast_type = 't2'
    workflow.connect(mean, 'outputspec.mean_image', maskflow, 'inputspec.source_file')

    # SEGMENT

    segment = pe.Node(spm.Segment(csf_output_type=[True,True,False],
                                  gm_output_type=[True,True,False],
                                  wm_output_type=[True,True,False]),name='segment')
    mergefunc = lambda in1,in2,in3:[in1,in2,in3]

    merge = pe.Node(niu.Function(input_names=['in1','in2','in3'],output_names=['out'],function=mergefunc),name='merge')
    workflow.connect(inputnode,'csf_prob',merge,'in3')
    workflow.connect(inputnode,'wm_prob',merge,'in2')
    workflow.connect(inputnode,'gm_prob',merge,'in1')

    sym_prob = sym_func
    workflow.connect(merge,'out',sym_prob,'in_file')
    workflow.connect(sym_prob,'out_link',segment,'tissue_prob_maps')

    xform_mask = pe.Node(fs.ApplyVolTransform(fs_target=True),name='transform_mask')
    workflow.connect(maskflow,('outputspec.reg_file',pickfirst),xform_mask,'reg_file')
    workflow.connect(maskflow,('outputspec.mask_file',pickfirst),xform_mask,'source_file')
    workflow.connect(xform_mask,"transformed_file",segment,'mask_image')

    fssource = maskflow.get_node('fssource')
    convert2nii = pe.Node(fs.MRIConvert(in_type='mgz',out_type='nii'),name='convert2nii')
    workflow.connect(fssource,'brain',convert2nii,'in_file')
    workflow.connect(convert2nii,'out_file',segment,'data')    

    # NORMALIZE

    normalize = pe.MapNode(spm.Normalize(jobtype='write'),name='normalize',iterfield=['apply_to_files'])
    normalize_struct = normalize.clone('normalize_struct')
    normalize_mask = normalize.clone('normalize_mask')

    workflow.connect(segment, 'transformation_mat', normalize, 'parameter_file')
    workflow.connect(segment, 'transformation_mat', normalize_mask, 'parameter_file')
    workflow.connect(segment, 'transformation_mat', normalize_struct, 'parameter_file')
    workflow.connect(convert2nii,'out_file',normalize_struct, 'apply_to_files')
    workflow.connect(xform_mask,"transformed_file",normalize_mask,'apply_to_files')

    xform_image = pe.MapNode(fs.ApplyVolTransform(fs_target=True),name='xform_image',iterfield=['source_file'])
    workflow.connect(maskflow,('outputspec.reg_file',pickfirst),xform_image,'reg_file')
    workflow.connect(realign,'out_file',xform_image,"source_file")
    workflow.connect(xform_image,"transformed_file",normalize,"apply_to_files")


    #SMOOTH

    smooth = pe.Node(spm.Smooth(), name='smooth')

    workflow.connect(inputnode, 'fwhm', smooth, 'fwhm')
    workflow.connect(normalize,'normalized_files',smooth,'in_files')

    # ART

    artdetect = pe.Node(ra.ArtifactDetect(mask_type='file',
        use_differences=[True,False],
        use_norm=True,
        save_plot=True),
        name='artdetect')
    workflow.connect(realign,'parameter_source',artdetect,'parameter_source')
    workflow.connect([(inputnode, artdetect,[('norm_threshold', 'norm_threshold'),
        ('zintensity_threshold',
         'zintensity_threshold')])])
    workflow.connect([(realign, artdetect, [('out_file', 'realigned_files'),
        ('par_file',
         'realignment_parameters')])])
    workflow.connect(maskflow, ('outputspec.mask_file', poplist), artdetect, 'mask_file')


    # OUTPUTS

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
                                                       'normalization_parameters',
                                                       'reverse_normalize_parameters'
    ]),
        name="outputspec")
    workflow.connect([
        (maskflow, outputnode, [("outputspec.reg_file", "reg_file")]),
        (maskflow, outputnode, [("outputspec.reg_cost", "reg_cost")]),
        (realign, outputnode, [('par_file', 'realignment_parameters')]),
        (smooth, outputnode, [('smoothed_files', 'smoothed_files')]),
        (artdetect, outputnode,[('outlier_files', 'outlier_files'),
            ('statistic_files','outlier_stats'),
            ('plot_files','outlier_plots'),
            ('norm_files','norm_components')])
    ])
    workflow.connect(normalize_mask,"normalized_files",outputnode,"mask_file")
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
    
    # CONNECT TO CONFIG

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
    workflow.inputs.inputspec.parameters = {"order": c.order}
    workflow.base_dir = c.working_dir
    workflow.config = {'execution': {'crashdump_dir': c.crash_dir}}

    datagrabber = get_dataflow(c)

    workflow.connect(datagrabber,'func',inputnode,'functionals')

    infosource = pe.Node(niu.IdentityInterface(fields=['subject_id']),
        name='subject_names')
    if not c.test_mode:
        infosource.iterables = ('subject_id', c.subjects)
    else:
        infosource.iterables = ('subject_id', c.subjects[:1])


    workflow.connect(infosource,'subject_id',inputnode,'subject_id')
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

    return workflow

mwf.workflow_function = create_spm_preproc

"""
Part 5: Main
"""

def main(config_file):
    c = load_config(config_file,config)
    workflow = create_spm_preproc(c,'spm_preproc')
    if c.test_mode:
        workflow.write_graph()

    from nipype.utils.filemanip import fname_presuffix
    workflow.export(fname_presuffix(config_file,'','_script_').replace('.json',''))

    if c.save_script_only:
        return 0

    if c.run_using_plugin:
        workflow.run(plugin=c.plugin,plugin_args=c.plugin_args)
    else:
        workflow.run()

    return None

mwf.workflow_main_function = main

"""
Part 6: Register
"""

register_workflow(mwf)
