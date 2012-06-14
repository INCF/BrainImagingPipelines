# -*- coding: utf-8 -*-
# <nbformat>3</nbformat>

# <codecell>

import os

from surfer import Brain
import scipy.io as sio
import numpy as np
from mayavi import mlab
from tables import openFile

from .base import MetaWorkflow, load_config, register_workflow

"""
MetaWorkflow
"""
mwf = MetaWorkflow()
mwf.help = """
Resting State Visualization
===========================

"""
mwf.uuid = '974a6910992311e18318001e4fb1404c'
mwf.tags = ['resting','visualization','correlation']

"""
Config
"""
from traits.api import HasTraits, Directory
import traits.api as traits

class config(HasTraits):
    files = traits.List(traits.File)
    pattern = traits.Str()
    base_directory = Directory
    use_pattern = traits.Bool(False)
    hemi = traits.Enum('lh','rh')
    surface = traits.Enum('white','inflated')
    target = traits.Enum('fsaverage5','fsaverage4','fsaverage')

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    return c

mwf.config_ui = create_config

"""
View
"""

def create_view():
    from traitsui.api import View, Item, Group
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='uuid', style='readonly'),
        Item(name='desc', style='readonly'),
        label='Description', show_border=True),
        Group(Item(name='use_pattern'),
            Item(name='pattern',enabled_when='use_pattern'),
            Item(name='base_directory',enabled_when='use_pattern'),
            Item(name='files', enabled_when='not use_pattern'),
            Item(name='hemi'), Item(name='surface'),
            Item(name='target'),
            label='Advanced',show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Workflow
"""

overlay_added = False
brains = []
corrmats = []

def do_overlay(idx):
    global overlay_added
    global brains
    global corrmats
    if overlay_added:
        for brain in brains:
            brain.overlays['mean'].remove()
            brain.foci['foci'].remove()
        overlay_added = False
    for i, brain in enumerate(brains):
        mlab.figure(brain._f)
        val = corrmats[i][idx]
        val[np.isnan(val)] = 0
        brain.add_overlay(val, min=0.3, max=1.0, sign='abs', name='mean')
        brain.add_foci(idx, coords_as_verts=True, name='foci', color=(.46,0.7,0.87))
    overlay_added = True

def picker_callback(picker_object):
    do_overlay(picker_object.point_id)

def display_matrices(filenames, target, hemi, surface):
    print '\n'.join(filenames)
    for name in filenames:
        try:
            corrmat = sio.loadmat(name)['corrmat']
        except:
            try:
                corrmat = np.load(name)['corrmat']
            except:
                try:
                    corrmat = np.load(name)['arr_0']
                except:
                    try:
                        corrmat = np.load(name)['avgcorr']
                    except:
                        h5file = openFile(name, 'r')
                        corrmat = h5file.root.corrmat
        corrmats.append(corrmat)
    for idx, name in enumerate(filenames):
        path, name = os.path.split(name)
        br = Brain(target, hemi, surface, title=name+'-%d' % idx)
        brains.append(br)
        for brain in brains[:-1]:
            mlab.sync_camera(br._f, brain._f)
            mlab.sync_camera(brain._f, br._f)
        br._f.on_mouse_pick(picker_callback)
    mlab.show()

"""
Main
"""

def main(config_file):

    args = load_config(config_file,config)
    if args.use_pattern:
        from glob import glob
        files = glob(os.path.join(args.base_directory,args.pattern))
        if not files:
            print "Couldn't match pattern!"
        print files
    else:
        files = args.files
    display_matrices(files, args.target, args.hemi, args.surface)

mwf.workflow_main_function = main

"""
Register
"""

register_workflow(mwf)