
def create_workflow(name='tracking'):
    from nipype.workflows.dmri.fsl import create_bedpostx_pipeline
    import nipype.interfaces.fsl as fsl
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu

    wf = pe.Workflow(name=name)
    bed_wf = create_bedpostx_pipeline()
    inputspec = pe.Node(niu.IdentityInterface(fields=['dwi',
                                                      'mask',
                                                      'reg',
                                                      'mean',
                                                      'bvecs',
                                                      'bvals',
                                                      "subject_id",
                                                      "surf_dir"]),
        name="inputspec")
    outputspec = pe.Node(niu.IdentityInterface(fields=['fdt_paths',
                                                       'log',
                                                       'particle_files',
                                                       'targets',
                                                       'way_total']),
        name='outputspec')

    wf.connect(inputspec,'dwi',bed_wf,'inputnode.dwi')
    wf.connect(inputspec,'mask', bed_wf, 'inputnode.mask')
    wf.connect(inputspec,'bvecs', bed_wf, 'inputnode.bvecs')
    wf.connect(inputspec,'bvals', bed_wf, 'inputnode.bvals')

    try:
        prob2 = fsl.ProbTrackX2(verbose=2)
    except AttributeError:
        prob2 = fsl.ProbTrackX(verbose=2)
    #prob2._cmd='probtrackx2'
    #prob2.inputs.mode = Undefined
    track = pe.MapNode(prob2,name='probtrackx',iterfield=["seed"])

    wf.connect(bed_wf,'outputnode.thsamples', track, 'thsamples')
    wf.connect(bed_wf,'outputnode.phsamples', track, 'phsamples')
    wf.connect(bed_wf,'outputnode.fsamples', track, 'fsamples')
    wf.connect(inputspec,'mask',track,'mask')

    regions = get_regions()
    wf.connect(inputspec,"subject_id",regions,"inputspec.subject_id")
    wf.connect(inputspec,"surf_dir",regions,"inputspec.surf_dir")
    wf.connect(inputspec,"reg",regions,"inputspec.reg_file")
    wf.connect(inputspec,"mean",regions,"inputspec.mean")
    wf.connect(regions,"outputspec.ROIs",track,"seed")
    wf.connect(regions,"outputspec.ROIs",track,"target_masks")

    wf.connect(track,'fdt_paths', outputspec, 'fdt_paths')
    wf.connect(track,'log', outputspec, 'log')
    wf.connect(track,'particle_files', outputspec, 'particle_files')
    wf.connect(track,'targets', outputspec, 'targets')
    wf.connect(track,'way_total', outputspec, 'way_total')

    return wf


def pickfile(in_list):
    import os
    outfiles=[]
    for li in in_list:
        for l in li:
            i=os.path.split(l)[1]
            if i=='lh.aparc.annot' or i=="rh.aparc.annot":
                outfiles.append(l)
    return outfiles

def binarize_and_name(in_file,subject_id,surf_dir,hemi):
    import numpy as np
    import nibabel as nib
    import os
    out_files=[]
    colorfile=os.path.join(surf_dir,subject_id,'label','aparc.annot.ctab')
    colors=np.genfromtxt(colorfile,dtype=str)
    img=nib.load(in_file)
    data,affine,hdr=img.get_data(),img.get_affine(),img.get_header()
    for i in range(1,36):
        outdata=data==i
        outdata = outdata.astype(int)
        outname=os.path.abspath('%s.%s.nii.gz'%(hemi,colors[i][1]))
        outfile=nib.Nifti1Image(outdata,affine=affine)
        outfile.to_filename(outname)
        out_files.append(outname)
    return out_files

merge=lambda x: x[0]+x[1]

def get_regions(name='get_regions'):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu
    import nipype.interfaces.io as nio
    import nipype.interfaces.freesurfer as fs
    wf= pe.Workflow(name=name)
    inputspec = pe.Node(niu.IdentityInterface(fields=["surf_dir",
                                                      "subject_id",
                                                      "surface",
                                                      "reg_file",
                                                      "mean"]),
        name='inputspec')
    l2v = pe.MapNode(fs.Label2Vol(),name="label2vol",iterfield=['hemi','annot_file'])
    l2v.inputs.hemi=['lh','rh']
    wf.connect(inputspec,'surf_dir',l2v,"subjects_dir")
    wf.connect(inputspec,'subject_id',l2v,'subject_id')
    wf.connect(inputspec,"reg_file",l2v,"reg_file")
    wf.connect(inputspec,"mean",l2v,"template_file")
    fssource=pe.MapNode(nio.FreeSurferSource(),name='fssource',iterfield=['hemi'])
    fssource.inputs.hemi=['lh','rh']
    wf.connect(inputspec,'surf_dir',fssource,"subjects_dir")
    wf.connect(inputspec,'subject_id',fssource,'subject_id')
    wf.connect(fssource,('annot',pickfile),l2v,'annot_file')
    bin=pe.MapNode(niu.Function(input_names=["in_file","subject_id","surf_dir","hemi"],
                                output_names=["out_files"],function=binarize_and_name),
        name="binarize_and_name",iterfield=['hemi',"in_file"])
    wf.connect(inputspec,"subject_id",bin,"subject_id")
    wf.connect(inputspec,"surf_dir",bin,"surf_dir")
    wf.connect(l2v,"vol_label_file",bin,"in_file")
    bin.inputs.hemi=['lh','rh']
    outputspec=pe.Node(niu.IdentityInterface(fields=["ROIs"]),name='outputspec')
    wf.connect(bin,("out_files",merge),outputspec,"ROIs")

    return wf
