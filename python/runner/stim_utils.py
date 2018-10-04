#
# Copyright (C) 2018 ETH Zurich, University of Bologna and GreenWaves Technologies
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# 
# Authors: Germain Haugou, ETH (germain.haugou@iis.ee.ethz.ch)
#

from elftools.elf.elffile import ELFFile
import os
import os.path
import struct



class stim(object):


  def __init__(self, verbose=False):
    self.binaries = []
    self.mem = {}
    self.verbose = verbose
    self.areas = []

    self.dump('Created stimuli generator')

  def dump(self, str):
    if self.verbose:
      print (str)

  def add_binary(self, binary):
    self.dump('  Added binary: %s' % binary)
    self.binaries.append(binary)

  def add_area(self, start, size):
    self.dump('  Added target area: [0x%x -> 0x%x]' % (start, start + size))
    self.areas.append([start, start+size])


  def __add_mem_word(self, base, size, data, width):

    aligned_base = base & ~(width - 1)

    shift = base - aligned_base
    iter_size = width - shift
    if iter_size > size:
      iter_size = size

    value = self.mem.get(str(aligned_base))
    if value is None:
      value = 0

    value &= ~(((1<<width) - 1) << (shift*8))
    value |= int.from_bytes(data[0:iter_size], byteorder='little') << (shift*8)

    self.mem[str(aligned_base)] = value

    return iter_size





  def __add_mem(self, base, size, data, width):

    while size > 0:

      iter_size = self.__add_mem_word(base, size, data, width)

      size -= iter_size
      base += iter_size
      data = data[iter_size:]


  def __gen_stim_slm(self, filename, width):

    self.dump('  Generating to file: ' + filename)

    try:
      os.makedirs(os.path.dirname(filename))
    except:
      pass

    with open(filename, 'w') as file:
      for key in sorted(self.mem.keys()):
        file.write('%X_%0*X\n' % (int(key), width*2, self.mem.get(key)))

  def __parse_binaries(self, width):

    self.mem = {}

    for binary in self.binaries:

        with open(binary, 'rb') as file:
            elffile = ELFFile(file)

            for segment in elffile.iter_segments():

                if segment['p_type'] == 'PT_LOAD':

                    data = segment.data()
                    addr = segment['p_paddr']
                    size = len(data)

                    load = True
                    if len(self.areas) != 0:
                      load = False
                      for area in self.areas:
                        if addr >= area[0] and addr + size <= area[1]:
                          load = True
                          break

                    if load:

                      self.dump('  Handling section (base: 0x%x, size: 0x%x)' % (addr, size))

                      self.__add_mem(addr, size, data, width)

                      if segment['p_filesz'] < segment['p_memsz']:
                          addr = segment['p_paddr'] + segment['p_filesz']
                          size = segment['p_memsz'] - segment['p_filesz']
                          self.dump('  Init section to 0 (base: 0x%x, size: 0x%x)' % (addr, size))
                          self.__add_mem(addr, size, [0] * size, width)

                    else:

                      self.dump('  Bypassing section (base: 0x%x, size: 0x%x)' % (addr, size))




  def gen_stim_slm_64(self, stim_file):

    self.__parse_binaries(8)

    self.__gen_stim_slm(stim_file, 8)


  def gen_stim_bin(self, stim_file):

    self.__parse_binaries(1)

    try:
      os.makedirs(os.path.dirname(stim_file))
    except:
      pass

    with open(stim_file, 'wb') as file:
      prev_addr = None
      for key in sorted(self.mem.keys()):
        addr = int(key)
        if prev_addr is not None:
          while prev_addr != addr - 1:
            file.write(struct.pack('B', 0))
            prev_addr += 1

        prev_addr = addr
        file.write(struct.pack('B', int(self.mem.get(key))))



class Efuse(object):

  def __init__(self, config, verbose=False):
    self.config = config
    self.verbose = verbose

    self.dump('Created efuse stimuli generator')


  def dump(self, str):
    if self.verbose:
      print (str)

  def gen_stim_txt(self, filename):

    efuses = self.config.get('**/efuse/values')
    if efuses is None:
      efuses = []

    nb_regs = self.config.get_child_int('**/efuse/nb_regs')

    pulp_chip = self.config.get_child_str('**/chip/name')

    if pulp_chip == 'gap':

      load_mode = self.config.get_child_str('**/runner/boot-mode')
      aes_key = self.config.get_child_str('**/efuse/aes_key')
      aes_iv = self.config.get_child_str('**/efuse/aes_iv')
      xtal_check = self.config.get_child_bool('**/efuse/xtal_check')
      xtal_check_delta = self.config.get_child_bool('**/efuse/xtal_check_delta')
      xtal_check_min = self.config.get_child_bool('**/efuse/xtal_check_min')
      xtal_check_max = self.config.get_child_bool('**/efuse/xtal_check_max')


      # In case we boot with the classic rom mode, don't init any efuse, the boot loader will boot with the default mode
      load_mode_hex = None
      if load_mode == 'rom':
        load_mode_hex = 0x3A
      elif load_mode == 'spi':
        load_mode_hex = 0x0A
      elif load_mode == 'jtag':
        load_mode_hex = 0x12
      elif load_mode == 'rom_hyper':
        load_mode_hex = 0x2A
      elif load_mode == 'rom_spim':
        load_mode_hex = 0x32
      elif load_mode == 'rom_spim_qpi':
        load_mode_hex = 0x3A
      elif load_mode == 'jtag_dev' or load_mode == 'spi_dev':
        load_mode_hex = None
      
      if xtal_check:
          if load_mode_hex == None: load_mode_hex = 0
          load_mode_hex |= 1<<7
          delta = int(xtal_check_delta*((1 << 15)-1))
          efuses.append('26:0x%x' % (delta & 0xff))
          efuses.append('27:0x%x' % ((delta >> 8) & 0xff))
          efuses.append('28:0x%x' % (xtal_check_min))
          efuses.append('29:0x%x' % (xtal_check_max))

      if load_mode_hex != None:
          if aes_key != None: 
              load_mode_hex |= 0x40
              for i in range(0, 16):
                  efuses.append('%d:0x%s' % (2+i, aes_key[30-i*2:32-i*2]))
              for i in range(0, 8):
                  efuses.append('%d:0x%s' % (18+i, aes_iv[14-i*2:16-i*2]))

          efuses.append('0:%s' % str(load_mode_hex))
    

    # Efuse preloading file generation
    if len(efuses) != 0:

        values = [0] * nb_regs * 8
        for efuse in efuses:
            efuseId, value = efuse.split(':')
            self.dump('  Writing register (index: %d, value: 0x%x)' % (int(efuseId), int(value)))
            efuseId = int(efuseId, 0)
            value = int(value, 0)
            for index in range(0, 8):
                if (value >> index) & 1 == 1: values[efuseId + index*128] = 1

        self.dump('  Generating to file: ' + filename)

        with open(filename, 'w') as file:
            for value in values:
                file.write('%d ' % (value))
