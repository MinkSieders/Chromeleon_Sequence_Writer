# Autosampler Sample Sequence Writer For Chromeleon Software

## Description
This script automatically generates HPLC sample sequence series from .xlsx 96-well plate designs and 1.5 mL vials. It's designed for use with Dionex AS-AP and Chromeleon V7.2.9 Software, but is compatible with a range of Chromeleon versions (tested with V6.8 as well).

## Key Features
- Automatically assigns trays for 96-well plates and 1.5 mL vials
- Supports more 96-well plates than available trays, assuming user switches them during the run
- Outputs a PDF file with an AutoSampler loading overview and potential plate/vial change points
- Handles standard samples (prefixed with 'STD') by running them at the start, end, and at user-defined intervals
- Allows omission of samples by prefixing them with 'OMIT'
- Generates technical replicates for samples

## Input Requirements
- A manifest folder containing:
  - A 'plates' subfolder with .xlsx files for 96-well plate designs
  - A 'vials.xlsx' file for 1.5 mL vial samples

## Usage
Run the script with the following command:

'python ChromeleonSequenceWriter_V6.1.py [arguments]'

### Arguments
- `--folder`: Path to the folder containing vials.xlsx and plates folder (required)
- `--instrument_method`: Instrument method used for all samples (default: MS_Catecholamine_Iso_col25)
- `--injection_volume`: Injection volume in µl (default: 25.0)
- `--output`: Output folder name (default: [input_folder_name]_output)
- `--plate_tray_number`: Number of trays allocated for plates (default: 2)
- `--standard_replicate_number`: Number of times the standard series is run (default: 5, must be at least 2)
- `--trays`: List of color codes for each sampling tray available in the HPLC autosampler (default: ['R', 'G', 'B'])
- `--technical_replicates_samples`: Number of times each sample is injected into HPLC (default: 2)
- `--vial_instrument_method`: Specify a method for vial samples that differs from the main instrument_method
- `--setup_env`: Create a template manifest folder environment (use: --setup_env True)

### Examples
1. Basic usage:

'python ChromeleonSequenceWriter_V6.1.py --folder /path/to/manifest_folder'

3. Custom settings:

'python ChromeleonSequenceWriter_V6.1.py --folder /path/to/manifest_folder --instrument_method Custom_Method --injection_volume 30 --plate_tray_number 3 --standard_replicate_number 4'

5. Setup template environment:

'python ChromeleonSequenceWriter_V6.1.py --setup_env True'

## Output
The script generates:
1. A sample sequence file in the specified output folder
2. A PDF file with the AutoSampler loading overview
3. Images of vial tray layouts

## Notes
- Do not change the 'vials.xlsx' filename
- Plate manifest files in the 'plates' folder can have any name, as long as they are .xlsx files
- Samples prefixed with 'STD' are treated as standards
- Samples prefixed with 'OMIT' are excluded from the sequence

## Author
Mink Sieders

## Version
6.1 (Last Updated: 21/10/2024)

## License
MIT License. Copyright (c) 2024 Mink Sieders

