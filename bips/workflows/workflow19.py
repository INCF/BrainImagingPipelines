import os
from glob import glob
import subprocess
import sys
import numpy as np
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio
import nipype.interfaces.freesurfer as fs
import nipype.pipeline.engine as pe
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits
from .base import MetaWorkflow, load_config, register_workflow, debug_workflow

"""
Part 1: MetaWorkFlow
"""

mwf = MetaWorkflow()
mwf.help = """
Dicom Conversion
================

"""
mwf.uuid = 'df490522b5ad11e19a4d001e4fb1404c'
mwf.tags = ['convert','dicom']
mwf.script_dir = 'u0a14c5b5899911e1bca80023dfa375f2'

"""
Part 2: Config
"""

class config(HasTraits):

    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    base_dir = Directory(mandatory=True, desc='Base directory of data. (Should be subject-independent)')
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")

    # Execution
    run_using_plugin = Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.Enum("PBS", "PBSGraph","MultiProc", "SGE", "Condor",
        usedefault=True,
        desc="plugin to use, if run_using_plugin=True")
    plugin_args = traits.Dict({"qsub_args": "-q many"},
        usedefault=True, desc='Plugin arguments.')
    test_mode = Bool(False, mandatory=False, usedefault=True,
        desc='Affects whether where and if the workflow keeps its \
                            intermediary files. True to keep intermediary files. ')
    #Subjects
    subjects= traits.List(traits.Str, mandatory=True, usedefault=True,
        desc="Subject id's. Bips expects dicoms to be organized by subject id's")
    dicom_dir_template = traits.String('%s/dicoms/')

    #Conversion Options
    embed_meta = traits.Bool(True)
    info_only = traits.Bool(True)
    use_heuristic = traits.Bool(False)
    heuristic_file = traits.File(desc="heuristic file")

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
    from traitsui.api import View, Item, Group, CSVListEditor, TupleEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='uuid', style='readonly'),
        Item(name='desc', style='readonly'),
        label='Description', show_border=True),
        Group(Item(name='working_dir'),
            Item(name='sink_dir'),
            Item(name='crash_dir'),
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'),
            label='Execution Options', show_border=True),
        Group(Item(name='subjects', editor=CSVListEditor()),
            Item(name='base_dir'),
            Item(name='dicom_dir_template'),
            label='Subjects', show_border=True),
        Group(Item('info_only'),
            Item('use_heuristic',enabled_when="not info_only"),
            Item('heuristic_file',enabled_when="use_heuristic"),
            Item('embed_meta',enabled_when='not info_only')),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Part 4: Construct Workflow
