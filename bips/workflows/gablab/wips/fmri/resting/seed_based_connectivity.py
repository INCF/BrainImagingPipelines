import os
from .....base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from .....flexible_datagrabber import Data, DataBase

"""
Part 1: Define a MetaWorkflow
"""

mwf = MetaWorkflow()
mwf.uuid = '9ce580861d2a11e2907600259080ab1a'
mwf.help="""
Seed-Based Surface Connectivity
===============================

Needs a timeseries file with shape num_timepoints x num_timeseries
 """
mwf.tags=['seed','connectivity','resting']

"""
Part 2: Define the config class & create_config function
"""

class config(HasTraits):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc="Workflow Description")
    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    sink_dir = Directory(os.path.abspath('.'), mandatory=True, desc="Location where the BIP will store the results")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")
    surf_dir = Directory(mandatory=True, desc= "Freesurfer subjects directory")
    save_script_only = traits.Bool(False)
    # Execution

    run_using_plugin = Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.Enum("PBS", "MultiProc", "SGE", "Condor",
        usedefault=True,
        desc="plugin to use, if run_using_plugin=True")
    plugin_args = traits.Dict({"qsub_args": "-q many"},
        usedefault=True, desc='Plugin arguments.')
    test_mode = Bool(False, mandatory=False, usedefault=True,
        desc='Affects whether where and if the workflow keeps its \
                            intermediary files. True to keep intermediary files. ')
    timeout = traits.Float(14.0)
    datagrabber = traits.Instance(Data, ())
    projection_stem = traits.Str('-projfrac-avg 0 1 0.1',
        desc='how to project data onto the surface')
    out_type = traits.Enum('mat', 'hdf5', desc='mat or hdf5')
    hdf5_package = traits.Enum('h5py', 'pytables',
        desc='which hdf5 package to use')
    target_surf = traits.Enum('fsaverage4', 'fsaverage3', 'fsaverage5',
        'fsaverage6', 'fsaverage', 'subject',
        desc='which average surface to map to')
    surface_fwhm = traits.List([5], traits.Float(), mandatory=True,
        usedefault=True,
        desc="How much to smooth on target surface")
    roiname= traits.String('amygdala')
    use_advanced_options = Bool(False)
    advanced_options = traits.Code()

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    c.datagrabber = get_datagrabber()

    return c

def get_datagrabber():
    foo = Data(['reg_file','mean_image','roi_timeseries','timeseries_file'])
    subs = DataBase()
    subs.name = 'subject_id'
    subs.values = ['sub01','sub02']
    subs.iterable = True
    foo.fields = [subs]
    foo.template= '*'
    foo.field_template = dict(reg_file='%s/preproc/bbreg/*.dat',
        mean_image='%s/preproc/mean/*.nii*',
        roi_timeseries = '%s/segstats/roi.txt',
        timeseries_file = '%s/preproc/output/bandpassed/*.nii*')
    foo.template_args = dict(mean_image=[['subject_id']],
        reg_file=[['subject_id']],
        roi_timeseries=[['subject_id']],
        timeseries_file=[['subject_id']])
    return foo

mwf.config_ui = create_config

"""
Part 3: Create a View
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
            Item(name='test_mode'), Item(name="timeout"),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),
            Item('projection_stem'),
            Item('out_type'),
            Item('hdf5_package'),
            Item('target_surf'),Item('surface_fwhm'),Item('roiname'),
            label='Subjects', show_border=True),
        Group(Item(name='use_advanced_options'),
            Item(name="advanced_options", enabled_when="use_advanced_options"),
            label="Advanced Options", show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Part 4: Workflow Construction
"""

