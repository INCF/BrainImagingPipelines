def new_getmask(segmentation_type='FAST',name='mask_segment_register'):
    if segmentation_type=='FAST':
        return fsl_getmask(name)
    elif segmentation_type=='Atropos':
        return ants_getmask(name)

def fsl_getmask(name):
    import nipype.interfaces.fsl as fsl
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu

    wf = pe.Workflow(name=name)
    inputspec = pe.Node(niu.IdentityInterface(fields=['functional','structural']),name='inputspec')
    bet = pe.Node(fsl.BET(mask=True,remove_eyes=True),name='bet')
    flirt = pe.Node(fsl.FLIRT(dof=6),name='flirt')
    applyxfm_mask = pe.Node(fsl.ApplyXfm(interp='nearestneighbour',apply_xfm=True),name='applyxfm_mask')
    applyxfm_seg = pe.MapNode(fsl.ApplyXfm(interp='nearestneighbour',apply_xfm=True),name='applyxfm_seg',iterfield=['in_file'])
    dilate = pe.Node(fsl.DilateImage(operation='mean'),name='dilate')
    fast = pe.Node(fsl.FAST(),name='fast')
    outputspec= pe.Node(niu.IdentityInterface(fields=['mask','reg_file','segments','warped_struct']),name='outputspec')

    #create brain mask
    wf.connect(inputspec,"structural",bet,"in_file")

    # calculate transfor, struct --> func
    wf.connect(inputspec,"functional",flirt,"reference")
    wf.connect(inputspec,"structural",flirt,"in_file")
    wf.connect(flirt,'out_matrix_file',outputspec,'reg_file')
    wf.connect(flirt,'out_file',outputspec,'warped_struct')

    #dilate brain mask
    wf.connect(bet,"mask_file",dilate,"in_file")

    #transform mask to functional space
    wf.connect(dilate,"out_file",applyxfm_mask,"in_file")
    wf.connect(inputspec,"functional",applyxfm_mask,"reference")
    wf.connect(flirt,"out_matrix_file",applyxfm_mask,"in_matrix_file")
    wf.connect(applyxfm_mask,'out_file',outputspec,'mask')

    #segment with FAST
    wf.connect(bet,"out_file", fast,"in_files")

    #transform segments
    wf.connect(fast,"tissue_class_map",applyxfm_seg,"in_file")
    wf.connect(flirt,'out_matrix_file',applyxfm_seg,"in_matrix_file")
    wf.connect(inputspec,"functional",applyxfm_seg,"reference")
    wf.connect(applyxfm_seg,"out_file",outputspec,"segments")

    return wf

def ants_getmask(name):
    import nipype.interfaces.fsl as fsl
    import nipype.pipeline.engine as pe
    import nipype.interfaces.utility as niu
    import nipype.interfaces.ants as ants
    import nipype.interfaces.freesurfer as fs

    wf = pe.Workflow(name=name)
    inputspec = pe.Node(niu.IdentityInterface(fields=['functional','structural']),name='inputspec')
    bet = pe.Node(fsl.BET(mask=True,remove_eyes=True),name='bet')
    applymask = pe.Node(fs.ApplyMask(),name='applymask')
    #flirt = pe.Node(fsl.FLIRT(),name='flirt')
    #applyxfm_mask = pe.Node(fsl.ApplyXfm(interp='nearestneighbour',apply_xfm=True),name='applyxfm_mask')
    #applyxfm_seg = pe.MapNode(fsl.ApplyXfm(interp='nearestneighbour',apply_xfm=True),name='applyxfm_seg',iterfield=['in_file'])
    dilate = pe.Node(fsl.DilateImage(operation='mean'),name='dilate')
    atropos = pe.Node(ants.Atropos(initialization='KMeans',number_of_tissue_classes=3,dimension=3),name='atropos')
    n4 = pe.Node(ants.N4BiasFieldCorrection(dimension=3),name='n4corrections')
    outputspec= pe.Node(niu.IdentityInterface(fields=['mask','reg_file','segments','warped_struct']),name='outputspec')

    #create brain mask
    wf.connect(inputspec,"structural",bet,"in_file")
    
    #dilate bets mask a bit for atropos
    wf.connect(bet,"mask_file",dilate,"in_file")
  
    # apply dilated mask to img

    wf.connect(dilate,'out_file',applymask,'mask_file')
    wf.connect(inputspec,'structural',applymask,'in_file')
    
    #N4 bias correction

    wf.connect(applymask,"out_file",n4,'input_image')

    # atropos it

    wf.connect(n4,"output_image",atropos,'intensity_images')
    wf.connect(dilate,'out_file',atropos,'mask_image')

    return wf


