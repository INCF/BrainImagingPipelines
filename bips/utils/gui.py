from Tkinter import *
from nipype.utils.filemanip import save_json, load_json
import argparse
import os
from tkFileDialog import askopenfilename

class gui_base():
    
    def __init__(self,name="config.json"):
        self.Top = Tk()
        
        self.Top.grid_rowconfigure(0, weight=1)
        self.Top.grid_columnconfigure(0, weight=1)
        
        self.canvas = Canvas(self.Top)
        self.canvas.grid(row=0, column=0, sticky='nswe')
        
        self.scrollbar = Scrollbar(self.Top,orient=VERTICAL,command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky='ns')

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

    def add_button(self,command,text='button'):
        B = Button(self.top, text=text, command=command)
        B.pack()
        self.buttons.append(B)
        self.top.update_idletasks()    
    
    def ask_filename(self):
        filename = askopenfilename(filetypes=[("allfiles","*"),("configfiles","*.json")])
        return filename
        
    def add_label(self,label):
        L = Label(self.top,text=label)
        L.pack()
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
        C = Checkbutton(self.top,text=label,variable=self.vars[label])
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

        

