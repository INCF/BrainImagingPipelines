# Import Stuff
from ...scripts.base import create_first
import os
from .....base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool
import traits.api as traits
from .....flexible_datagrabber import Data, DataBase

"""
Part 1: Define a MetaWorkflow
"""


mwf = MetaWorkflow()
mwf.uuid = '431e1fd2a37f11e2bff300259058e3f2'
mwf.help = """
Stimulus Motion Correlation
===========================
This workflow can be used to compute and visualize stimulus-motion correlation.

"""

mwf.tags=['fMRI','First Level', 'Stimulus Motion']

"""
Part 2: Define the config class & create_config function
"""

class config(HasTraits):
    uuid = traits.Str(desc="UUID")
    desc = traits.Str(desc="Workflow Description")
    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    sink_dir = Directory(os.path.abspath('.'), mandatory=True, desc="Location where the BIP will store the results")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")
    save_script_only = traits.Bool(False)

    # Execution

    run_using_plugin = Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.Enum("PBS", "MultiProc", "SGE", "Condor",
        usedefault=True,
        desc="plugin to use, if run_using_plugin=True")
    plugin_args = traits.Dict({"qsub_args": "-q many"},
        usedefault=True, desc='Plugin arguments.')
    test_mode = Bool(False, mandatory=False, usedefault=True,
        desc='Affects whether where and if the workflow keeps its \
                            intermediary files. True to keep intermediary files. ')
    timeout = traits.Float(14.0)
    # Subjects
    datagrabber = traits.Instance(Data, ())

    # Stimulus Motion
    subjectinfo = traits.Code()
    is_sparse = traits.Bool(False)

def create_config():
    c = config()
    c.uuid = mwf.uuid
    c.desc = mwf.help
    c.datagrabber = create_datagrabber_config()
    return c

def create_datagrabber_config():
    dg = Data(['input_files'])
    foo = DataBase()
    foo.name="subject_id"
    foo.iterable = True
    foo.values=["sub01","sub02"]
    dg.fields = [foo]
    dg.template= '*'
    dg.field_template = dict(input_files='%s/modelfit/design/fwhm_6.0/_generate_model*/run*.mat')
    dg.template_args = dict(input_files=[['subject_id']])
    dg.fields = [foo]
    return dg

mwf.config_ui = create_config

"""
Part 3: Create a View
"""

def create_view():
    from traitsui.api import View, Item, Group
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
    Group(Item(name='subjectinfo'),
        Item("is_sparse"),
            label='Subjectinfo', show_border=True),
        buttons = [OKButton, CancelButton],
        resizable=True,
        width=1050)
    return view

mwf.config_view = create_view

"""
Part 4: Workflow Construction
"""
# 


