# -*- coding: utf-8 -*-
import argparse
from plp_platform import *

import os
import os.path
import time
import binary_tools as binaryTools
import plptree

def execCmd(cmd):
    print ('Executing command: ' + cmd)
    return os.system(cmd)

class Runner(Platform):

    def __init__(self, config):

        super(Runner, self).__init__(config)
        
        parser = config.getParser()

        parser.add_argument("--binary", dest="binary",
                            help='specify the binary to be loaded')
                        
        parser.add_argument("--wwolf", dest="wwolf", default=None,
                            help='specify path to wwolf tool')
        parser.add_argument("--emu-addr", dest="emuAddr", default='haugoug@iis-haugoug.ee.ethz.ch',
                            help='specify the emulator address. Default: %(default)s')
        parser.add_argument("--emu-destDir", dest="emuDestDir", default='/home/haugoug/',
                            help='specify the emulator address. Default: %(default)s')        
        parser.add_argument("--emu-mapping", dest="emuMapping", default=None,
                            help='specify the emulator bitstream loaded with command map. Default: %(default)s')
        parser.add_argument("--pulp-core-archi", dest="pulpCoreArchi",
                            help='specify the core architecture to be simulated', default="or1k")
        parser.add_argument("--pulp-archi", dest="pulpArchi",
                            help='specify the PULP architecture to be simulated', default="mia")
        parser.add_argument("--comp", dest="comps", default=[], action="append", help='specify dynamic component')
        parser.add_argument("--devices", dest="devices", default=[], action="append",
                            help='specify platform devices')
                        

        [args, otherArgs] = parser.parse_known_args()
   
        self.addCommand('run', 'Run execution on FPGA')
        self.addCommand('map', 'Load bitstream on FPGA')
        self.addCommand('prepare', 'Prepare binary for FPGA mapping')
        self.addCommand('copy', 'Copy binary for FPGA mapping')

        self.system_tree = plptree.get_configs_from_file(self.config.getOption('configFile'))[0]

        self.pulpArchi = self.system_tree.get('pulp_chip')

    def getEmuAddr(self):
        emuAddr = os.environ.get('PULP_EMU_ADDR')
        if emuAddr == None:
            emuAddr = self.config.getOption('emuAddr')
        return emuAddr

    def getEmuDestDir(self):
        emuDestDir = os.environ.get('PULP_EMU_DEST_DIR')
        if emuDestDir == None:
            emuDestDir = self.config.getOption('emuDestDir')
        return emuDestDir

    def getWwolf(self):
        wwolf = os.environ.get('PULP_EMU_WWOLF')
        if wwolf == None: wwolf = self.config.getOption('wwolf')
        if wwolf == None: wwolf = 'wwolf'
        return wwolf

    def remoteExec(self, cmd):
        return execCmd("ssh %s %s" % (self.getEmuAddr(), cmd))

    def copy(self):
        binary = self.config.getOption('binary')
        if binary != None:
            binFile = '%s.l2.bin' % (os.path.join(os.path.dirname(binary), os.path.basename(binary)))
            binFileTcdm = '%s.tcdm.bin' % (os.path.join(os.path.dirname(binary), os.path.basename(binary)))
            if execCmd("scp %s %s:%s%s" % (binFile, self.getEmuAddr(), self.getEmuDestDir(), os.path.basename(binFile))): return -1
            if execCmd("scp %s %s:%s%s" % (binFileTcdm, self.getEmuAddr(), self.getEmuDestDir(), os.path.basename(binFileTcdm))): return -1
            return 0
        else: return -1

    def prepare(self):
        binary = self.config.getOption('binary')
        if binary != None:
            archi = self.system_tree.get('pe/archi')
            if archi is None:
                archi = self.system_tree.get('fc/archi')
            return binaryTools.genSectionBinaries(binary, os.path.dirname(binary), archi)
        else: return -1

    def reset(self):
        switchAddr = os.environ.get('PULP_REMOTE_SWITCH_ADDR')
        if switchAddr == None:
            switchAddr = 'powerswitch.ee.ethz.ch'
            print ('No power switch address defined in PULP_REMOTE_SWITCH_ADDR, taking default one: ' + switchAddr)
        switchId = os.environ.get('PULP_REMOTE_SWITCH_ID')
        if switchId == None:
            switchId = '1'
            print ('No power switch ID defined in PULP_REMOTE_SWITCH_ID, taking default one: ' + switchId)
        execCmd("curl --silent %s/hidden.htm?M0:O%s=off > /dev/null" % (switchAddr, switchId))
        time.sleep(1)
        execCmd("curl --silent %s/hidden.htm?M0:O%s=on > /dev/null" % (switchAddr, switchId))

    def waitAlive(self):
        emuAddr = self.getEmuAddr()
        if emuAddr.find('@'): emuAddr = emuAddr.split('@')[1]
        isFirst = True
        retryCount = 10
        remCount = retryCount
        while True:
            if execCmd("timeout 5 ssh %s exit" % (self.getEmuAddr())) == 0: break
            if isFirst:
                self.reset()
                isFirst = False
            else: time.sleep(5)
            remCount -= 1
            if remCount == 0:
                raise Exception("Did not manage to reach FPGA at this address after %s resets: %s" % (retryCount, emuAddr))


    def bitstream(self):
        self.fpgaBitstream = self.config.getOption('emuMapping')

        archi = self.pulpArchi
        if archi != None:
            if self.fpgaBitstream == None:
                if archi == 'mia':
                    dir = os.environ.get('PULP_MIA_BITSTREAM')
                    if dir == None: raise Exception("PULP_MIA_BITSTREAM must be defined to the directory containing miaemu.bit.bin")
                    self.fpgaBitstream = dir + '/miaemu.bit.bin'
                elif archi == 'pulp3':
                    dir = os.environ.get('PULP_PULP3_BITSTREAM')
                    if dir == None: raise Exception("PULP_PULP3_BITSTREAM must be defined to the directory containing pulp3emu.bit.bin")
                    self.fpgaBitstream = dir + '/pulp3emu.bit.bin'
                elif archi == 'pulp4':
                    dir = os.environ.get('PULP_PULP4_BITSTREAM')
                    if dir == None: raise Exception("PULP_PULP4_BITSTREAM must be defined to the directory containing pulp4emu.bit.bin")
                    self.fpgaBitstream = dir + '/pulp4emu.bit.bin'
                elif archi == 'fulmine':
                    dir = os.environ.get('PULP_FULMINE_BITSTREAM')
                    if dir == None: raise Exception("PULP_FULMINE_BITSTREAM must be defined to the directory containing fulmineemu.bit.bin")
                    self.fpgaBitstream = dir + '/fulmineemu.bit.bin'
                elif archi == 'fulmine8':
                    dir = os.environ.get('PULP_FULMINE8_BITSTREAM')
                    if dir == None: raise Exception("PULP_FULMINE8_BITSTREAM must be defined to the directory containing fulmine8emu.bit.bin")
                    self.fpgaBitstream = dir + '/fulmine8emu.bit.bin'
                else:
                    raise Exception("Didn't find any mapping for this chip: " + archi)

        print ('Loading bitstream %s in FPGA' % self.fpgaBitstream)
        if not os.path.exists(self.fpgaBitstream):
            print ('ERROR: the specified bitstream does not exist')
            return -1
        if execCmd("scp %s %s:%s%s" % (self.fpgaBitstream, self.getEmuAddr(), self.getEmuDestDir(), os.path.basename(self.fpgaBitstream))):
            print ('ERROR: failed to upload FPGA bitstream')
            return -1
        if self.remoteExec("sudo load_bitstream %s%s" % (self.getEmuDestDir(), os.path.basename(self.fpgaBitstream))) != 0:
            print ('ERROR: failed to upload FPGA bitstream')
            return -1
        return 0

    def run(self):

        # Always map FPGA mapping in case of validation mode to avoid being
        # disturbed
        if os.environ.get('PULP_VALID_MODE') != None: 
            self.waitAlive()
            self.bitstream()

        emuAddr = self.getEmuAddr()
        wwolf = self.getWwolf()

        binary = self.config.getOption('binary')
        if binary != None:
            archi = self.pulpArchi
            if archi.find('gap') != -1:
                return execCmd("debug_bridge --proxy -c shell -b gap -copt \"ssh %s sudo %s -p -l\" --binary %s --load -m 0x1A104074 -wm 0x00000001 --printf --start -1 --loop" % (emuAddr, wwolf, binary))
            else:
                if self.copy() != 0:
                    return -1

                if archi == 'mia' or archi == 'pulp3':
                    wwolf = 'wwolf3'

                if os.environ.get('PULP_VALID_MODE') != None: 
                    return execCmd("ssh %s sudo %s -n %s%s.l2.bin" % (emuAddr, wwolf, self.getEmuDestDir(), os.path.basename(binary)))
                else:
                    return execCmd("ssh %s sudo %s -n %s%s.l2.bin -T %s%s.tcdm.bin" % (emuAddr, wwolf, self.getEmuDestDir(), os.path.basename(binary), self.getEmuDestDir(), os.path.basename(binary)))

class PlpHsaRunner(Platform):

    def __init__(self, config):

        super(PlpHsaRunner, self).__init__(config)
        
        parser = config.getParser()

        parser.add_argument("--binary", dest="binary",
                            help='specify the binary to be loaded')
                        
        parser.add_argument("--devices", dest="devices", default=[], action="append",
                            help='specify platform devices')

        [args, otherArgs] = parser.parse_known_args()
   
        self.addCommand('run', 'Run execution on HSA emulator')

    def run(self):

        binary = self.config.getOption('binary')
        if binary != None:
            binFile = '%s.bin' % (os.path.join(os.path.dirname(binary), os.path.basename(binary)))
            if execCmd("objcopy -R .debug_frame -R .comment -R .stack -R .heapsram -R .heapscm -R .libgomp -R .heapl1 -O binary %s %s" % (binary, binFile)) != 0: return -1 
            if execCmd("scp %s root@zedboard-05:/tmp/%s" % (binFile, os.path.basename(binFile))) != 0: return -1
        

            return execCmd("ssh root@zedboard-05 /media/nfs/programs/standalone /tmp/%s" % (os.path.basename(binary)))
