# 
# Copyright (C) 2015 ETH Zurich and University of Bologna
# All rights reserved.
#
# This software may be modified and distributed under the terms
# of the BSD license.  See the LICENSE file for details.
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#

def efuse_genStimuli_fromOption(efuses, efuseSize, filename, loadMode, aesKey=None, aesIv=None, xtalCheck=False, xtalCheck_delta=0.1, xtalCheck_min=3, xtalCheck_max=10):

    # In case we boot with the classic rom mode, don't init any efuse, the boot loader will boot with the default mode
    loadModeHex = None
    if loadMode == 'rom': loadModeHex = 0x3A
    elif loadMode == 'spi': loadModeHex = 0x0A
    elif loadMode == 'jtag': loadModeHex = 0x12
    elif loadMode == 'hyper': loadModeHex = 0x2A
    elif loadMode == 'rom_spim': loadModeHex = 0x32
    elif loadMode == 'rom_spim_qpi': loadModeHex = 0x3A
    elif loadMode == 'jtag_dev' or loadMode == 'spi_dev': loadModeHex = None
    
    if xtalCheck:
        if loadModeHex == None: loadModeHex = 0
        loadModeHex |= 1<<7
        delta = int(xtalCheck_delta*((1 << 15)-1))
        efuses.append('26:0x%x' % (delta & 0xff))
        efuses.append('27:0x%x' % ((delta >> 8) & 0xff))
        efuses.append('28:0x%x' % (xtalCheck_min))
        efuses.append('29:0x%x' % (xtalCheck_max))

    if loadModeHex != None:
        if aesKey != None: 
            loadModeHex |= 0x40
            for i in range(0, 16):
                efuses.append('%d:0x%s' % (2+i, aesKey[30-i*2:32-i*2]))
            for i in range(0, 8):
                efuses.append('%d:0x%s' % (18+i, aesIv[14-i*2:16-i*2]))

        efuses.append('0:%s' % str(loadModeHex))


    # Efuse preloading file generation
    if len(efuses) != 0:

        values = [0] * efuseSize
        for efuse in efuses:
            efuseId, value = efuse.split(':')
            efuseId = int(efuseId, 0)
            value = int(value, 0)
            for index in range(0, 8):
                if (value >> index) & 1 == 1: values[efuseId + index*128] = 1

        with open(filename, 'w') as file:
            for value in values:
                file.write('%d ' % (value))

        return filename

    else:

        return None
