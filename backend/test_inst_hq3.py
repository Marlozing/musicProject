# -*- coding: utf-8 -*-

import os
import sys
from audio_separator.separator import Separator

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python3 {os.path.basename(__file__)} <input_audio_path>")
        sys.exit(1)

    input_file = sys.argv[1]
    if not os.path.isfile(input_file):
        print(f"Error: Input file not found at {input_file}")
        sys.exit(1)

    # --- Configuration ---
    model_path = "./UVR-MDX-NET-Inst_HQ_3.onnx"
    output_dir = "./separation_results"
    
    print(f"Separating {input_file} using {os.path.basename(model_path)}...")

    try:
        # Initialize the separator with the specific ONNX model
        separator = Separator(
            model_file_path=model_path,
            output_dir=output_dir,
            # Common settings for MDX-NET models
            mdx_params={
                'hop_length': 1024,
                'segment_size': 256,
                'overlap': 0.02,
                'batch_size': 4,
                'denoise': True
            }
        )
        
        # Perform the separation
        # The primary stem will be instrumental, secondary will be vocals
        primary_stem_path, secondary_stem_path = separator.separate(input_file)
        
        print(f"Separation complete.")
        print(f"  - Instrumental saved to: {primary_stem_path}")
        print(f"  - Vocals saved to: {secondary_stem_path}")

    except Exception as e:
        print(f"An error occurred during separation: {e}")
        sys.exit(1)
