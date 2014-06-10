# -*- coding: utf-8 -*-
"""
File handling utils
"""
import cmd
from datetime import datetime
import getpass
import locale
import os
import pkg_resources
import shlex
import shutil
import io
import sys
import time
import traceback
import urllib
import zipfile

from concurrent.core.util.texttransforms import _, printerr, printout

def create_file(fname, data=None):
    """
    Simple file creator
    """
    fd = open(fname, 'w')
    if data:
        fd.write(data)
    fd.close()

def create_dir_gitsafe(dir_name):
    """
    Create directory and add a nice git safe file in so we will handle
    the folder in version control
    """
    os.mkdir(dir_name)
    create_file(os.path.join(dir_name,'.gitkeep'))

def purge_dir(path):
    """Purge a whole dir, including all it's containing files and subfolders!"""
    for root, dirs, files in os.walk(path, topdown=False):        
        # remove all files
        for file in files:
            os.remove(os.path.join(root,file))        
        # remove all dirs
        for dir in dirs:
            os.rmdir(os.path.join(root,dir))
    os.rmdir(path)     
    
def create_unique_file(path):
    """Create a new file. An index is added if the path exists"""
    parts = os.path.splitext(path)
    idx = 1
    while 1:
        try:
            flags = os.O_CREAT + os.O_WRONLY + os.O_EXCL
            if hasattr(os, 'O_BINARY'):
                flags += os.O_BINARY
            return path, os.fdopen(os.open(path, flags, 0o666), 'w')
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
            idx += 1
            # A sanity check
            if idx > 100:
                raise Exception('Failed to create unique name: ' + path)
            path = '%s.%d%s' % (parts[0], idx, parts[1])
    
def copytree(src, dst, symlinks=False, skip=[]):
    """Recursively copy a directory tree using copy2() (from shutil.copytree.)

    Added a `skip` parameter consisting of absolute paths
    which we don't want to copy.
    """
    def str_path(path):
        if isinstance(path, unicode):
            path = path.encode(sys.getfilesystemencoding() or
                               locale.getpreferredencoding())
        return path
    skip = [str_path(f) for f in skip]
    def copytree_rec(src, dst):
        names = os.listdir(src)
        os.mkdir(dst)
        errors = []
        for name in names:
            srcname = os.path.join(src, name)
            if srcname in skip:
                continue
            dstname = os.path.join(dst, name)
            try:
                if symlinks and os.path.islink(srcname):
                    linkto = os.readlink(srcname)
                    os.symlink(linkto, dstname)
                elif os.path.isdir(srcname):
                    copytree_rec(srcname, dstname)
                else:
                    shutil.copy2(srcname, dstname)
                # XXX What about devices, sockets etc.?
            except (IOError, OSError) as why:
                errors.append((srcname, dstname, str(why)))
            # catch the Error from the recursive copytree so that we can
            # continue with other files
            except shutil.Error as err:
                errors.extend(err.args[0])
        try:
            shutil.copystat(src, dst)
        except OSError as why:
            errors.append((src, dst, str(why)))
        if errors:
            raise shutil.Error(errors)
    copytree_rec(str_path(src), str_path(dst))
    
# -- zipfile handling
def zip_print_info( zip_file_name ):
    zf = zipfile.ZipFile( zip_file_name )
    for info in zf.infolist():
        printout(_(info.filename))
        printout(_("tComment:t",info.comment))
        printout(_("tModified:t", datetime.datetime(*info.date_time)))
        printout(_("tSystem:tt", info.create_system, '(0 = Windows, 3 = Unix)'))
        printout(_("tZIP version:t", info.create_version))
        printout(_("tCompressed:t", info.compress_size, 'bytes'))
        printout(_("tUncompressed:t", info.file_size, 'bytes'))

def zip_is_valid( zip_file_name ):
    """
    Returns True if the file name is pointing to a zip file. Otherwise False
    """
    return zipfile.is_zipfile( zip_file_name )

def zip_open( zip_file_name, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True ):
    """
    Open a zip file
    """
    return zipfile.ZipFile(zip_file_name, mode, compression=zipfile.ZIP_DEFLATED, allowZip64=True)
    
def zip_create_from_folder( source_dir, dest_file='', exclude_dirs=[], include_root=True ):
    """
    Method that just.
    Inpired by: http://stackoverflow.com/questions/458436/adding-folders-to-a-zip-file-using-python
    @param source_dir: The folder that will be zipped
    @param dest_file: Destination zip file. If not set `source_dir` base name will be used
    @param exclude_dirs: List of directories that should be excluded 
    @param include_root: If True `source_dir` will be included in the resulting zip   
    """  
    # Build right dest_file name and verify if source exists
    if dest_file is '':
        dest_file = os.path.join(os.path.basename(source_dir),'.zip')
        
    if not os.path.isdir(source_dir):
        raise OSError("source_folder argument must point to a valid directory.")
    
    base_dir, root_dir = os.path.split(source_dir)
    
    #Little nested function to prepare the proper archive path
    def trim_path(path):
        archive_dir = path.replace(base_dir, "", 1)
        if base_dir:
            archive_dir = archive_dir.replace(os.path.sep, "", 1)
        if not include_root:
            archive_dir = archive_dir.replace(root_dir + os.path.sep, "", 1)
        return os.path.normcase(archive_dir)
    
    # nested function to exclude a file from beeing added to the zip file
    def should_be_excluded( dir ):
        for excluded_dir in exclude_dirs:
            if root.rfind(excluded_dir) > 0:
                return True
        return False
    
    # Create file
    out_file = zip_open(dest_file)
    
    printout(_( "Creating Zip %(NewZip)s", NewZip=dest_file))
    
    for root, dirs, files in os.walk(source_dir):
        for file_name in files:
            # Check excluded dirs!
            if not should_be_excluded( root ):                
                # Write the file
                file_path = os.path.join(root, file_name)
                printout(_( " - Adding %(file_path)s", file_path=trim_path(file_path)))
                out_file.write(file_path, trim_path(file_path))
        
        # Empty folder needs to be added too       
        if not files and not dirs:
            zipInfo = zipfile.ZipInfo(trim_path(root) + "/")
            out_file.writestr(zipInfo, "")
    
    out_file.close()
    printout(_( "Zip file created successfully!"))
