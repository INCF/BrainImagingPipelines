from glob import glob
import os

import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio
from nipype.interfaces.freesurfer import SampleToSurface

from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits

from .base import MetaWorkflow, load_config, register_workflow


desc = """
Map resting timeseries to surface correlations
==============================================

"""

mwf = MetaWorkflow()
mwf.uuid = '2b00d9ee8bde11e1a0960023dfa375f2'
mwf.tags = ['surface', 'resting', 'correlation']


def check_path(path):
    fl = glob(path)
    if not len(fl):
        print "ERROR:", path, "does NOT exist!"
    else:
        print "Exists:", fl


# create gui
class config(HasTraits):
    uuid = traits.Str(desc="UUID")

    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    base_dir = Directory(exists=True, desc='Base directory of data. (Should be subject-independent)')
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")
    surf_dir = Directory(mandatory=True, desc="Freesurfer subjects directory")

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
    # Subjects
    subjects = traits.List(traits.Str, mandatory=True, usedefault=True,
                          desc="Subject id's. Note: These MUST match the subject id's in the \
                                Freesurfer directory. For simplicity, the subject id's should \
                                also match with the location of individual functional files.")
    func_template = traits.String('%s/cleaned_resting.nii.gz')
    reg_template = traits.String('%s/cleaned_resting_reg.dat')
    ref_template = traits.String('%s/cleaned_resting_ref.nii.gz')

    # Target surface
    target_surf = traits.Enum('fsaverage4', 'fsaverage3', 'fsaverage5',
                              'fsaverage6', 'fsaverage', 'subject',
                              desc='which average surface to map to')
    surface_fwhm = traits.List([5], traits.Float(), mandatory=True,
                               usedefault=True,
                               desc="How much to smooth on target surface")
    projection_stem = traits.Str('-projfrac-avg 0 1 0.1',
                                 desc='how to project data onto the surface')
    combine_surfaces = traits.Bool(desc=('compute correlation matrix across'
                                         'both left and right surfaces'))

    # Saving output
    out_type = traits.Enum('mat', 'hdf5', desc='mat or hdf5')
    hdf5_package = traits.Enum('h5py', 'pytables',
                               desc='which hdf5 package to use')
    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()

    # Atlas mapping
    surface_atlas = traits.Str('None',
                               desc='Name of parcellation atlas')

    # Buttons
    check_func_datagrabber = Button("Check")

    def _check_func_datagrabber_fired(self):
        subs = self.subjects
        for s in subs:
            for template in [self.func_template, self.ref_template,
                             self.reg_template]:
                check_path(os.path.join(self.base_dir, template % s))
            check_path(os.path.join(self.surf_dir, s))

def create_config():
    c = config()
    c.uuid = mwf.uuid
    return c

mwf.config_ui = create_config
mwf.help = desc


def create_view():
    from traitsui.api import View, Item, Group, CSVListEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='working_dir'),
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
                      Item(name='base_dir', ),
                      Item(name='func_template'),
                      Item(name='reg_template'),
                      Item(name='ref_template'),
                      Item(name='check_func_datagrabber'),
                      label='Subjects', show_border=True),
                Group(Item(name='target_surf'),
                      Item(name='surface_fwhm', editor=CSVListEditor()),
                      Item(name='projection_stem'),
                      Item(name='combine_surfaces'),
                      Item(name='surface_atlas'),
                      label='Smoothing', show_border=True),
                Group(Item(name='out_type'),
                      Item(name='hdf5_package',
                           enabled_when="out_type is 'hdf5'"),
                      label='Output', show_border=True),
                Group(Item(name='use_advanced_options'),
                    Item(name='advanced_script',enabled_when='use_advanced_options'),
                    label='Advanced',show_border=True),
                buttons=[OKButton, CancelButton],
                resizable=True,
                width=1050)
    return view

mwf.config_view = create_view


def create_correlation_matrix(infiles, out_type, package):
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

    corrmat = np.corrcoef(timeseries)
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


def create_workflow(c):
    workflow = pe.Workflow(name='surface_correlation')
    inputnode = pe.Node(util.IdentityInterface(fields=['subject_id']),
                        name='subjectsource')
    inputnode.iterables = ('subject_id', c.subjects)
    datasource = pe.Node(nio.DataGrabber(infields=['subject_id'],
                                         outfields=['timeseries_file',
                                                   'ref_file',
                                                   'reg_file']),
                         name='datasource')
    datasource.inputs.template = '*'
    datasource.inputs.base_directory = os.path.abspath(c.base_dir)
    datasource.inputs.field_template = dict(timeseries_file=c.func_template,
                                            ref_file=c.ref_template,
                                            reg_file=c.reg_template)
    workflow.connect(inputnode, 'subject_id', datasource, 'subject_id')

    # vol2surf
    if c.combine_surfaces:
        vol2surf = pe.MapNode(SampleToSurface(),
                              iterfield=['hemi'],
                              name='sampletimeseries')
        vol2surf.iterables = ('smooth_surf', c.surface_fwhm)
        vol2surf.inputs.hemi = ['lh', 'rh']
    else:
        vol2surf = pe.Node(SampleToSurface(),
                           name='sampletimeseries')
        vol2surf.iterables = [('smooth_surf', c.surface_fwhm),
                              ('hemi', ['lh', 'rh'])]
    vol2surf.inputs.projection_stem = c.projection_stem
    vol2surf.inputs.interp_method = 'trilinear'
    vol2surf.inputs.out_type = 'niigz'
    vol2surf.inputs.subjects_dir = c.surf_dir
    if c.target_surf != 'subject':
        vol2surf.inputs.target_subject = c.target_surf

    workflow.connect(datasource, 'timeseries_file', vol2surf, 'source_file')
    workflow.connect(datasource, 'reg_file', vol2surf, 'reg_file')
    workflow.connect(datasource, 'ref_file', vol2surf, 'reference_file')

    # create correlation matrix
    corrmat = pe.Node(util.Function(input_names=['infiles', 'out_type',
                                                 'package'],
                                    output_names=['corrmatfile'],
                                    function=create_correlation_matrix),
                      name='correlation_matrix')
    corrmat.inputs.out_type = c.out_type
    corrmat.inputs.package = c.hdf5_package
    workflow.connect(vol2surf, 'out_file', corrmat, 'infiles')

    datasink = pe.Node(nio.DataSink(), name='sinker')
    datasink.inputs.base_directory = c.sink_dir
    datasink.inputs.regexp_substitutions = [('_subject_id.*smooth_surf', 'surffwhm')]
    workflow.connect(inputnode, 'subject_id', datasink, 'container')
    workflow.connect(corrmat, 'corrmatfile', datasink, '@corrmat')
    return workflow


def main(config_file):
    c = load_config(config_file, create_config)
    workflow = create_workflow(c)
    workflow.base_dir = c.working_dir
    workflow.config = {'execution': {'crashdump_dir': c.crash_dir}}
    if c.use_advanced_options:
        exec c.advanced_script
    if c.run_using_plugin:
        workflow.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        workflow.run()


mwf.workflow_main_function = main
register_workflow(mwf)
