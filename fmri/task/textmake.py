from numpy import *
from nibabel import load
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from config import *
from time import ctime
from glob import glob
from PIL import Image
import reportlab
import os


def con_corr(in_files):
    # this function should compute correlations between two sets of averaged contrasts:
    #   - contrasts derived from EVEN runs (runs numbered 1 and 3 in this case, since python
    #     indexes from 0) and ODD runs (runs 0 and 2)
    # con_num = the contrast that you wish to correlate. 0 corresponds to all_vs_fixation 
    in_files = array(in_files)
    in_files = list(in_files[:])
    odd = []
    even = []
    # grab only even files 
    #findlist = array(range(len(in_files)))+1
    findlist = array(range(len(in_files)))
    odd = list(array(in_files)[list(findlist[mod(findlist,2)==1])[:]])
    even = list(array(in_files)[list(findlist[mod(findlist,2)==0])[:]])
    
    o = [load(x).get_data() for x in odd]
    e = [load(x).get_data() for x in even]
    o = [o[x].reshape(1,1,o[x].size) for x in range(len(o))]
    e = [e[x].reshape(1,1,e[x].size) for x in range(len(e))]
    def ret_col_array(ar):
        if str(type(ar[0]))=="<type 'numpy.ndarray'>":
            return ret_col_array(ar[0])
        else:
            return ar
    o = map(lambda x: ret_col_array(x),o)
    e = map(lambda x: ret_col_array(x),e)
    modd = array([o[x]/len(o) for x in range(len(o))]).sum(0)
    meve = array([e[x]/len(e) for x in range(len(e))]).sum(0)
    R = corrcoef(modd,meve)
    return R[0,1]