def stim_corr(subinfo, inpath, sparse, subject_id):
    import scipy as scipy
    import scipy.io as sio
    from scipy.stats.stats import pearsonr
    import matplotlib.pyplot as plt
    import numpy as np
    import os
    import glob

    alls = []
    out_images1 = []
    out_images2 = []
    output_info = []
    
    if not sparse:
        for j, i in enumerate(subinfo):
            c_label = i.conditions
            cond = len(i.conditions)
            # reg = len(i.regressor_names)
        output_path = os.path.abspath("Outlier.csv")
        ofile = open(output_path, 'w')
        ofile.write(', '.join(["Subject ID"]+["Run"]+["Outlier All"]+["Outlier in %s" %c_label[d] for d in range(cond)]))
        ofile.write('\n')
        for r in range(len(subinfo)): 
            run = 'run%s' %(r)
            # path = os.path.join(inpath, '_generate_model%d/run%d.mat' %(r,r)) #
            if len(subinfo) > 1:
                param = np.genfromtxt(inpath[r], skip_header=5)
            else:
                param = np.genfromtxt(inpath, skip_header=5)
            mat = param.shape
            columns = param.shape[1]
            count = cond+6
            outlier = columns - count
            out = 'Outlier = %d' %(outlier)
            con = 'Conditions = %d' %(cond)
            matr = 'Design Matrix Shape = [%d rows, %d columns]' %(mat)
            output_info.append([[run, out, con, matr]])
            ofile.write(', '.join([str(subject_id)]+[str(r)]+[str(outlier)]))
            if outlier > 0:
                o = param[:, count:columns]
                o_sums = o.sum(axis=1)
                param_o = np.column_stack((param, o_sums))
                # param_int = param_o.astype(int)
                ofile.write(', ')
                for i in range(cond):
                     c_out = np.sum((param_o[:,i] > 0).astype(int) + (param_o[:,-1] > 0.9).astype(int)==2)
                     out_c = 'Outlier in %s = %d' %(c_label[i], c_out) 
                     output_info.append([run, out_c])
                     ofile.write('%s, ' %(c_out))
            else: 
                param_o = param
                for i in range(cond):
                    c_out = 0
                    out_c = 'Outlier in %s = %d' %(c_label[i], c_out) 
                    output_info.append([run, out_c])
            ofile.write('\n')
            # compute correlation coefficients
            stim_corr = []
            p_values = []
            #pa = param_o.astype(int)
            #pa2 = abs(pa)
            for i in range(cond):
                # correlate each motion parameter with each (i) condition onset
                mp1 = [scipy.stats.pearsonr(param_o[:,(i)], param_o[:,(cond)])]
                mp2 = [scipy.stats.pearsonr(param_o[:,(i)], param_o[:,(cond+1)])]
                mp3 = [scipy.stats.pearsonr(param_o[:,(i)], param_o[:,(cond+2)])]
                mp4 = [scipy.stats.pearsonr(param_o[:,(i)], param_o[:,(cond+3)])]
                mp5 = [scipy.stats.pearsonr(param_o[:,(i)], param_o[:,(cond+4)])]
                mp6 = [scipy.stats.pearsonr(param_o[:,(i)], param_o[:,(cond+5)])]
                # correlate sum of outliers with each (i) condition onset
                if outlier > 0:
                    out = [scipy.stats.pearsonr(param_o[:,(i)], param_o[:,-1])]
                    stim_corr.append([[i,mp1[0][0]], [i, mp2[0][0]], [i, mp3[0][0]], [i, mp4[0][0]], [i, mp5[0][0]], [i, mp6[0][0]], [i, out[0][0]]])
                    p_values.append([[i,mp1[0][1]], [i, mp2[0][1]], [i, mp3[0][1]], [i, mp4[0][1]], [i, mp5[0][1]], [i, mp6[0][1]], [i, out[0][1]]])
                else:
                    stim_corr.append([[i,mp1[0][0]], [i, mp2[0][0]], [i, mp3[0][0]], [i, mp4[0][0]], [i, mp5[0][0]], [i, mp6[0][0]]])
                    p_values.append([[i,mp1[0][1]], [i, mp2[0][1]], [i, mp3[0][1]], [i, mp4[0][1]], [i, mp5[0][1]], [i, mp6[0][1]]])
            # save plot of parameter file (each run)
            max1 = np.amax(param_o)
            min1 = np.amin(param_o)
            fig1 = plt.figure(figsize=(12,6), dpi=80)
            fig1_title = plt.title("Parameter %s" %(run))
            # fig1_plot1 = plt.plot(param_o[:,0:(0+reg)], color='gray', label= r'$Regressor$')
            fig1_plot2 = plt.plot(param_o[:,(0):cond], color='blue', label=r'$Stimulus Onset$')
            fig1_plot3 = plt.plot(param_o[:,cond:(cond+6)], color='red', label=r'$Motion Parameter$')

            if outlier > 0:
                fig1_plot4 = plt.plot(param_o[:,columns], color='yellow', label=r'$Outlier Sum$')

            fig1_legend = plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
            fig1_ylim = plt.ylim(min1-0.5,max1+0.5)

            plt.savefig(os.path.abspath('parameter_img_%s.png' %(run)),bbox_extra_artists=(fig1_legend,), bbox_inches='tight')
            out_images1.append(os.path.abspath('parameter_img_%s.png'%run))
            
            # save image of p-values for correlation coefficients (each run)
            p_values_fig = np.asarray(p_values)
            fig2 = plt.figure()
            fig2_title = plt.title("P Values %s" %(run))
            fig2_xticks = plt.xticks([0,1,2,3,4,5,6,7,8,10], c_label)
            if outlier > 0:
                fig2_yticks = plt.yticks([0,1,2,3,4,5,6], [r'$Motion1$', r'$Motion2$', r'$Motion3$', r'$Motion4$', r'$Motion5$', r'$Motion6$',  r'$OutlierSum$' ])
            else: 
                fig2_yticks = plt.yticks([0,1,2,3,4,5], [r'$Motion1$', r'$Motion2$', r'$Motion3$', r'$Motion4$', r'$Motion5$', r'$Motion6$'])
            ps = p_values_fig[:, :, 1]
            fig2_image = plt.imshow(ps.T, interpolation='nearest', cmap = plt.get_cmap('seismic_r'), vmin = 0, vmax = 0.1)
            cb = plt.colorbar()
            plt.savefig(os.path.abspath('p_values_img_%s.png' %(run)))
            out_images2.append(os.path.abspath('p_values_img_%s.png'%run))
        output1_path = os.path.abspath("output_check_%s.txt" %subject_id)
        np.savetxt(output1_path, np.asarray(output_info), fmt='%s')
        stim_path = os.path.abspath('stimulus_motion_correlation.csv')
        sfile = open(stim_path, 'w')
        sfile.write(', '.join(["Condition"]+["Motion%d" %d for d in range(6)] + ["Outliers"]))
        sfile.write('\n')
        for i, line in enumerate(stim_corr):
            print line
            sfile.write(', '.join([c_label[i]]+[str(l[1]) for l in line]))
            sfile.write('\n')
        sfile.close()
        p_path = os.path.abspath('p_values_correlation.csv')
        pfile = open(p_path,'w')
        pfile.write(', '.join(["Condition"]+["Motion %d" %d for d in range(6)]+["Outliers"]))
        pfile.write('\n') 
        for i,line in enumerate(p_values):
            print line
            pfile.write(', '.join([c_label[i]]+[str(l[1]) for l in line]))
            pfile.write('\n')
        pfile.close()
        ofile.close()
        return output_path, output1_path, out_images1, out_images2, stim_path, p_path
            
    if sparse:  
        for j, i in enumerate(subinfo):
            c_label = i.conditions
            cond = len(i.conditions)
            reg = len(i.regressor_names)
        output_path = os.path.abspath("Outlier.csv")
        ofile = open(output_path, 'w')
        ofile.write(', '.join(["Subject ID"]+["Run"]+["Outlier All"]+["Outlier in %s" %c_label[d] for d in range(cond)]))
        ofile.write('\n')        
        for r in range(len(subinfo)): 
            run = 'run%s' %(r)
            # path = os.path.join(inpath, '_generate_model%d/run%d.mat' %(r,r)) # 
            if range(len(subinfo)) > 0:
                param = np.genfromtxt(inpath[r], skip_header=5)
            else:
                param = np.genfromtxt(inpath, skip_header=5)
            mat = param.shape
            columns = param.shape[1]
            count = reg+6+cond
            outlier = columns-count
            out = 'Outlier = %d' %(outlier)
            regs = 'Regressors = %d' %(reg)
            con = 'Conditions = %d' %(cond)
            matr = 'Design Matrix Shape = [%d rows, %d columns]' %(mat)
            output_info.append([[run, out, regs, con, matr]])
            ofile.write(', '.join([str(subject_id)]+[str(r)]+[str(outlier)]))
            if outlier > 0:
                o = param[:, count:columns]
                o_sums = o.sum(axis=1)
                param_o = np.column_stack((param, o_sums))
                ofile.write(', ')
                for i in range(cond):
                    c_out = np.sum((param_o[:,i+reg+6] > 0).astype(int) + (param_o[:,-1] > 0.9).astype(int)==2)
                    out_c = 'Outlier in %s = %d' %(c_label[i], c_out) 
                    output_info.append([run, out_c])
                    ofile.write('%s, ' %(c_out))
            else: 
                param_o = param
                c_out = 0
                ofile.write(', ')
                for i in range(cond):
                    out_c = 'Outlier in %s = %d' %(c_label[i], c_out) 
                    output_info.append([run, out_c])
                    ofile.write('%s, ' %(c_out))
            ofile.write('\n')

            # compute correlation coefficients
            stim_corr = []
            p_values = []
            for i in range(cond):
                # correlate each motion parameter with each (i) condition onset
                mp1 = [scipy.stats.pearsonr(param_o[:,(reg)], param_o[:,(i+reg+6)])]
                mp2 = [scipy.stats.pearsonr(param_o[:,(reg+1)], param_o[:,(i+reg+6)])]
                mp3 = [scipy.stats.pearsonr(param_o[:,(reg+2)], param_o[:,(i+reg+6)])]
                mp4 = [scipy.stats.pearsonr(param_o[:,(reg+3)], param_o[:,(i+reg+6)])]
                mp5 = [scipy.stats.pearsonr(param_o[:,(reg+4)], param_o[:,(i+reg+6)])]
                mp6 = [scipy.stats.pearsonr(param_o[:,(reg+5)], param_o[:,(i+reg+6)])]
                # correlate sum of outliers with each (i) condition onset
                if outlier > 0:
                    out = [scipy.stats.pearsonr(param_o[:,-1], param_o[:,(i+reg+6)])]
                    stim_corr.append([[i,mp1[0][0]], [i, mp2[0][0]], [i, mp3[0][0]], [i, mp4[0][0]], [i, mp5[0][0]], [i, mp6[0][0]], [i, out[0][0]]])
                    p_values.append([[i,mp1[0][1]], [i, mp2[0][1]], [i, mp3[0][1]], [i, mp4[0][1]], [i, mp5[0][1]], [i, mp6[0][1]], [i, out[0][1]]])
                else:
                    stim_corr.append([[i,mp1[0][0]], [i, mp2[0][0]], [i, mp3[0][0]], [i, mp4[0][0]], [i, mp5[0][0]], [i, mp6[0][0]]])
                    p_values.append([[i,mp1[0][1]], [i, mp2[0][1]], [i, mp3[0][1]], [i, mp4[0][1]], [i, mp5[0][1]], [i, mp6[0][1]]])
            
            # save plot of parameter file (each run)
            max1 = np.amax(param_o)
            min1 = np.amin(param_o)
            fig1 = plt.figure(figsize=(12,6), dpi=80)
            fig1_title = plt.title("Parameter %s" %(run))
            fig1_plot1 = plt.plot(param_o[:,0:(0+reg)], color='gray', label= r'$Regressor$')
            fig1_plot2 = plt.plot(param_o[:,reg:(reg+6)], color='red', label=r'$Motion Parameter$')
            fig1_plot3 = plt.plot(param_o[:,(reg+6):count], color='blue', label=r'$Stimulus Onset$')
            if outlier > 0:
                fig1_plot4 = plt.plot(param_o[:,columns], color='yellow', label=r'$Outlier Sum$')

            fig1_legend = plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
            fig1_ylim = plt.ylim(min1-0.5,max1+0.5)

            plt.savefig(os.path.abspath('parameter_img_%s.png' %(run)),bbox_extra_artists=(fig1_legend,), bbox_inches='tight')
            out_images1.append(os.path.abspath('parameter_img_%s.png'%run))
            
            # save image of p-values for correlation coefficients (each run)
            p_values_fig = np.asarray(p_values)
            fig2 = plt.figure()
            fig2_title = plt.title("P Values %s" %(run))
            fig2_xticks = plt.xticks([0,1,2,3,4,5,6,7,8,10], [r'$Cond1$', r'$Cond2$', r'$Cond3$', r'$Cond4$', r'$Cond5$', r'$Cond6$' ])
            if outlier > 0:
                fig2_yticks = plt.yticks([0,1,2,3,4,5,6], [r'$Motion1$', r'$Motion2$', r'$Motion3$', r'$Motion4$', r'$Motion5$', r'$Motion6$',  r'$OutlierSum$' ])
            else: 
                fig2_yticks = plt.yticks([0,1,2,3,4,5], [r'$Motion1$', r'$Motion2$', r'$Motion3$', r'$Motion4$', r'$Motion5$', r'$Motion6$'])
             ps = p_values_fig[:, :, 1]
            fig2_image = plt.imshow(ps.T, interpolation='nearest', cmap = plt.get_cmap('seismic_r'), vmin = 0, vmax = 0.1)
            cb = plt.colorbar()

            plt.savefig(os.path.abspath('p_values_img_%s.png' %(run)))
            out_images2.append(os.path.abspath('p_values_img_%s.png'%run))

        output1_path = os.path.abspath("output_check_%s.txt" %subject_id)
        np.savetxt(output1_path, np.asarray(output_info), fmt='%s')
        stim_path = os.path.abspath('stimulus_motion_correlation.csv')
        sfile = open(stim_path, 'w')
        sfile.write(', '.join(["Condition"]+["Motion%d" %d for d in range(6)] + ["Outliers"]))
        sfile.write('\n')
        for i, line in enumerate(stim_corr):
            print line
            sfile.write(', '.join([c_label[i]]+[str(l[1]) for l in line]))
            sfile.write('\n')
        sfile.close()
        p_path = os.path.abspath('p_values_correlation.csv')
        pfile = open(p_path,'w')
        pfile.write(', '.join(["Condition"]+["Motion%d"%d for d in range(6)]+["Outliers"]))
        pfile.write('\n') 
        for i,line in enumerate(p_values):
            print line
            pfile.write(', '.join([c_label[i]]+[str(l[1]) for l in line]))
            pfile.write('\n')
        pfile.close()
        ofile.close()


        return output_path, output1_path, out_images1, out_images2, stim_path, p_path


