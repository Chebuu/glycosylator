#! /usr/bin/env python
'''
----------------------------------------------------------------------------

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>

2016 Thomas Lemmin
----------------------------------------------------------------------------
'''

import Tkinter as tk
import ttk
import Tkconstants, tkFileDialog, tkMessageBox
import os,sys

import sqlite3
import networkx as nx

import matplotlib as mpl
mpl.use('TkAgg')
import matplotlib.backends.tkagg as tkagg
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
import numpy as np

SELF_BIN = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, SELF_BIN + '/support')
import glycosylator as glc 

class CreateToolTip(object):
    '''
    create a tooltip for a given widget
    Code from https://www.daniweb.com/programming/software-development/code/484591/a-tooltip-class-for-tkinter
    '''
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.close)
    def enter(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("all")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = tk.Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background='white', relief='solid', borderwidth=1,
                       font=("Arial", "8", "normal"))
        label.pack(ipadx=1)
    def close(self, event=None):
        if self.tw:
            self.tw.destroy()

class GlycosylatorGUI(tk.Tk):
    """ This Class creates the graphical interface for glycosylator. It is composted of a main window.
    In addition, it will create one window for the displaying the database (db_window) and one for uploading a new glycan
    Variables:
        myGlycosylator: glycosylator instance (for identifying and building glycans)
        myDrawer: drawer instance (for displaying glycoprotien and glycans)
        user_glycans: dictionary of glycans defined by user. Glycan name as a key and glycan topology as a value
        common_glycans: dictionary of common glycans. Glycan name as a key and glycan topology as a value
        db_window: database window
        selected_glycan: glycan selected by the user
        original_glycans: dictionary of glycans detected in the original glycoprotein. Sequon as a key and glycan tree as a value
        original_glycanMolecules: dictionary of glycans Molecules. Sequon as key and Molecule instance as value
        linked_glycans:  dictionary of built-in glycans. Sequon as a key and glycan tree as a value
        linked_glycanMolecules: dictionary of built-in glycans Molecules. Sequon as key and Molecule instance as value
        names: dictionary of glycan residue name. Residue id as key and resname as value
    """

    def __init__(self):
        self.cwd = os.getcwd()
        self.myGlycosylator = glc.Glycosylator(SELF_BIN +'/support/toppar_charmm/carbohydrates.rtf', SELF_BIN + '/support/toppar_charmm/carbohydrates.prm')
        self.myGlycosylator.builder.Topology.read_topology(SELF_BIN +'/support/topology/DUMMY.top')
        self.myDrawer = glc.Drawer()
        #database variables
        self.user_glycans = {} 
        self.db_commong = SELF_BIN + '/test_db.db'
        self.common_glycans = {}
        #database window
        self.db_window =  None
        self.selected_canvas = None
        self.selection = None
        self.selected_glycan = None
	
        #bookkeeping
        self.sequon_colors = {}
        self.original_glycans = {}
        self.original_glycanMolecules = {}
        self.linked_glycans = {}
        self.linked_glycanMolecules = {}
        self.names = {}

        #create root window
        tk.Tk.__init__(self)
        self.title('Glycosylator')
        self.geometry('520x520')
        #estimate dpi of screen
        mm2in = 1/25.4
        pxw = self.winfo_screenwidth()
        inw = self.winfo_screenmmwidth() * mm2in
        #DPI is usually overestimated by about 30% for an unknown reason
        self.dpi = int(pxw/inw*.65)
        #self.resizable(False, False)
        self.protocol('WM_DELETE_WINDOW', self.save_before_close)
        # Create menubar
        self.menubar = tk.Menu(master=self, bg="lightgrey", fg="black")
        # file menu
        self.file_menu = tk.Menu(self.menubar, tearoff=0, bg="lightgrey", fg="black") 
        self.file_menu.add_command(label="Open glycoprotein", accelerator = "Ctrl+O", command = self.load_glycoprotein) 
        self.file_menu.add_command(label="Save glycoprotein", accelerator = "Ctrl+S", command = self.save_glycoprotein) 
        self.file_menu.add_command(label="Export patches", accelerator = "Ctrl+P", command = self.save_patches) 
        self.file_menu.add_command(label="Propreties", command = self.set_propreties) 
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.config(menu=self.menubar)
        # glycan menu
        self.gl_menu = tk.Menu(self.menubar, tearoff=0, bg="lightgrey", fg="black") 
        self.gl_menu.add_command(label="Import glycan library", accelerator = "Ctrl+I", command = self.import_library) 
        self.gl_menu.add_command(label="Export glycan library", accelerator = "Ctrl+E", command = self.export_library)
        self.menubar.add_cascade(label="Glycan library", menu=self.gl_menu)

        self.config(menu=self.menubar)
        
        # Create and layout main frames
        self.left_frame = tk.Frame(self, width = 250, height = 500, bg = 'white')
        self.right_frame = tk.Frame(self, width = 250, height = 500, bg = 'white')
        self.left_frame.grid(column=0, row=0)
        self.right_frame.grid(column=1, row=0)
        
        # Create widget for left frame
        self.v_scrollbar = tk.Scrollbar(self.left_frame, orient = 'vertical')
        self.h_scrollbar = tk.Scrollbar(self.left_frame, orient = 'horizontal')
        self.glycoprotein_2D = tk.Canvas(self.left_frame, width= 250, height = 500, bg = 'white', scrollregion=(0, 0, 400, 800))
        self.glycoprotein_2D.configure(yscrollcommand = self.v_scrollbar.set)
        self.glycoprotein_2D.configure(xscrollcommand = self.h_scrollbar.set)
        self.v_scrollbar.config(command = self.glycoprotein_2D.yview)
        self.h_scrollbar.config(command = self.glycoprotein_2D.xview)

        self.detach_button = tk.Button(self.left_frame, command = self.detach_plot)
        self.detach_icon = tk.PhotoImage(file="icons/detach.gif")
        self.detach_button.config(image = self.detach_icon)
        #Layout left frame
        self.glycoprotein_2D.grid(column = 0, row= 0)
        self.detach_button.grid(column = 0, row= 0, sticky='SE')
        self.v_scrollbar.grid(column = 1, row = 0, sticky='NS')
        self.h_scrollbar.grid(column = 0, row = 1, sticky='EW')


        # Create widget for right frame       
        self.glycosylator_logo = tk.PhotoImage(file="icons/glycosylator_logo.gif")
        self.w_logo = tk.Label(self.right_frame, image=self.glycosylator_logo)
        self.chain_label = tk.Label(self.right_frame, text="Chain:", bg = 'white')
        options = ['-']
        self.chain = tk.StringVar(self.right_frame)
        self.chain_menu = tk.OptionMenu(self.right_frame, self.chain, *options, command = self.update_sequons)
        self.chain_menu.configure(state="disabled")
        self.sequon_label = tk.Label(self.right_frame, text="Sequon:", bg = 'white')
        self.sequon = tk.StringVar(self.right_frame)
        self.sequon_menu = tk.OptionMenu(self.right_frame, self.sequon, *options)
        self.sequon_menu.configure(state="disabled")
        self.glycan_label = tk.Label(self.right_frame, text="Click to modify glycan", bg = 'white')
        self.glycan_2D = tk.Canvas(self.right_frame, width = 150, height = 150, bg = 'white')
        self.glycan_2D.bind("<Button-1>", self.database_window)
        self.glycosylate_button = tk.Button(self.right_frame, text="Glycosylate", command = self.glycosylate)
        self.glycosylateAll_button = tk.Button(self.right_frame, text="Glycosylate all")
        self.clashes = tk.Button(self.right_frame, text="Remove clashes")
        # Layout right frame       
        i = 0
        self.w_logo.grid(column = 0, row =  i, sticky='N'); i+=1
        self.chain_label.grid(column = 0, row =  i, sticky='W'); i+=1
        self.chain_menu.grid(column = 0, row =  i); i+=1
        self.sequon_label.grid(column = 0, row =  i, sticky='W'); i+=1
        self.sequon_menu.grid(column = 0, row =  i); i+=1
        self.glycan_label.grid(column = 0, row =  i, sticky='W'); i+=1
        self.glycan_2D.grid(column = 0, row =  i); i+=1
        self.glycosylate_button.grid(column = 0, row =  i); i+=1
        self.glycosylateAll_button.grid(column = 0, row =  i); i+=1
        self.clashes.grid(column = 0, row =  i); i+=1 


    def save_before_close(self):
        """Do some clean up before destroying main window
        """
        if self.db_window:
            self.db_window.destroy()
        self.destroy()

    def detach_plot(self):
        """Opens 2D represenation of glycoprotein in a separate window. 
        """
        detached = tk.Toplevel(self)
        detached.wm_title("Glycoprotein")
        fig = mpl.figure.Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(111)
        chid =  self.chain.get()

        l = len(self.myGlycosylator.sequences[chid])
        sequons = [k for k in self.myGlycosylator.sequons.keys() if chid in k[:len(chid)]]
        trees = self.myGlycosylator.glycans
        trees.update(self.linked_glycans)
        self.myDrawer.draw_glycoprotein(l, self.myGlycosylator.get_start_resnum(chid), sequons, ax = ax, axis = 0,
                trees = trees, names = self.names, sequon_color = self.sequon_colors)
        ax.axis('equal')
        ax.axis('off')

        canvas = FigureCanvasTkAgg(fig, master=detached)
        canvas.show()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        toolbar = NavigationToolbar2TkAgg(canvas, detached)
        toolbar.update()
        canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def update_sequons(self, chid, *arg):
        """ Updates option menu of sequons
        Parameters:
            chid: selected chain id
        """
        sequons = [k for k in self.myGlycosylator.sequons.keys() if chid in k[:len(chid)]]
        sequons = glc.alphanum_sort(sequons)
        self.sequon_menu['menu'].delete(0, 'end')
        self.sequon.set(sequons[0])

        for sequon in sequons:
            self.sequon_menu['menu'].add_command(label=sequon, command=tk._setit(self.sequon, sequon, self.draw_glycan))
        self.draw_glycan(self.sequon)
        self.draw_glycoprotein(chid)
    
    def draw_glycan(self, sequon, *arg):
        """ Draws 2D representation of glycan of selected sequon
        Updates glycan_2D canvas
        Parameters:
            sequon: id of sequon
        """
        fig = mpl.figure.Figure(figsize=(100./self.dpi, 100./self.dpi))
        ax = fig.add_subplot(111)
        if type(sequon) is not str:
            sequon =  sequon.get()
        
        if sequon in self.sequon_colors:
            color = self.sequon_colors[sequon]
        else:
            color = [.5, .5, .5]
        # Draw protein fragment
        self.myDrawer.draw_protein_fragment(ax = ax, sequon_color = color)
        # Drawing glycan

        if sequon in self.linked_glycans:
            root,tree =  self.linked_glycans[sequon]
        elif sequon in self.original_glycans:
            root,tree =  self.original_glycans[sequon]
        else:
            return 0
        self.myDrawer.draw_tree(tree, root, self.names, root_pos = [0, 0], direction = 1, ax = ax, axis = 0)
        ax.axis('equal')
        ax.axis('off')
        ax.set_ylim((-3, 6))
        ax.set_xlim((-3, 3))

        # Add to tk window
        figure_canvas_agg = FigureCanvasAgg(fig)
        figure_canvas_agg.draw()
        figure_x, figure_y, figure_w, figure_h = fig.bbox.bounds
        figure_w, figure_h = int(figure_w), int(figure_h)
        self.glycan_image = tk.PhotoImage(master=self.glycan_2D)
        self.glycan_image = tk.PhotoImage(master=self.glycan_2D, width=figure_w, height=figure_h)
        self.glycan_2D.create_image(figure_w/2, figure_h/2, image=self.glycan_image)
        tkagg.blit(self.glycan_image, figure_canvas_agg.get_renderer()._renderer, colormode=2)
        
    def draw_glycoprotein(self, chid):
        """Draws 2D representation of glycoprotein in right panel
        Updates glycoprotein_2D canvas
        Parameters:
            chid: chain id (string or handle)
        """
        fig = mpl.figure.Figure(figsize=(250/self.dpi, 500/self.dpi)) 
        ax = fig.add_axes([0, 0, 1, 1])

        if type(chid) is not str:
            chid =  chid.get()

        l = len(self.myGlycosylator.sequences[chid])
        
        trees = self.myGlycosylator.glycans
        trees.update(self.linked_glycans)
         
        sequons = [k for k in self.myGlycosylator.sequons.keys() if chid in k[:len(chid)]]
        self.myDrawer.draw_glycoprotein(l, self.myGlycosylator.get_start_resnum(chid), sequons, ax = ax, axis = 1,
                trees = trees, names = self.names)
        ax.axis('equal')
        ax.axis('off')
        figure_canvas_agg = FigureCanvasAgg(fig)
        figure_canvas_agg.draw()
        figure_x, figure_y, figure_w, figure_h = fig.bbox.bounds
        figure_w, figure_h = int(figure_w), int(figure_h)
        # attaching figure to canvas
        self.glycoprotein_image = tk.PhotoImage(master=self.glycan_2D, width=figure_w, height=figure_h)
        self.glycoprotein_2D.create_image(figure_w/2, figure_h/2, image=self.glycoprotein_image)
        tkagg.blit(self.glycoprotein_image, figure_canvas_agg.get_renderer()._renderer, colormode=2)


    def load_glycoprotein(self):
        """Open pdb file containing a glycoprotein. 
        Updates:
            - left_panel display glycoprotein
            - righ_panel chains, sequons and displayed glycan
        """
        filename = tkFileDialog.askopenfilename(initialdir = self.cwd, title = "Select glycoprotein", filetypes = (("pdb files","*.pdb"),("all files","*.*"))) 
        if not filename:
            return -1
        #Clear previous variable
        self.linked_glycans = {}
        self.linked_glycanMolecules = {}
        #Load new glycoprotein and extract glycans
        self.myGlycosylator.load_glycoprotein(filename)
        self.original_glycansMolecules = self.myGlycosylator.glycanMolecules.copy()
        self.original_glycans = self.myGlycosylator.glycans.copy()
        self.names = self.myGlycosylator.names
        
        #Update the option menus
        chids = self.myGlycosylator.sequences.keys()
        self.chain_menu['menu'].delete(0, 'end')
        self.chain.set(chids[0])
        for chid in chids:
            self.chain_menu['menu'].add_command(label = chid, command = tk._setit(self.chain, chid, self.update_sequons))
        self.chain_menu.configure(state="normal")
        chid  = chids[0]

        self.draw_glycoprotein(self.chain.get())

        sequons = [k for k in self.myGlycosylator.sequons.keys() if chid in k[:len(chid)]]
        sequons = glc.alphanum_sort(sequons)
        self.sequon_menu['menu'].delete(0, 'end')
        self.sequon.set(sequons[0])
        for sequon in sequons:
            self.sequon_menu['menu'].add_command(label = sequon, command = tk._setit(self.sequon, sequon, self.draw_glycan))
        self.sequon_menu.configure(state="normal")
        self.draw_glycan(self.sequon.get())

    def save_glycoprotein(self):
        """Dialog for saving a glycoprotein
        """
        filename = tkFileDialog.asksaveasfilename(initialdir = self.cwd, defaultextension=".pdb", filetypes = (("pdb files","*.pdb"),("all files","*.*"))) 
        if filename is None:
            return
        self.myGlycosylator.glycans.update(self.linked_glycans)
        self.myGlycosylator.save_glycoprotein(filename)


    def show_database(self):
        """Make database window visible again
        """
        self.db_window.update()
        self.db_window.deiconify()
        self.selected_glycan =  None

    def hide_database(self):
        """Hide database window
        """
        if self.selected_canvas:
            self.selected_canvas.delete(self.selection)
            self.selected_canvas = None
            self.selection = None
        self.db_window.withdraw()
        if self.selected_glycan:
            root,tree,names = self.build_glycan_tree(self.selected_glycan[1]['UNIT'])
            self.glycan_image = self.draw_glycan_in_canvas(self.glycan_2D, tree, root, names)
 
    def select_glycan(self, event = None):
        """ Check if a glycan has been selected
        """
        if not self.selected_glycan:
            tkMessageBox.showerror("Error", "Please select a glycan")
        else:
            self.hide_database()


    def database_window(self, event=None):
        """Window with all databases (common and user defined)
           -Notebook with two tabs: one for common glycans and one for user's
        """
        if self.db_window:
            self.show_database()
            return -1
        self.db_window = tk.Toplevel(self)
        self.db_window.wm_title("Glycan Databases")
        self.db_window.protocol('WM_DELETE_WINDOW', self.hide_database)
        #tabs
        self.db_window.bind('<Return>', self.select_glycan)
        self.tab_control = ttk.Notebook(self.db_window)
        self.tb_commong = tk.Frame(self.tab_control)
        self.tb_userg = tk.Frame(self.tab_control )
        self.tab_control.add(self.tb_commong, text='Common glycans')
        self.tab_control.add(self.tb_userg, text='My glycans')
        self.db_ok = tk.Button(self.db_window, text='OK', command = self.select_glycan)
        self.db_cancel = tk.Button(self.db_window, text='cancel', command = self.hide_database)
        
        self.tab_control.grid(column = 0, row = 0, columnspan=2)
        self.db_cancel.grid(column = 1, row = 1)
        self.db_ok.grid(column = 1, row = 1, sticky ='E')

        #common glycans tab
        self.canvas_commong = tk.Canvas(self.tb_commong, scrollregion=(0, 0, 1000, 2000))
        self.v_sb_cg = tk.Scrollbar(self.tb_commong, orient = 'vertical', command = self.canvas_commong.yview)
        self.canvas_commong.config(yscrollcommand = self.v_sb_cg.set)
        self.canvas_commong.grid(column = 0, row = 0)
        self.v_sb_cg.grid(column = 1, row = 0, sticky='NS')

        if not self.common_glycans:
            self.common_glycans = self.import_glycans(self.db_commong)
            self.common_images = []
            self.common_canvas = []
            self.common_names = []
            self.display_db(self.canvas_commong, self.common_glycans, self.common_images, self.common_canvas, self.common_names)

        #user glycans tab
        self.canvas_userg = tk.Canvas(self.tb_userg, scrollregion=(0, 0, 1000, 2000))
        self.v_sb_ug = tk.Scrollbar(self.tb_userg, orient = 'vertical', command = self.canvas_userg.yview)
        self.canvas_userg.config(yscrollcommand = self.v_sb_ug.set)
        self.ug_button_frame = tk.Frame(self.tb_userg)
        self.canvas_userg.grid(column = 0, row = 0)
        self.v_sb_ug.grid(column = 1, row = 0, sticky='NS')
        self.ug_button_frame.grid(column = 0, row = 1, sticky= 'SE')

        #add buttons for import
        self.ug_import = tk.Button(self.ug_button_frame, command = self.import_library)
        self.import_icon = tk.PhotoImage(file="icons/import.gif")
        self.ug_import.config(image = self.import_icon)

        self.ug_export = tk.Button(self.ug_button_frame, command = self.export_library)
        self.export_icon = tk.PhotoImage(file="icons/export.gif")
        self.ug_export.config(image = self.export_icon)
        
        self.ug_add = tk.Button(self.ug_button_frame, command = self.add_glycan_form)
        self.add_icon = tk.PhotoImage(file="icons/add.gif")
        self.ug_add.config(image = self.add_icon)
        
        self.ug_delete = tk.Button(self.ug_button_frame, command = self.delete_glycan)
        self.delete_icon = tk.PhotoImage(file="icons/delete.gif")
        self.ug_delete.config(image = self.delete_icon)

        self.ug_import.grid(column = 0, row = 0)
        self.ug_export.grid(column = 1, row = 0)
        self.ug_add.grid(column = 2, row = 0)
        self.ug_delete.grid(column = 3, row = 0)

        self.user_images = []
        self.user_canvas = []
        self.user_names = []
        if self.user_glycans:
            self.display_db(self.canvas_userg, self.user_glycans, self.user_images, self.user_canvas, self.user_names)

    def display_db(self, master, glycans, glycan_images, glycan_canvas, glycan_ttp):
        """Generates thumbnail images for all glycans in a database
        Parameters:
            master: master Canvas for drawing
            glycans: dictionary of glycans. Names as keys and connectivity topology as values
            glycan_images: list for storing generated images
            glycan_canvas: list for storing generated canvas
            glycan_ttp: list for storing labels for each glycan

        """
        i = 0
        j = 0
        counter = 0
        for name in glycans.keys():
            # put five images per row
            if j and not j%5:
                i += 1
                j = 0
            units = glycans[name]['UNIT']
            root,tree,names = self.build_glycan_tree(units)
            fig = mpl.figure.Figure(figsize=(70./self.dpi, 70./self.dpi))
            ax = fig.add_subplot(111)
            
            self.myDrawer.draw_tree(tree, root, names, root_pos = [0, 0], direction = 1, ax = ax, axis = 0)
            ax.axis('equal')
            ax.axis('off')
            ax.set_ylim((-1, 6))
            ax.set_xlim((-3, 3))

            # Add to tk window
            figure_canvas_agg = FigureCanvasAgg(fig)
            figure_canvas_agg.draw()
            figure_x, figure_y, figure_w, figure_h = fig.bbox.bounds
            figure_w, figure_h = int(figure_w), int(figure_h)
            canvas = tk.Canvas(master, width = 100, height = 100)
            glycan_image = tk.PhotoImage(master = canvas, width=figure_w, height=figure_h)
            canvas.create_image(figure_w/2, figure_h/2, image = glycan_image, tags = counter)
            canvas.bind("<Button-1>", self.clicked_glycan)
            canvas_ttp = CreateToolTip(canvas, 'Name: ' + name + '\nStrucutre: ' + self.myDrawer.tree_to_text(tree, root, names, visited = []))
            tkagg.blit(glycan_image, figure_canvas_agg.get_renderer()._renderer, colormode=2)
            canvas.grid(column = j, row =  i)
            glycan_images.append(glycan_image)
            glycan_canvas.append(canvas)
            glycan_ttp.append(canvas_ttp)
            j += 1
            counter += 1
        
    def build_glycan_tree(self, glycan):
        """Convert a glycan connectivity tree into a graph for drawing
        Parameters:
            glycan: list of units form connectivity topology ['UNIT']
        Returns:
            G: graph representation of glycans
            names: dictionary with unit id as key and resname as value
            root: id of root unit 
        """
        G = nx.Graph()
        idx = 0
        top = {}
        names = {}
        for unit in glycan:
            if not unit[1]:
                root = idx
            top[' '.join(unit[2])] = idx
            names[idx] = unit[0]
            idx += 1
        for k in top.keys():
            e1 = ' '.join(k.split(' ')[:-1])
            if e1 != k:
                e = (top[k], top[e1])
                G.add_edge(top[k], top[e1], patch=k.split(' ')[-1])
                #G.add_edge(*e)
            else:
                G.add_node(top[k])
        return root,G,names

    def clicked_glycan(self, event):
        """Determines which glycan has been selected from database
        The glycan will be highlighted with a red rectangle.
        Initializes:
            selection: rectangle around the canvas
            selected_canvas: selected canvas
            selected_glycan: item form glycan dictionary (Key: name, Value: glycan connect topology)
        """
        #tab  = self.tab_control.tab(self.tab_control.select(), "text")
        tab  = self.tab_control.index(self.tab_control.select())
        item = event.widget.find_closest(event.x, event.y)
        idx = int(event.widget.gettags(item)[0])
        
        if self.selected_canvas:
            self.selected_canvas.delete(self.selection)

        if tab == 0:
            self.selected_canvas = self.common_canvas[idx]
            self.selected_glycan = self.common_glycans.items()[idx] 
        elif tab == 1:
            self.selected_canvas = self.user_canvas[idx]
            self.selected_glycan = self.user_glycans.items()[idx] 
        self.selection = self.selected_canvas.create_rectangle(0, 0, 100, 100, outline='red', width=4)


    def import_library(self):
        """ Opens dialog for user to import their library
        Update the database windows, if it has already been created.
        """
        filename = tkFileDialog.askopenfilename(initialdir = self.cwd, title = "Select glycan library", filetypes = (("db files","*.db"),("all files","*.*")))
        if not filename:
            return -1
        self.user_glycans = self.import_glycans(filename)
        if self.db_window:
            if self.user_canvas:
                self.canvas_userg.delete(all)
            self.user_images = []
            self.user_canvas = []
            self.user_names = []
            self.display_db(self.canvas_userg, self.user_glycans, self.user_images, self.user_canvas, self.user_names)
        

    def import_glycans(self, filename):
        """Import connectivity topology from sql database
        This function will initialize connect_topology
        Parameters:
            filename: path to database
        """
        try:
            conn = sqlite3.connect(filename)
        except:
            print "Error while connecting to the database " + filename
            return -1
        cursor =  conn.cursor()
        cursor.execute("SELECT * FROM glycans")
        glycans = cursor.fetchall()

        connect_topology = {}
        for glycan in glycans:
            name,tree =  glycan
            residue = {}
            residue['UNIT'] = []
            nbr_unit = 0
            for unit in tree.split('|'):
                unit = unit.split(' ')
                nbr_unit += 1
                if len(unit) > 2:
                    residue['UNIT'].append([unit[0],unit[1], unit[2:]])
                else:
                    residue['UNIT'].append([unit[0], ' ', []])
                
            residue['#UNIT'] = nbr_unit
            connect_topology[name] = residue
        return connect_topology 
    
    def export_library(self):
        """Open dialog for user to save their glycan library
        """
        filename = tkFileDialog.asksaveasfilename(initialdir = self.cwd, title = "Save glycan library", filetypes = (("db files","*.db"),("all files","*.*")))
        self.export_glycans(filename, self.user_glycans)
    
    def export_glycans(self, filename, connect_topology):
        """Export connectivity topology to sql database
        This function will export a SQL database with all the user glycans.
        """
        try:
            conn = sqlite3.connect(filename)
        except:
            print "Error while connecting to the database " + filename
            return -1
        cursor =  conn.cursor()
        tn = 'glycans'
        gn = 'glycan_name'
        
        self.selected_glycan[1] = 'glycan_tree'
        cursor.execute("DROP TABLE IF EXISTS {tn}".format(tn = tn))
        cursor.execute("CREATE TABLE {tn} ({gn} text, {gt} text)".format(tn =  tn, gn = gn, gt = gt))

        for key in connect_topology.keys():
            units = connect_topology[key]['UNIT']
            glycan = []
            for unit in units:
                v = []
                v.extend(unit[0:2])
                v.extend(unit[2])
                glycan.append(' '.join(v))
            glycan = '|'.join(glycan)
            
            cursor.execute("INSERT INTO {tn} VALUES (\'{gn}\', \'{gt}\')".format(tn = tn, gn = key, gt = glycan))

        conn.commit()
        conn.close()

    def add_glycan_form(self):
        """Adds a glycan to a library. 
        Supported format:
              pdb
              glycosylator topology 
        """
        self.new_connect_top = {}
        self.add_window = tk.Toplevel(self)
        self.add_window.wm_title("Add glycan")
        #Labels
        tk.Label(self.add_window, text = 'File: ').grid(row = 0, column =  0, sticky = 'W')
        tk.Label(self.add_window, text = 'Glycan Name: ').grid(row = 1, column = 0, sticky = 'W')
        tk.Label(self.add_window, text = 'Structure: ').grid(row = 2, column = 0, sticky = 'W')
        #
        self.glycan_name_entry = tk.Entry(self.add_window)
        self.choose_file = tk.Button(self.add_window, text = 'Choose file', command = self.get_connect_topology)
        self.structure_entry = tk.Entry(self.add_window, state = 'disable')
        self.glycan_canvas = tk.Canvas(self.add_window, width =  100, height =  100)
        self.cancel_glycan_button =  tk.Button(self.add_window, text = 'Cancel', command = self.add_window.destroy)
        self.add_glycan_button = tk.Button(self.add_window, text = 'Add glycan', command = self.add_glycan)
        #Pack
        self.choose_file.grid(row = 0, column = 1, sticky = 'E')
        self.glycan_name_entry.grid(row = 1, column = 1, sticky = 'E')
        self.structure_entry.grid(row = 2, column = 1, sticky = 'E')
        self.glycan_canvas.grid(row = 0, column = 2, rowspan = 3, columnspan = 2)
        self.cancel_glycan_button.grid(row = 3, column = 2)
        self.add_glycan_button.grid(row = 3, column = 3)

