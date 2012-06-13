# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Perform fixed effects analysis on runs processed by preproc.py
"""

import os                                    # system functions
from nipype.workflows.fmri.fsl.estimate import create_fixed_effects_flow
import nipype.interfaces.io as nio           # i/o routines
import nipype.interfaces.fsl as fsl          # fsl
import nipype.interfaces.utility as util     # utility
import nipype.pipeline.engine as pe          # pypeline engine
from .base import MetaWorkflow, load_config, register_workflow

from .workflow10 import config as baseconfig

import traits.api as traits

"""
Part 1: MetaWorkflow
"""

desc = """
Fixed Effects fMRI workflow
=====================================

"""
mwf = MetaWorkflow()
mwf.uuid = '7263507a8fe211e1b274001e4fb1404c'
mwf.tags = ['fMRI','task','fixed effects']
mwf.help = desc

"""
Part 2: Config
"""

class config(baseconfig):
    first_level_config = traits.File
    overlay_thresh = traits.BaseTuple(traits.Float,traits.Float)
    num_runs = traits.Int

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    return c

mwf.config_ui = create_config

"""
Part 3: View
"""

def create_view():
    from traitsui.api import View, Item, Group, CSVListEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='uuid', style='readonly'),
        Item(name='desc', style='readonly'),
        label='Description', show_border=True),
        Group(Item(name='working_dir'),
            Item(name='sink_dir'),
            Item(name='crash_dir'),
            Item(name='json_sink'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'),
            label='Execution Options', show_border=True),
        Group(Item(name='subjects', editor=CSVListEditor()),
            label='Subjects', show_border=True),
        Group(Item(name='preproc_config'),
              Item(name='first_level_config'),
            label = 'Preproc & First Level Info'),
        Group(Item('overlay_thresh'),
              Item(name='num_runs'),
            label='Fixed Effects'),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Part 4: Construct Workflow
"""

def getinfo(cons, info):
    numruns = len(info)
    print numruns  # dbg
    numcon = len(cons)
    info = dict(copes=[['subject_id', 'fwhm', range(1, numcon + 1)]],
                varcopes=[['subject_id', 'fwhm', range(1, numcon + 1)]],
                dof_files=[['subject_id', 'fwhm']],
                mask_file=[['subject_id']])
    return info


def num_copes(files):
    if type(files[0]) is list:
        return len(files[0])
    else:
        return len(files)


def getsubs(subject_id, cons):
    subs = [('_subject_id_%s/' % subject_id, ''),
            ('_runs', '/runs'),
            ('_fwhm', 'fwhm')]
    for i, con in enumerate(cons):
        subs.append(('_flameo%d/cope1' % i, 'cope_%s' % con[0]))
        subs.append(('_flameo%d/varcope1' % i, 'varcope_%s' % con[0]))
        subs.append(('_flameo%d/tstat1' % i, 'tstat_%s' % con[0]))
        subs.append(('_flameo%d/zstat1' % i, 'zstat_%s' % con[0]))
        subs.append(('_flameo%d/res4d' % i, 'res4d_%s' % con[0]))
        subs.append(('_ztop%d/zstat1_pval' % i, 'pval_%s' % con[0]))
        subs.append(('_slicestats%d/zstat1_overlay.png' % i,
                     'zstat_overlay%d_%s.png' % (i, con[0])))
    return subs


