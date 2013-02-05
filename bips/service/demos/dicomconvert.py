from glob import glob
import os
import string

from tempfile import mkdtemp
from dcmstack import parse_and_stack, NiftiWrapper

def sanitize_path_comp(path_comp):
    result = []
    for char in path_comp:
        if not char in string.letters + string.digits + '-_.':
            result.append('_')
        else:
            result.append(char)
    return ''.join(result)

def get_dicom_info(dicom_dir, dest):
    """Return a freesurfer style dicom info generator
    """
    fl = sorted(glob(os.path.join(dicom_dir, '*.dcm')))
    stack = parse_and_stack(fl, force=True, warn_on_except=True)
    info = {}
    for key in sorted(stack):
        key_fields = key.split('-')
        idx = int(key_fields[0])
        name = key_fields[1]
        stack_object = stack[key]
        if not stack_object.error:
            size = list(stack_object.get_shape())
            if len(size) == 3:
                size.append(1)
            err_status = 'ok'
            out_fn = sanitize_path_comp(key) + '.nii.gz'
            out_path = os.path.join(dest, out_fn)
            nii = stack_object.to_nifti(embed_meta=True)
            nii_wrp = NiftiWrapper(nii)
            meta_fn = out_fn + '.json'
            meta_path = os.path.join(dest, meta_fn)
            with open(meta_path, 'w') as fp:
                fp.write(nii_wrp.meta_ext.to_json())
            nii.to_filename(out_path)
        else:
            size = [0, 0, 0, 0]
            err_status = 'err'
            out_fn = None
            meta_fn = None
        filepath = out_fn
        filename = stack_object._files_info[0][2]
        info[idx] = dict(idx=idx, name=name, err_status=err_status,
                         size=size, filename=filename,
                         filepath=filepath,
                         metapath=meta_fn)
        size = [str(val) for val in size]
        print '\t'.join([str(idx), name, err_status] + size + [filename])
    return info

def unzip_and_extract(filename, dest):
    outdir = mkdtemp()
    if '.tgz' in filename or '.tar.gz' in filename:
        import tarfile
        bundle =  tarfile.open(filename, 'r')
    elif '.zip' in filename:
        import zipfile
        bundle =  zipfile.ZipFile(filename, 'r')
    else:
        raise ValueError('Unknown compression format. Only zip and tar+gzip supported')
    bundle.extractall(outdir)
    dcmdir = None
    print outdir
    for r,d,f in os.walk(outdir):
        print r
        for files in f:
            print files
            if files.endswith(".dcm"):
                dcmdir = r
                break
    print dcmdir
    info = get_dicom_info(dcmdir, dest)
    return info

