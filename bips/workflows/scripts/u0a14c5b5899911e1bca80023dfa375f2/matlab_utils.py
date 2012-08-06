import os
import scipy.io as sio
from nipype.interfaces.base import TraitedSpec, BaseInterface, BaseInterfaceInputSpec
import shutil

class ConnImportInputSpec(BaseInterfaceInputSpec):
    from nipype.interfaces.base import traits, InputMultiPath

    functional_files = InputMultiPath(desc="preprocessed functional files")
    structural_files = InputMultiPath(desc="structural files")
    csf_mask = InputMultiPath(desc="csf mask files")
    white_mask = InputMultiPath(desc="white matter mask files")
    grey_mask = InputMultiPath(desc="grey matter mask files")
    tr = traits.Float()
    n_subjects = traits.Int()
    realignment_parameters = InputMultiPath( desc='realignment parameters')
    outliers = InputMultiPath( desc='art outliers')
    norm_components = InputMultiPath(desc='art norm components')
    project_name = traits.Str(desc="name of the project")
    script = traits.Str()

class ConnImportOutputSpec(TraitedSpec):
    from nipype.interfaces.base import traits
    conn_inputs = traits.File()
    conn_batch = traits.File()
    conn_directory = traits.Directory()

class ConnImport(BaseInterface):
    input_spec = ConnImportInputSpec
    output_spec = ConnImportOutputSpec

    def _run_interface(self, runtime):
        from nipype.interfaces.matlab import MatlabCommand
        def islist(i):
            if not isinstance(i,list):
                i = [str(i)]
                return i
            else:
                I = []
                for l in i:
                    if not l.endswith('.par'):
                        I.append(str(l))
                    else:
                        shutil.copy2(l,l+'.txt')
                        I.append(l+'.txt')
                return I

        info = {}
        info["functional_files"] = islist(self.inputs.functional_files)
        info["structural_files"] = islist(self.inputs.structural_files)
        info["csf_mask"] = islist(self.inputs.csf_mask)
        info["white_mask"] = islist(self.inputs.white_mask)
        info["grey_mask"] = islist(self.inputs.grey_mask)
        info["TR"] = float(self.inputs.tr)
        info["realignment_parameters"] = islist(self.inputs.realignment_parameters)
        info["outliers"] = islist(self.inputs.outliers)
        info["norm_components"] = islist(self.inputs.norm_components)
        info["filename"] = '%s/conn_%s.mat'%(os.getcwd(),self.inputs.project_name)
        info["n_subjects"] = int(self.inputs.n_subjects)
        conn_inputs = os.path.abspath('inputs_to_conn.mat')
        sio.savemat(conn_inputs, {"in":info})
        print "saved conn_inputs.mat file"
        script="""load %s; batch=bips_load_conn(in); conn_batch(batch)"""%conn_inputs
        mlab = MatlabCommand(script=script, mfile=True)
        result = mlab.run()
        return result.runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs['conn_inputs'] = os.path.abspath('inputs_to_conn.mat')
        outputs['conn_batch'] = '%s/conn_%s.mat'%(os.getcwd(),self.inputs.project_name)
        #outputs['conn_directory'] = '%s/conn_%s'%(os.getcwd(),self.inputs.project_name)
        return outputs
