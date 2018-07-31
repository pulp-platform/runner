#
# Copyright (c) 2015 Germain Haugou
#
# This file is part of the gvsoc software
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import argparse
import os
import sys
import re
import imp
import plptree
import json_tools as js

class Property(object):
    def __init__(self, path, className, compName, propertyName, value):
        self.path = path
        self.className = className
        self.compName = compName
        self.pathRegexp = re.compile(path)
        self.classNameRegexp = re.compile(className)
        self.propertyName = propertyName
        self.value = value
        self.compNameRegexp = re.compile(compName)

    def __str__(self):
        return "%s: %s: %s: %s: %s" % (self.path, self.className, self.compName, self.propertyName, self.value)

    def check(self, path, className, compName):
        # In case we match the component path, its class and its component name, we set the property as being
        # an argument to overload the arguments with the same name
        # Note that components with no name always match the name
        return self.pathRegexp.search(path) and self.classNameRegexp.search(className) and (compName == None or self.compNameRegexp.search(compName))

class Option(object):

    def __init__(self, name, comp, config):
        self.name = name
        self.config = config
        self.comp = comp

    def bindToProperty(self, propertyName, path='.*', className='.*', compName='.*'):
        prop = self.config.setProperty(propertyName=propertyName, path=path, compName=compName, value=self.config.args.__dict__[self.name])
        self.comp.applyProperty(prop)
        

class Config(object):

    def __init__(self, parser):
        self.props = []
        self.parser = parser

    def setProperty(self, propertyName, value=None, path='.*', className='.*', compName='.*'): 
        prop = Property(path=path, className=className, compName=compName, propertyName=propertyName, value=value)
        self.props.append(prop)
        return prop

    def getProperties(self):
        return self.props

    def dumpProperties(self):
        for prop in self.props:
            print(str(prop))

    def getProperty(self, propertyName, path='.*', className='.*', compName='.*'):
        for prop in self.props:
            if prop.propertyName == propertyName and prop.check(path, className, compName):
                return prop
        return None

    def checkOptions(self):
        self.parser.parse_args()        

    def getParser(self):
        return self.parser

    def getArgs(self):
        self.args = self.parser.parse_known_args()[0]
        return self.args

    def addOption(self, *args, **kwargs):
        if 'comp' in kwargs:
            comp = kwargs['comp']
            del kwargs['comp']
        else:
            comp = None
        self.parser.add_argument(*args, **kwargs)
        self.args = self.parser.parse_known_args()[0]
        return Option(name=kwargs['dest'], config=self, comp=comp)

    def getOption(self, name):
        self.args = self.parser.parse_known_args()[0]
        if name not in self.args.__dict__: return None
        return self.args.__dict__[name]

class Runner(object):
    def __init__(self):
        parser = argparse.ArgumentParser(description='Launch a test on the specified architecture.', add_help=False)
        self.config = Config(parser)
        self.platforms = {}
        self.modules = []
        self.parser = parser

    def addModule(self, module):
        self.modules.append(module)

    def addPlatform(self, name, platform):
        self.platforms[name] = platform

    def run(self):
        self.config.addOption("--help", dest="showHelp", action="store_true", help="show this help message and exit")

        self.config.addOption("--platform", dest="platform", default=None, choices=list(self.platforms.keys()), help="specify the platform. Default: %(default)s.")
    
        self.config.addOption("--prop", dest="props", action="append",
                         help="specify a property to be given to the platform", metavar="PATH")
        
        self.config.addOption("--dir", dest="dir", default=os.getcwd(),
                         help="specify the test directory containing the binaries and from which the execution must be launched.", metavar="PATH")
        
        self.config.addOption("--launcher", dest="launcher", default=os.path.join(os.environ['PULP_SDK_HOME'], 'bin', 'launcher'),
                         help="specify the launcher command to be executed", metavar="CMD")
        
        self.config.addOption("--commands", dest="showCommands", action="store_true", default=False,
                         help="show the available commands.")
    
        self.parser.add_argument('command', metavar='commands', type=str, nargs='*',
                            help='a command to be executed')

        self.parser.add_argument("--chip", dest="chip", default=None, help="Specify target chip")

        self.config.addOption("--dev", dest="dev", action="store_true", default=False,
                         help="activate development mode (more advanced options)")

        self.config.addOption("--no-warnings", dest="warnings", action="store_false", default=True,
                         help='deactivate warnings')

        self.config.addOption("--config", dest="config", default=None, help='specify the system configuration')

        self.config.addOption("--reentrant", dest="reentrant", action="store_true", help='This script was called was pulp-run')

        self.config.addOption("--config-file", dest="configFile", default=None, help='specify the system configuration file')

        self.config.addOption("--config-opt", dest="configOpt", default=[], action="append", help='specify configuration option')

        if self.config.getOption('dev'):
            self.config.addOption("--py-stack", dest="pyStack", action="store_true", default=False,
                            help="activate Python tracestack")

        props = self.config.getOption('props')
        if props != None:
            for rawProp in props:
                prop = rawProp.split(':')
                self.config.setProperty(propertyName=prop[1], value=prop[2], path=prop[0])


        testPath = os.path.abspath(self.config.getOption('dir'))
        try:
            os.makedirs(testPath)
        except:
            pass
        os.chdir(testPath)

        systemConfig = self.config.getOption('config')
        if systemConfig != None:
            self.system_tree = plptree.get_configs_from_env(self.config.args.configDef, systemConfig)
        else:
            self.system_tree = plptree.get_configs_from_file(self.config.getOption('configFile'))[0]

        self.pyStack = self.system_tree.get_bool('runner/py-stack')



        # First get the json configuration
        config_path = self.config.getOption('configFile')
        chip = self.config.getOption('chip')

        if chip is not None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(sys.argv[0])),
                'configs', 'systems', '%s.json' % chip
            )
        elif config_path is None:
            raise Exception('A chip or a config file must be specified')

        config = js.import_config_from_file(config_path)


        platform = self.config.getOption('platform')
        if platform is not None:
            config.set('platform', platform)


        self.system_tree = plptree.get_config_tree_from_dict(config.get_dict())

        platform_name = config.get('**/platform').get()

        if platform_name == 'gvsoc' and self.system_tree.get('pulp_chip') in ['pulp', 'pulpissimo', 'oprecompkw', 'oprecompkw_sfloat', 'oprecompkw_sfloat_sa', 'multino', 'oprecompkw_sa', 'bigpulp', 'bigpulp-z-7045', 'wolfe']:
            platform_name = 'vp'

        try:

            module = imp.load_source('module', self.platforms[platform_name])

            

            platform = module.Runner(self.config, config)

            for module in self.modules:
                platform.addParser(module(self.config, self.system_tree))

            retval = platform.handleCommands()
            return retval
        except Exception as e:
            if self.pyStack:
                raise
            else:
                print(e)
                return -1
