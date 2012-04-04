import nipype.interfaces.freesurfer as fs
import nipype.interfaces.ants as ants
import nipype.pipeline.engine as pe
import os
import nipype.interfaces.utility as util

#converts fsl-style Affine registration into ANTS compatible itk format
def convert_affine(brain,moving_image,bbreg_mat):
	cmd ="c3d_affine_tool -ref %s -src %s %s -fsl2ras \
		-oitk fsl2antsAffine.txt"%(brain,moving_image,bbreg_mat)
	print cmd
	os.system(cmd)
	return os.path.abspath('fsl2antsAffine.txt')

#return dimensions of input image
def image_dimensions(images):
	import nibabel as nb
	if isinstance(images,list):
		dims = []
		for image in images:
			dims.append(len(nb.load(image).get_shape()))
	else:
		dims =  len(nb.load(images).get_shape())
	
	print dims
	return dims

def first_element_of_list(_list):
	return _list[0]

#returns the workflow
def return_post_struct_warpflow(base_dir):

	#inputs to workflow
	inputspec = pe.Node(
		util.IdentityInterface(
			fields=['template_file','unwarped_brain','warp_field',
                'affine_transformation','out_fsl_file','moving_image',
                'mean_func']),
		name='inputspec')


	#makes fsl-style coregistration ANTS compatible
	fsl_registration_to_itk = pe.Node(
		util.Function(
			input_names=['unwarped_brain','mean_func','out_fsl_file'],
			output_names=['fsl2antsAffine'],
			function=convert_affine),
		name='fsl_registration_to_itk')

	#collects series of transformations to be applied to the moving images
	collect_transforms = pe.Node(
		util.Merge(3),
		name='collect_transforms')

	#performs series of transformations on moving images
	warp_images = pe.MapNode(
		ants.WarpTimeSeriesImageMultiTransform(),
		name='warp_images',
		iterfield=['moving_image','dimension'])

	#collects workflow outputs
	outputspec = pe.Node(
		util.IdentityInterface(
			fields=['warped_image']),
		name='outputspec')

	#initializes and connects workflow nodes
	normalize_post_struct = pe.Workflow(name='normalize_post_struct')
	normalize_post_struct.base_dir = base_dir
	normalize_post_struct.connect([

		(inputspec,fsl_registration_to_itk,[('unwarped_brain','unwarped_brain')]),
		(inputspec,fsl_registration_to_itk,[('out_fsl_file','out_fsl_file')]),
		(inputspec,fsl_registration_to_itk,[('mean_func','mean_func')]),
		(fsl_registration_to_itk,collect_transforms,[('fsl2antsAffine','in3')]),
		(inputspec,collect_transforms,[('warp_field','in1'),
			('affine_transformation','in2')]),
		(inputspec,warp_images,[('moving_image','moving_image')]),
		(inputspec,warp_images,[(('moving_image',image_dimensions),'dimension')]),
		(inputspec,warp_images,[('template_file','reference_image')]),
		(collect_transforms,warp_images,[(('out',first_element_of_list),'transformation_series')]),
		(warp_images,outputspec,[('output_image','warped_image')])])

	return normalize_post_struct
