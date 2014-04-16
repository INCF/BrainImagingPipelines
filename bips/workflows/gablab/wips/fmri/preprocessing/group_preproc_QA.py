from .....base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from .....flexible_datagrabber import Data, DataBase
from bips.workflows.base import BaseWorkflowConfig
"""
Part 1: Define a MetaWorkflow
"""

desc = """
Group Task/Resting fMRI QA json
============================================
"""
mwf = MetaWorkflow()
mwf.uuid = '26637830708311e2a24100259080ab1a'
mwf.tags = ['group','task','fMRI','preprocessing','QA', 'resting']
mwf.uses_outputs_of = ['63fcbb0a890211e183d30023dfa375f2','7757e3168af611e1b9d5001e4fb1404c']
mwf.script_dir = 'fmri'
mwf.help = desc

"""
Part 2: Define the config class & create_config function
"""

# config_ui
class config(BaseWorkflowConfig):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc='Workflow description')
    # Directories
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")
    save_script_only = traits.Bool(False)

    # Subjects

    datagrabber = traits.Instance(Data, ())
    group_name = traits.String('preproc')
    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    c.datagrabber = Data(['preproc_metrics'])
    sub = DataBase()
    sub.name="subject_id"
    sub.value=['sub01','sub02']
    sub.iterable=True
    c.datagrabber.fields.append(sub)
    c.datagrabber.field_template = dict(preproc_metrics='%s/preproc_metrics.json')
    c.datagrabber.template_args = dict(preproc_metrics=[['subject_id']])

    return c

mwf.config_ui = create_config

"""
Part 3: Create a View
"""

def create_view():
    from traitsui.api import View, Item, Group
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='uuid', style='readonly'),
        Item(name='desc', style='readonly'),
        label='Description', show_border=True),
        Group(Item(name='working_dir'),
            Item(name='sink_dir'),
            Item(name='crash_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin',enabled_when='not save_script_only'),Item('save_script_only'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),Item('group_name'),
            label='Subjects', show_border=True),
        Group(Item(name='use_advanced_options'),
            Item(name='advanced_script',enabled_when='use_advanced_options'),
            label='Advanced',show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Part 4: Workflow Construction
"""

def extract_snr(table,name):
    import numpy as np
    names = [ b[0] for b in table[0]]
    try:
        idx = names.index(name)
    except:
        idx = None
    if not idx == None:
        return table[0][idx][1]
    else:
        return 0    

def extract_art(art):
    art = art[0]
    motion_outliers = int(art[5][1])
    intensity_outliers = int(art[7][1])
    common_outliers = int(art[6][1])
    total_outliers = motion_outliers+intensity_outliers+common_outliers
    return motion_outliers,intensity_outliers,common_outliers,total_outliers

def group_things(list_of_jsons):
    """Fields to save in output csv
- Subject id
- Num Outliers
- Mincost
- All tsnr values (0 for missing values)
"""
    import numpy as np
    from nipype.utils.filemanip import load_json
    from bips.workflows.gablab.wips.fmri.preprocessing.group_preproc_QA import extract_snr, extract_art
    #from bips.workflows.group_preproc_QA import extract_art

    snr_names = []
    snr_dict = {}

    for tmp in list_of_jsons:
        a = load_json(tmp)
        names = [ b[0] for b in a['SNR_table'][0][1:]]
        snr_names += names
        snr_names = np.unique(snr_names).tolist()
 
    for name in snr_names:
        snr_dict[name] = []

    mincost = []
    common_outliers = []
    total_outliers = []
    intensity_outliers = []
    motion_outliers = []
    subject_id = []

    all_fields = ['subject_id','total_outliers','mincost','motion_outliers','intensity_outliers','common_outliers']+snr_names
    dtype=[('subject_id','|S20')]+[(str(n),'f4') for n in all_fields[1:]]
    arr = np.zeros(len(list_of_jsons), dtype=dtype)
    
    for fi in list_of_jsons:
        f = load_json(fi)
        subject_id.append(f['subject_id'])
        mot,inten,com,out = extract_art(f['art'])
        motion_outliers.append(mot)
        intensity_outliers.append(inten)
        common_outliers.append(com)
        total_outliers.append(out)
        mincost.append(f['mincost'][0])
        for n in snr_names:
            t = extract_snr(f['SNR_table'],n)
            snr_dict[n].append(t)

    arr['subject_id'] = subject_id
    arr['total_outliers'] = total_outliers
    arr['mincost'] = mincost
    arr['motion_outliers'] = motion_outliers
    arr['intensity_outliers'] = intensity_outliers
    arr['common_outliers'] = common_outliers

    for key,item in snr_dict.iteritems():
        arr[key] = item
       
    import os
    from matplotlib.mlab import rec2csv
    outfile = os.path.abspath('grouped_metrics.csv')
    rec2csv(arr,outfile)
    return outfile

def group_preproc_metrics(c,name='group_metrics'):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    import nipype.interfaces.io as nio
    # Define Workflow
        
    workflow =pe.Workflow(name=name)
    datagrabber = c.datagrabber.create_dataflow()

    grouper = pe.Node(util.Function(input_names=['list_of_jsons'],output_names=['outfile'],function=group_things),name='group_metrics')
    
    sinker = pe.Node(nio.DataSink(),name='sinker')
    sinker.inputs.base_directory = c.sink_dir
    workflow.connect(datagrabber,'datagrabber.preproc_metrics',grouper,'list_of_jsons')
    workflow.connect(grouper,'outfile',sinker,'metrics.%s'%c.group_name)

    return workflow

mwf.workflow_function = group_preproc_metrics
 
def main(config_file):

    c = load_config(config_file,create_config)

    a = group_preproc_metrics(c)
    a.base_dir = c.working_dir
    a.config = {'execution' : {'crashdump_dir' : c.crash_dir, 'job_finished_timeout' : 14}}

    if c.use_advanced_options:
        exec c.advanced_script

    from nipype.utils.filemanip import fname_presuffix
    a.export(fname_presuffix(config_file,'','_script_').replace('.json',''))

    if c.run_using_plugin:
        a.run(plugin=c.plugin,plugin_args=c.plugin_args)
    else:
        a.run()

mwf.workflow_main_function = main

"""
Part 6: Register the Workflow
"""

register_workflow(mwf)

 











