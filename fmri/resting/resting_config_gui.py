import argparse
import os
import sys
sys.path.insert(0,'../../utils')
from gui import gui_base

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
    a.add_entry("working_dir")
    a.add_entry("base_dir")
    a.add_entry("data_field_template")
    a.add_entry("sink_dir")
    a.add_entry("field_dir")
    a.add_entry("fieldmap_field_template")
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
    a.add_checkbox("regress_motion")
    a.add_checkbox("regress_motion_derivs")
    a.add_checkbox("regress_composite_norm")
    a.add_checkbox("regress_outliers")
    a.add_checkbox("regress_compcorr_components")
    a.add_entry("highpass_freq",float)
    a.add_entry("lowpass_freq",float)
    
    
    a.add_button(a.to_json,"save")
    
    
    if os.path.exists(args.config):
        a.from_json()
    
    a.run()
