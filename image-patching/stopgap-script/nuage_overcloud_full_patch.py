# !/usr/bin/python
# Copyright 2019 NOKIA
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import argparse
import sys
import yaml
import logging
from utils import utils as utils
from utils import nuage_patching_5_0 as nuage_patching_5_0
from utils import nuage_patching_6_0 as nuage_patching_6_0
from utils.constants import *


logger = logging.getLogger(LOG_FILE_NAME)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(formatter)
logger.addHandler(consoleHandler)



def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--nuage-config",
        dest="nuage_config",
        type=str,
        required=True,
        help="path to nuage_patching_config.yaml")
    args = parser.parse_args()

    with open(args.nuage_config) as nuage_config:
        try:
            nuage_config = yaml.load(nuage_config)
        except yaml.YAMLError as exc:
            logger.error(
                'Error parsing file {filename}: {exc}. Please fix and try '
                'again with correct yaml file.'.format(filename=args.nuage_config, exc=exc))
            sys.exit(1)
    if nuage_config.get("logFileName"):
        handler = logging.FileHandler(nuage_config["logFileName"])
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.info("nuage_overcloud_full_patch.py was run with following config options %s " % nuage_config)
    if nuage_config.get("NuageMajorVersion"):
        if nuage_config["NuageMajorVersion"] == "5.0":
            nuage_patching_5_0.main(nuage_config)
        elif nuage_config["NuageMajorVersion"] == "6.0":
            nuage_patching_6_0.main(nuage_config)
        else:
            logger.error(
                "Please provide Correct value of NuageMajorVersion"
                "Allowed values are: '5.0' or '6.0' "
            )

            sys.exit(1)
    else:
        logger.error("Please provide missing config NuageMajorVersion")
        sys.exit(1)



if __name__ == "__main__":
    main()
