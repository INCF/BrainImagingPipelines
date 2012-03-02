import matplotlib
matplotlib.use('Agg')
import os
from scipy.ndimage import label
from nipy.labs import viz
from nibabel import load
import pylab
import matplotlib.pyplot as plt
from nipype.interfaces import fsl
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio
import nipype.interfaces.freesurfer as fs

""" To create this report you need to know the locations of:
    - freesurfer output for each subject
    - fmri zstat images per contrast per subject
    - you may need to make tweaks to the code to print the contrast title above each picture correctly! (unless you used fsl naming) 
    - before running, in the terminal type 'echo $DISPLAY' and copy the output.
    - then you need to add a line in your bash_profile: export DISPLAY=output(for me it was ba3:2.0)
    - always run this script on the cluster.
    - ask Anisha if you have any questions """
    

def get_coords(labels, in_file, subsess, fsdir):
    from nibabel import load
    import numpy as np
    import os 
    
    img = labels[0]
    data1 = in_file
    data,affine = load(data1).get_data(), load(data1).get_affine()
    coords = []
    labels = np.setdiff1d(np.unique(img.ravel()), [0])
    cs = []
    
    brain_dir = os.path.join(fsdir,subsess,'mri')
    lut_file='/software/Freesurfer/5.1.0/FreeSurferColorLUT.txt'
    colorfile = np.genfromtxt(lut_file,dtype='string')
    seg_file = os.path.join(brain_dir,'aparc+aseg.mgz')
    data_seg,aff_seg = load(seg_file).get_data(), load(seg_file).get_affine()
    inv_aff_seg = np.linalg.inv(aff_seg)
    
    def make_chart(coords):
        brain_loc = []
        
        for co in coords:
            realspace = np.dot(affine,np.hstack((co,1)))
            #segspace = np.dot(inv_aff_seg, np.hstack((co,1)))
            segspace = np.dot(inv_aff_seg, realspace)
            colornum = str(data_seg[segspace[0],segspace[1],segspace[2]])
            brain_loc.append(colorfile[:,1][colorfile[:,0]==colornum][0])
        
        percents = []

        for loc in np.unique(brain_loc):
            #percents.append(np.mean(loc==brain_loc, dtype=np.float64))
            percents.append(np.mean(loc==np.array(brain_loc), dtype=np.float64))
        return np.unique(brain_loc), percents
    
    for label in labels:
        cs.append(np.sum(img==label))
    
    locations = []
    percents = []
    meanval = []
    for label in labels[np.argsort(cs)[::-1]]:
        coordinates = np.asarray(np.nonzero(img==label))  
        print coordinates.shape
        locs, pers = make_chart(coordinates.T)
        i =  np.argmax(abs(data[coordinates[0,:],coordinates[1,:],coordinates[2,:]])) 
        meanval.append(np.mean(data[coordinates[0,:],coordinates[1,:],coordinates[2,:]]))
        q =  coordinates[:,i]
        locations.append(locs)
        percents.append(pers)
        coords.append(np.dot(affine, np.hstack((q,1)))[:3].tolist())  
                                 
    return [coords], [cs], locations, percents, meanval


def get_labels(in_file,thr,csize):
    from nibabel import load
    from scipy.ndimage import label
    #from numpy import *
    min_extent=csize
    data = load(in_file).get_data()
    labels, nlabels = label(abs(data)>thr)
    for idx in range(1, nlabels+1):
        if sum(sum(sum(labels==idx)))<min_extent:
            labels[labels==idx] = 0
    return [labels]
            