"""

def get_subjectdcmdir(subjid, dcm_template):
    """Return the TrioTim directory for each subject

    Assumes that this directory is inside the subjects directory
    """
    from glob import glob
    dirlist = glob(dcm_template%subjid)
    if not dirlist:
        raise IOError('Directory %s does not exist'%(dcm_template%subjid))
    return dirlist[0]

"""
run a workflow to get at the dicom information
"""

def get_dicom_info(c):
    """Get the dicom information for each subject

    """
    subjnode = pe.Node(interface=util.IdentityInterface(fields=['subject_id']),
                       name='subjinfo')
    if c.test_mode:
        subjnode.iterables = ('subject_id', [c.subjects[0]])
    else:
        subjnode.iterables = ('subject_id', c.subjects)

    infonode = pe.Node(interface=fs.ParseDICOMDir(sortbyrun=True,
                                                  summarize=True),
                       name='dicominfo')

    datasink = pe.Node(interface=nio.DataSink(parameterization=False), name='datasink')
    datasink.inputs.base_directory = c.sink_dir

    infopipe = pe.Workflow(name='extractinfo')
    infopipe.base_dir = os.path.join(c.working_dir,'workdir')
    infopipe.connect([(subjnode, datasink,[('subject_id','container')]),
                      (subjnode, infonode,[(('subject_id', get_subjectdcmdir, os.path.join(c.base_dir,c.dicom_dir_template)),
                                           'dicom_dir')]),
                      (infonode, datasink,[('dicom_info_file','@info')]),
                      ])
    #infopipe.config = {'execution' : {'stop_on_first_crash' : True}}
    if c.run_using_plugin:
        infopipe.run(plugin=c.plugin,plugin_args=c.plugin_args)
    else:
        infopipe.run()


def isMoco(dcmfile):
    """Determine if a dicom file is a mocoseries
    """
    import subprocess
    cmd = ['mri_probedicom', '--i', dcmfile, '--t', '8', '103e']
    proc  = subprocess.Popen(cmd,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    return stdout.strip().startswith('MoCoSeries')


def convert_dicoms(sid, dicom_dir_template, outputdir, queue=None, heuristic_func=None,
                   extension = None):

    import os
    from nipype.utils.filemanip import load_json,save_json

    sdir = dicom_dir_template%sid
    tdir = os.path.join(outputdir, sid)
    infofile =  os.path.join(tdir,'%s.auto.txt' % sid)
    editfile =  os.path.join(tdir,'%s.edit.txt' % sid)
    if os.path.exists(editfile) and heuristic_func:
        info = load_json(editfile)
    elif not heuristic_func:
        pass
    else:
        infofile =  os.path.join(tdir,'%s.auto.txt' % sid)
        info = heuristic_func(sdir, os.path.join(tdir,'dicominfo.txt'))
        save_json(infofile, info)

    if heuristic_func:
        for key in info:
            if not os.path.exists(os.path.join(tdir,key)):
                os.mkdir(os.path.join(tdir,key))
            for idx, ext in enumerate(info[key]):
                convertcmd = ['dcmstack', sdir,'--dest-dir', os.path.join(tdir,key),
                              '--file-ext', '*-%d-*'%ext, '--force-read', '-v', '--output-name', key+'%03d'%(idx+1)]
                print convertcmd
                convertcmd = ' '.join(convertcmd)
                print convertcmd
                os.system(convertcmd)
    else:
        convertcmd = ['dcmstack', sdir, '--dest-dir', os.path.join(outputdir,sid),
                      '--force-read','-v','--embed-meta']
        convertcmd = ' '.join(convertcmd)
        print convertcmd
        os.system(convertcmd)
    return 1


def convert_wkflw(c,heuristic_func=None):
    wk = pe.Workflow(name='convert_workflow')
    infosource=pe.Node(util.IdentityInterface(fields=['subject_id']),name='subject_names')
    convert = pe.Node(util.Function(input_names=['sid', 'dicom_dir_template',
                                                 'outputdir', 'queue',
                                                 'heuristic_func','extension'],
                                    output_names=['out'],
                                    function=convert_dicoms),
                      name='converter')
    if not c.test_mode:
        infosource.iterables = ("subject_id",c.subjects)
    else:
        infosource.iterables = ("subject_id",[c.subjects[0]])

    wk.connect(infosource,"subject_id",convert,"sid")
    convert.inputs.dicom_dir_template = os.path.join(c.base_dir,c.dicom_dir_template)
    convert.inputs.outputdir = c.sink_dir
    convert.inputs.queue = None
    convert.inputs.heuristic_func = heuristic_func
    convert.inputs.extension= None
    wk.base_dir = c.working_dir
    return wk

mwf.workflow_function = convert_wkflw

"""
Part 5: Main
"""

def main(config_file):
    c = load_config(config_file,config)

    if c.heuristic_file and c.use_heuristic:
        path, fname = os.path.split(os.path.realpath(c.heuristic_file))
        sys.path.append(path)
        mod = __import__(fname.split('.')[0])
        heuristic_func = mod.infotodict
    else:
        heuristic_func=None

    get_dicom_info(c)
    if not c.info_only:
        wk = convert_wkflw(c,heuristic_func)
        if c.run_using_plugin:
            wk.run(plugin=c.plugin,plugin_args=c.plugin_args)
        else:
            wk.run()
    return 1

mwf.workflow_main_function = main

"""
Part 6: Register
"""

register_workflow(mwf)
