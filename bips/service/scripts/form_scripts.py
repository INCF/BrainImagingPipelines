import colander
from colander import Schema
from deform import Form
import deform
import traits.api as traits

class Schema(colander.MappingSchema):
    pass 

def getNode(_type,tr,config):
    from bips.workflows.flexible_datagrabber import Data, DataBase
    if _type == type(traits.Int()):
            col_type = colander.SchemaNode(colander.Int(),
                                           name=tr,description=config.trait(tr).desc)
    elif _type == type(traits.Float()):
        col_type = colander.SchemaNode(colander.Decimal(),name=tr)    
        
    elif _type == type(traits.String()) or _type==type(traits.Str()):
        col_type = colander.SchemaNode(colander.String(),name=tr)
        
    elif _type == type(traits.Enum('')):
        values=config.trait(tr).trait_type.values
        the_values = []
        for v in values:
            the_values.append((v,v))
        col_type = colander.SchemaNode(
            deform.Set(),
            widget=deform.widget.SelectWidget(values=the_values),
            name=tr)
    elif _type == type(traits.Bool()):
        col_type = colander.SchemaNode(colander.Boolean(),widget=deform.widget.CheckboxWidget(),name=tr)
    elif _type == type(traits.Code()):
        col_type = colander.SchemaNode(colander.String(),name=tr,widget=deform.widget.TextAreaWidget(cols=100,rows=20))
    elif _type == type(traits.Instance(Data,())):
        from bips.workflows.flexible_datagrabber import create_datagrabber_html_view
        col_type = create_datagrabber_html_view() 
    elif _type == type(traits.List()):
        col_type =get_list(_type,tr,config) 
    else:
        print "type: ", _type, "not found!"
        col_type = colander.SchemaNode(colander.String(),name=tr)
    return col_type

def get_form(config,mwf):
    from nipype.interfaces.traits_extension import isdefined
    if not isdefined(mwf.html_view):
        schema = colander.Schema()    
        all_traits = config.trait_names()  
        all_traits.remove('trait_added')
        all_traits.remove('trait_modified')
     
        for tr in all_traits:
            _type = type(config.trait(tr).trait_type)
        
            col_type = getNode(_type,tr,config)    
        
            schema.add(col_type)
    
        form = Form(schema,buttons = ('submit',),action='')   
    
        return form.render(appstruct=config.get())
    else:
        form = Form(mwf.html_view(),buttons = ('submit',),action='')
        return form.render()

def validator(form,value):
    pass

def get_list(thetype,tr,config):
    col_type = colander.SchemaNode(colander.Sequence(),
                                   name=tr,
                                   description=config.trait(tr).desc,
                                   widget=deform.widget.TextInputCSVWidget(cols=100,rows=1))
    col_type.add(colander.SchemaNode(colander.String()))
    return col_type
    