def show_slices(image_in, anat_file, coordinates,thr):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import pylab as pl
    import numpy as np
    from nibabel import load
    import os
    from nipy.labs import viz
    anat = anat_file
    img = image_in
    coords = coordinates[0]
    threshold=thr
    cmap=pl.cm.jet 
    prefix=None,
    show_colorbar=True
    formatter='%.2f'
    
    img1 = load(img)
    data, aff = img1.get_data(), img1.get_affine()
    anatimg = load(anat) #load('/usr/share/fsl/data/standard/MNI152_T1_1mm_brain.nii.gz')
    anatdata, anataff = anatimg.get_data(), anatimg.get_affine()
    anatdata = anatdata.astype(np.float)
    anatdata[anatdata<10.] = np.nan
    outfile1 = os.path.split(img)[1][0:-7]
    outfiles = []
    for idx,coord in enumerate(coords):
        outfile = outfile1+'cluster%02d' % idx
        osl = viz.plot_map(np.asarray(data), aff, anat=anatdata, anat_affine=anataff,
                           threshold=threshold, cmap=cmap,
                           black_bg=False, cut_coords=coord)
        if show_colorbar:
            cb = plt.colorbar(plt.gca().get_images()[1], cax=plt.axes([0.4, 0.075, 0.2, 0.025]), 
                     orientation='horizontal', format=formatter)
            cb.set_ticks([cb._values.min(), cb._values.max()])
            
        #osl.frame_axes.figure.savefig(outfile+'.svg', bbox_inches='tight', transparent=True)
        osl.frame_axes.figure.savefig(os.path.join(os.getcwd(),outfile+'.png'), dpi=600, bbox_inches='tight', transparent=True)
        #pl.savefig(os.path.join(os.getcwd(),outfile+'.png'), dpi=600, bbox_inches='tight', transparent=True)               
        outfiles.append(os.path.join(os.getcwd(),outfile+'.png'))
    return outfiles



def img_wkflw(outdir,subsess,fsdir, thr, csize, name='slice_image_generator'):
    inputspec = pe.Node(util.IdentityInterface(fields=['in_file','mask_file','anat_file','reg_file']),
                        name='inputspec')
    workflow = pe.Workflow(name=name)
    workflow.base_dir = outdir
    
    #applyreg = pe.MapNode(interface=fs.ApplyVolTransform(),name='applyreg',iterfield=['source_file'])
    #workflow.connect(inputspec,'anat_file',applyreg,'target_file')
    #workflow.connect(inputspec,'in_file',applyreg,'source_file')
    #workflow.connect(inputspec,'reg_file',applyreg,'reg_file')
    
    
    
    applymask = pe.MapNode(interface=fsl.ApplyMask(), name='applymask',iterfield=['in_file'])
    workflow.connect(inputspec,'in_file',applymask,'in_file')
    workflow.connect(inputspec,'mask_file',applymask,'mask_file')
    
    getlabels = pe.MapNode(util.Function( input_names = ["in_file","thr","csize"], output_names =["labels"], function = get_labels), iterfield=['in_file'], name = "getlabels")
    getlabels.inputs.csize = csize
    getlabels.inputs.thr = thr
                           
    workflow.connect(applymask,'out_file',getlabels,'in_file')
    
    getcoords = pe.MapNode(util.Function(input_names=["labels","in_file",'subsess','fsdir'], output_names = ["coordinates","cs",'locations','percents','meanval'], function= get_coords), iterfield=['labels','in_file']
                          , name="get_coords")   
    getcoords.inputs.subsess = subsess
    getcoords.inputs.fsdir = fsdir
    workflow.connect(getlabels,'labels', getcoords, 'labels')
    workflow.connect(applymask,'out_file',getcoords,'in_file')  
    
   
    showslices = pe.MapNode(util.Function(input_names=['image_in','anat_file','coordinates','thr'], output_names = ["outfiles"], function=show_slices), iterfield= ['image_in','coordinates'],
                            name='showslices')  
    showslices.inputs.thr = thr
    
    workflow.connect(inputspec,'anat_file',showslices,'anat_file')
    workflow.connect(getcoords,'coordinates',showslices,'coordinates') 
    workflow.connect(applymask,'out_file',showslices,'image_in')
    
    outputspec = pe.Node(util.IdentityInterface(fields=['coordinates','cs','locations','percents','meanval','imagefiles']), name='outputspec')
    workflow.connect(getcoords,'coordinates',outputspec,'coordinates')
    workflow.connect(getcoords,'cs',outputspec,'cs')
    workflow.connect(getcoords,'locations',outputspec,'locations')
    workflow.connect(getcoords,'percents',outputspec,'percents')
    workflow.connect(getcoords,'meanval',outputspec,'meanval')
    
    
    workflow.connect(showslices,'outfiles',outputspec,'imagefiles')
    
    return workflow               
    
