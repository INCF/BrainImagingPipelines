from Tkinter import *
import Tix
from nipype.utils.filemanip import save_json, load_json
import argparse
import os

class gui_base():
    
    def __init__(self,name="config.json"):
        self.Top = Tk()
        
        self.Top.grid_rowconfigure(0, weight=1)
        self.Top.grid_columnconfigure(0, weight=1)
        
        self.canvas = Canvas(self.Top)
        self.canvas.grid(row=0, column=0, sticky='nswe')
        
        self.scrollbar = Scrollbar(self.Top,orient=VERTICAL,command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky='we')
        #self.scrollbar.pack(side=RIGHT)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.top = Frame(self.canvas)
        
        self.canvas.create_window(0, 0, window=self.top, anchor='nw')
        
        self.buttons = []
        self.entries = {}
        self.types = {}
        self._name = name
        self.vars = {}
        
    def run(self):
        
        self.canvas.configure(scrollregion=(0, 0, self.top.winfo_width(), self.top.winfo_height()))
        self.Top.mainloop()
    """
    def add_scrollbar(self):
        self.scrollbar = Scrollbar(self.Top,orient=horizontal,command=self.canvas.xview)
        self.scrollbar.grid(row=1, column=0, sticky='we')
        self.scrollbar.pack(side=RIGHT)
        self.canvas.configure(xscrollcommand=self.scrollbar.set)
    """
    def add_button(self,command,text='button'):
        B = Button(self.top, text=text, command=command)
        B.pack()
        self.buttons.append(B)
        self.top.update_idletasks()    
    
    def add_entry(self,label,typ=str):
        L = Label(self.top,text=label)
        L.pack()
        E = Entry(self.top,bd=1)
        E.pack()
        self.entries[label] = E
        self.types[label] = typ
        self.top.update_idletasks()
    
    def add_checkbox(self,label,typ=bool):
        self.vars[label] = BooleanVar()
        C = Checkbutton(self.top,text=label,variable=self.vars[label])#onvalue=True,offvalue=False)
        C.pack()
        self.entries[label] = C
        self.types[label] = typ
        self.top.update_idletasks()
        
    def to_json(self):
        D = {}
        for key, ent in self.entries.iteritems():
            if isinstance(ent,Entry):
                D[key]= self.types[key](ent.get())
            else:
                D[key]=self.types[key](self.vars[key].get())
        save_json(self._name,D)    
        
    def from_json(self):
        J = load_json(self._name)
        for key, ent in self.entries.iteritems():
            if isinstance(ent,Entry):
                ent.delete(0, END)
                try:
                    ent.insert(0, J[key])
                except:
                    continue     
            else:
                try:
                    if J[key]:
                        ent.select()
                except:
                    continue    

        
if __name__== "__main__":
    
    parser = argparse.ArgumentParser(description="example: \
                        run resting_preproc.py -c config.py")
    parser.add_argument('-c','--config',
                        dest='config',
                        required=True,
                        help='location of config file'
                        )
    args = parser.parse_args()
    
    a = gui_base(args.config)
    #a.add_scrollbar()
    a.add_entry("working_dir")
    a.add_entry("base_dir")
    a.add_entry("field_template")
    a.add_entry("sink_dir")
    a.add_entry("field_dir")
    a.add_entry("surf_dir")
    a.add_entry("crash_dir")
    a.add_entry("subjects")
    a.add_checkbox("run_on_grid")
    a.add_checkbox("use_fieldmap")
    a.add_checkbox("test_mode")
    a.add_checkbox("Interleaved")
    a.add_entry("SliceOrder")
    a.add_entry("TR",float)
    a.add_entry("echospacing",float)
    a.add_entry("TE_diff",float)
    a.add_entry("sigma",int)
    a.add_entry("norm_thresh",float)
    a.add_entry("z_thresh",float)
    a.add_entry("fwhm")
    a.add_checkbox("a_compcor")
    a.add_checkbox("t_compcor")
    a.add_entry("num_noise_components",float)
    a.add_entry("hpcutoff",float)
    a.add_entry("interscan_interval",float)
    a.add_entry("film_threshold",float)
    a.add_entry("overlayThresh")
    a.add_checkbox("is_block_design")
    
    a.add_button(a.to_json,"save")
    
    
    if os.path.exists(args.config):
        a.from_json()
    
    a.run()
