# -*- coding: utf-8 -*-
import argparse
from plp_platform import *

import os
import os.path

class Runner(Platform):

    def __init__(self, config, tree):

        super(Runner, self).__init__(config, tree)
        
        parser = config.getParser()

        parser.add_argument("--binary", dest="binary",
                            help='specify the binary to be loaded')
                     
        parser.add_argument("--devices", dest="devices", default=[], action="append",
                            help='specify platform devices')

        parser.add_argument("--core", dest="core", default='or1k',
                            help='specify core architecture')
        
        [args, otherArgs] = parser.parse_known_args()
   
        self.addCommand('prepare', 'Prepare binary for zedboard platform')

    def prepare(self):

        binary = self.config.getOption('binary')

        #if self.config.getOption('core') == 'or1k':
        #    return os.system("hsa_run %s %s" % (self.config.getOption('dir'), binary))
        #else:
        return os.system("hsa_run_riscv %s %s" % (self.config.getOption('dir'), binary))

