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

from plp_platform import *
import plp_rtl_runner
import runner.rtl.default_runner



def get_runner(chip):
    if chip in ['vega', 'pulpissimo', 'gap', 'wolfe']:
        return runner.rtl.default_runner.Runner
    return None


# This class is just a stub class which will return the proper class
# depending on the chip, as recent chips are using new runner while old
# chips are still using the old one.

class Runner(Platform):

    def __new__(cls, config, tree):

        runner = get_runner(tree.get('**/pulp_chip_family').get())
        if runner is None:
            return plp_rtl_runner.Runner(config, tree)
        else:
            return runner(config, tree)
