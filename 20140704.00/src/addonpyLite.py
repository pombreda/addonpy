from imp import load_source
import importlib

__author__ = 'Ninad Mhatre'

# VERSION: 20140624.01
# Changes:
#   - Option to load via ".info" files
#   - Function to recursively load other addons from another addon
#   - support for 'os' type in addon info
#   - BugFix: Search for addon-loader.info in scripts directory only

import os
from importlib import import_module
from glob import glob
from datetime import datetime
from src.addonpyHelpers import AddonHelper
import sys


class AddonLoader(object):
    """
    Addon Loader class, scans, validates, loads the addons and used to get the instance of the addons
    """

    ext = '.py'

    # Initializer

    def __init__(self, verbose=False, logger=None, recursive=False, lazy_load=False):
        """
        Initialize with optional verbose mode (print information) and optional logger (not implemented)
        :param verbose: print loading information
        :param logger: custom logger used in verbose mode
        :return: void
        """
        # Instance variables
        self.scanned_addons = dict()
        self.loaded_addons = dict()
        self.active_config = dict()
        self.current_dir = os.path.abspath('.')

        # Required variables supplied by caller
        self.verbose = verbose
        self.logger = logger
        self.addon_dirs = []
        self.recursive_search = recursive

        # Setting up module
        self.init_dir = AddonLoader._get_calling_script_dir()
        self._load_own_config()
        self._apply_config()
        self.print_current_config()

    def _apply_config(self):
        """
        apply given configuration
        :return: void
        """
        self.addon_dirs = self.active_config.get('addon_places')

    def print_current_config(self):
        self.log("Recursive addon search is: {0}".format('On' if self.recursive_search else 'Off'))
        self.log("Lazy load mode is not supported!")

    # Setters

    def set_logger(self, logger):
        """
        set logger for addonpy explicitly once module is initialized
        :param logger: logger instance
        """
        self.logger = logger

    def set_addon_dirs(self, dirs):
        """
        override the default config value to look for addons
        :param dirs: directories to search for addons as list
        :return: void
        :raises: TypeError
        """
        if not isinstance(dirs, list) or len(dirs) == 0:
            error_message = 'set_add_dirs: dirs must be a list with at least 1 directory to search'
            self.log(error_message, 'error')
            raise TypeError(error_message)

        self.addon_dirs = dirs

    # Getters

    @staticmethod
    def get_loaded_addon_instance(addon_name):
        """
        Use to for nested addon calls.
        :param addon_name: addon to load
        :return: addon instance
        """
        if addon_name.endswith("Addon"):
            if addon_name in sys.modules:
                _temp = sys.modules.get(addon_name, None)
                _temp_class = _temp.__dict__.get(addon_name)
                return _temp_class()
        else:
            return None

    # Public

    def load_addons(self):
        """
        Load addons from specified directories
        - scan files
        - load them
        - validate for required methods
        - load
        :return: void (sets class level dict)
        """
        self._scan_for_addons()
        self._validate_addons()

        for addon in self.scanned_addons.keys():
            self._get_addon_class(addon)

    def get_instance(self, addon):
        """
        get instance of addon loaded by name
        :param addon: addon name for which instance will be returned
        :return: instance of loaded addon
        :rtype: class instance
        :raises: ImportWarning, NameError
        """
        if len(self.loaded_addons) == 0:
            err = 'No addon loaded, first call .load_addons() or no addons found in given directory'
            self.log(err, 'error')
            raise ImportWarning(err)

        if addon not in self.loaded_addons:
            raise NameError("'{0}' addon is not loaded".format(addon))
        _instance = self.loaded_addons.get(addon)
        return _instance.get('Class')()

    def get_loaded_addons(self):
        return self.loaded_addons.keys()

    # Private functions

    @staticmethod
    def _get_calling_script_dir():
        caller = sys.argv[0]
        return os.path.dirname(caller)

    def _get_addon_class(self, addon):
        """
        Get addon class from loaded module
        :param addon: addon to get
        :return: void ( creates new dict() with class )
        """
        _temp = self.scanned_addons.get(addon)
        self.loaded_addons[addon] = _temp.__dict__.get(addon)

    def _load_own_config(self):
        """
        load AddonLoader config file or if not found set to default
        :return: config
        :rtype: dict
        """
        config_file = os.path.join(self.init_dir, 'addon-loader.info')
        self.log("Trying to read addonpy config for this project from '{0}'".format(config_file))
        addon_conf = AddonHelper.parse_info_file(config_file)

        if addon_conf is None:
            self.log("addon-loader.info file not found/not proper, loading pre-configured addon config")
            addon_conf = dict(required_functions=['start', 'stop', 'execute', '__addon__'],
                              addon_places=[os.path.abspath(os.curdir)],
                              recursive='False',
                              verbose='False')

            self.active_config = addon_conf
            return

        for dir_name in addon_conf.get('addon_places'):
            if dir_name.startswith('.') or dir_name.startswith('..'):
                self.log("Addon directory(ies) mentioned as relative paths, converting to absolute paths...")
                _abs_temp_path = os.path.abspath(os.path.join(self.init_dir, dir_name))
            else:
                # Its not a relative path. you cannot use $ENV in loader.info file, rely on set_addon_dirs method...
                _abs_temp_path = dir_name

            if os.path.isdir(_abs_temp_path):
                self.addon_dirs.append(_abs_temp_path)

        addon_conf['addon_places'] = self.addon_dirs
        self.active_config = addon_conf

    def _scan_for_addons(self):
        """
        scan directories and load the addons
        :return: void ( sets class level dict with all the found addons )
        :raises: ImportError
        """
        possible_addons = self._search_for_addons()

        if len(possible_addons) > 0:
            for addon_file in possible_addons:
                addon_name, ext = AddonHelper.get_basename_and_ext(addon_file)

                if not addon_name.endswith('Addon'):
                    self.log(">> Not loading '{0}' as file name does not end with 'Addon'".format(addon_file))
                    continue

                self.log("> Addon file '{0}' found...".format(addon_file))

                addon_info = AddonHelper.parse_info_file(addon_file)
                compatible_platforms = addon_info.get('os')

                if compatible_platforms is not None:
                    if self.is_compatible_for_current_platform(compatible_platforms):
                        # Add in scanned_addons
                        self._update_scanned_addon_list(addon_name, addon_file, addon_info)
                        self._load_module_from_source(addon_name, addon_file)
                    else:
                        self.logger.info(">>> Addon '{0}' not compatible with current '{1}' platform."
                                         "supported platforms by this addon '{2}'".
                                         format(addon_name, self.current_platform, ','.join(compatible_platforms)))
                else:
                    # Add in scanned_addons
                    self._update_scanned_addon_list(addon_name, addon_file, addon_info)
                    self._load_module_from_source(addon_name, addon_file)
        else:
            self.log("No addons found", "error")

    def _search_for_addons(self):
        """
        Get file list of matching addons by their extension
        :return: list with possible addon files
        :rtype: list
        """

        matching_list = list()

        for dir_a in self.addon_dirs:
            if os.path.isdir(dir_a):
                self.log("Searching '{0}' for addons with extension {1}...".format(dir_a, self.ext))
                m_list = AddonHelper.walk_dir(dir_a, self.ext, self.recursive_search)
                matching_list.extend(m_list)

        return matching_list

    def _update_scanned_addon_list(self, addon_name, addon_path, addon_info):
        """
        Add addon to scanned addon list with basic module information
        :param addon_name: addon name
        :param addon_path: absolute addon file path
        :param addon_info: addon info dict()
        :return: void
        """
        if addon_name in self.scanned_addons:
            return

        self.scanned_addons[addon_name] = {'FILE': addon_path, 'META': addon_info, 'MODULE': None}

    def _load_module_from_source(self, addon_name, addon_file):

        base_dir = AddonHelper.add_to_module_search_dir(addon_file)

        try:
            module = importlib.import_module(addon_name)
        except (ImportError, SystemError) as why:
            self.log("Failed to load '{0}' from '{1}' directory".format(addon_name, base_dir), 'error')
            self.log("\t More info: {}".format(why), 'error')
        else:
            self.log("addon loaded: '{0}'".format(addon_name))
            self.scanned_addons[addon_name]['MODULE'] = module

    # def is_compatible_for_current_platform(self, eligible_platforms):
    #     return self.current_platform in eligible_platforms

    def _validate_addons(self):
        """
        validate the addon by checking if addon has required functions defined
        :return: void ( updates scanned_addon dict )
        """
        total = 0
        passed = 0
        failed = 0

        for addon in self.scanned_addons.keys():
            total += 1
            error_cnt = 0
            self.log("Validating addon: '{0}'".format(addon))
            addon_as_module = self.scanned_addons.get(addon)
            addon_functions = getattr(addon_as_module, addon_as_module.__name__)
            all_functions = addon_functions.__dict__.keys()

            for expected_function in self.config.get('required_functions'):
                if expected_function not in all_functions:
                    error_cnt += 1
                    self.log("     Required method: '{0}' not found!".format(expected_function), 'error')

            if error_cnt > 0:
                self.log("Failed! Unloading addon...".format(addon), 'error')
                self.scanned_addons.__delitem__(addon)
                failed += 1
            else:
                passed += 1
                self.log('Passed...')

        self.log("Total '{0}' addons found. passed validation: {1} failed validations: {2}".
                 format(total, passed, failed))

    # Logger

    def log(self, message, level='debug'):
        """
        log messages to console
        :param message: message to log
        :param level: message level, default: debug
        :return: void
        """
        if level is None or message is None:
            return

        if not self.verbose and level.lower() == 'debug':
            return

        if self.logger is None:
            print("{0} [{1}] {2}".format(datetime.now(), level.upper(), message))
        else:
            if level == 'info':
                self.logger.info(message)
            elif level == 'debug':
                self.logger.debug(message)
            elif level == 'trace':
                self.logger.trace(message)
            elif level == 'error':
                self.logger.error(message)
            elif level == 'fatal':
                self.logger.fatal(message)

if __name__ == '__main__':
    print("use this as module, basic help: import addonpyLite")