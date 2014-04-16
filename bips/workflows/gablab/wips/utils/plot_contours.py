from bips.workflows.base import BaseWorkflowConfig
__author__ = 'keshavan'
from ....base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from ....flexible_datagrabber import Data, DataBase
"""
Part 1: Define a MetaWorkflow
"""

desc = """
Plot Contours
======================

Use for checking registration. Input mean, mask, in anatomical space (use workflow 0d)
with wm.mgz

"""
mwf = MetaWorkflow()
mwf.uuid = '42cb3b88804c11e2b92700259080ab1a'
mwf.tags = ['contour','registration']
mwf.help = desc

"""
Part 2: Define the config class & create_config function
"""

# config_ui
class config(BaseWorkflowConfig):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc='Workflow description')
    # Directories
    save_script_only = traits.Bool(False)
    sink_dir = Directory(mandatory=True,desc="Location to store results")

    # Subjects
    datagrabber = traits.Instance(Data, ())
    name= traits.String('images')
    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    c.datagrabber = Data(['contour','mask','mean'])
    sub = DataBase()
    sub.name="subject_id"
    sub.values=[]
    sub.iterable=True
    c.datagrabber.fields.append(sub)
    c.datagrabber.field_template = dict(contour='%s/*',mask='%s/*',mean='%s/*')
    c.datagrabber.template_args = dict(contour=[['subject_id']],
                                       mask=[['subject_id']],
                                       mean=[['subject_id']])
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
            Item(name='crash_dir'),Item('sink_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin',enabled_when='not save_script_only'),Item('save_script_only'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),Item('name'),
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

def contour_image(contour,mean,mask,title=''):
    import nibabel as nib
    import numpy as np
    import nipy.labs.viz as viz
    import os
    import matplotlib.pyplot as plt
    def get_data(imfile):
        img = nib.load(imfile)
        data, affine = img.get_data(), img.get_affine()
        return data,affine
    bold_data, nat_aff = get_data(mean)
    wm_data, _ = get_data(contour)
    brain_mask, _ = get_data(mask)
    f = plt.figure(figsize=(12, 6))
    kwargs = dict(figure=f, draw_cross=False, annotate=False, slicer="y")
    for cut_coords, ax_pos in zip(np.linspace(-50, 70, 8).reshape(2, 4), [(0, 0, 1, .5), (0, .5, 1, .5)]):
        slicer = viz.plot_anat(bold_data, nat_aff, cut_coords=cut_coords, axes=ax_pos, **kwargs)
        slicer.contour_map(wm_data, nat_aff, colors="palegreen")
        slicer.contour_map(brain_mask, nat_aff, colors="tomato")
        plt.gca().set_title("%s"%title, size=14)
    outfile = os.path.abspath('%s_contour.png'%title)
    plt.savefig(outfile)
    return outfile

def contour_workflow(c,name='take_mean'):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu
    import nipype.interfaces.io as nio

    wf = pe.Workflow(name=name)
    datagrabber = c.datagrabber.create_dataflow()
    subject_names = datagrabber.get_node('subject_id_iterable')
    sink = pe.Node(nio.DataSink(),name='sinker')
    sink.inputs.base_directory = c.sink_dir
    contour = pe.Node(niu.Function(input_names=['contour','mean','mask','title'],output_names=['outfile'],
        function=contour_image),name='plot_contour')
    if subject_names:
        wf.connect(subject_names,'subject_id',sink,'container')
        subs = lambda x: [('_subject_id_%s'%x,'')]
        wf.connect(subject_names,('subject_id',subs),sink,'substitutions')
        wf.connect(subject_names,'subject_id',contour,'title')

    wf.connect(contour,'outfile',sink,'%s.@image'%c.name)
    wf.connect(datagrabber,'datagrabber.contour', contour, 'contour')
    wf.connect(datagrabber,'datagrabber.mean', contour, 'mean')
    wf.connect(datagrabber,'datagrabber.mask', contour, 'mask')
    wf.base_dir = c.working_dir
    return wf

    mwf.workflow_function = contour_workflow

def main(config_file):

    c = load_config(config_file,create_config)
    a = contour_workflow(c)

    a.config = {'execution' : {'crashdump_dir' : c.crash_dir, 'job_finished_timeout' : 14}}

    if c.use_advanced_options:
        exec c.advanced_script

    from nipype.utils.filemanip import fname_presuffix

    a.export(fname_presuffix(config_file,'','_script_').replace('.json',''))

    if c.save_script_only:
        return 0

    if c.run_using_plugin:
        a.run(plugin=c.plugin,plugin_args=c.plugin_args)
    else:
        a.run()

mwf.workflow_main_function = main

register_workflow(mwf)