def textmake(subid):
    # this is a function I'm composing to write out a buncha text...
    width, height = letter
    fname = os.path.join(root_dir,'analyses','func',subid,'prep_and_firstlvl_report.pdf')
    c = canvas.Canvas(fname, pagesize=letter)
    c.setFont("Courier",8) # need a monotyped font
    runs = get_run_numbers(subid)
    bolds = glob(os.path.join(root_dir,'brain_data/niftis',subid,'functional_SST/','*.nii.gz'))
    pit = [['Subject',subid],
           ['Runs',str(len(runs))],
           ['Run Numbers', str(runs)],
           ['Date',ctime()]]
    cfg = [['Art Thresh Norm',str(norm_thresh)],
           ['Art Thresh Z',str(z_thresh)],
           ['FWHM',str(fwhm)],
           ['Film Threshold',str(film_threshold)],
           ['TR',str(TR)],
           ['Highpass Cutoff',str(hpcutoff)],
           ['Number of noise components',str(num_noise_components)]]
    #brk = '-'*80
    brkT = '_'*80
    def gen_str(strlist):
        # expects a 2-element list of the form ['title','data']
        return strlist[0] + ' :' + ' '*(40-len(strlist[0])-2) + strlist[1]
    def prin_title(t,nme):
        # prints a title
        t.textLine('')
        t.textLine(brkT)
        t.textLine(nme)
        t.textLine('')
    def scale_im(im):
        # scales an image so that it will fit on the page with various margins...
        newsize = array(im.size)/(max(array(im.size)/array([width-(1*inch), height-(2*inch)])))
        newsize = tuple(map(lambda x: int(x), tuple(newsize)))
        return im.resize(newsize)
    def newpage(t,c):
        # starts a newpage and returns a new text object.
        c.drawText(t)
        c.showPage()
        c.setFont("Courier",8)
        t = c.beginText()
        t.setTextOrigin(inch, height-inch)
        return t
    textobject = c.beginText()
    textobject.setTextOrigin(inch, height-inch)
    prin_title(textobject,'GENERAL')
    for i in pit:
        textobject.textLine(gen_str(i))
    prin_title(textobject,'BOLDS')
    for i in bolds:
        textobject.textLine(i)
    prin_title(textobject,'CONFIG')
    for i in cfg:
        textobject.textLine(gen_str(i))
    # now obtain the number of artifact regressors, even/odd contrast correlation
    artz = glob(os.path.join(root_dir,'analyses','func',subid,'preproc','art','fwhm_%d'%fwhm[-1],'art.*'))
    prin_title(textobject,'NUMBER OF ARTIFACTS')
    for i,j in enumerate(artz):
        s1 = 'Run %d'%runs[i]
        textobject.textLine(gen_str([s1,str(len(open(j,'r').read().split('\n'))-1)]))
    prin_title(textobject,'CONTRAST CORRELATIONS')
    cons = getcontrasts(subid)
    print cons
    for i in fwhm:
        textobject.textLine('')
        textobject.textLine('FWHM %d mm:'%i)
        textobject.textLine('')
        for j in cons:
            print j[0]
            con_ims = glob(os.path.join(root_dir,'analyses','func',subid,'modelfit','contrasts','fwhm_%d'%i,'*_cope*'+j[0]+'*.nii.gz'))
            print con_ims
            #textobject.textLine(gen_str([j[0],str(con_corr(con_ims))[:5]]))
    c.drawText(textobject)
    # DESIGN MATRICIES
    des_mat = glob(os.path.join(root_dir,'analyses','func',subid,'modelfit','design','fwhm_%d'%fwhm[-1],'_run_?_??_run?.png'))
    for i in range(len(runs)):
        # start a new page
        c.showPage()
        textobject = c.beginText()
        textobject.setTextOrigin(inch, height-(0.5*inch))
        textobject.textLine('Design Matrix, Run %s'%str(i+1))
        c.drawText(textobject)
        im = Image.open(des_mat[i])
        im = scale_im(im)
        c.drawImage(des_mat[i],0.5*inch,height-(inch+im.size[1]),width=im.size[0],height=im.size[1],mask=None)
        #c.drawImage(im,0.5*inch, height-(1.0*inch), width=None, height=None, mask=None)
    # COV MATRICIES
    des_mat_cov = glob(os.path.join(root_dir,'analyses','func',subid,'modelfit','design','fwhm_%d'%fwhm[-1],'_run_?_??_run?_cov.png'))
    print des_mat_cov
    for i in range(len(runs)):
        # start a new page
        c.showPage()
        textobject = c.beginText()
        textobject.setTextOrigin(inch, height-(0.5*inch))
        textobject.textLine('Covariance Matrix, Run %s'%str(i+1))
        c.drawText(textobject)
        im = Image.open(des_mat_cov[i])
        im = scale_im(im)
        c.drawImage(des_mat_cov[i],0.5*inch,height-(inch+im.size[1]),width=im.size[0],height=im.size[1],mask=None)
        #c.drawImage(im,0.5*inch, height-(1.0*inch), width=None, height=None, mask=None) 
    # MOTION PLOTS
    comt_im = glob(os.path.join(root_dir,'analyses','func',subid,'preproc','motion','*trans.png'))
    comr_im = glob(os.path.join(root_dir,'analyses','func',subid,'preproc','motion','*rot.png'))
    # for motion, it's not super necessary to separate them out by page. So I'll see how many I can fit on one. They
    # also come with their own titles...
    for i in range(len(runs)):
        c.showPage()
        textobject = c.beginText()
        textobject.setTextOrigin(inch, height-(0.5*inch))
        textobject.textLine('Translation, Run %d'%(i+1))
        c.drawText(textobject)
        im = Image.open(comt_im[i])
        im = scale_im(im)
        c.drawImage(comt_im[i],0.5*inch,height-(inch+im.size[1]),width=im.size[0],height=im.size[1],mask=None)
        oimh = im.size[1]
        textobject = c.beginText()
        textobject.setTextOrigin(inch, height-(inch+oimh+0.5*inch))
        textobject.textLine('Rotation, Run %d'%(i+1))
        c.drawText(textobject)
        im = Image.open(comr_im[i])
        im = scale_im(im)
        c.drawImage(comr_im[i],0.5*inch,height-(2*inch+oimh+im.size[1]),width=im.size[0],height=im.size[1],mask=None)
    # now, at long last, output all the raw data...
    c.showPage()
    textobject = c.beginText()
    textobject.setTextOrigin(inch, height-inch)
    # artifactual timepoints...
    c.setFont("Courier",8) 
    textobject.textLine('Artifact Timepoints')
    for i in range(len(runs)):
        textobject.textLine(' '*4+'Run %d:'%(i+1))
        artdata = open(artz[i],'r').read().split('\n')
        for j in artdata:
            textobject.textLine(' '*8+j)
            if textobject.getY() < (0.5*inch):
                textobject = newpage(textobject,c)
                textobject.textLine('Artifact Timepoints Continued')
    # MOTION parameters
    # note that textobject does NOT automatically pagebreak, but you can get the current Y value of 
    # the cursor with textobject.getY()
    c.drawText(textobject)
    c.showPage()
    textobject = c.beginText()
    textobject.setTextOrigin(inch, height-inch)
    c.setFont("Courier",8)
    mot_par = glob(os.path.join(root_dir,'analyses','func',subid,'preproc','motion','*.nii.gz.par'))
    textobject.textLine('Motion Parameters')
    for i in range(len(runs)):
        textobject.textLine('Run %d:'%(i+1))
        textobject.textLine('%-6s%-15s%-15s%-15s%-15s%-15s%-15s'%('TR','x','y','z','rot_x','rot_y','rot_z'))
        motdata = filter(lambda z: len(z)>0,[filter(lambda y: y!='',x.split(' ')) for x in open(mot_par[i],'r').read().split('\n')])
        for i,j in enumerate(motdata):
            for q,z in enumerate(j):
                if z[0]!='-':
                    j[q] = ' '+'%.5f'%float(z)
                else:
                    j[q] = '%.5f'%float(z)
            textobject.textLine('%-5s%-15s%-15s%-15s%-15s%-15s%-15s'%tuple([str(i+1)]+j))
            if textobject.getY() < (0.5*inch):
                textobject = newpage(textobject,c)
                textobject.textLine('Motion Parameters Continued')
                textobject.textLine('%-6s%-15s%-15s%-15s%-15s%-15s%-15s'%('TR','x','y','z','rot_x','rot_y','rot_z'))
    
    # NORM motion parameters
    norm_par = glob(os.path.join(root_dir,'analyses','func',subid,'preproc','art','fwhm_%i'%fwhm[-1],'norm.*.txt'))
    # 72 lines per page seems about fitting, with 4 columns of data, 8 columns total counting the TR. Each of the
    # normalized motion parameters is 6 characters, 'a.bcde'
    for i in range(len(runs)):
        #if not i%2:
        textobject = newpage(textobject,c)
        textobject.textLine('NORM Motion Parameters (rapidart output)')
        textobject.textLine('Run %d:'%(i+1));
        textobject.textLine('%6s%10s   %6s%10s   %6s%10s   %6s%10s'%('TR','Val  ','TR','Val  ','TR','Val  ','TR','Val  '))
        normdata = open(norm_par[i],'r').read().split('\n')[:-1]
        # now we have to determine the optimal arrangement...we can presume that because this pipeline is specificially designed
        # for the ellison project, *all* runs will be exactly 117 TRs, thus the columns should be 30, 30, 30, 27...
        normdata_ar = [[],[],[],[]]
        cnt = 0
        
        
        for TR2,datum in enumerate(normdata):
            normdata_ar[cnt].append([str(TR2+1),datum])
            if len(normdata_ar[cnt]) == 60 and cnt < 3:
                cnt+=1
    
        while len(normdata_ar[cnt]) < 61:
            normdata_ar[cnt].append(['',''])
        for row in range(60):
            textobject.textLine('%6s%10s   %6s%10s   %6s%10s   %6s%10s'%tuple(normdata_ar[0][row]+normdata_ar[1][row]+normdata_ar[2][row]+normdata_ar[3][row]))
        
    c.drawText(textobject)
    c.save()