def create_overlay_workflow(c,name='overlay'):
    # Setup overlay workflow

    overlay = pe.Workflow(name='overlay')

    inputspec = pe.Node(util.IdentityInterface(fields=['subject_id',
                                                       'fwhm',
                                                       'stat_image']),
                        name='inputspec')

    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
                                                   outfields=['meanfunc']),
                         name='datasource')

    datasource.inputs.base_directory = c.sink_dir
    datasource.inputs.template = '*'
    datasource.inputs.sort_filelist = True
    datasource.inputs.field_template = dict(meanfunc='%s/preproc/meanfunc/*.nii.gz')
    datasource.inputs.template_args = dict(meanfunc=[['subject_id']])

    overlaystats = pe.MapNode(interface=fsl.Overlay(),
                              name="overlaystats",
                              iterfield=['stat_image'])

    slicestats = pe.MapNode(interface=fsl.Slicer(),
                            name="slicestats",
                            iterfield=['in_file'])

    slicestats.inputs.all_axial = True
    slicestats.inputs.image_width = 512
    overlaystats.inputs.show_negative_stats = True
    overlaystats.inputs.auto_thresh_bg = True
    overlaystats.inputs.stat_thresh = c.overlay_thresh

    overlay.connect(inputspec, 'subject_id', datasource, 'subject_id')
    #overlay.connect(inputspec, 'fwhm', datasource, 'fwhm')
    overlay.connect(inputspec, 'stat_image', overlaystats, 'stat_image')
    overlay.connect(datasource, 'meanfunc', overlaystats, 'background_image')
    overlay.connect(overlaystats, 'out_file', slicestats, 'in_file')

    return overlay

from .workflow10 import create_config as first_config
from .workflow1 import create_config as prep_config

foo0 = first_config()
foo1 = prep_config()

