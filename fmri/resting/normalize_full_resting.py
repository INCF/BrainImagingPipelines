import argparse
import os
import sys
sys.path.insert(0, '../../normalize')
from base import get_full_norm_workflow
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
from nipype.interfaces.io import FreeSurferSource
import nipype.interfaces.io as nio


pickfirst = lambda x: x[0]


def func_datagrabber(name="resting_output_datagrabber"):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio
    # create a node to obtain the functional images
    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id',
                                                             'fwhm'],
                                                   outfields=['output',
                                                              'meanfunc',
                                                              'fsl_mat']),
                         name=name)
    datasource.inputs.base_directory = os.path.join(c.sink_dir, 'analyses',
                                                   'func')
    datasource.inputs.template = '*'
    datasource.inputs.field_template = dict(
                                output='%s/preproc/output/fwhm_%s/*.nii.gz',
                                meanfunc='%s/preproc/mean/*_mean.nii.gz',
                                fsl_mat='%s/preproc/bbreg/*.mat')
    datasource.inputs.template_args = dict(output=[['subject_id', 'fwhm']],
                                           meanfunc=[['subject_id']],
                                           fsl_mat=[['subject_id']])
    return datasource


def normalize_workflow(name="normalize"):

    norm = get_full_norm_workflow()
    datagrab = func_datagrabber()

    fssource = pe.Node(interface=FreeSurferSource(), name='fssource')
    fssource.inputs.subjects_dir = c.surf_dir

    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
                         name='subject_names')
    infosource.iterables = ('subject_id', c.subjects)

    infofwhm = pe.Node(util.IdentityInterface(fields=['fwhm']),
                         name='fwhm')
    infofwhm.iterables = ('fwhm', c.fwhm)

    inputspec = norm.get_node('inputspec')

    norm.connect(infosource, 'subject_id', fssource, 'subject_id')
    norm.connect(fssource, ('aparc_aseg', pickfirst),
                 inputspec, 'segmentation')
    norm.connect(fssource, 'orig', inputspec, 'brain')
    norm.connect(infosource, 'subject_id', datagrab, 'subject_id')
    norm.connect(infofwhm, 'fwhm', datagrab, 'fwhm')
    norm.connect(datagrab, 'fsl_mat', inputspec, 'out_fsl_file')
    norm.connect(datagrab, 'output', inputspec, 'moving_image')
    norm.connect(datagrab, 'meanfunc', inputspec, 'mean_func')

    norm.inputs.inputspec.template_file = c.norm_template

    sinkd = pe.Node(nio.DataSink(), name='sinkd')
    sinkd.inputs.base_directory = os.path.join(c.sink_dir, 'analyses', 'func')

    outputspec = norm.get_node('outputspec')
    norm.connect(infosource, 'subject_id', sinkd, 'container')
    norm.connect(outputspec, 'warped_image', sinkd, 'normalize.warped_image')
    norm.connect(outputspec, 'warp_field', sinkd, 'normalize.warped_field')
    norm.connect(outputspec, 'affine_transformation',
                 sinkd, 'normalize.affine_transformation')
    norm.connect(outputspec, 'inverse_warp', sinkd, 'normalize.inverse_warp')
    norm.connect(outputspec, 'unwarped_brain',
                 sinkd, 'normalize.unwarped_brain')
    norm.connect(outputspec, 'warped_brain', sinkd, 'normalize.warped_brain')

    return norm


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="example: \
                        run resting_preproc.py -c config.py")
    parser.add_argument('-c', '--config',
                        dest='config',
                        required=True,
                        help='location of config file'
                        )
    args = parser.parse_args()
    path, fname = os.path.split(os.path.realpath(args.config))
    sys.path.append(path)
    c = __import__(fname.split('.')[0])

    workflow = normalize_workflow()
    workflow.base_dir = c.working_dir

    if len(c.subjects) == 1:
        workflow.write_graph()
    if c.run_on_grid:
        workflow.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        workflow.run()
