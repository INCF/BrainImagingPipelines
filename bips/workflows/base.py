from nipype.interfaces.base import TraitedSpec, traits

class MetaWorkflowInputSpec(TraitedSpec):
    version = traits.Constant(1)
    # uuid of workflow
    uuid = traits.UUID(mandatory=True)
    # description of workflow
    help = traits.Str(mandatory=True)
    # workflows that should be run prior to this workflow
    dependencies = traits.List(traits.UUID, mandatory=True)
    # software necessary to run this workflow
    required_software = traits.List(traits.Str)
    # workflow creation function takes a configuration file as input
    create_function = traits.Function(mandatory=True)
    # configuration creation function (can take a config file as input)
    config_ui = traits.Function()
    # purl to describe workflow
    url = traits.Str()
    # keyword tags for the workflow
    tags = traits.List(traits.Str)
    # use this workflow instead
    superceded_by = traits.List(traits.UUID)
    # script dir
    script_dir = traits.UUID()
S
class MetaWorkflow(object):

    _input_spec = MetaWorkflowInputSpec

    def __init__(self):
        self.inputs = self._input_spec()

    def to_json(self):
        pass

    def from_json(self):
        pass

