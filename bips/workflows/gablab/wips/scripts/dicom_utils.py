import os

def parse_dcm_dir(dcmdir,outfile=os.path.abspath('dicominfo.json')):
    import dicom
    from glob import glob
    from nipype.utils.filemanip import save_json

    # grab all dicoms in the dir
    files = glob(os.path.join(dcmdir,'*.dcm'))

    # initialize a dict that will be a summary in json format.
    
    info = {}

    # info's keys are 'SeriesNumber_ProtocolName' and PatientName
    # items are dicts with keys "dicoms": list of dicoms
    # "TE" and "TR" floats
    # if for some reason there is a mismatch, raise error for now
    for d in files: 
        sortdcm(d,info)

    save_json(outfile,info)
    return outfile    

def readdcm(dcm):
    import dicom
   
    out = {}   
    dicm = dicom.read_file(dcm,force=True)

    out["PatientName"] = dicm.PatientName
    out["SeriesNumber"] = dicm.SeriesNumber.real
    out["ProtocolName"] = dicm.ProtocolName
    out["TR"] = dicm.RepetitionTime.to_eng_string()
    out["TE"] = dicm.EchoTime.to_eng_string()

    return out

def sortdcm(dcm,info):
    data = readdcm(dcm)
    if not "PatientName" in info.keys():
        info["PatientName"] = data["PatientName"]
    if not data["PatientName"] == info["PatientName"]:
        raise Exception("Different Patients!")

    keyname = str(data["SeriesNumber"])+"_"+data["ProtocolName"]
    if not keyname in info.keys():
        info[keyname] = {"dicoms":[],"TR":data["TR"], "TE": data["TE"]}
    
    if not data["TR"] == info[keyname]["TR"]:
        newkeyname = keyname+"_TR_%1.3f"%(float(data["TR"])/1000)
        if not newkeyname in info.keys():
            keyname = newkeyname
            info[keyname] = {"dicoms":[],"TR":data["TR"], "TE": data["TE"]}
 
    if not data["TE"] == info[keyname]["TE"]:
        newkeyname = keyname+"_TE_%1.3f"%(float(data["TE"]))
        if not newkeyname in info.keys():
            keyname = newkeyname
            info[keyname] = {"dicoms":[],"TR":data["TR"], "TE": data["TE"]}

    info[keyname]["dicoms"].append(dcm)
    return info