def create_correlation_matrix(infiles, roi, out_type, package):
    import os
    import numpy as np
    import scipy.io as sio
    import nibabel as nb
    from nipype.utils.filemanip import split_filename, filename_to_list
    for idx, fname in enumerate(filename_to_list(infiles)):
        data = np.squeeze(nb.load(fname).get_data())
        if idx == 0:
            timeseries = data
        else:
            timeseries = np.vstack((timeseries, data))
    roi_data = np.genfromtxt(roi)
    if not len(roi_data.shape)==2:
        roi_data = roi_data[:,None]
    corrmat = np.zeros((roi_data.shape[1],timeseries.shape[0]))
    print timeseries.shape
    for i in xrange(roi_data.shape[1]):
        for j in xrange(timeseries.shape[0]):
            r = np.corrcoef(timeseries[j,:],roi_data[:,i])[0][1]
            corrmat[i,j] = np.sqrt(timeseries.shape[1]-3)*0.5*np.log((1+r)/(1-r))

    #corrmat = np.corrcoef(timeseries,roi_data.T)
    print corrmat.shape
    
    _, name, _ = split_filename(filename_to_list(infiles)[0])
    if len(filename_to_list(infiles))>1:
        name = 'combined_' + name
    if 'mat' in out_type:
        matfile = os.path.abspath(name + '.mat')
        sio.savemat(matfile, {'corrmat': corrmat})
        output = matfile
    elif 'hdf5' in out_type:
        hdf5file = os.path.abspath(name + '.hf5')
        if package == 'h5py':
            import h5py
            f = h5py.File(hdf5file, 'w')
            f.create_dataset('corrmat', data=corrmat, compression=5)
            f.close()
        else:
            from tables import openFile, Float64Atom, Filters
            h5file = openFile(hdf5file, 'w')
            arr = h5file.createCArray(h5file.root, 'corrmat', Float64Atom(),
                corrmat.shape, filters=Filters(complevel=5))
            arr[:] = corrmat
            h5file.close()
        output = hdf5file
    else:
        raise Exception('Unknown output type')
    return output

def roi_connectivity(c):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    import nipype.interfaces.io as nio
    from nipype.interfaces.freesurfer import SampleToSurface
    workflow = pe.Workflow(name='surface_correlation')

    datasource = c.datagrabber.create_dataflow()
    dg = datasource.get_node("datagrabber")
    #dg.run_without_submitting = True
    inputnode = datasource.get_node("subject_id_iterable")
    # vol2surf

    vol2surf = pe.MapNode(SampleToSurface(),
        iterfield=['hemi'],
        name='sampletimeseries')
    vol2surf.iterables = ('smooth_surf', c.surface_fwhm)
    vol2surf.inputs.hemi = ['lh', 'rh']

    vol2surf.inputs.projection_stem = c.projection_stem
    vol2surf.inputs.interp_method = 'trilinear'
    vol2surf.inputs.out_type = 'niigz'
    vol2surf.inputs.subjects_dir = c.surf_dir
    if c.target_surf != 'subject':
        vol2surf.inputs.target_subject = c.target_surf

    workflow.connect(datasource, 'datagrabber.timeseries_file', vol2surf, 'source_file')
    workflow.connect(datasource, 'datagrabber.reg_file', vol2surf, 'reg_file')
    workflow.connect(datasource, 'datagrabber.mean_image', vol2surf, 'reference_file')

    # create correlation matrix
    corrmat = pe.Node(util.Function(input_names=['infiles','roi', 'out_type',
                                                 'package'],
        output_names=['corrmatfile'],
        function=create_correlation_matrix),
        name='correlation_matrix')
    corrmat.inputs.out_type = c.out_type
    corrmat.inputs.package = c.hdf5_package
    workflow.connect(vol2surf, 'out_file', corrmat, 'infiles')
    workflow.connect(datasource, 'datagrabber.roi_timeseries', corrmat, 'roi')

    datasink = pe.Node(nio.DataSink(), name='sinker')
    datasink.inputs.base_directory = c.sink_dir
    datasink.inputs.regexp_substitutions = [('_subject_id.*smooth_surf', 'surffwhm')]
    workflow.connect(inputnode, 'subject_id', datasink, 'container')
    workflow.connect(corrmat, 'corrmatfile', datasink, 'roi_connectivity.%s.z_corrmat'%c.roiname)
    workflow.connect(vol2surf,'out_file',datasink,'roi_connectivity.%s.surfaces'%c.roiname)
    return workflow


mwf.workflow_function = roi_connectivity

"""
Part 5: Define the main function
"""

def main(config_file):
    c = load_config(config_file, create_config)
    workflow = roi_connectivity(c)
    workflow.base_dir = c.working_dir
    workflow.config = {'execution': {'crashdump_dir': c.crash_dir, "job_finished_timout":14}}
    if c.use_advanced_options:
        exec c.advanced_script

    workflow.export(os.path.join(c.sink_dir,'bips_'))
    if c.save_script_only:
        return 0

    if c.run_using_plugin:
        workflow.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        workflow.run()


mwf.workflow_main_function = main

"""
Part 6: Register the Workflow
"""

register_workflow(mwf)
