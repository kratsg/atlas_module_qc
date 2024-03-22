#!/bin/bash

FOLDER=/media/yannick/sirrush/rd53/Hybridisation_QC/HPK_IZM/Module_QC/Preprod_7_QC_0321

# Non-DAQ scans
#module-qc-tools-upload --path "$FOLDER/INJECTION_CAPACITANCE/" --host itkpix-localdb.physik.uni-bonn.de --port 00000
#module-qc-tools-upload --path "$FOLDER/OVERVOLTAGE_PROTECTION/" --host itkpix-localdb.physik.uni-bonn.de --port 00000
#module-qc-tools-upload --path "$FOLDER/LP_mode/" --host itkpix-localdb.physik.uni-bonn.de --port 00000
#module-qc-tools-upload --path "$FOLDER/SLDO/" --host itkpix-localdb.physik.uni-bonn.de --port 00000
#module-qc-tools-upload --path "$FOLDER/VCAL_CALIBRATION/" --host itkpix-localdb.physik.uni-bonn.de --port 00000
#module-qc-tools-upload --path "$FOLDER/ADC_CALIBRATION/" --host itkpix-localdb.physik.uni-bonn.de --port 00000
module-qc-tools-upload --path "$FOLDER/ANALOG_READBACK/" --host itkpix-localdb.physik.uni-bonn.de --port 00000
# module-qc-tools-upload --path "$FOLDER/IV_MEASURE/" --host itkpix-localdb.physik.uni-bonn.de --port 00000 # IV_MEASURE



# DAQ scans
#FOLDER=/media/yannick/sirrush/rd53/Hybridisation_QC/HPK_IZM/Module_QC/Preprod_23_QC/Preprod_23/

# MHT
#python localdbtool-upload.py scan "$FOLDER/0010_std_digitalscan" --username "itkpix" --password "silab_pidub12_itkpix" -d /home/yannick/git/YARR/localdb/setting/default/database.json --tag MHT
#python localdbtool-upload.py scan "$FOLDER/0011_std_analogscan" --username "itkpix" --password "silab_pidub12_itkpix" -d /home/yannick/git/YARR/localdb/setting/default/database.json --tag MHT
#python localdbtool-upload.py scan "$FOLDER/0012_std_thresholdscan_hr" --username "itkpix" --password "silab_pidub12_itkpix" -d /home/yannick/git/YARR/localdb/setting/default/database.json --tag MHT
#python localdbtool-upload.py scan "$FOLDER/0013_std_totscan" --username "itkpix" --password "silab_pidub12_itkpix" -d /home/yannick/git/YARR/localdb/setting/default/database.json --tag MHT

# TUN
#python localdbtool-upload.py scan "$FOLDER/0015_std_thresholdscan_hr" --username "itkpix" --password "silab_pidub12_itkpix" -d /home/yannick/git/YARR/localdb/setting/default/database.json --tag TUN
#python localdbtool-upload.py scan "$FOLDER/0021_std_thresholdscan_hd" --username "itkpix" --password "silab_pidub12_itkpix" -d /home/yannick/git/YARR/localdb/setting/default/database.json --tag TUN
#python localdbtool-upload.py scan "$FOLDER/0022_std_totscan" --username "itkpix" --password "silab_pidub12_itkpix" -d /home/yannick/git/YARR/localdb/setting/default/database.json --tag TUN

# PFA
#python localdbtool-upload.py scan "$FOLDER/0023_std_digitalscan" --username "itkpix" --password "silab_pidub12_itkpix" -d /home/yannick/git/YARR/localdb/setting/default/database.json --tag PFA
#python localdbtool-upload.py scan "$FOLDER/0024_std_analogscan" --username "itkpix" --password "silab_pidub12_itkpix" -d /home/yannick/git/YARR/localdb/setting/default/database.json --tag PFA
#python localdbtool-upload.py scan "$FOLDER/0025_std_thresholdscan_hd" --username "itkpix" --password "silab_pidub12_itkpix" -d /home/yannick/git/YARR/localdb/setting/default/database.json --tag PFA
#python localdbtool-upload.py scan "$FOLDER/0026_std_noisescan" --username "itkpix" --password "silab_pidub12_itkpix" -d /home/yannick/git/YARR/localdb/setting/default/database.json --tag PFA
# python localdbtool-upload.py scan "$FOLDER/0029_std_thresholdscan_zerobias" --username "itkpix" --password "silab_pidub12_itkpix" -d /home/yannick/git/YARR/localdb/setting/default/database.json --tag PFA
#python localdbtool-upload.py scan "$FOLDER/0028_selftrigger_source" --username "itkpix" --password "silab_pidub12_itkpix" -d /home/yannick/git/YARR/localdb/setting/default/database.json --tag PFA
