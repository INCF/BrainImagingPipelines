==========================================
Preprocessing Resting State Data Tutorial
==========================================

This tutorial will explain how to use the Bips gui to preprocess resting state data.  

Opening Up the Gui
------------------

To list all bips workflows type:

>>> bips -l

You will see a list of UUID's and their associated workflows. For Preprocessing resting state data, you want uuid 7757e3168af611e1b9d5001e4rb1404cfMRI preprocessing workflow

To open this workflow type:

>>> bips -c 77

.. image:: bips_images/Bips_Config.png

* Click 'new' to open a new configuration file
* Click 'load' to open a pre-existing configuration file and navigate to where you saved your desired file
* Configuration files are stored in JSON format so you can edit your confirguration file in any text editor.
* Name your configuration file with the suffix'.json'

Description
^^^^^^^^^^^
The description tab should show:

.. image:: bips_images/Description.png

* The description tab tells you the name of the workflow you have opened.

Directories
^^^^^^^^^^^^
The Directories tab should show:

* Working dir: This is the working direcotyr where nipype_ stores all the intermediate files and cache-ing information of your workflow. Once your analysis is complete you can delete the working directory because the results are saved in the sink directory. 
* Sink dir: This is the base directory where BIPS will look for each subject's data.
* Crash dir: This is the directory where your crash files will be stored
* Surfaces dir:This is the directory where your image surfaces are stored.

Execution Option
^^^^^^^^^^^^^^^^
Under the 'execution option' tab you can choose how and where you want your program to run.

.. image:: bips_images/Execution_options.png

* Run using plugin: click here to run on the cluster
* For more informaton on what the plugin options mean, go to the nipype website on plugins_.

.. _plugins: http://nipy.sourceforge.net/nipype/users/plugins.html

* Plugin args: arguments to the plugin engine.
* Test mode: click here if you want to test the puline with one subject.

Subjects
^^^^^^^^
This is where you will enter the subjects that you want to run in your analysis.

.. image:: bips_images/Subjects.png

* Subjects: enter your subject numbers
* Base dir: enter where your subject files live.
* Func template: enter the template to find your data
* Check func datagrabber: click here to make sure that your files exist where you told the program they live.
* Run datagrabber without submitting: click here if you want your program to grab your data locally instead of running on the cluster.
* Timpoints to remove: enter any volumes you don't want to preprocess here.

Fieldmap
^^^^^^^^
This is where you can enter information about the fieldmap (if you collected it) before the resting state scans.

.. image:: bips_images/FieldMap.png

* Use fieldmap: click here if you want to include your fieldmap.
* Field dir: enter the directory where your fieldmap data lives.
* Magnitude template: enter where your template for the magnitude image lives.
* Phase template: enter where your template for the phase image lives.
* Check field datagrabber: click here to make sure that your files exist where you told the program they live.
* Echospacing: enter your echospacing parameters
* Te diff: enter your Te diff parameters
* Sigma: enter your sigma parameters

Motion Correction
^^^^^^^^^^^^^^^^^
You can enter your motion correction parameters here.

.. image:: bips_images/Motion_correction.png

* do despike: ANISHA
* Motion correct node: pick the program that you want to run motion correction on.
  
  * Nipy_
  * fsl_
  * Spm_
  * Afni_

.. _fsl: http://www.fmrib.ox.ac.uk/fsl/mcflirt/index.htmlspm
.. _Spm: http://www.ncbi.nlm.nih.gov/pubmed/22036679
.. _Afni: http://www.personal.reading.ac.uk/~sxs07itj/web/AFNI_motion.html

* Tr: enter your TRs for the resting state scan
* Do slicetiming: click here if you want to perform slicetiming on your data
* Use metadata: click here if you used bips dicom convert and it will automatically enter your TRs and slice order (0 based).
* Slice order: enter your slice order (0 based)
* Loops: parameters for nipy realign, ANISHA
* Speedup: parameters for nipy realign, ANISHA

Artifact Detection
^^^^^^^^^^^^^^^^^^
Enter your artigact decetion parameters here.

.. image:: bips_images/Artifact_detect.png

* Norm thresh: a threshold used to detect motion-related outliers when composite motion is being used.
* Z thresh: threshold used to detect images that deviate from the mean.

CompCor
^^^^^^^
CompCor_

.. _Compcor: http://www.sciencedirect.com/science/article/pii/S1053811907003837.

* click on the first Compcor select to do T-compcor
* Click on the second Compcor select to do A-compcor
* Num noise components: enter the number of noise components you want to regress out
* Regress before PCA: click if you want to run the CompCor regression before Art and motion correction.

Nuisance Filtering
^^^^^^^^^^^^^^^^^^
Choose what components you want to regress out of your time series.

.. image:: bips_images/Nuisance_filter.png

* First Reg params: regress out motion prameters from motion correction
* Second Reg params: regress out norm components from ART
* Third Reg params: regress out noise components from CompCor
* Fourth Reg params: regress out ART outliers
* Fifth Reg params: regress out motion derivaties from motion correction

Smoothing
^^^^^^^^
Enter your smoothing parameters here.

* Smooth type: choose the smoothing program you would like to use

  * Susan_
  * Isotropic: ANISHA
  * Freesurfer_

.. _Susan: http://nipy.sourceforge.net/nipype/interfaces/generated/nipype.interfaces.fsl.preprocess.html#susan
.. _Freesurfer: http://nipy.sourceforge.net/nipype/interfaces/generated/nipype.interfaces.freesurfer.preprocess.html#smooth

* Fwhm: enter your smoothing kernal
* Surface fshm: enter your surface smoothing kernal (only if you smoothed with Freesurfer).





 
 