def create_fixedfx(c, first_c=foo0, prep_c=foo1, name='fixedfx'):
    selectnode = pe.Node(interface=util.IdentityInterface(fields=['runs']),
                         name='idselect')

    selectnode.iterables = ('runs', [range(0,c.num_runs)]) # this is really bad.

    copeselect = pe.MapNode(interface=util.Select(), name='copeselect',
                            iterfield=['inlist'])

    varcopeselect = pe.MapNode(interface=util.Select(), name='varcopeselect',
                               iterfield=['inlist'])

    dofselect = pe.Node(interface=util.Select(), name='dofselect')

    if c.test_mode:
        infosource = pe.Node(interface=util.IdentityInterface(fields=['subject_id','fwhm']), name="infosource")
        infosource.iterables = [('subject_id', [c.subjects[0]]),
                                ('fwhm',prep_c.fwhm)]
    else:
        infosource = pe.Node(interface=util.IdentityInterface(fields=['subject_id','fwhm']), name="infosource")
        infosource.iterables = [('subject_id', c.subjects),('fwhm',prep_c.fwhm)]

    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id','fwhm'],
                                                   outfields=['copes', 
                                                              'varcopes',
                                                              'dof_files',
                                                              'mask_file']),
                         name = 'datasource')

    datasource.inputs.base_directory = c.sink_dir
    datasource.inputs.template ='*'
    datasource.inputs.sort_filelist = True
    datasource.inputs.field_template = dict(copes='%s/modelfit/contrasts/fwhm_%s/_estimate_contrast*/cope%02d*.nii.gz',
                                            varcopes='%s/modelfit/contrasts/fwhm_%s/_estimate_contrast*/varcope%02d*.nii.gz',
                                            dof_files='%s/modelfit/dofs/fwhm_%s/*/*',
                                            mask_file='%s/preproc/mask/*.nii')

    fixedfx = create_fixed_effects_flow()

    fixedfxflow = pe.Workflow(name=name)
    fixedfxflow.config = {'execution' : {'crashdump_dir' : c.crash_dir}}

    overlay = create_overlay_workflow(c,name='overlay')

    subjectinfo = pe.Node(util.Function(input_names=['subject_id'], output_names=['output']), name='subjectinfo')
    subjectinfo.inputs.function_str = first_c.subjectinfo

    contrasts = pe.Node(util.Function(input_names=['subject_id'], output_names=['contrasts']), name='getcontrasts')
    contrasts.inputs.function_str = first_c.contrasts

    get_info = pe.Node(util.Function(input_names=['cons','info'], output_names=['info'], function=getinfo), name='getinfo')
    get_subs = pe.Node(util.Function(input_names=['subject_id','cons'], output_names=['subs'], function=getsubs), name='getsubs')

    fixedfxflow.connect(infosource, 'subject_id',           datasource, 'subject_id')

    #fixedfxflow.connect(infosource, ('subject_id',getinfo, c.getcontrasts, c.subjectinfo), datasource, 'template_args')

    fixedfxflow.connect(infosource, 'subject_id', contrasts, 'subject_id')
    fixedfxflow.connect(infosource, 'subject_id', subjectinfo, 'subject_id')
    fixedfxflow.connect(contrasts, 'contrasts', get_info, 'cons')
    fixedfxflow.connect(subjectinfo, 'output', get_info, 'info')
    fixedfxflow.connect(get_info,'info',datasource,'template_args')

    fixedfxflow.connect(infosource, 'fwhm',                 datasource, 'fwhm')
    fixedfxflow.connect(datasource,'copes',                 copeselect,'inlist')
    fixedfxflow.connect(selectnode,'runs',                  copeselect,'index')
    fixedfxflow.connect(datasource,'copes',                   fixedfx,'inputspec.copes')
    fixedfxflow.connect(datasource,'varcopes',              varcopeselect,'inlist')
    fixedfxflow.connect(selectnode,'runs',                  varcopeselect,'index')
    fixedfxflow.connect(datasource,'varcopes',                fixedfx,'inputspec.varcopes')
    fixedfxflow.connect(datasource,'dof_files',             dofselect,'inlist')
    fixedfxflow.connect(selectnode,'runs',                  dofselect,'index')
    fixedfxflow.connect(datasource,'dof_files',                    fixedfx,'inputspec.dof_files')
    fixedfxflow.connect(datasource,('copes',num_copes),       fixedfx,'l2model.num_copes')
    fixedfxflow.connect(datasource,'mask_file',             fixedfx,'flameo.mask_file') 
    fixedfxflow.connect(infosource, 'subject_id',           overlay, 'inputspec.subject_id')
    fixedfxflow.connect(infosource, 'fwhm',                 overlay, 'inputspec.fwhm')
    fixedfxflow.connect(fixedfx, 'outputspec.zstats',       overlay, 'inputspec.stat_image')



    datasink = pe.Node(interface=nio.DataSink(), name="datasink")
    datasink.inputs.base_directory = c.sink_dir
    # store relevant outputs from various stages of the 1st level analysis
    fixedfxflow.connect([(infosource, datasink,[('subject_id','container'),
                                          #(('subject_id', getsubs, c.getcontrasts), 'substitutions')
                                          ]),
                   (fixedfx, datasink,[('outputspec.copes','fixedfx.@copes'),
                                       ('outputspec.varcopes','fixedfx.@varcopes'),
                                       ('outputspec.tstats','fixedfx.@tstats'),
                                       ('outputspec.zstats','fixedfx.@zstats'),
                                       ('outputspec.res4d','fixedfx.@pvals'),
                                       ])
                   ])
    fixedfxflow.connect(infosource,'subject_id', get_subs, 'subject_id')
    fixedfxflow.connect(contrasts,'contrasts', get_subs, 'cons')
    fixedfxflow.connect(get_subs, 'subs', datasink, 'substitutions')
    fixedfxflow.connect(overlay, 'slicestats.out_file', datasink, 'overlays')
    return fixedfxflow

mwf.workflow_function = create_fixedfx

"""
Part 5: Main
"""

def main(config_file):

    c = load_config(config_file, create_config)
    from .workflow10 import create_config as first_config
    first_c = load_config(c.first_level_config, first_config)
    from .workflow1 import create_config as prep_config
    prep_c = load_config(first_c.preproc_config, prep_config)

    fixedfxflow = create_fixedfx(c,first_c, prep_c)
    fixedfxflow.base_dir = c.working_dir

    if c.test_mode:
        fixedfxflow.write_graph()

    if c.run_using_plugin:
        fixedfxflow.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        fixedfxflow.run()
    #fixedfxflow.write_graph(graph2use='flat')


mwf.workflow_main_function = main

"""
Part 6: Register
"""
register_workflow(mwf)