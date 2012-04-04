import nipype.interfaces.freesurfer as fs
import nipype.interfaces.ants as ants
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util 

def return_struct_warpflow(base_dir):
	#inputs to workflow
	inputspec = pe.Node(
		util.IdentityInterface(
			fields=['template_file','brain','segmentation']),
		name='inputspec')

	#converts brain from freesurfer mgz into nii
	brain_2nii = pe.Node(
		fs.preprocess.MRIConvert(),
		name='brain_2nii')
	brain_2nii.inputs.out_type='nii'

	#converts freesurfer segmentation into nii 
	aparcaseg_2nii = pe.Node(
		fs.preprocess.MRIConvert(),
		name='aparcaseg_2nii')
	aparcaseg_2nii.inputs.out_type='nii'

	#create mask excluding everything outside of cortical surface (from 
	#freesurfer segmentation file)
	create_mask = pe.Node(
		fs.model.Binarize(),
		name='create_mask')
	create_mask.inputs.min=1
	create_mask.inputs.out_type = 'nii'

	#apply mask to anatomical
	apply_mask = pe.Node(
		fs.utils.ApplyMask(),
		name='apply_mask')

	#use ANTS to warp the masked anatomical image to a template image
	warp_brain = pe.Node(
		ants.GenWarpFields(), 
		name='warp_brain')

	#collects workflow outputs
	outputspec = pe.Node(
		util.IdentityInterface(
			fields=['warp_field','affine_transformation',
				'inverse_warp','unwarped_brain','warped_brain']),
		name='outputspec')

	normalize_struct = pe.Workflow(name='normalize_struct')
	normalize_struct.base_dir = base_dir
	normalize_struct.connect([
		(inputspec,warp_brain,[('template_file','reference_image')]),
		(inputspec,brain_2nii,[('brain','in_file')]),
		(inputspec,aparcaseg_2nii,[('segmentation','in_file')]),
		(aparcaseg_2nii,create_mask,[('out_file','in_file')]),
		(create_mask,apply_mask,[('binary_file','mask_file')]),
		(brain_2nii,apply_mask,[('out_file','in_file')]),
		(apply_mask,warp_brain,[('out_file','input_image')]),
        (apply_mask,outputspec,[('out_file','unwarped_brain')]),
		(warp_brain,outputspec,[('affine_transformation','affine_transformation'),
			('warp_field','warp_field'),
			('inverse_warp_field','inverse_warp'),
			('output_file','warped_brain')])])

	return normalize_struct