#    def close_add(self):


    def add_glycan(self):
        """Add new glycan to user's database

        """
        self.user_glycans[self.glycan_name_entry.get()] = self.new_connect_top
        self.add_window.destroy()
        self.user_images = []
        self.user_canvas = []
        self.user_names = []
        if self.user_glycans:
            self.display_db(self.canvas_userg, self.user_glycans, self.user_images, self.user_canvas, self.user_names)
        
    def draw_glycan_in_canvas(self, canvas, tree, root, names, h = 100., w = 100.):
        """ Draws a glycan on to a canvas
            Parameters:
                canvas: tk.Canvas where the image should be drawn
                tree: tree representation of the glycan
                root: id of root node in tree
                names: dictionary with node id as keys and resname as values
                h: height of figure in px
                w: width of figure in px
            Returns:
                glycan_image: image instance. This should be saved otherwise the image will be destroyed, thus not displayed.
        """
            fig = mpl.figure.Figure(figsize=(h/self.dpi, w/self.dpi))
            ax = fig.add_subplot(111)
            
            self.myDrawer.draw_tree(tree, root, names, root_pos = [0, 0], direction = 1, ax = ax, axis = 0)
            ax.axis('equal')
            ax.axis('off')
            ax.set_ylim((-1, 6))
            ax.set_xlim((-3, 3))

            # Add to tk window
            figure_canvas_agg = FigureCanvasAgg(fig)
            figure_canvas_agg.draw()
            figure_x, figure_y, figure_w, figure_h = fig.bbox.bounds
            figure_w, figure_h = int(figure_w), int(figure_h)
            glycan_image = tk.PhotoImage(master = canvas, width=figure_w, height=figure_h)
            canvas.create_image(figure_w/2, figure_h/2, image = glycan_image)
            tkagg.blit(glycan_image, figure_canvas_agg.get_renderer()._renderer, colormode=2)
            return glycan_image

    def get_connect_topology(self):
        """Dialog window for selecting new glycan. Can be either pdb or topology file
        Intialize new_connect_top 
        """
        filename = tkFileDialog.askopenfilename(initialdir = self.cwd, title = "Select glycan library", filetypes = (("pdb files","*.pdb"), ("topology file", "*.top"), ("all files","*.*")))
        if not filename:
            return -1
        path, file_extension = os.path.splitext(filename)

        if file_extension == '.pdb':
            glycan = glc.Molecule('glycan')
            glycan.read_molecule_from_PDB(filename, update_bonds = False)
            self.myGlycosylator.assign_patches(glycan)
            connect_tree = self.myGlycosylator.build_connect_topology(glycan)
            self.new_connect_top = self.connect_tree_to_topology(connect_tree)
        elif file_extension == '.top':
            name,self.new_connect_top = self.read_connect_topology(filename)
            print self.new_connect_top
            self.glycan_name_entry.insert(0, name)

        root,tree,names = self.build_glycan_tree(self.new_connect_top['UNIT'])
        self.new_glycan_image = self.draw_glycan_in_canvas(self.glycan_canvas, tree, root, names, h = 70., w = 70.)
        self.structure_entry.configure(state='normal')
        self.structure_entry.delete(0, tk.END)
        self.structure_entry.insert(0, self.myDrawer.tree_to_text(tree, root, names, visited = []))
        self.structure_entry.configure(state='disabled')
    
    def read_connect_topology(self, filename):
        """Reads glycan connect topology from text file
        Returns:
            resname: name of glycan
            residue: dictionary with connect topology
        """
        lines = glc.readLinesFromFile(filename)
        residue = {}
        nbr_units = 0
        for line in lines:                                                             # Loop through each line 
            line = line.split('\n')[0].split('!')[0].split() #remove comments and endl
            if line:
                if line[0] == 'RESI':    
                    residue['UNIT'] = []
                    resname = line[1]
                    nbr_units = 0
                elif line[0] == 'UNIT':
                    self.read_unit(line, residue)
                    nbr_units += 1
        residue['#UNIT'] = nbr_units
        return resname,residue
    
    def read_unit(self, unit, residue):
        """Reads an unit in glycan connect topology
        """
        if len(unit)>2:
            residue['UNIT'].append([unit[1], unit[2], unit[3:]])
        else:
            residue['UNIT'].append([unit[1], '', []])


    def connect_tree_to_topology(self, connect_tree):
        """Converts a connect tree to a connect topology
           In connect tree the connectivity is represented as a string whereas it is a list in connect topology
        """
        connect_topology = {}
        units = connect_tree['UNIT']
        unit_list = []
        n_unit = 0
        for unit in units:
            unit = filter(None, unit.split(' '))
            n_unit +=1
            if len(unit) > 1:
                unit_list.append([unit[0], 'C1', unit[1:]])
            else:
                unit_list.append([unit[0], '', []])
        connect_topology['UNIT'] = unit_list
        connect_topology['#UNIT'] = n_unit
        return connect_topology

    def delete_glycan(self):
        """Delete glycan from database
        """
        if not self.selected_glycan:
            tkMessageBox.showerror("Error", "Please select a glycan to be deleted")

        k,v = self.selected_glycan
        del self.user_glycans[k]
        self.canvas_userg.delete(all)
        self.user_images = []
        self.user_canvas = []
        self.display_db(self.canvas_userg, self.user_glycans, self.user_images, self.user_canvas, self.user_names)
    
    def glycosylate(self):
        """ Glycosylate sequon with chosen glycan
        
        """
        chid = self.chain.get()
        sequon = self.sequon.get()
        self.sequon_colors[sequon] = [.7, .1, 0]
        key = self.sequon.get()
        residue = self.myGlycosylator.get_residue(key)
        #Build new glycan
        if self.selected_glycan:
            self.myGlycosylator.connect_topology['SELECTED'] = self.selected_glycan[1]
            original_glycan = None
            connect_tree = None 
        #Use current glycan
        else:
            original_glycan = self.original_glycan[key]
            connect_tree = self.myGlycosylator(original_glycan) 
            self.myGlycosylator.connect_topology['SELECTED'] = self.connect_tree_to_topology(connect_tree) 

        #if key in self.original_glycans:
        #    connect_tree = 
        #    original_glycan = self.original_glycans[key]
        glycan,bonds = self.myGlycosylator.glycosylate('SELECTED', 
                                                        template_glycan_tree = connect_tree, 
                                                        template_glycan = original_glycan,
                                                        link_residue=residue, link_patch = 'NGLB')
        new_glycan = glc.Molecule(key)
        new_glycan.set_AtomGroup(glycan, bonds = bonds)
        self.linked_glycanMolecules[key] = new_glycan
        self.linked_glycans[key] = [new_glycan.rootRes, new_glycan.interresidue_connectivity]
        self.names.update(new_glycan.get_names())
        # Update glycoprotein and sequon panels
        self.draw_glycoprotein(chid)
        self.draw_glycan(sequon)

    def set_propreties(self):
        """Allows user to ajust parameters to improve the rendering of the GUI (size and resolution)
        """
        pass
    def export_patches(self):
        """Exports a configuration file for CHARMM with all the patches that have to be applied in order to build glycans.
        """
        pass
if __name__ == "__main__":
    glycogui = GlycosylatorGUI()
    glycogui.mainloop()
       
