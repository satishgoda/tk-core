"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Handles the creation of a configuration object structure based on the folder configuration on disk.

"""

import os
import fnmatch

from .folder_types import Static, ListField, Entity, Project, UserWorkspace, ShotgunStep, ShotgunTask

from ..errors import TankError

from tank_vendor import yaml


class FolderConfiguration(object):
    """
    Class that loads the schema from disk and constructs folder objects.
    """
    
    def __init__(self, tk, schema_config_path):
        """
        Constructor
        """
        self._tk = tk
        # access shotgun nodes by their entity_type
        self._entity_nodes_by_type = {}
        # read skip files config
        self._ignore_files = self._read_ignore_files(schema_config_path)
        # load schema
        self._load_schema(schema_config_path)
        

    ##########################################################################################
    # public methods

    def get_folder_objs_for_entity_type(self, entity_type):
        """
        Returns all the nodes representing a particular sg entity type 
        """
        return self._entity_nodes_by_type.get(entity_type, [])


    ####################################################################################
    # utility methods
    
    def _get_sub_directories(self, parent_path):
        """
        Returns all the directories for a given path
        """
        directory_paths = []
        for file_name in os.listdir(parent_path):
            full_path = os.path.join(parent_path, file_name)
            # ignore files
            if os.path.isdir(full_path) and not file_name.startswith("."):
                directory_paths.append(full_path)
        return directory_paths

    def _get_files_in_folder(self, parent_path):
        """
        Returns all the files for a given path except yml files
        Also ignores any files mentioned in the ignore files list
        """
        file_paths = []
        for file_name in os.listdir(parent_path):

            # don't process files matching ignore pattern(s)
            if not any(fnmatch.fnmatch(file_name, p) for p in self._ignore_files):

                full_path = os.path.join(parent_path, file_name)
                # yml files - those are our config files
                if os.path.isfile(full_path) and not full_path.endswith(".yml"):
                    file_paths.append(full_path)

        return file_paths
                    
    def _read_metadata(self, full_path):
        """
        Reads metadata file.

        :param full_path: Absolute path without extension
        :returns: Dictionary of file contents or None
        """
        metadata = None
        # check if there is a yml file with the same name
        yml_file = "%s.yml" % full_path
        if os.path.exists(yml_file):
            # try to parse it
            try:
                open_file = open(yml_file)
                try:
                    metadata = yaml.load(open_file)
                finally:
                    open_file.close()
            except Exception, error:
                raise TankError("Cannot load config file '%s'. Error: %s" % (yml_file, error))
        return metadata
    

    def _read_ignore_files(self, schema_config_path):
        """
        Reads ignore_files from root of schema if it exists.
        Returns a list of patterns to ignore.
        """
        ignore_files = []
        file_path = os.path.join(schema_config_path, "ignore_files")
        if os.path.exists(file_path):
            open_file = open(file_path, "r")
            try:
                for line in open_file.readlines():
                    # skip comments
                    if "#" in line:
                        line = line[:line.index("#")]
                    line = line.strip()
                    if line:
                        ignore_files.append(line)
            finally:
                open_file.close()
        return ignore_files

    ##########################################################################################
    # internal stuff


    def _load_schema(self, schema_config_path):
        """
        Scan the config and build objects structure
        """
                
        project_dirs = self._get_sub_directories(schema_config_path)
        
        # make some space in our obj/entity type mapping
        self._entity_nodes_by_type["Project"] = []
        
        for project_dir in project_dirs:
            
            schema_config_project_folder = os.path.join(schema_config_path, project_dir)
            
            # read metadata to determine root path 
            metadata = self._read_metadata(schema_config_project_folder)
            
            if metadata is None:
                raise TankError("Project directory missing required metadata file: %s" % schema_config_project_folder)
            
            if metadata.get("type") != "project":
                raise TankError("Only items of type 'project' are allowed at the root level: %s" % schema_config_project_folder)
                            
            project_obj = Project.create(self._tk, schema_config_project_folder, metadata)

            # store it in our lookup tables
            self._entity_nodes_by_type["Project"].append(project_obj)
            
            # recursively process the rest
            self._process_config_r(project_obj, schema_config_project_folder)
        

    def _process_config_r(self, parent_node, parent_path):
        """
        Recursively scan the file system and construct an object
        hierarchy. 
        
        Factory method for Folder objects.
        """
        for full_path in self._get_sub_directories(parent_path):
            # check for metadata (non-static folder)
            metadata = self._read_metadata(full_path)
            if metadata:
                node_type = metadata.get("type", "undefined")
                
                if node_type == "shotgun_entity":
                    cur_node = Entity.create(self._tk, parent_node, full_path, metadata)
                    
                    # put it into our list where we group entity nodes by entity type
                    et = cur_node.get_entity_type()
                    if et not in self._entity_nodes_by_type:
                        self._entity_nodes_by_type[et] = []
                    self._entity_nodes_by_type[et].append(cur_node)
                    
                elif node_type == "shotgun_list_field":
                    cur_node = ListField.create(self._tk, parent_node, full_path, metadata)
                    
                elif node_type == "static":
                    cur_node = Static.create(self._tk, parent_node, full_path, metadata)     
                
                elif node_type == "user_workspace":
                    cur_node = UserWorkspace.create(self._tk, parent_node, full_path, metadata)     
                
                elif node_type == "shotgun_step":
                    cur_node = ShotgunStep.create(self._tk, parent_node, full_path, metadata)     

                elif node_type == "shotgun_task":
                    cur_node = ShotgunTask.create(self._tk, parent_node, full_path, metadata)     

                else:
                    # don't know this metadata
                    raise TankError("Error in %s. Unknown metadata type '%s'" % (full_path, node_type))
            else:
                # no metadata - so this is just a static folder!
                # specify the type in the metadata chunk for completeness
                # since we are passing this into the hook later
                cur_node = Static.create(self._tk, parent_node, full_path, {"type": "static"})

            # and process children
            self._process_config_r(cur_node, full_path)
           
        # now process all files and add them to the parent_node token
        for f in self._get_files_in_folder(parent_path):
            parent_node.add_file(f)

    
    









