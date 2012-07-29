===============
Getting Started
===============
This tutorial will explain how to convert dicoms using the BIPS Dicom Convert workflow. BIPS uses a dicom converter written in Python, called dcmstack_. 

dcmsctack embeds meta-data from dicoms into niftis. This is very useful for later processing steps and can avoid inputting wrong information. For example, in preprocessing the slice-order and TR are embedded within the nifti, so you won't have to type it in.

BIPS also gives you the flexibility to reorganize and rename your dicoms any way you choose by writing a heuristic python script. 

.. _dcmstack: https://github.com/moloney/dcmstack

Listing Workflows
-----------------

To list all the BIPS workflows, type

>>> bips -l

You will see a list of UUID's and their associated workflows.

.. image:: bips_images/bips_list.png

To open a workflow, type

>>> bips -c <first 3-4 digits of the UUID>

Dicom Conversion
----------------

Open the Dicom Conversion workflow with

>>> bips -c df4

A window will pop up, as shown in the figure below:

.. image:: bips_images/bips_baseGUI.png

Click 'New' to create a new configuration file. Configuration files are stored in JSON format, so you can edit your configuration file in any text editor.

.. image:: bips_images/bips_newfiledialog.png

Name your configuration file with the suffix '.json'.

.. image:: bips_images/bips_firsttab.png

First verify that this is the workflow you want to run. Then click the "Directories" tab

.. admonition:: 
   When you hover your mouse over any field, it will give a description.       

Directories
^^^^^^^^^^^
The directories tab should show: 

.. image:: bips_images/bips_directories.png

* Working dir: This is the working directory where nipype_ stores all the intermediate files and cache-ing information of your workflow. Once your analysis is complete you can delete the working directory because the results are saved in the sink directory.
* Sink dir: This is where nipype_ stores the outputs of your workflow.
* Crash dir: This is the crash directory, where nipype_ will store crash files, in case something goes wrong.

Execution Options
^^^^^^^^^^^^^^^^^
Next you must specify the execution options of the worfklow

.. image:: bips_images/bips_plugins.png

* Run using plugin: when selected, nipype will run the workflow using the selected plugin
* Plugin: choose from PBS, PBSGraph, Condor, SGE, MultiProc. For more information see the nipype_ website.
* Plugin args: arguments to the plugin engine.
* Test mode: selecting test mode will run only 1 subject


Subjects
^^^^^^^^

BIPS needs to locate the dicoms for each subject:

.. image:: bips_images/bips_subjects.png 

* Subjects: Enter each subject's name as a comma seperated list
* Base dir: This is the base directory where BIPS will look for each subject's data
* Dicom dir template: This is the template for the subject's dicom directory. The '%s' will be replaced by each subject in the list of subjects. In this example, BIPS will find the dicoms in the folder /mindhive/gablab/users/keshavan/scripts/brainproducts/dicoms/bp01. 

Group
^^^^^

In the last tab, 'Group':

.. image:: bips_images/bips_dicomgroup.png

* Info only: Selecting this will NOT convert your dicoms. It will just make a dicominfo.txt file that summarizes the contents in your dicom directory. This is useful for making a heuristic file to name and sort your dicoms later.
* Use heuristic: Selecting this will tell the workflow to convert and sort your dicoms according to your heuristic file. If left unselected the workflow will assign default names based on the dicom headers.
* Heuristic file: The location of your heuristic file
* Embed meta: Check this box to embed dicom meta-data to the resulting Niftis. This is highly recommended for later processing steps!

Saving and Running
^^^^^^^^^^^^^^^^^^

Click 'OK', then save, then Run. 



.. include:: links_names.txt
