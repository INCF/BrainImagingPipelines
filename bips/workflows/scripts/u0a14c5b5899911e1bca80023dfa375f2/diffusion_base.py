from nipype.workflows.dmri.fsl import create_bedpostx_pipeline
import nipype.interfaces.fsl as fsl
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as niu


def create_workflow(name='tracking'):
    wf = pe.Workflow(name=name)
    bed_wf = create_bedpostx_pipeline()
    inputspec = pe.Node(niu.IdentityInterface(fields=['dwi',
                                                      'mask',
                                                      'seed']),
        name="inputspec")
    outputspec = pe.Node(niu.IdentityInterface(fields=['fdt_paths',
                                                       'log',
                                                       'particle_files',
                                                       'targets',
                                                       'way_total']),
        name='outputspec')

    wf.connect(inputspec,'dwi',bed_wf,'inputnode.dwi')
    wf.connect(inputspec,'mask', bed_wf, 'inputnode.mask')

    track = pe.Node(fsl.ProbTrackX(verbose=2),name='probtrackx')

    wf.connect(bed_wf,'outputnode.thsamples', track, 'thsamples')
    wf.connect(bed_wf,'outputnode.phsamples', track, 'phsamples')
    wf.connect(bed_wf,'outputnode.fsamples', track, 'fsamples')
    wf.connect(inputspec, 'seed', track, 'seed')
    wf.connect(inputspec,'mask',track,'mask')

    wf.connect(track,'fdt_paths', outputspec, 'fdt_paths')
    wf.connect(track,'log', outputspec, 'log')
    wf.connect(track,'particle_files', outputspec, 'particle_files')
    wf.connect(track,'targets', outputspec, 'targets')
    wf.connect(track,'way_total', outputspec, 'way_total')

    return wf