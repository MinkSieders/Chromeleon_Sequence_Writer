# Autosampler Sample Sequence Writer For Chromeleon Software


Script that automatically generates HPLC sample sequence series from .xlsx 96-well plate designs and "normal" 
1.5 mL vials. Trays where 96-well plates need to be mounted on are automatically assigned, and the script allows
for more 96-well plates than available trays assuming the user switches them throughout the program. 1.5 mL vials 
are automatically assigned a position in an available tray. Created for usage on Dionex AS-AP and Chromeleon V7.2.9 Software
but should work for a range of Chromeleon versions (V6.8 is tested too). 


Script outputs a pdf file with a AutoSampler loading overview and potential points where vials / 96-well plates 
need to be changed. 


Samples designated as beginning with STD will be considered standard samples, and will be ran in the beginning and
the end of a sequence in addition to a user defined number of times throughout the sequence. Samples names beginning with OMIT
will not be included in the sample sequence. 


User can define their samples using a manifest folder containing .xlsx files which contains a folder named 'plates' 
and a manifest for 'vial' samples named 'vials.xlsx'. the 'plates' folder contains .xlsx files which have 
plate sample designs (plate manifest files) in .xlsx format where the user can define respective sample names.
Plate .xlsx files can be named anything as long as they are located in the plates folder. The user should not change 
the vials.xlsx filename. 


For usage, run with --help. 


To setup a mock/template manifest folder environment, run with --setup_env True