def create_sm(c):
    import nipype.interfaces.utility as util    # utility
    import nipype.pipeline.engine as pe         # pypeline engine
    import nipype.interfaces.io as nio          # input/output
    import numpy as np
    motionflow = pe.Workflow('stim_mot')
    motionflow.base_dir = os.path.join(c.working_dir)
    stim_mot = pe.Node(util.Function(input_names=['subinfo', 'inpath', 'sparse', 'subject_id'], output_names=['output_path', 'output1_path', 'out_images1', 'out_images2', 'stim_path', 'p_path'], function=stim_corr), name='stim_motion')
    stim_mot.inputs.sparse = c.is_sparse
    datagrabber = c.datagrabber.create_dataflow()
    sink = pe.Node(nio.DataSink(), name='sink')
    sink.inputs.base_directory = c.sink_dir
    subjects = datagrabber.get_node('subject_id_iterable')
    motionflow.connect(subjects,'subject_id',sink,'container')
    subjectinfo = pe.Node(util.Function(input_names=['subject_id'], output_names=['output']), name='subjectinfo')
    subjectinfo.inputs.function_str = c.subjectinfo
    def getsubs(subject_id):
        #from config import getcontrasts, get_run_numbers, subjectinfo, fwhm
        subs = [('_subject_id_%s/'%subject_id,'')]

        return subs

    get_substitutions = pe.Node(util.Function(input_names=['subject_id'],
        output_names=['subs'], function=getsubs), name='getsubs')

    motionflow.connect(subjects,'subject_id',get_substitutions,'subject_id')
    motionflow.connect(get_substitutions,"subs",sink,"substitutions")
    motionflow.connect(datagrabber, 'datagrabber.input_files', stim_mot, 'inpath')
    motionflow.connect(subjects,'subject_id',stim_mot,'subject_id')
    motionflow.connect(subjectinfo,'output', stim_mot, 'subinfo')
    motionflow.connect(subjects,'subject_id',subjectinfo,'subject_id')
    motionflow.connect(stim_mot, 'output_path', sink, 'Stimulus_Motion.@file1')
    motionflow.connect(stim_mot, 'output1_path', sink, 'Stimulus_Motion.@file2')
    motionflow.connect(stim_mot,'out_images1',sink,'Stimulus_Motion.@images1')
    motionflow.connect(stim_mot,'out_images2',sink,'Stimulus_Motion.@images2')
    motionflow.connect(stim_mot,'stim_path',sink,'Stimulus_Motion.@parameter')
    motionflow.connect(stim_mot,'p_path',sink,'Stimulus_Motion.@pvalues')
    motionflow.base_dir = c.working_dir
    return motionflow

mwf.workflow_function = create_sm

"""
Part 5: Define the main function
"""

def main(config_file):

    c = load_config(config_file, create_config)
    wf = create_sm(c)
    wf.config = {'execution' : {'crashdump_dir' : c.crash_dir, "job_finished_timeout": c.timeout}}
    wf.base_dir = c.working_dir

    if c.test_mode:
        wf.write_graph()

    from nipype.utils.filemanip import fname_presuffix
    wf.export(fname_presuffix(config_file,'','_script_').replace('.json',''))
    if c.save_script_only:
        return 0

    if c.run_using_plugin:
        wf.run(plugin=c.plugin, plugin_args = c.plugin_args)
    else:
        wf.run()


mwf.workflow_main_function = main

"""
Part 6: Register the Workflow
"""


register_workflow(mwf)




