import json
import os

from nipype.utils.filemanip import save_json
from nipype.interfaces.base import TraitedSpec, traits
from pyface.api import FileDialog, OK, confirm, YES
from traits.api import HasTraits, HasStrictTraits, Str, Bool, Button, Instance
from traitsui.api import Handler, View, Item, UItem, HGroup

_workflow = {}

def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv

def _decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv

def load_json(s):
    obj = None
    with open(s) as fp:
        obj = json.load(fp, object_hook=_decode_dict)
    if obj is None:
        raise Exception('could not read json file')
    return obj

class MetaWorkflow(HasStrictTraits):
    version = traits.Constant(1)
    # uuid of workflow
    uuid = traits.String(mandatory=True)
    # description of workflow
    help = traits.Str(mandatory=True)
    # workflows that should be run prior to this workflow
    dependencies = traits.List(traits.Str(), mandatory=True)
    # software necessary to run this workflow
    required_software = traits.List(traits.Str)
    # workflow creation function takes a configuration file as input
    workflow_main_function = traits.Function(mandatory=True)
    # configuration creation function (can take a config file as input)
    config_ui = traits.Function
    # config view
    config_view = traits.Function
    # purl to describe workflow
    url = traits.Str()
    # keyword tags for the workflow
    tags = traits.List(traits.Str)
    # use this workflow instead
    superceded_by = traits.List(traits.UUID)
    # script dir
    script_dir = traits.Str()

    def to_json(self):
        pass

    def from_json(self):
        pass

    def create_config(self):
        f = Foo(self.config_ui(),
                self.workflow_main_function,
                self.config_view)
        f.configure_traits()
        
    def run(self,configfile):
        self.workflow_main_function(configfile)

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
            self._config.configure_traits(view=self.config_view())
            self._save_to_file()
            self.saved = False
            self.config_changed = True
            
    def _load_button_fired(self):
        dialog = FileDialog(action="open", wildcard=self.file_wildcard)
        dialog.open()
        if dialog.return_code == OK:
            c = self.config_class()
            for item, val in load_json(dialog.path).items():
                try:
                    setattr(c, item, val)
                except:
                    print('Could not set: %s to %s' % (item, str(val)))
            self._config = c
            self._config.configure_traits(view=self.config_view())
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


def register_workflow(wf):
    _workflow[wf.uuid] = dict(object = wf)


def get_workflow(uuid):
    if uuid in _workflow:
        return _workflow[uuid]['object']
    wf_found = [key for key in _workflow if key.startswith(uuid)]
    if not len(wf_found):
        raise ValueError('No workflow with uuid %s found' % uuid)
    if len(wf_found) > 1:
        raise Exception('Multiple workflows found with partial uuid %s' % uuid)
    return get_workflow(wf_found[0])


def list_workflows():
    for wf, value in sorted(_workflow.items()):
        print('%s %s' % (wf,
                         value['object'].help.split('\n')[1]))


def configure_workflow(uuid):
    wf = get_workflow(uuid)
    wf.create_config()


def run_workflow(configfile):
    config = load_json(configfile)
    wf = get_workflow(config['uuid'])
    wf.run(configfile)


def display_workflow_info(uuid):
    wf = get_workflow(uuid)
    import pprint
    pprint.pprint(wf.get())


def query_workflows(query_str):
    pass
