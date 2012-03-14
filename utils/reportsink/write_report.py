# general class for writing reportlab stuff. 

from reportlab.platypus import SimpleDocTemplate, Paragraph,\
                               Table, TableStyle, Spacer,\
                               PageBreak, PageTemplate
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
import time
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import Image as Image2
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from PIL import Image


def get_and_scale(imagefile,scale=1):
    from reportlab.platypus import Image as Image2
    im1 = scale_im(Image.open(imagefile))
    im = Image2(imagefile, im1.size[0]*scale, im1.size[1]*scale)  
    return im      
           
def scale_im(im):
    from numpy import array 
    # scales an image so that it will fit on the page with various margins...
    width, height = letter
    newsize = array(im.size)/(max(array(im.size)/array([width-(1*inch), height-(2*inch)])))
    newsize = tuple(map(lambda x: int(x), tuple(newsize)))
    return im.resize(newsize)     

class report():
    def __init__(self,fname,title):
        self.report = fname
        self.doc = SimpleDocTemplate(self.report, pagesize=letter,
                                rightMargin=36,leftMargin=36,
                                topMargin=72,bottomMargin=72)
        self.elements = []
        self.styles=getSampleStyleSheet()
        self.styles.add(ParagraphStyle(name='RIGHT', alignment=TA_RIGHT))
        
        formatted_time = time.ctime()
        
        ptext = '<font size=10>%s</font>' % formatted_time     
        self.elements.append(Paragraph(ptext, self.styles["Normal"]))
        self.elements.append(Spacer(1, 12)) 
        
        ptext = '<font size=22>%s</font>' %(title)   
        self.elements.append(Paragraph(ptext, self.styles["Normal"]))
        self.elements.append(Spacer(1, 24))
    
    def add_text(self,text,fontsize=12):
        ptext = '<font size=%s>%s</font>' % (str(fontsize),text)  
        self.elements.append(Paragraph(ptext, self.styles["Normal"]))
        self.elements.append(Spacer(1, 12)) 
        
    def add_image(self,fname,scale=1):
        im = get_and_scale(fname,scale=scale)
        self.elements.append(im)    
        self.elements.append(Spacer(1, 12))    
    
    def add_table(self,data,para=False):
        if para:
            data_para = []
            for dat in data:
                temp = []
                for da in dat:
                    temp.append(Paragraph(str(da),self.styles["Normal"]))
                data_para.append(temp)
            t=Table(data_para)
        else:
            t = Table(data)
            
        t.setStyle(TableStyle([('ALIGN',(0,0), (-1,-1),'LEFT'),
                               ('VALIGN',(0,0), (-1,-1), 'TOP'),
                               ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                               ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))
        t.hAlign='LEFT'
        self.elements.append(t)
        self.elements.append(Spacer(1, 12))
    
    def add_pagebreak(self):
        self.elements.append(PageBreak())
    
    def write(self):
        self.doc.build(self.elements)
        return self.report    
       
