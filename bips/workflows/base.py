import json
import os

from nipype.utils.filemanip import save_json
from nipype.interfaces.base import traits
from traits.api import (HasTraits, HasStrictTraits, Str, Bool, Button, File)

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

def load_config(configfile, config_class):
    c = config_class()
    for item, val in load_json(configfile).items():
        if item == 'uuid' or item == 'desc':
            continue
        try:
            setattr(c, item, val)
        except:
            print('Could not set: %s to %s' % (item, str(val)))
    return c

class MetaWorkflow(HasStrictTraits):
    version = traits.Constant(1)
    # uuid of workflow
    uuid = traits.String(mandatory=True)
    # description of workflow
    help = traits.Str(mandatory=True)
    # workflows that should be run prior to this workflow
    uses_outputs_of = traits.List(traits.Str(), mandatory=True)
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
    supercedes = traits.List(traits.UUID)
    # script dir
    script_dir = traits.Str()
    # Workflow function
    workflow_function = traits.Function


def OpenFileDialog(action, wildcard, self):
    from pyface.api import FileDialog, OK
    doaction = action
    if action == "new":
        doaction = "save as"
    dialog = FileDialog(action=doaction, wildcard=wildcard)
    dialog.open()
    if dialog.return_code == OK:
        self.filedir = dialog.directory
        self.filename = dialog.filename
        self.Configuration_File = os.path.join(dialog.directory, dialog.filename)
        if action == "open":
            self._config = load_config(dialog.path, self.config_class)
            self._config.configure_traits(view=self.config_view())
            self.saved = False
            self.config_changed = True
        if action == "new":
            self._config = self.config_class()
            self._config.configure_traits(view=self.config_view())
            self._save_to_file()
            self.saved = False
            self.config_changed = True
        if action == "save as":
            self._save_to_file()
            self.saved = True
            self.config_changed = False

class ConfigUI(HasTraits):
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
    py_button = Button("Save to Python script")
    graph_button = Button("Graph")

    # Wildcard pattern to be used in file dialogs.
    file_wildcard = Str(("json file (*.json)|*.json|Data file (*.json)"
                         "|*.dat|All files|*"))
    #-----------------------------------------------
    # Trait change handlers
    #-----------------------------------------------

    def _Configuration_File_changed(self):
        self.saved = False

    def _save_button_fired(self):
        self._save_to_file()
        self.config_changed = False

    def _save_as_button_fired(self):
        OpenFileDialog(action="save as", wildcard=self.file_wildcard,
                       self=self)

    def _new_button_fired(self):
        OpenFileDialog(action="new", wildcard=self.file_wildcard,
                       self=self)

    def _load_button_fired(self):
        OpenFileDialog(action="open", wildcard=self.file_wildcard,
                       self=self)

    def _run_button_fired(self):
        run_workflow(self.Configuration_File)

    def _py_button_fired(self):
        f = open(os.path.join(self.filedir,
                              os.path.split(self.Configuration_File)[1].split('.json')[0]+'.py'),'w')
        f.write("from bips.workflows.base import get_config\n\n")
        f.write("uuid = \'%s\' \n\n" % self._config.uuid)
        f.write("c = get_config(uuid)\n\n")
        for key, item in self._config.class_traits().iteritems():
            try:
                if key in self._config.editable_traits() and not key=='uuid':
                    f.write("\"\"\"%s : %s\"\"\"\n\n"% (key, item.desc))
                    if 'Directory' in str(item.trait_type)\
                       or 'Str' in str(item.trait_type)\
                    or "Enum" in str(item.trait_type):
                        f.write("c.%s = \'%s\'\n\n"% (key, self._config.trait_get([key])[key]))
                    elif 'Code' in str(item.trait_type):
                        f.write("c.%s = \"\"\" %s \"\"\" \n\n"% (key, self._config.trait_get([key])[key]))
                    else:
                        f.write("c.%s = %s\n\n"% (key, self._config.trait_get([key])[key]))
            except:
                print "could not write %s" %key
        f.close()

    def _graph_button_fired(self):
        mwf = get_workflow(self.config_class().uuid)
        wf= mwf.workflow_function(self.config_class())
        wf.write_graph()
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

def create_bips_config(workflow):
    from pyface.api import confirm, YES
    from traitsui.api import Handler, View, Item, UItem, HGroup, VGroup
    config = ConfigUI()
    class FooHandler(Handler):
        """Handler for the Foo class.
        This handler will
        (1) listen for changes to the 'filename' Trait of the object and
            update the window title when it changes; and
        (2) intercept request to close the window, and if the data is not saved,
            ask the user for confirmation.
        """

        def object_filename_changed(self, info):
            filename = info.object.Configuration_File
            if filename is "":
                filename = "<no file>"
            info.ui.title = "BIPS: " + filename

        def close(self, info, isok):
            # Return True to indicate that it is OK to close the window.
            if not info.object.saved:
                response = confirm(info.ui.control,
                                   "Value is not saved.  Are you sure you want to exit?")
                return response == YES
            else:
                return True
    view = View(Item('Configuration_File',style='readonly'),
                HGroup(
                    UItem('save_button', enabled_when='not saved and filename is not ""'),
                    UItem('save_as_button', enabled_when='not saved and filename is not ""'),
                    UItem('new_button'),
                    UItem('load_button', enabled_when='not config_changed')),
                VGroup(
                    UItem('run_button', enabled_when='saved and filename is not ""'),
                    UItem('py_button', enabled_when='saved and filename is not ""'),
                    UItem('graph_button')  #, enabled_when='filename is not ""')
                ),
                resizable=True,
                width=355,
                height=165,
                handler=FooHandler(),
                title="File Dialog")
    config.config_class = workflow.config_ui
    config.runfunc = workflow.workflow_main_function
    config.config_view = workflow.config_view
    config.configure_traits(view=view)



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

def get_config(uuid):
    wf = get_workflow(uuid)
    return wf.config_ui()

def get_workflows():
    return sorted(_workflow.items())

def list_workflows():
    for wf, value in get_workflows():
        print('%s %s' % (wf,
                         value['object'].help.split('\n')[1]))

def configure_workflow(uuid):
    wf = get_workflow(uuid)
    create_bips_config(wf)


def run_workflow(configfile):
    config = load_json(configfile)
    wf = get_workflow(config['uuid'])
    wf.workflow_main_function(configfile)


def display_workflow_info(uuid):
    wf = get_workflow(uuid)
    import pprint
    pprint.pprint(wf.get())


def query_workflows(query_str):
    pass

def debug_workflow(workflow):
    from traitsui.menu import OKButton, CancelButton
    names=workflow.list_node_names()
    print names
    class debug(HasTraits):
        pass
    foo = debug()
    for n in names:
        foo.add_class_trait(n.replace('.','___'),traits.Bool)

    view = foo.trait_view()
    view.resizable = True
    view.buttons = [OKButton, CancelButton]
    view.scrollable= True
    
    foo.configure_traits(view=view)
    bar = foo.get()
    for key,item in bar.iteritems():
        a = workflow.get_node(key.replace('___','.'))
        if item:
            a.run_without_submitting = True

    return workflow