def get_data(subs, maindir, outdir, fsdir,fwhm,name='get_data'):
    
    if not os.path.exists(outdir):
        os.mkdir(outdir)
    
    print maindir
    print outdir
    workflow = pe.Workflow(name=name)
    workflow.base_dir = outdir
    
    datasource = pe.Node(nio.DataGrabber(infields=['subject_id'], outfields=['func', 'struct','mask','reg']), name='datasource')
    datasource.inputs.base_directory = outdir
    datasource.inputs.template = '*'
    print os.path.join(maindir,'/%s/modelfit/contrasts/fwhm_5/*zstat*')
    print os.path.join(fsdir,'/%s/mri/brain.mgz')
    print os.path.join(maindir,'/%s/preproc/mask/fwhm_5/funcmask.nii')
    print os.path.join(maindir,'/%s/preproc/bbreg/*.dat')
    datasource.inputs.field_template = dict(func=os.path.join(maindir,'%s/modelfit/contrasts/fwhm_'+str(fwhm)+'/*zstat*'),
                                            struct=os.path.join(fsdir,'%s/mri/brain.mgz'),
                                            mask = os.path.join(maindir,'%s/preproc/mask/fwhm_'+str(fwhm)+'/funcmask.nii'),
                                            reg = os.path.join(maindir,'%s/preproc/bbreg/_register0/*.dat'))
    datasource.inputs.template_args = dict(func=[['subject_id']],
                                           struct=[['subject_id']], mask=[['subject_id']], reg = [['subject_id']])
    datasource.inputs.subject_id = subs
    outputspec = pe.Node(util.IdentityInterface(fields=['func','struct','mask','reg']), name='outputspec')
                        
    
    workflow.connect(datasource,'func',outputspec,'func')
    workflow.connect(datasource,'struct',outputspec,'struct')
    workflow.connect(datasource,'mask',outputspec,'mask')
    workflow.connect(datasource,'reg',outputspec,'reg')
    
    return workflow
    

    
def combine_report(subjects,maindir,fsdir,thr=2.326,csize=30,fwhm=5):
    import os
    print maindir
    outdir = maindir+'analyses/func/images'
    if not os.path.exists(outdir):
        os.mkdir(outdir)
    workflow = pe.Workflow(name='volumes')
    workflow.base_dir = os.path.join(outdir,subjects)
    
    dataflow = get_data(subjects, maindir = os.path.join(maindir,'analyses/func'), fsdir = fsdir, outdir = os.path.join(outdir,subjects),fwhm = fwhm)
    
    imgflow = img_wkflw(os.path.join(outdir,subjects),subjects,fsdir,thr=thr,csize=csize)
    
    writereport = pe.Node(util.Function( input_names = ["cs","locations","percents", "in_files", "maindir","subjects","meanval","imagefiles","surface_ims",'thr','csize','fwhm'], output_names =["report","elements"], function = write_report), name = "writereport" )
    writereport.inputs.maindir = outdir
    writereport.inputs.subjects = subjects
    writereport.inputs.thr = thr
    writereport.inputs.csize = csize
    writereport.inputs.fwhm = fwhm
        
    workflow.connect(dataflow,'outputspec.func',imgflow, 'inputspec.in_file')
    workflow.connect(dataflow,'outputspec.struct',imgflow, 'inputspec.anat_file')
    workflow.connect(dataflow,'outputspec.mask',imgflow, 'inputspec.mask_file')
    workflow.connect(dataflow,'outputspec.reg',imgflow, 'inputspec.reg_file')
    
    
    makesurfaceplots = pe.Node(util.Function(input_names = ['con_image','reg_file','subject_id','thr'], output_names = ['surface_ims', 'surface_mgzs'], function = make_surface_plots), 
                               name = 'make_surface_plots')
    makesurfaceplots.inputs.subject_id = subjects
    makesurfaceplots.inputs.thr = thr

    sinker = pe.Node(nio.DataSink(), name='sinker')
    sinker.inputs.base_directory = os.path.join(outdir,subjects)
    
    workflow.connect(dataflow,'outputspec.func',makesurfaceplots,'con_image')
    workflow.connect(dataflow,'outputspec.reg',makesurfaceplots,'reg_file')
    
    workflow.connect(imgflow, 'outputspec.cs', writereport, 'cs')
    workflow.connect(imgflow, 'outputspec.locations', writereport, 'locations')
    workflow.connect(imgflow, 'outputspec.percents', writereport, 'percents')
    workflow.connect(imgflow, 'outputspec.meanval', writereport, 'meanval')
    workflow.connect(imgflow,'outputspec.imagefiles', writereport, 'imagefiles')
    
    workflow.connect(dataflow, 'outputspec.func', writereport, 'in_files')
    workflow.connect(makesurfaceplots,'surface_ims', writereport, 'surface_ims')
    workflow.connect(writereport,"report",sinker,"report")
    
    
    return workflow

