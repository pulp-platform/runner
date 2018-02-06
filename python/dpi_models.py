# 
# Copyright (C) 2015 ETH Zurich and University of Bologna
# All rights reserved.
#
# This software may be modified and distributed under the terms
# of the BSD license.  See the LICENSE file for details.
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#

def get_devices(system_config, vp=None, clockDomain=None, fabric=None):

    board_config = system_config.get_config('board')
    bindings = board_config.get_config('bindings')
    devices = []
    if bindings is not None:
        for binding_group in bindings():
            if type(binding_group[0]) != list:
                binding_group = [binding_group]

            for binding in binding_group:
                master = binding[0]
                slave = binding[1]
                comp, port = master.split('.')
                if 'self.' in slave:
                    slave_name = slave.split('.')[1]
                    dev_conf = system_config.get_config(slave_name)
                else:
                    slave_name = slave.split('.')[0]
                    dev_conf = system_config.get_config('board/' + slave_name)
                dev_args = []

                if dev_conf is not None:

                    model_options = dev_conf.get('model_options')

                    for key in dev_conf.keys():
                      value = dev_conf.get(key)

                      if model_options is not None and not key in model_options:
                          continue
                      if type(value) == list:
                        for val in value:
                          dev_args.append('%s=%s' % (key, val))
                      else:
                        dev_args.append('%s=%s' % (key, value))


                    if vp is not None:
                      vp.build_devices(
                          slave_name, dev_conf, clockDomain, fabric
                      )

                    dev_name = dev_conf.get('model')
                    if dev_name is None:
                        dev_name = slave_name

                    dev_option = '%s=%s@%s' % (port, dev_name, ','.join(dev_args))

                    if not 'i2c' in port:
                        devices.append(dev_option)

    return devices