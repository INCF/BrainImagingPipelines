import bips
import os
import tempfile
from tools.interfacedocgen import help
from nipype.utils.misc import trim

base_dir = os.path.abspath('doc/workflows/generated')

workflows = bips.workflows.get_workflows()
container='generated'
all_wf_path = os.path.join(base_dir,"all.rst")
all_wf = open(all_wf_path,'w')
title=""".. AUTO-GENERATED FILE -- DO NOT EDIT!

.. toctree::
   :maxdepth: 1

"""
all_wf.write(title)

config="""Config
^^^^^^

"""

tags="""
Tags
^^^^

"""

Uuid="""uuid: """

def write_graph_section(fname):
    ad="""Graph
^^^^^

"""
    ad += '.. graphviz::\n\n'
    fhandle = open(fname)
    for line in fhandle:
        ad += '\t' + line + '\n'

    fhandle.close()
    os.remove(fname)
    os.remove(fname + ".png")
    return ad


for wf in workflows:
    uuid = wf[0]
    mwf = wf[1]["object"]
    fname = os.path.join(base_dir,"uuid_"+uuid+'.rst')
    print fname
    foo = open(fname,'w')
    foo.write(mwf.help)
    foo.write(Uuid)
    foo.write(uuid+'\n')
    foo.write(tags)
    for t in mwf.tags:
        foo.write('* '+t+'\n')

    foo.write(config)
    cls = mwf.config_ui()

    foo.write(trim(help(cls,True))+'\n')

    (_,graphname) =  tempfile.mkstemp(suffix=".dot")
    try:
        mwf.workflow_function(mwf.config_ui()).write_graph(dotfilename=graphname,graph2use="orig")
        graph = write_graph_section(graphname) + '\n'
        foo.write(graph)
    except TypeError:
        pass
    #except:
    #    print "There is some error :("

    foo.close()
    all_wf.write("   "+container+'/'+"uuid_"+uuid+'.rst'+'\n')

all_wf.close()
print "done"


