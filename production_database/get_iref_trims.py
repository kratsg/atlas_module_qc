from itkprodDB_interface import ITkProdDB


with ITkProdDB() as itk_prodDB:
    # Get Iref trim bits for different modules from PDB
    bare_module_sns = ['20UPGB42000111', '20UPGB42000112', '20UPGB42000113', '20UPGB42000114', '20UPGB42000115']
    itk_prodDB.get_irefs_of_module(bare_module_sns)
        