def write_report(cs,locations,percents,in_files,maindir,subjects, meanval, imagefiles, surface_ims, thr, csize, fwhm):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, BaseDocTemplate, Frame, NextPageTemplate, PageBreak, PageTemplate
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    import reportlab
    from reportlab.platypus.flowables import PageBreak 
    import time
    from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT
    from reportlab.platypus import Image as Image2
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from numpy import array 
    from reportlab.platypus.doctemplate import NextPageTemplate, PageTemplate
    import os
    from reportlab.lib.styles import getSampleStyleSheet
    from glob import glob
    from PIL import Image
    import numpy as np
    
    def get_and_scale(imagefile,scale=1):
        from reportlab.platypus import Image as Image2
        im1 = scale_im(Image.open(imagefile))
        im = Image2(imagefile, im1.size[0]*scale, im1.size[1]*scale)  
        return im      
               
    def scale_im(im):
        # scales an image so that it will fit on the page with various margins...
        width, height = letter
        newsize = array(im.size)/(max(array(im.size)/array([width-(1*inch), height-(2*inch)])))
        newsize = tuple(map(lambda x: int(x), tuple(newsize)))
        return im.resize(newsize)      
    
     
    
    fwhm = [fwhm]
    report = os.path.join(os.getcwd(),"slice_tables.pdf")
    doc = SimpleDocTemplate(report, pagesize=letter,
                            rightMargin=36,leftMargin=36,
                            topMargin=72,bottomMargin=72)
    elements = []
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='RIGHT', alignment=TA_RIGHT))
    
    formatted_time = time.ctime()
    
    ptext = '<font size=10>%s</font>' % formatted_time     
    elements.append(Paragraph(ptext, styles["Normal"]))
    elements.append(Spacer(1, 12)) 
    
    ptext = '<font size=22>%s</font>' %('Subject '+subjects+' Report')   
    elements.append(Paragraph(ptext, styles["Normal"]))
    elements.append(Spacer(1, 24))
    
    ptext = '<font size=10>%s</font>' %("The contrast files are: ")    
    elements.append(Paragraph(ptext, styles["Normal"]))
    elements.append(Spacer(1, 12)) 
    
    contrasts = []
    for fil in in_files:
        pt = os.path.split(fil)[1]
        contrasts.append(pt[18:-7]) # This is where the contrast name is extracted from the file name! change the indices if it doesn't look nice
        ptext = '<font size=10>%s</font>' %pt   
        elements.append(Paragraph(ptext, styles["Normal"]))
        elements.append(Spacer(1, 12))     
    
    ptext = '<font size=10>%s</font>' %("The stat images were thresholded at z = %s and min cluster size = %s voxels. FWHM = %d "%(thr,csize,fwhm[0]))    
    elements.append(Paragraph(ptext, styles["Normal"]))
    elements.append(Spacer(1, 12)) 
    elements.append(PageBreak())
    
    # Design & Covariance Matrices
    maindir = os.path.split(maindir)[0]

    des_mat_all = sorted(glob(os.path.join(maindir,subjects,'modelfit','design','fwhm_%d'%fwhm[-1],'*.png')))
    des_mat_cov = sorted(glob(os.path.join(maindir,subjects,'modelfit','design','fwhm_%d'%fwhm[-1],'*_cov.png')))
    des_mat = np.setdiff1d(des_mat_all,des_mat_cov)
    
    print des_mat
    print des_mat_cov
    for i in range(len(des_mat)):
        ptext = '<font size=10>%s</font>' %('Design Matrix:')   
        elements.append(Paragraph(ptext, styles["Normal"]))
        elements.append(Spacer(1, 12))
        im = get_and_scale(des_mat[i],.6)
        elements.append(im)    
        elements.append(Spacer(1, 12))  
    
        ptext = '<font size=10>%s</font>' %('Covariance Matrix:')   
        elements.append(Paragraph(ptext, styles["Normal"]))
        elements.append(Spacer(1, 12))
        im = get_and_scale(des_mat_cov[i],.6)
        elements.append(im)    
        elements.append(PageBreak())
    
    for i, con_cs in enumerate(cs):
        data = [['Size','Location','Ratio','Mean(z)','Image']]
        for j, cluster in enumerate(con_cs[0]):
            data.append([])
            data[j+1].append(cluster)
            locstr = ''
            perstr = ''
            if len(locations[i][j]) <= 50:
                for k, loc in enumerate(locations[i][j]):
                    locstr = locstr + loc + '\n'
                    perstr = perstr+'%.2f\n'%percents[i][j][k]
                    
            data[j+1].append(locstr)
            data[j+1].append(perstr)
            meanstr = '%2.2f'%meanval[i][j]
            data[j+1].append(meanstr)
            im = get_and_scale(imagefiles[i][j],.5)
            data[j+1].append(im)
        
        print data
        t=Table(data)
        t.setStyle(TableStyle([('ALIGN',(0,0), (-1,-1),'LEFT'),
                               ('VALIGN',(0,0), (-1,-1), 'TOP'),
                               ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                               ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))
        t.hAlign='LEFT'
        ptext = '<font size=10>%s</font>' %('Contrast:  %s'%(contrasts[i]))   
        elements.append(Paragraph(ptext,styles["Normal"]))
        elements.append(Spacer(1, 12))
        elements.append(get_and_scale(surface_ims[i]))
        elements.append(Spacer(1, 12))
        elements.append(t)
        elements.append(Spacer(1, 12))
        #elements.append(PageBreak())
    
    doc.build(elements)
    return report, elements 

def make_surface_plots(con_image,reg_file,subject_id,thr):  
    import matplotlib
    matplotlib.use('Agg')
    #from surfer import Brain
    import os
    from glob import glob
        
    def make_image(zstat_path,bbreg_path):
        name_path = os.path.join(os.getcwd(),os.path.split(zstat_path)[1]+'_reg_surface.mgh')
        systemcommand ='mri_vol2surf --mov %s --reg %s --hemi lh --projfrac-max 0 1 0.1 --o %s --out_type mgh'%(zstat_path,bbreg_path,name_path)
        print systemcommand
        os.system(systemcommand)
        return name_path
        
    def make_brain(subject_id,image_path):
        from mayavi import mlab
        #mlab.options.backend = 'Agg'
        from surfer import Brain
        hemi = 'lh'
        surface = 'inflated'
        overlay = image_path 
        brain = Brain(subject_id, hemi, surface)
        brain.add_overlay(image_path,min=thr)
        outpath = os.path.join(os.getcwd(),os.path.split(image_path)[1]+'_surf.png')
        brain.save_montage(outpath)
        return outpath
            
    surface_ims = []
    surface_mgzs = []
    for con in con_image:
        surf_mgz = make_image(format(con),reg_file)
        surface_mgzs.append(surf_mgz)
        surface_ims.append(make_brain(subject_id,surf_mgz))
                            
    return surface_ims, surface_mgzs   
  
  
  
  
if __name__ == '__main__':

    subsess = ['SAD_017']
      
    for sub in subsess:
        modelflow = combine_report(sub,maindir = '/mindhive/gablab/sad/PY_STUDY_DIR/Block/scripts/l1preproc/workflows/', fsdir = '/mindhive/xnat/surfaces/sad/')
        print "###########  RUNNING %s #################"%sub
        modelflow.run()

    
    
    
        
