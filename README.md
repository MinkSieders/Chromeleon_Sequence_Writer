# Autosampler Sample Sequence Writer For Chromeleon Software


Script that automatically generates HPLC sample sequence series from .xlsx 96-well plate designs and "normal" 
1.5 mL vials. Trays where 96-well plates need to be mounted on are automatically assigned, and the script allows
for more 96-well plates than available trays assuming the user switches them throughout the program. 1.5 mL vials 
are automatically assigned a position in an available tray. Created for usage on Dionex AS-AP and Chromeleon V7.2.9 Software
but should work for a range of Chromeleon versions (V6.8 is tested too). 


Script outputs a pdf file with a AutoSampler (AS) loading overview and potential points where vials / 96-well plates 
need to be changed. 


Samples designated as beginning with STD will be considered standard samples, and will be ran in the beginning and
the end of a sequence in addition to a user defined number of times throughout the sequence. 


For usage, run in command-line. 
