import os
import warnings
from nipype.interfaces.fsl.base import FSLCommand, FSLCommandInputSpec
from nipype.interfaces.base import (TraitedSpec, File,
                                    traits, isdefined)
from nipype.utils.filemanip import split_filename

warn = warnings.warn
warnings.filterwarnings('always', category=UserWarning)

class EPIDeWarpInputSpec(FSLCommandInputSpec):

    mag_file = File(exists=True,
                  desc='Magnitude file',
                  argstr='--mag %s', position=0, mandatory=True)
    dph_file = File(exists=True,
                  desc='Phase file assumed to be scaled from 0 to 4095',
                  argstr='--dph %s', mandatory=True)
    exf_file = File(exists=True,
                  desc='example func volume (or use epi)',
                  argstr='--exf %s', mandatory=False)
    epi_file = File(exists=True,
                  desc='EPI volume to unwarp',
                  argstr='--epi %s', mandatory=False)
    tediff = traits.Float(2.46, usedefault=True,
                          desc='difference in B0 field map TEs',
                          argstr='--tediff %s')
    esp = traits.Float(0.58, desc='EPI echo spacing',
                  argstr='--esp %s', usedefault=True)
    sigma = traits.Int(2, usedefault=True, argstr='--sigma %s',
                       desc="2D spatial gaussing smoothing \
                       stdev (default = 2mm)")
    vsm = traits.String(genfile=True, desc='voxel shift map',
                        argstr='--vsm %s')
    exfdw = traits.String(desc='dewarped example func volume', genfile=True,
                          argstr='--exfdw %s')
    epidw = traits.String(desc='dewarped epi volume', genfile=False,
                          argstr='--epidw %s')
    tmpdir = traits.String(genfile=True, desc='tmpdir',
                           argstr='--tmpdir %s')
    nocleanup = traits.Bool(True, usedefault=True, desc='no cleanup',
                            argstr='--nocleanup')
    cleanup = traits.Bool(desc='cleanup',
                          argstr='--cleanup')

class EPIDeWarpOutputSpec(TraitedSpec):
    unwarped_file = File(desc="unwarped epi file")
    vsm_file = File(desc="voxel shift map")
    exfdw = File(desc="dewarped functional volume example")
    exf_mask = File(desc="Mask from example functional volume")


class EPIDeWarp(FSLCommand):
    """Wraps fieldmap unwarping script from Freesurfer's epidewarp.fsl_

    Examples
    --------
    >>> dewarp = interface=EpiDeWarp()
    >>> dewarp.inputs.epi_file = "functional.nii"
    >>> dewarp.inputs.mag_file = "magnitude.nii"
    >>> dewarp.inputs.dph_file = "phase.nii"
    >>> res = dewarp.run()

    References
    ----------
    _epidewarp.fsl: http://surfer.nmr.mgh.harvard.edu/fswiki/epidewarp.fsl

    """

    _cmd = 'epidewarp.fsl'
    input_spec = EPIDeWarpInputSpec
    output_spec = EPIDeWarpOutputSpec

    def _gen_filename(self, name):
        if name == 'exfdw':
            if isdefined(self.inputs.exf_file):
                return self._gen_fname(split_filename(self.inputs.exf_file)[1],
                                  suffix="_exfdw")
            else:
                return self._gen_fname("exfdw")
        if name == 'epidw':
            if isdefined(self.inputs.epi_file):
                return self._gen_fname(split_filename(self.inputs.epi_file)[1],
                                  suffix="_epidw")
        if name == 'vsm':
            return self._gen_fname('vsm')
        if name == 'tmpdir':
            return os.path.join(os.getcwd(), 'temp')
        return None

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if not isdefined(self.inputs.exfdw):
            outputs['exfdw'] = self._gen_filename('exfdw')
        else:
            outputs['exfdw'] = self.inputs.exfdw
        if isdefined(self.inputs.epi_file):
            if isdefined(self.inputs.epidw):
                outputs['unwarped_file'] = self.inputs.epidw
            else:
                outputs['unwarped_file'] = self._gen_filename('epidw')
        if not isdefined(self.inputs.vsm):
            outputs['vsm_file'] = self._gen_filename('vsm')
        else:
            outputs['vsm_file'] = self._gen_fname(self.inputs.vsm)
        if not isdefined(self.inputs.tmpdir):
            outputs['exf_mask'] = self._gen_fname(cwd=self._gen_filename('tmpdir'),
                                                  basename='maskexf')
        else:
            outputs['exf_mask'] = self._gen_fname(cwd=self.inputs.tmpdir,
                                                  basename='maskexf')
        return outputs
        
if __name__ == "__main__":
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    import nipype.interfaces.io as nio
    
    phase_file = '/mindhive/gablab/rtsmoking/test_retest/brain_data/niftis/sub01s1/fieldmap/sub01s1_run01_20.nii.gz'
    mag_file = '/mindhive/gablab/rtsmoking/test_retest/brain_data/niftis/sub01s1/fieldmap/sub01s1_run00_19.nii.gz'
    in_file = '/mindhive/gablab/rtsmoking/test_retest/brain_data/niftis/sub01s1/functional_MID/sub01s1_run00_15.nii.gz'
    
    workflow = pe.Workflow(name='test')
    
    dewarp = pe.Node(interface=EpiDeWarp(),name='fmunwarp')
    dewarp.inputs.epi_file = in_file
    dewarp.inputs.mag_file = mag_file
    dewarp.inputs.dph_file = phase_file    
    
    
    workflow.base_dir = os.getcwd()
    workflow.add_nodes([dewarp])
    workflow.run()
    
