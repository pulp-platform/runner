# 
# Copyright (c) 2017 GreenWaves Technologies SAS
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of GreenWaves Technologies SAS nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# 
# 
# Authors: Florent Rotenberg, GWT (florent.rotenberg@greenwaves-technologies.com)
#

from plp_platform import *
import plp_flash_stimuli
import time
import sys
import subprocess
import shlex
import io
import platform
import runner.stim_utils
from shutil import copyfile


GWT_NETWORK="greenwaves-technologies.com"
ETH_NETWORK="ee.ethz.ch"
UNIBO_NETWORK="eees.dei.unibo.it"

# This class is the default runner for all chips but can be overloaded
# for specific chips in order to change a bit the behavior.
class Runner(Platform):



    def __init__(self, config, tree):

        super(Runner, self).__init__(config, tree)
        
        parser = config.getParser()

        parser.add_argument("--binary", dest="binary",
                            help='specify the binary to be loaded')
                        
        parser.add_argument("--boot-from-flash", dest="boot_from_flash",
                            action="store_true", help='boot from flash')
                        
        [args, otherArgs] = parser.parse_known_args()

        self.addCommand('run', 'Run execution on RTL simulator')
        self.addCommand('prepare', 'Prepare binary for RTL simulator (SLM files, etc)')


        # Overwrite JSON configuration with specific options
        binary = self.config.getOption('binary')
        if binary is not None:
            tree.get('**/runner').set('binary', binary)

        if self.config.getOption('boot from flash'):
            tree.get('**/runner').set('boot from flash', True)

        self.env = {}
        self.rtl_path = None


    # def power(self):
    #     os.environ['POWER_VCD_FILE'] = os.path.join(os.getcwd(), 'cluster_domain.vcd.gz')
    #     os.environ['POWER_ANALYSIS_PATH'] = os.path.join(os.environ.get('PULP_SRC_PATH'), 'gf22fdx', 'power_analysis')

    #     if os.path.exists('cluster_domain.vcd.gz'):
    #         os.remove('cluster_domain.vcd.gz')

    #     if os.system('gzip cluster_domain.vcd') != 0:
    #         return -1

    #     if os.system(os.path.join(os.environ.get('POWER_ANALYSIS_PATH'), 'start_power_zh.csh')) != 0:
    #         return -1

    #     copyfile('reports_cluster_domain_0.8V/CLUSTER_power_breakdown.csv', 'power_report.csv')

    #     if os.system('power_report_extract --report=power_report.csv --dump --config=rtl_config.json --output=power_synthesis.txt') != 0:
    #         return -1

    #     return 0

    def __check_env(self):
        if self.get_json().get_child_str('**/runner/boot-mode').find('rom') != -1:
            if self.tree.get_child_str('**/vsim/boot-mode') in ['jtag']:
                self.get_json().get('**/runner').set('boot_from_flash', False)
            else:
                self.get_json().get('**/runner').set('boot_from_flash', True)


    def prepare(self):

        self.__check_env()

        if self.tree.get('**/runner/boot_from_flash').get():

            # Boot from flash, we need to generate the flash image
            # containing the application binary.
            # This will generate SLM files used by the RTL platform
            # to preload the flash.
            comps = []
            fs = self.tree.get('**/fs')
            if fs is not None:
                comps_conf = self.get_json().get('**/flash/fs/files')
                if comps_conf is not None:
                    comps = comps_conf.get_dict()

            encrypted = self.get_json().get_child_str('**/efuse/encrypted')
            aes_key = self.get_json().get_child_str('**/efuse/aes_key')
            aes_iv = self.get_json().get_child_str('**/efuse/aes_iv')

            if plp_flash_stimuli.genFlashImage(
                slmStim=self.tree.get('**/runner/flash_slm_file').get(),
                bootBinary=self.get_json().get('**/loader/binaries').get_elem(0).get(),
                comps=comps,
                verbose=self.tree.get('**/runner/verbose').get(),
                archi=self.tree.get('**/pulp_chip_family').get(),
                flashType=self.tree.get('**/runner/flash_type').get(),
                encrypt=encrypted, aesKey=aes_key, aesIv=aes_iv):
                return -1

        else:

            stim = runner.stim_utils.stim(verbose=self.tree.get('**/runner/verbose').get())

            for binary in self.get_json().get('**/loader/binaries').get_dict():
                stim.add_binary(binary)

            stim.gen_stim_slm_64('vectors/stim.txt')


        if self.get_json().get('**/efuse') is not None:
            efuse = runner.stim_utils.Efuse(self.get_json(), verbose=self.tree.get('**/runner/verbose').get())
            efuse.gen_stim_txt('efuse_preload.data')

        return 0


    def __check_debug_bridge(self):

        gdb = self.get_json().get('**/gdb/active')
        autorun = self.tree.get('**/debug_bridge/autorun')

        bridge_active = False

        if gdb is not None and gdb.get_bool() or autorun is not None and autorun.get_bool():
            bridge_active = True
            self.get_json().get('**/jtag_proxy').set('active', True)
            self.get_json().get('**/runner').set('use_tb_comps', True)
            self.get_json().get('**/runner').set('use_external_tb', True)


        if bridge_active:
            # Increase the access timeout to not get errors as the RTL platform
            # is really slow
            self.tree.get('**/debug_bridge/cable').set('access_timeout_us', 10000000)



    def run(self):

        self.__check_env()

        if self.get_json().get('**/runner/peripherals') is not None:
            self.get_json().get('**/runner').set('use_tb_comps', True)

        self.__check_debug_bridge()

        with open('rtl_config.json', 'w') as file:
            file.write(self.get_json().dump_to_string())

        cmd = self.__get_sim_cmd()

        autorun = self.tree.get('**/debug_bridge/autorun')
        if autorun is not None and autorun.get():
            print ('Setting XCSIM env')
            print (self.env)
            os.environ.update(self.env)

            print ('Launching XCSIM with command:')
            print (cmd)
            vsim = subprocess.Popen(shlex.split(cmd),stderr=subprocess.PIPE, bufsize=1)
            port = None
            for line in io.TextIOWrapper(vsim.stderr, encoding="utf-8"):
                sys.stderr.write(line)
                string = 'Proxy listening on port '
                pos = line.find(string)
                if pos != -1:
                    port = line[pos + len(string):]
                    break

            if port is None:
                return -1

            options = self.tree.get_child_str('**/debug_bridge/options')
            if options is None:
                options  = ''

            bridge_cmd = 'plpbridge --config=rtl_config.json --verbose=10 --port=%s %s' % (port, options)
            print ('Launching bridge with command:')
            print (bridge_cmd)
            time.sleep(10)
            bridge = subprocess.Popen(shlex.split(bridge_cmd))
            
            retval = bridge.wait()
            vsim.terminate()

            return retval

        else:
            for key, value in self.env.items():
                cmd = 'export %s="%s" && ' % (key, value) + cmd

            print ('Launching XCSIM with command:')
            print (cmd)

            if os.system(cmd) != 0: 
                print ('XCSIM reported an error, leaving')
                return -1

        

        return 0


    def __create_symlink(self, rtl_path, name):
        if os.path.islink(name):
          os.remove(name)

        os.symlink(os.path.join(rtl_path, name), name)


    def __get_rtl_path(self):

        if self.rtl_path is None:

            vsim_chip = self.tree.get_child_str('**/runner/vsim_chip')
            if vsim_chip is None:
                vsim_chip = self.tree.get('**/pulp_chip_family').get()

            chip_path_name = 'PULP_RTL_%s' % vsim_chip.upper()
            chip_path = os.environ.get(chip_path_name)
            vsim_path = os.environ.get('XCSIM_PATH')

            if vsim_path is not None:
                path_name = chip_path_name
                self.rtl_path = vsim_path
            elif chip_path is not None:
                path_name = 'XCSIM_PATH'
                self.rtl_path = chip_path
            else:
                raise Exception("WARNING: no RTL install specified, neither %s nor XCSIM_PATH is defined:" % (chip_path_name))


            if not os.path.exists(self.rtl_path):
                raise Exception("ERROR: %s=%s path does not exist" % (path_name, self.rtl_path))

            os.environ['XCSIM_PATH'] = self.rtl_path
            os.environ['PULP_PATH'] = self.rtl_path
            os.environ['TB_PATH']   = self.rtl_path


            self.__create_symlink(self.rtl_path, 'boot')
            self.__create_symlink(self.rtl_path, 'cds.lib')
            self.__create_symlink(self.rtl_path, 'hdl.var')
            self.__create_symlink(self.rtl_path, 'tcl_files')
            self.__create_symlink(self.rtl_path, 'waves')
            self.__create_symlink(self.rtl_path, 'xcsim_libs')
            self.__create_symlink(self.rtl_path, 'min_access.txt')
            self.__create_symlink(self.rtl_path, 'models')

        return self.rtl_path


    def set_env(self, key, value):
        self.env[key] = value

    def __get_sim_cmd(self):


        simulator = self.tree.get_child_str('**/runner/simulator')
        if simulator == 'xcelium':
            # vsim_script = self.tree.get_child_str('**/vsim/script')
            # tcl_args = self.tree.get('**/vsim/tcl_args').get_dict()
            # xmsim_args = self.tree.get('**/vsim/args').get_dict()
            xmelab_args = self.tree.get('**/vsim/tcl_args').get_dict()
            xmsim_args = self.tree.get('**/vsim/args').get_dict()
            gui = self.tree.get_child_str('**/vsim/gui')

            # recordwlf = self.tree.get_child_str('**/vsim/recordwlf')
            # vsimdofile = self.tree.get_child_str('**/vsim/dofile')
            # enablecov = self.tree.get_child_str('**/vsim/enablecov')
            # vopt_args = self.tree.get_child_str('**/vsim/vopt_args')

            if not self.tree.get('**/runner/boot_from_flash').get():
                xmelab_args.append('-defparam tb.tb_test_i.LOAD_L2=JTAG')

            autorun = self.tree.get('**/debug_bridge/autorun')
            if self.tree.get('**/runner/use_external_tb').get() or \
              autorun is not None and autorun.get():
                xmelab_args.append('-defparam tb.tb_test_i.ENABLE_EXTERNAL_DRIVER=1')

            if self.tree.get('**/runner/boot_from_flash').get():
              if self.tree.get('**/runner/flash_type').get() == 'spi':
                xmelab_args.append('-defparam tb.tb_test_i.SPI_FLASH_LOAD_MEM=1')
              elif self.tree.get('**/runner/flash_type').get() == 'hyper':
                xmelab_args.append('-defparam tb.tb_test_i.HYPER_FLASH_LOAD_MEM=1')
                if self.tree.get_child_str('**/chip/name') == 'vega':
                    xmelab_args.append('-defparam tb.tb_test_i.LOAD_L2=HYPER_DEV')
                    xmsim_args.append('+VSIM_BOOTTYPE_CFG=TB_BOOT_FROM_HYPER_FLASH')

            if self.tree.get('**/use_tb_comps').get():
                xmelab_args.append('-defparam CONFIG_FILE=rtl_config.json')

            if self.tree.get('**/efuse') is not None:
                xmsim_args.append('+preload_file=efuse_preload.data') #+debug=1  Add that to get debug messages from efuse

            # if gui:
            #     self.set_env('VOPT_ACC_ENA', 'YES')

            # if recordwlf:
            #     self.set_env('RECORD_WLF', 'YES')
            
            # if vsimdofile:
            #     self.set_env('RECORD_WLF', 'YES')
            #     tcl_args.append('-do %s/waves/%s' % (self.__get_rtl_path(), vsimdofile))

            # if enablecov:
            #     self.set_env('VSIM_COV', 'YES')                
            
            xmelab_args.append('-64bit \
                               -licqueue \
                               -timescale 1ns/1ps \
                               -mccodegen \
                               -perfstat \
                               -update \
                               -nxmbind \
                               -nowarn STRINT:CUDEFB \
                               -disable_sem2009 \
                               -gateloopwarn \
                               -show_forces \
                               -dpiheader %s/../tb/tb_driver/dpiheader.h' % (self.__get_rtl_path()))

                               # -always_trigger \
                               # -default_delay_mode distributed \
                               # -no_tchk_msg \
                               # -noassert \


            xmsim_args.append('-64bit \
                               -licqueue \
                               -update \
                               -perfstat \
                               -messages \
                               -xceligen on \
                               -assert_logging_error_off \
                               +GAP_PATH=%s/../../' % (self.__get_rtl_path()))
            xmsim_args.append('-sv_lib %s/install/ws/lib/libpulpdpi' % (os.environ.get('PULP_SDK_HOME')))
           
            if gui:
                xmelab_args.append('-access +rwc +fsmdebug \
                                    -createdebugdb')
                xmsim_args.append('-gui')
            else:
                xmelab_args.append('-afile min_access.txt')
                xmsim_args.append('-input %s/tcl_files/%s' % (self.__get_rtl_path(), "run_and_exit.tcl"))

            if platform.node()[-len(ETH_NETWORK):] == ETH_NETWORK or platform.node()[-len(UNIBO_NETWORK):] == UNIBO_NETWORK:
                cds_xmelab = 'cds_ius-18.09.005 xmelab'
                cds_xmsim = 'cds_ius-18.09.005 xmsim'
            else:
                cds_xmelab = 'xmelab'
                cds_xmsim = 'xmsim'

            xmelab_cmd = "%s tb_lib.tb %s" % (cds_xmelab, ' '.join(xmelab_args))
            xmsim_cmd = "%s tb %s" % (cds_xmsim, ' '.join(xmsim_args))
            cmd = "%s; %s" % (xmelab_cmd, xmsim_cmd)
            return cmd

        else:
            raise Exception('Unknown RTL simulator: ' + simulator)
