# flexible datagrabber workflow
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits

import os
try:
    os.environ["DISPLAY"]
    use_view = True
except KeyError:
    use_view = False

import os

def get_view():
    from traitsui.api import View, Item, Group
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='fields'),
        Item(name='base_directory'),
        Item(name='template'),
        Item(name='field_template'),
        Item(name='template_args')),
        Item(name='sort'),
        Item(name='check'),
        buttons=[OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view
    
def create_datagrabber_html_view():
    import colander
    class Input(colander.MappingSchema):
        name = colander.SchemaNode(colander.String())
        value = colander.SchemaNode(colander.String())
        iterable = colander.SchemaNode(colander.Boolean(),name='iterable')

    class Inputs(colander.SequenceSchema):
        inputs = Input()

    class Grabber(colander.MappingSchema):
        base_directory = colander.SchemaNode(colander.String())
        template = colander.SchemaNode(colander.String())
        field_template = colander.SchemaNode(colander.String())
        template_args = colander.SchemaNode(colander.String())
        fields = Inputs()

    class DataGrabber(colander.Schema):
        datagrabber = Grabber()
        
    view = DataGrabber()
    return view    

class DataBase(HasTraits):
    name = traits.Str('name')
    values = traits.List([''],traits.Str)
    iterable= traits.Bool(False)
    if use_view:
        from traitsui.api import View, Item, Group, CSVListEditor, TupleEditor, EnumEditor
        from traitsui.menu import OKButton, CancelButton
        view = View(Group(Item(name='name'), Item(name='values', editor=CSVListEditor()), Item(name='iterable')),
                    buttons=[OKButton, CancelButton],
                    resizable=True,
                    width=1050)
    
class Data(HasTraits):
    fields = traits.List(traits.Instance(DataBase, ()))
    base_directory = Directory(os.path.abspath('.'))
    template = traits.Str('*')     
    template_args = traits.Dict({"a":"b"},usedefault=True) 
    field_template = traits.Dict({"key":["hi"]},usedefault=True)
    sort = traits.Bool(True)

    if use_view:
        check = traits.Button("Check")
        view = get_view()

    def __init__(self,outfields=None):
        if outfields:
            d_ft = {}
            d_ta = {}
            for out in outfields:
                d_ft[out] = '%s'
                d_ta[out] = [['name']]
            self.field_template = d_ft
            self.template_args = d_ta
            self.outfields = outfields
       
    def _get_infields(self):
        infields = []
        for f in self.fields:
            infields.append(f.name)
        return infields
    
    def _add_iterable(self,field):
        import nipype.interfaces.utility as niu
        import nipype.pipeline.engine as pe
        it = pe.Node(niu.IdentityInterface(fields=[field.name]),
                     name=field.name+"_iterable")
        it.iterables = (field.name, field.values)
        return it
        
    def _set_inputs(self):
        self._node_added = False
        set_dict = {}
        for f in self.fields:
            if not f.iterable:
                set_dict[f.name] = f.values
            else:
                it = self._add_iterable(f)
                self._node_added = True
                self._wk.connect(it,f.name,self._dg,f.name)
        self._dg.inputs.trait_set(**set_dict)
        
    def create_dataflow(self):
        import nipype.interfaces.io as nio
        import nipype.pipeline.engine as pe
        self._wk = pe.Workflow(name='custom_datagrabber')
        self._dg = pe.Node(nio.DataGrabber(outfields = self.outfields, 
                                     infields = self._get_infields(),sort_filelist=self.sort),
                                     name='datagrabber') 
        self._set_inputs()
        self._dg.inputs.base_directory = self.base_directory
        self._dg.inputs.field_template = self.field_template
        self._dg.inputs.template_args = self.template_args
        self._dg.inputs.template = self.template 
        if not self._node_added:
            self._wk.add_nodes([self._dg])                                
        return self._wk
    
    def get_fields(self):
        foo=self.get()
        d = {}
        for key, item in foo.iteritems():
            if not key.startswith('_'):
                if isinstance(item,list):
                    d[key] = []
                    for it in item:
                        if isinstance(it,DataBase):
                            d[key].append(it.get())
                        else:
                            d[key].append(it)
                else:
                    d[key] = item 
        return d
        
    def set_fields(self,d):
        for key, item in d.iteritems():
            if not key=="fields":
                self.set(**{key: item})
            else:
                foo = []
                for f in item:
                    tmp = DataBase()
                    tmp.set(**f)
                    foo.append(tmp)
                self.set(**{key:foo})

    def _check_fired(self):
        dg = self.create_dataflow()
        dg.run()

if __name__ == "__main__":    
    a = Data(['func','struct'])
    a.fields = []
    subs = DataBase()
    subs.name = 'subjects'
    subs.values = ['sub01','sub02','sub03']
    subs.iterable = True
    a.fields.append(subs)
    a.template_args = {"func":[["subjects"]], "struct":[["subjects"]]}
    a.base_directory = os.path.abspath('.')
    #a.configure_traits()
    dg = a.create_dataflow()
    d = a.get_fields()
    from nipype.utils.filemanip import save_json
    from .bips.workflows.base import load_json
    save_json("test.json",d)
    foo = load_json("test.json")
    b = Data()
    b.set_fields(foo)
    b.configure_traits()
    

