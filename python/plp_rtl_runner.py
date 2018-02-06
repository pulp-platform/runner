# 
# Copyright (C) 2015 ETH Zurich and University of Bologna
# All rights reserved.
#
# This software may be modified and distributed under the terms
# of the BSD license.  See the LICENSE file for details.
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#

import argparse
import shutil
from plp_platform import *

import os
import os.path
import shutil
from functools import partial
import struct
import plp_flash_stimuli
from efuse import *
import dpi_models as dpi

import plptree

def execCmd(cmd):
    print ('Executing command: ' + cmd)
    return os.system(cmd)

class Runner(Platform):

    def __init__(self, config):

        super(Runner, self).__init__(config)
        
        self.rtlLibs = None

        parser = config.getParser()

        parser.add_argument("--vsimCov", dest="vsimCov", default=False, action="store_true",
                            help='Activate Code Coverage feature in Questasim')
                        
        parser.add_argument("--vsimPa", dest="vsimPa", default=False, action="store_true",
                            help='Activate Power Aware feature in Questasim')
                        
        parser.add_argument("--vsimFlashLoadMem", dest="vsimFlashLoadMem", default=False, action="store_true",
                            help='Activate SPI flash load memory with user slm file in testbench')
                        
        parser.add_argument("--vsimGpioLoopback", dest="vsimGpioLoopback", default=False, action="store_true",
                            help='Activate GPIO loopback feature in testbench')
                        
        parser.add_argument("--vsimPadMuxMode", dest="vsimPadMuxMode", default=None,
                            help='Select padmux mode feature in testbench')

        parser.add_argument("--vsimBootTypeMode", dest="vsimBootTypeMode", default=None,
                            help='Select boot mode feature in testbench')
                        
        parser.add_argument("--recordWlf", dest="recordWlf", default=False, action="store_true",
                            help='record waveform WLF file during console mode simulation')
                        
        parser.add_argument("--vsim-testname", dest="vsimTestName",
                            help='Specify testname to use for running RTL simulation', default=None)
        
        parser.add_argument("--vsim-do", dest="vsimDo",
                            help='Specify do scripts to use for running RTL simulation (specially to set waveforms to be recorded into wlf file)', default=None)
        
        parser.add_argument("--power", dest="power", default=False, action="store_true",
                            help='Do power estimation')
                        
        parser.add_argument("--hyperflash", dest="hyperFlash", default=False, action="store_true",
                            help='Use hyper flash')
                        
        parser.add_argument("--vopt", dest="vopt", default=False, action="store_true",
                            help='Use RTL platform compiled with vopt')
                        
        parser.add_argument("--model", dest="model", default=None,
                            help='specify simulation model (postsynth, postsynth_ba, fpga, fpga_netlist, fpga_netlist_ba)')
                        
        parser.add_argument("--binary", dest="binary",
                            help='specify the binary to be loaded')
                        
        parser.add_argument("--devices", dest="devices", default=[], action="append",
                            help='specify platform devices')
                        
        parser.add_argument("--use-dpi", dest="useDpi", default=False, action="store_true",
                            help='Activate DPI models')
                        
        parser.add_argument("--boot-binary", dest="bootBinary", default=None, help='specify a boot binary to be loaded', metavar="PATH")

        parser.add_argument("--uart-loopback", dest="loopBack", default=False, action="store_true", help='activate loopback')
        parser.add_argument("--flash-stimuli", dest="flashStimuli", default=None, help='specify flash stimuli data file')
        parser.add_argument("--flash", dest="flash", default=None, help='specify flash raw data file')
        parser.add_argument("--i2s-0", dest="i2s0", default=None, help='specify I2S stream file')

        parser.add_argument("--adc", dest="adc", default=[], action="append", help='specify ADC stream file')

        parser.add_argument("--load", dest="load",
                            help='specify the way the binary is loaded', default=None)
        
        parser.add_argument("--vsim-script", dest="vsimScript",
                            help='specify the script to use for running RTL simulation', default=None)
        
        parser.add_argument("--pulp-archi", dest="pulpArchi",
                            help='specify the PULP architecture to be simulated', default=None)
        parser.add_argument("--core-archi", dest="coreArchi",
                            help='specify the core architecture', default=None)
        parser.add_argument("--kcg", dest="kcg", default=None, help='Activate PC analysis through kcachegrind for the specified path')

        parser.add_argument("--efuse", dest="efuses", default=[], action="append", help='specify efuse value with format <efuse ID>:<efuse value>')

        parser.add_argument("--hyper", dest="hyper", action="store_true", default=False, help='Activate hyperbus')
                        
        parser.add_argument("--encrypt", dest="encrypt", action="store_true", default=False, help='Activate binary encryption')
                        
        parser.add_argument("--xtal-wait", dest="xtalWait", action="store_true", default=False, help='Activate xtal stabilization wait')
                        
        parser.add_argument("--xtal-wait-delta", dest="xtalWaitDelta", default=0.1, help='Xtal stabilization allowed delta')

        parser.add_argument("--xtal-wait-min", dest="xtalWaitMin", default=3, help='Xtal stabilization min stable period')

        parser.add_argument("--xtal-wait-max", dest="xtalWaitMax", default=10, help='Xtal stabilization max periods')
        
        [args, otherArgs] = parser.parse_known_args()
   
        self.system_tree = plptree.get_configs_from_file(self.config.getOption('configFile'))[0]

        self.addCommand('run', 'Run execution on RTL simulator')
        self.addCommand('prepare', 'Prepare binary for RTL simulator (SLM files, etc)')

        self.pulpArchi = config.getOption('pulpArchi')
        if self.pulpArchi is None:
            self.pulpArchi = self.system_tree.get('pulp_chip')
        self.pulpCore = 'or10n'
        if self.pulpArchi.find('-riscv') != -1:
            self.pulpCore = 'riscv'
        elif self.pulpArchi.find('-or10nv2') != -1:
            self.pulpCore = 'or10nv2'
        self.pulpChip = self.pulpArchi.split('-')[0]
        self.simArgs = self.system_tree.get_config('vsim/args').get_dict()

        if self.config.getOption('encrypt'):
            self.aesKey = '12345678275689075642768987654345'
            self.aesIv = '0987654323456789'
        else:
            self.aesKey = None
            self.aesIv = None

        self.gui = self.system_tree.get('vsim/gui')

        if self.system_tree.get('vsim/simchecker'):
            os.environ['PULP_SIMCHECKER'] = '1'

    def prepareSim(self):
        if self.rtlLibs == None:

            # Firts see if a single RTL build is specified
            rtlLibs = os.environ.get('VSIM_PATH')
            if rtlLibs != None and os.path.exists(rtlLibs):
                print ('VSIM_PATH is correctly defined, using following RTL platform: ' + rtlLibs)
                if not os.path.exists(rtlLibs):
                    raise Exception("ERROR: VSIM_PATH=%s path does not exist" % rtlLibs)

            if rtlLibs == None:
                rtlLibs = os.environ.get('PULP_RTL_INSTALL')
                if rtlLibs != None and os.path.exists(rtlLibs):
                    print ('PULP_RTL_INSTALL is correctly defined, using following RTL platform: ' + rtlLibs)
                    if not os.path.exists(rtlLibs):
                        raise Exception("ERROR: PULP_RTL_INSTALL=%s path does not exist" % rtlLibs)
        
            # Otherwise see if we can get it from the RTL root directory
            chipPath = 'PULP_RTL_%s' % self.pulpChip.upper()
            if rtlLibs == None:
                rtlHome = os.environ.get(chipPath)
                if rtlHome != None and os.path.exists(rtlHome):
                    os.environ['PULP_RTL_HOME'] = rtlHome
                    rtlLibs = rtlHome
                    print ('%s is correctly defined, using following RTL platform: %s' % (chipPath, rtlLibs))
                    if self.config.getOption('power'):
                        rtlLibs = rtlLibs + '_power'

            if rtlLibs == None:
                print ("WARNING: no RTL install specified, neither %s nor PULP_RTL_INSTALL nor VSIM_PATH is correctly defined:" % (chipPath))
                print ("  VSIM_PATH        : " + str(os.environ.get('VSIM_PATH')))
                print ("  PULP_RTL_INSTALL : " + str(os.environ.get('PULP_RTL_INSTALL')))
                print ("  %-16s : " % (chipPath) + str(os.environ.get(chipPath)))

            self.rtlLibs = rtlLibs

            if os.environ.get('VSIM_PATH') == None: os.environ['VSIM_PATH'] = rtlLibs
            os.environ['TB_PATH'] = rtlLibs

        if self.config.getOption('flashStimuli') != None:
            shutil.copy2(self.config.getOption('flashStimuli'), 'slm_files/flash_stim.slm')


    def prepare(self):

        if not os.path.exists('stdout'): os.makedirs('stdout')

        os.environ['PULP_CORE'] = self.pulpCore

        binary = self.config.getOption('binary')
        if binary != None:
            print ('Generating stimuli for binary: ' + binary)

            try:
                os.makedirs('vectors')
            except:
                pass
            try:
                os.makedirs('slm_files')
            except:
                pass

            if self.pulpArchi.find('pulpino') != -1:
                slmScript = 's19toslm-pulpino.py'
            elif self.pulpArchi.find('mia') != -1: # or self.pulpArchi.find('vivosoc2') != -1: TODO this has been added because s19toslm.py is needed for boot from flash on the board but the other version is needed for slm stimuli
                slmScript = 's19toslm.py'
            elif self.pulpArchi.find('pulp3') != -1:
                slmScript = 's19toslm-pulp3.py'
            else:
                slmScript = 's19toslm-new.py'

            if execCmd("objcopy --srec-len 1 --output-target=srec %s %s.s19" % (binary, os.path.basename(binary))) != 0: return -1
            if execCmd("parse_s19.pl %s.s19 > ./vectors/stim.txt" % (os.path.basename(binary))) != 0: return -1
            if execCmd("cd slm_files && %s ../%s.s19 %s %s" % (slmScript, os.path.basename(binary), self.pulpArchi.replace('-riscv', ''), self.config.getOption('coreArchi'))) != 0: return -1

            if self.config.getOption('bootBinary') != None:
                # If we boot from rom and a boot binary is specified, this means it comes from the SDK, and we have to generate the CDE file
                bootBinary = self.config.getOption('bootBinary')
                if execCmd("objcopy --srec-len 1 --output-target=srec %s %s.s19" % (bootBinary, os.path.basename(bootBinary))) != 0: return -1
                if execCmd("cd slm_files && s19toboot.py ../%s.s19 %s" % (os.path.basename(bootBinary), self.pulpArchi.replace('-riscv', ''))) != 0: return -1

                try:
                    os.remove('boot')
                except:
                    pass
                    
                try:
                    os.makedirs('boot')
                except :
                    pass
                if execCmd("cp slm_files/boot_code.cde boot") != 0: return -1

            comps = []
            fs = self.system_tree.get_config('fs')
            if fs is not None:
                comps = fs.get('files')

            if self.pulpArchi.find('gap') != -1:
                if self.system_tree.get('boot_from_rom'):
                    flashType = 'spi'
                    if self.config.getOption('hyper') or self.config.getOption('load') == 'hyper': flashType = 'hyper'
                    if plp_flash_stimuli.genFlashImage(slmStim='slm_files/flash_stim.slm', bootBinary=self.config.getOption('binary'), comps=comps, verbose=True, archi=self.pulpArchi, encrypt=self.config.getOption('encrypt'), aesKey=self.aesKey, aesIv=self.aesIv, flashType=flashType): return -1
            else:
                if self.system_tree.get('boot_from_rom'):
                    if plp_flash_stimuli.genFlashImage(slmStim='slm_files/flash_stim.slm', bootBinary=self.config.getOption('binary'), comps=comps, verbose=True, archi=self.pulpArchi, encrypt=self.config.getOption('encrypt'), aesKey=self.aesKey, aesIv=self.aesIv, flashType='spi'): return -1

                if self.config.getOption('load') == 'hyper' or self.config.getOption('hyper'):
                    if plp_flash_stimuli.genFlashImage(slmStim='slm_files/hyper_flash_stim.slm', bootBinary=self.config.getOption('binary'), comps=comps, verbose=True, archi=self.pulpArchi, encrypt=self.config.getOption('encrypt'), aesKey=self.aesKey, aesIv=self.aesIv, flashType='hyper'): return -1


        if self.config.getOption('flash') != None:
            self.genFlashStimuli(self.config.getOption('flash'))

        if self.config.getOption('adc') != None:
            self.genAdcStimuli(self.config.getOption('adc'))

        return 0

    def process(self):
        self.prepareSim()
        if self.config.getOption('power'):
            os.system('plp_power_estimate.py --vcd=%s/pulpchip.vcd --platform=%s' % (os.getcwd(), self.rtlLibs))

    def genAdcStimuli(self, fullOpt):
        opt = {}
        for adcOpt in fullOpt:
            ch, name = adcOpt.split(':')
            if ch == '0':
                localName = 'stimuli/stimuli_sin_hex.asc'
            elif ch == '1':
                localName = 'stimuli/stimuli_cos_hex.asc'
            elif ch == '2':
                localName = 'stimuli/stimuli_exp_hex.asc'
            elif ch == '3':
                localName = 'stimuli/stimuli_log_hex.asc'
            if os.path.exists(localName):
                os.unlink(localName)
            try:
                os.makedirs('stimuli')
            except:
                pass
            os.symlink(name, localName)

    def genFlashStimuli(self, flashImage):
        print ('Generating flash stimuli from file: ' + flashImage)
        try:
            os.makedirs('slm_files')
        except:
            pass
        with open('slm_files/flash_stim.slm', "w") as output:
            with open(flashImage, "rb") as image:
                addr = 0
                for byte in iter(partial(image.read, 1), b''):
                    output.write('@%8.8x %2.2x\n' % (addr, struct.unpack("B", byte)[0]))
                    addr += 1

    def getVsimCmd_v1(self):
        
        if self.pulpArchi.find('patronus') != -1 and self.config.getOption('model') == 'postsynth':
            runScript = 'run_jtag_ps.tcl'
        elif self.config.getOption('power'):
            runScript = "run_power_soc.tcl"
        else:
            runScript = self.system_tree.get('vsim/script')

            if runScript == None:
                    if self.config.getOption('load') == None and (self.config.getOption('vopt') or (os.environ.get('PULP_VALID_MODE') != None and self.pulpArchi != 'vivosoc2')):
                        runScript = 'run_vopt.tcl'
                    else:
                        loadMode = self.config.getOption('load')
                        if self.config.getOption('load') == None: loadMode = 'preload'

                        if loadMode == 'preload': runScript = 'run.tcl'
                        elif loadMode == 'jtag': runScript = 'run_jtag.tcl'
                        elif loadMode.find('rom') != -1: runScript = 'run_boot.tcl'
                        elif loadMode == 'spi': runScript = 'run_spi.tcl'
                        else: raise Exception("Unknown load mode: " + loadMode)

        if self.gui:
            cmd = "vsim -64 -do 'source %s/tcl_files/%s;'" % (self.rtlLibs, runScript)
        else:
            cmd = "vsim -64 -c -do 'source %s/tcl_files/%s; run -a; exit'" % (self.rtlLibs, runScript)

        return cmd


    def getVsimCmd_v2(self):

        exportVsimDesignModel = "export VSIM_DESIGN_MODEL=sverilog;"
        if self.config.getOption('model') != None:
            print ('This simulation model is set to ' + self.config.getOption('model'))
            exportVsimDesignModel = "export VSIM_DESIGN_MODEL=%s;" % (self.config.getOption('model'))
            #+ print ('This simulation model is not yet supported: ' + self.config.getOption('model'))
            #+ return -1

        runScript = self.system_tree.get('vsim/script')

        if runScript == None:
            runScript = 'run.tcl'

        exportVarCmd = ""

        if self.config.getOption('vsimCov'):
            exportVarCmd = "export VSIM_COV=YES;"

        if self.config.getOption('vsimPa'):
            exportVarCmd = "%s export VSIM_PA=YES;" % (exportVarCmd)

        if self.system_tree.get('boot_from_rom'):
            if self.config.getOption('hyperFlash') or self.config.getOption('load') == 'hyper' or self.config.getOption('hyper'):
                self.simArgs.append('-gHYPER_FLASH_LOAD_MEM=1')
            else:
                exportVarCmd = "%s export SPI_FLASH_LOAD_MEM=YES;" % (exportVarCmd)

        if self.config.getOption('load') == 'hyper' or self.config.getOption('hyper'):
            self.simArgs.append('+VSIM_BOOTTYPE_CFG=TB_BOOT_FROM_HYPER_FLASH')

        if self.config.getOption('hyper'):
            self.simArgs.append('+VSIM_PADMUX_CFG=TB_PADMUX_ALT3_HYPERBUS')

        if self.config.getOption('vsimGpioLoopback'):
            exportVarCmd = "%s export VSIM_PADMUX_CFG=TB_PADMUX_GPIO_LOOPBACK;" % (exportVarCmd)

        padMuxMode = self.config.getOption('vsimPadMuxMode')
        if padMuxMode != None:
            exportVarCmd = "%s export VSIM_PADMUX_CFG=%s;" % (exportVarCmd, padMuxMode)

        bootTypeMode = self.config.getOption('vsimBootTypeMode')
        if bootTypeMode != None:
            exportVarCmd = "%s export VSIM_BOOTTYPE_CFG=%s;" % (exportVarCmd, bootTypeMode)

        uidTestName = self.config.getOption('vsimTestName')
        if uidTestName != None:
            exportVarCmd = "%s export TESTNAME=%s;" % (exportVarCmd, uidTestName)

        if self.config.getOption('recordWlf'):
            exportVarCmd = "%s export RECORD_WLF=YES;" % (exportVarCmd)

        doFiles = self.config.getOption('vsimDo')
        if doFiles != None:
            exportVarCmd = "%s export DO_FILES=\'%s\';" % (exportVarCmd, doFiles)

        loadMode = self.config.getOption('load')

        if loadMode == None: 
            if self.pulpArchi.find('pulpissimo') != -1:
                loadMode = 'jtag'
            elif self.pulpArchi.find('gap') == -1 and self.pulpArchi.find('wolfe') == -1 and self.pulpArchi != 'quentin':
                loadMode = 'preload'            
            else:
                loadMode = 'rom'

        efuses = self.config.getOption('efuses')
        if efuse_genStimuli_fromOption(efuses, 1024, 'efuse_preload.data', loadMode, aesKey=self.aesKey, aesIv=self.aesIv, xtalCheck=self.config.getOption('xtalWait'), xtalCheck_delta=float(self.config.getOption('xtalWaitDelta')), xtalCheck_min=int(self.config.getOption('xtalWaitMin')), xtalCheck_max=int(self.config.getOption('xtalWaitMax'))) != None:
            self.simArgs.append('+preload_file=efuse_preload.data') #+debug=1  Add that to get debug messages from efuse


        if self.system_tree.get('vsim/simchecker'):
            self.simArgs.append('+SIMCHECKER=1')

        # Add option which specify to the platform the boot mode
        if loadMode == 'spi':
            self.simArgs.append('-gLOAD_L2=SPI')
        elif loadMode == 'jtag':
            self.simArgs.append('-gLOAD_L2=JTAG')
        elif loadMode == 'spi_dev':
            self.simArgs.append('-gLOAD_L2=SPI_DEV')
        elif loadMode == 'jtag_dev':
            self.simArgs.append('-gLOAD_L2=JTAG_DEV')
        else:
            self.simArgs.append('-gLOAD_L2=STANDALONE')

        if self.system_tree.get('loader/bridge') == 'debug-bridge':
            self.simArgs.append('-gENABLE_DEBUG_BRIDGE=1')
            exportVarCmd = "%s export VSIM_EXIT_SIGNAL=/tb/dev_dpi/i_dev_dpi/exit_status;" % (exportVarCmd)

        #if self.system_tree.get('loader/bridge') == 'debug-bridge'or self.system_tree.get('dpi_models') is not None:
        #    exportVarCmd = "%s export PULP_CONFIG_FILE=%s;" % (exportVarCmd, self.config.getOption('configFile'))

        if os.environ.get('QUESTA_CXX') != None:
            self.simArgs.append('-dpicpppath ' + os.environ.get('QUESTA_CXX'))

        # Tell vsim to consider DPI errors as warnings as DPI modules are not mandatory
        self.simArgs.append('-warning 3197,3748')

        if len(self.simArgs) != 0: simArgs = 'export VSIM_RUNNER_FLAGS="%s" &&' % ' '.join(self.simArgs)

        if self.gui:
            exportVarCmd = "%s export VOPT_ACC_ENA=YES;" % (exportVarCmd)

        cmd = "%s %s %s vsim -64" % (exportVsimDesignModel, exportVarCmd, simArgs)

        # On wolfe, as only the chip is optimized and not the testbench, we need this option
        # to prevent the tb.exit_status signal from being optimized away
        if self.pulpArchi.find('wolfe') != -1 or self.pulpArchi == 'quentin' or self.pulpArchi == 'devchip': cmd += ' -novopt'

        if self.gui:
            cmd += " -do 'source %s/tcl_files/config/run_and_exit.tcl' -do 'source %s/tcl_files/%s;'" % (self.rtlLibs, self.rtlLibs, runScript)
        else:
            cmd += " -c -do 'source %s/tcl_files/config/run_and_exit.tcl' -do 'source %s/tcl_files/%s; run_and_exit;'" % (self.rtlLibs, self.rtlLibs, runScript)

        return cmd

    def getVsimCmd(self):
        if self.pulpArchi.find('honey') != -1 or self.pulpArchi.find('fulmine') != -1 or self.pulpArchi == 'mia' or self.pulpArchi == 'vivosoc2' or self.pulpArchi == 'pulp3':
            return self.getVsimCmd_v1()
        else:
            return self.getVsimCmd_v2()


    def run(self):

        retval = 0

        self.prepareSim()

        devices = dpi.get_devices(self.system_tree.get_config('system'))
        if self.system_tree.get('loader/bridge') == 'debug-bridge':
            devices.append('controller')
        if len(devices) != 0:
            os.environ['PLP_DEVICES'] = ':'.join(devices)


        if self.config.getOption('useDpi'):
            devices = self.config.getOption('devices')
            if len(devices) != 0:
                os.environ['PLP_DEVICES'] = ':'.join(devices)
            if 'controller' in devices:                
                self.simArgs.append('-gENABLE_DEBUG_BRIDGE=1')

        if self.rtlLibs == None:
            raise Exception("ERROR: no RTL install specified, can't launch simulation")

        if self.rtlLibs != None:
            # If not boot binary is specified, this means it comes from the RTL just create a symbolic link to it
            if self.config.getOption('bootBinary') == None:
                try:
                    os.remove('boot')
                except:
                    pass
                os.symlink(os.path.join(self.rtlLibs, 'boot'), 'boot')
            if os.path.islink('modelsim.ini'): os.remove('modelsim.ini')
            os.symlink(os.path.join(self.rtlLibs, 'modelsim.ini'), 'modelsim.ini')
            if os.path.islink('work'): os.remove('work')
            os.symlink(os.path.join(self.rtlLibs, 'work'), 'work')
            if os.path.islink('tcl_files'): os.remove('tcl_files')
            os.symlink(os.path.join(self.rtlLibs, 'tcl_files'), 'tcl_files')
            if os.path.islink('waves'): os.remove('waves')
            os.symlink(os.path.join(self.rtlLibs, 'waves'), 'waves')
            if self.pulpArchi.find('wolfe') != -1 or self.pulpArchi == 'quentin' or self.pulpArchi.find('vivosoc3') != -1:
                if os.path.islink('modelsim_libs'): os.remove('modelsim_libs')
                os.symlink(os.path.join(self.rtlLibs, 'modelsim_libs'), 'modelsim_libs')
                
        cmd = self.getVsimCmd()

        print ('Launching VSIM with command:')
        print (cmd)
        if os.system(cmd) != 0: 
            print ('VSIM reported an error, leaving')
            return -1
        os.system("tail -n +1 -- ./stdout/*")

        if os.path.exists('core_state'):
            with open('core_state', 'r') as file:
                retval = int(file.readline(), 0)

        kcg = self.config.getOption('kcg')
        if kcg != None:
            binary = self.config.getOption('binary')
            if self.pulpCore == 'riscv':
                cmd = "pulp-pc-analyze --input=./%s --binary=%s --riscv --rtl" % (kcg, os.path.basename(binary))
            else:
                cmd = "pulp-pc-analyze --bin-input=./%s --binary=%s" % (kcg, os.path.basename(binary))
            print(cmd)
            if os.system(cmd) != 0: return -1
            print()
            print("KCacheGrind report generated, it can be launched with:")
            print("kcachegrind %s/kcg.txt" % (os.getcwd()))


        return retval
