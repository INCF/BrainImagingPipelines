import os
from .....base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from .....flexible_datagrabber import Data, DataBase
from bips.workflows.base import BaseWorkflowConfig

"""
Part 1: Define a MetaWorkflow
"""

mwf = MetaWorkflow()
mwf.uuid = 'f5c66232a22d11e2b861001e4fb1404c'#'9ce580861d2a11e2907600259080ab1a'
mwf.help="""
Seed-Based Volume Connectivity
=================================

Supply ROI masks (seeds). Will compute ROI-ROI and ROI-voxel
 """
mwf.tags=['seed','connectivity','resting']

"""
Part 2: Define the config class & create_config function
"""

class config(BaseWorkflowConfig):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc="Workflow Description")
    # Directories
    sink_dir = Directory(os.path.abspath('.'), mandatory=True, desc="Location where the BIP will store the results")
    save_script_only = traits.Bool(False)

    datagrabber = traits.Instance(Data, ())

    use_advanced_options = Bool(False)
    advanced_options = traits.Code()

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    c.datagrabber = get_datagrabber()

    return c

def get_datagrabber():
    foo = Data(['timeseries_file',"rois","mask_file"])
    subs = DataBase()
    subs.name = 'subject_id'
    subs.values = ['sub01','sub02']
    subs.iterable = True
    foo.fields = [subs]
    foo.template= '*'
    foo.field_template = dict(timeseries_file = '%s/preproc/output/bandpassed/*.nii*',
                              rois="*.nii.gz",mask_file='')
    foo.template_args = dict(rois=[[]],
        timeseries_file=[['subject_id']],mask_file=[[]])
    return foo

mwf.config_ui = create_config

"""
Part 3: Create a View
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
            label='Directories', show_border=True),
        Group(Item(name='run_using_plugin',enabled_when='not save_script_only'),Item('save_script_only'),
            Item(name='plugin', enabled_when="run_using_plugin"),
            Item(name='plugin_args', enabled_when="run_using_plugin"),
            Item(name='test_mode'), Item(name="timeout"),
            label='Execution Options', show_border=True),
        Group(Item(name='datagrabber'),
            label='Subjects', show_border=True),
        Group(Item(name='use_advanced_options'),
            Item(name="advanced_options", enabled_when="use_advanced_options"),
            label="Advanced Options", show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Part 4: Workflow Construction
"""

def get_mean_timeseries(infile,roi,mask):
    import os
    import nibabel as nib
    from nipype.utils.filemanip import fname_presuffix, split_filename
    import numpy as np

    img = nib.load(infile)
    data, aff = img.get_data(), img.get_affine()

    roi_img = nib.load(roi) 
    roi_data, roi_affine = roi_img.get_data(), roi_img.get_affine()

    if len(roi_data.shape) > 3:
        roi_data = roi_data[:,:,:,0]

    mask = nib.load(mask).get_data()
    roi_data = (roi_data > 0).astype(int) + (mask>0).astype(int)

    _,roiname,_ = split_filename(roi)
    outfile = fname_presuffix(infile,"%s_"%roiname,'.txt',newpath=os.path.abspath('.'),use_ext=False)
    
    out_data = np.mean(data[roi_data>1,:],axis=0)
    print out_data.shape
    
    np.savetxt(outfile,out_data)

    return outfile, roiname

def roi2roi(roifiles,roinames,subject):
    import numpy as np
    import os

    data = None
    if len(roifiles)==1:
        return os.path.abspath("dummy.txt")

    for i,roi in enumerate(roifiles):
        if not i:
            data = np.genfromtxt(roi)
        else:
            tmp = np.genfromtxt(roi)
            data = np.vstack((data,tmp)) 

    print data.shape
    
    corrmat = np.corrcoef(data)
    nt = data.shape[1]
    print corrmat.shape
    zmat =  np.sqrt(nt-3)*0.5*np.log(np.divide((np.ones(corrmat.shape)+corrmat),(np.ones(corrmat.shape)-corrmat)))

    z_outfile = os.path.abspath("z_%s_roi2roi.csv"%subject)
    out = open(z_outfile,'w')
    out.write("roi, ")
    out.write(', '.join(roinames))
    for i in xrange(len(roifiles)):
        out.write('\n')
        out.write('%s, '%roinames[i])
        out.write(', '.join(zmat[i,:].astype('|S10').tolist()))
    out.close()

    r_outfile = os.path.abspath("r_%s_roi2roi.csv"%subject)
    out = open(r_outfile,'w')
    out.write("roi, ")
    out.write(', '.join(roinames))
    for i in xrange(len(roifiles)):
        out.write('\n')
        out.write('%s, '%roinames[i])
        out.write(', '.join(corrmat[i,:].astype('|S10').tolist()))
    out.close()
    return z_outfile, r_outfile

