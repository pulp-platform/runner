# -*- coding: utf-8 -*-
import argparse
from plp_platform import *
from elftools.elf.elffile import ELFFile

import os
import os.path

class Runner(Platform):

    def __init__(self, config):

        super(Runner, self).__init__(config)
        
        parser = config.getParser()

        parser.add_argument("--binary", dest="binary",
                            help='specify the binary to be loaded')
                     
        parser.add_argument("--devices", dest="devices", default=[], action="append",
                            help='specify platform devices')
        
        [args, otherArgs] = parser.parse_known_args()
   
        self.addCommand('prepare', 'Prepare binary for HSA platform')


    def append_data(self, data, addr, mem_data, mem_addr):
        if addr > mem_addr:
            for i in range(0, addr - mem_addr):
                mem_data += b'\x00'
        mem_data += data

        return (mem_data, addr + len(data))


    def prepare(self):

        binary = self.config.getOption('binary')

        l1_data = b''
        l2_data = b''
        current_l1_addr = 0x10000000
        current_l2_addr = 0x1c000000

        with open(binary, 'rb') as file:
            elffile = ELFFile(file)
            for segment in elffile.iter_segments():
                if segment['p_type'] == 'PT_LOAD':

                    addr = segment['p_paddr']
                    data = segment.data()

                    print ('%x %x' % (segment['p_paddr'], len(segment.data())))

                    if addr >= 0x10000000 and addr < 0x11000000:
                        (l1_data, current_l1_addr) = self.append_data(data, addr, l1_data, current_l1_addr)
                    elif addr >= 0x1C000000 and addr < 0x20000000:
                        (l2_data, current_l2_addr) = self.append_data(data, addr, l2_data, current_l2_addr)


        with open('%s.tcdm.bin' % binary, 'wb') as file:
            file.write(l1_data)

        with open('%s.l2.bin' % binary, 'wb') as file:
            file.write(l2_data)


        return os.system("hsa_run_riscv_new %s %s" % (self.config.getOption('dir'), binary))

