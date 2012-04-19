from nipype.interfaces.base import TraitedSpec, traits
import os
from enthought.traits.api import HasTraits, Str, Bool, Button, Instance
from enthought.traits.ui.api import Handler, View, Item, UItem, HGroup
from enthought.pyface.api import FileDialog, OK, confirm, YES
from nipype.utils.filemanip import load_json, save_json
import sys


class MetaWorkflowInputSpec(TraitedSpec):
    version = traits.Constant(1)
    # uuid of workflow
    uuid = traits.String(mandatory=True)
    # description of workflow
    help = traits.Str(mandatory=True)
    # workflows that should be run prior to this workflow
    dependencies = traits.List(traits.UUID, mandatory=True)
    # software necessary to run this workflow
    required_software = traits.List(traits.Str)
    # workflow creation function takes a configuration file as input
    workflow_main_function = traits.Function(mandatory=True)
    # configuration creation function (can take a config file as input)
    config_ui = traits.Function()
    # config view
    config_view = traits.Instance(View)
    # purl to describe workflow
    url = traits.Str()
    # keyword tags for the workflow
    tags = traits.List(traits.Str)
    # use this workflow instead
    superceded_by = traits.List(traits.UUID)
    # script dir
    script_dir = traits.UUID()

class MetaWorkflow(object):

    _input_spec = MetaWorkflowInputSpec

    def __init__(self):
        self.inputs = self._input_spec()

    def to_json(self):
        pass

    def from_json(self):
        pass

    def create_config(self):
        f = Foo(self.inputs.config_ui(),self.inputs.workflow_main_function,self.inputs.config_view)
        f.configure_traits()
        
    def run(self,configfile):
        self.inputs.workflow_main_function(configfile)

class FooHandler(Handler):
    """Handler for the Foo class.
    This handler will
    (1) listen for changes to the 'filename' Trait of the object and
        update the window title when it changes; and
    (2) intercept request to close the window, and if the data is not saved,
        ask the user for confirmation.
    """

    def object_filename_changed(self, info):
        filename = info.object.filename
        if filename is "":
            filename = "<no file>"
        info.ui.title = "Editing: " + filename

    def close(self, info, isok):
        # Return True to indicate that it is OK to close the window.
        if not info.object.saved:
            response = confirm(info.ui.control,
                            "Value is not saved.  Are you sure you want to exit?")
            return response == YES
        else:
            return True
        

class Foo(HasTraits):

    Configuration_File = Str

    saved = Bool(True)
    config_changed = Bool(False)
    
    filedir = Str
    filename = Str
    
    _config = None
    
    save_button = Button("Save")
    new_button = Button("New")
    save_as_button = Button("Save As")
    load_button = Button("Load")
    run_button = Button("Run")

    # Wildcard pattern to be used in file dialogs.
    file_wildcard = Str("json file (*.json)|*.json|Data file (*.json)|*.dat|All files|*")

    view = View(Item('Configuration_File',style='readonly'),
                HGroup(
                    UItem('save_button', enabled_when='not saved and filename is not ""'),
                    UItem('save_as_button', enabled_when='not saved and filename is not ""'),
                    UItem('new_button'),
                    UItem('load_button', enabled_when='not config_changed'),
                    UItem('run_button', enabled_when='saved and filename is not ""')
                ),
                resizable=True,
                width=500,
                handler=FooHandler(),
                title="File Dialog")
    
    def __init__(self,config_class,runfunc,config_view):
        self.config_class = config_class
        self.runfunc = runfunc
        self.config_view = config_view
    #-----------------------------------------------
    # Trait change handlers
    #-----------------------------------------------

    def _Configuration_File_changed(self):
        self.saved = False

    def _save_button_fired(self):
        self._save_to_file()
        self.config_changed = False
        
    def _save_as_button_fired(self):
        dialog = FileDialog(action="save as", wildcard=self.file_wildcard)
        dialog.open()
        if dialog.return_code == OK:
            self.filedir = dialog.directory
            self.filename = dialog.filename
            self.Configuration_File = os.path.join(dialog.directory, dialog.filename)
            self._save_to_file()
            self.saved = True
            self.config_changed = False
                
    def _new_button_fired(self):
        dialog = FileDialog(action="save as", wildcard=self.file_wildcard)
        dialog.open()
        if dialog.return_code == OK:
            self.filedir = dialog.directory
            self.filename = dialog.filename
            self.Configuration_File = os.path.join(dialog.directory, dialog.filename)
            self._config = self.config_class()
            self._config.configure_traits(view=self.config_view)
            self._save_to_file()
            self.saved = False
            self.config_changed = True
            
    def _load_button_fired(self):
        dialog = FileDialog(action="open", wildcard=self.file_wildcard)
        dialog.open()
        if dialog.return_code == OK:
            c = self.config_class()
            self._config = c.set(**load_json(dialog.path))
            self._config.configure_traits(view=self.config_view)
            self.filedir = dialog.directory
            self.filename = dialog.filename
            self.Configuration_File = os.path.join(dialog.directory, dialog.filename)
            self.saved = False
            self.config_changed = True
            
    def _run_button_fired(self):
        self.runfunc(self.Configuration_File)
    
    #-----------------------------------------------
    # Private API
    #-----------------------------------------------

    def _save_to_file(self):
        """Save `self.Configuration_File` to the file `self.filedir`+`self.filename`."""
        path = os.path.join(self.filedir, self.filename)
        #f = open(path, 'w')
        #f.write(self.value + '\n')
        #f.close()
        save_json(filename=path,data=self._config.get())
        self.saved = True