def create_correlation_matrix(infiles,mask_file, roi, roiname):
    import os
    import numpy as np
    import scipy.io as sio
    import nibabel as nb
    from nipype.utils.filemanip import split_filename, fname_presuffix
    img = nb.load(infiles)
    data, affine = img.get_data(), img.get_affine()

    mask = nb.load(mask_file).get_data()
    #data = data.ravel()
    roi_data = np.genfromtxt(roi)

    zmat = np.zeros(mask.shape)
    rmat = np.zeros(mask.shape)
    masked_data = data[mask==1,:]

    masked_zmat = np.zeros(masked_data.shape[0])
    masked_rmat = np.zeros(masked_data.shape[0])
    for i in xrange(masked_data.shape[0]):
        r = np.corrcoef(masked_data[i,:],roi_data)[0][1]
        masked_rmat[i] = r
        masked_zmat[i] = np.sqrt(data.shape[-1]-3)*0.5*np.log((1+r)/(1-r))

    zmat[mask==1] = masked_zmat
    rmat[mask==1] = masked_rmat

    zfile = fname_presuffix(infiles,"z_%s_"%roiname,'',os.path.abspath('.'))
    out = nb.Nifti1Image(zmat, affine=affine)
    out.to_filename(zfile)    
    
    rfile = fname_presuffix(infiles,"r_%s_"%roiname,'',os.path.abspath('.'))
    out = nb.Nifti1Image(rmat, affine=affine)
    out.to_filename(rfile)    


    return zfile, rfile

def roi_connectivity(c):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as util
    import nipype.interfaces.io as nio
    from nipype.interfaces.freesurfer import SampleToSurface
    workflow = pe.Workflow(name='volume_correlation')

    datagrabber = c.datagrabber.create_dataflow()
    #dg = datasource.get_node("datagrabber")
    #dg.run_without_submitting = True
    inputnode = datagrabber.get_node("subject_id_iterable")

    #mean timeseries
    mean = pe.MapNode(util.Function(input_names=["infile","roi","mask"],
                                    output_names=["outfile","roiname"],
                                    function=get_mean_timeseries),
                      name="mean_timeseries",iterfield=["roi"])

    workflow.connect(datagrabber,'datagrabber.timeseries_file',mean,"infile")
    workflow.connect(datagrabber,'datagrabber.rois',mean,'roi')
    workflow.connect(datagrabber,"datagrabber.mask_file",mean,'mask')

    #roi2roi
    roitoroi = pe.Node(util.Function(input_names=["roifiles","roinames","subject"],
                                     output_names=["z_outfile","r_outfile"],
                                     function=roi2roi),name='roi2roi')

    workflow.connect(mean,"roiname",roitoroi,"roinames")
    workflow.connect(mean,"outfile",roitoroi,"roifiles")
    workflow.connect(inputnode,"subject_id",roitoroi,"subject")
    # create correlation matrix
    corrmat = pe.MapNode(util.Function(input_names=['infiles','mask_file','roi','roiname'],
        output_names=['zfile','rfile'],
        function=create_correlation_matrix),
        name='correlation_matrix',iterfield=["roi","roiname"])

    workflow.connect(mean,"outfile",corrmat,"roi")
    workflow.connect(mean,"roiname",corrmat,"roiname")
    workflow.connect(datagrabber,"datagrabber.timeseries_file",corrmat,"infiles")
    workflow.connect(datagrabber,"datagrabber.mask_file",corrmat,"mask_file")
        

    datasink = pe.Node(nio.DataSink(), name='sinker')
    datasink.inputs.base_directory = c.sink_dir

    def getsubs(subject_id):
        subs = []
        subs.append(('_subject_id_%s'%subject_id,''))
        for i in range(100)[::-1]:
            subs.append(('_mean_timeseries%d/'%i,''))
            subs.append(('_correlation_matrix%d'%i,''))
        return subs

    workflow.connect(inputnode, 'subject_id', datasink, 'container')
    workflow.connect(inputnode, ("subject_id",getsubs),datasink,"substitutions")
    workflow.connect(corrmat, 'zfile', datasink, 'seed_connectivity.@zcorrmat')
    #workflow.connect(corrmat, 'rfile', datasink, 'seed_connectivity.@rcorrmat')
    workflow.connect(mean,'outfile',datasink,'seed_connectivity.mean_timeseries')
    workflow.connect(roitoroi,"z_outfile",datasink,'seed_connectivity.@zroi2roi')
    #workflow.connect(roitoroi,"r_outfile",datasink,'seed_connectivity.@rroi2roi')
    return workflow


mwf.workflow_function = roi_connectivity

"""
Part 5: Define the main function
"""

def main(config_file):
    c = load_config(config_file, create_config)
    workflow = roi_connectivity(c)
    workflow.base_dir = c.working_dir
    workflow.config = {'execution': {'crashdump_dir': c.crash_dir, "job_finished_timout":14}}
    if c.use_advanced_options:
        exec c.advanced_script

    from nipype.utils.filemanip import fname_presuffix
    workflow.export(fname_presuffix(config_file,'','_script_').replace('.json',''))

    if c.save_script_only:
        return 0

    if c.run_using_plugin:
        workflow.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        workflow.run()


mwf.workflow_main_function = main

"""
Part 6: Register the Workflow
"""

register_workflow(mwf)
