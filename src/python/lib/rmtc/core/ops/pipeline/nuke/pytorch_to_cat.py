# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import argparse
import os
import nuke

# parse args
parser = argparse.ArgumentParser(description="Publish RMTC Publish Example.")
parser.add_argument(
    "--cat_path",
    help="Output Cat Path",
    required=True,
)
parser.add_argument(
    "--torchscript",
    help="TorchScript Path",
    required=True,
)
parser.add_argument(
    "--channels_in",
    help="Channels In",
    required=True,
)
parser.add_argument(
    "--channels_out",
    help="Channels Out",
    required=True,
)
parser.add_argument(
    "--model_id",
    help="Model ID",
    required=True,
)
args = parser.parse_args()

# delete file so we don't prompt to overwrite
if os.path.exists(args.cat_path):
    os.remove(args.cat_path)

# create node
cat_creator = nuke.createNode("CatFileCreator")
cat_creator["torchScriptFile"].setValue(args.torchscript)
cat_creator["catFile"].setValue(args.cat_path)
cat_creator["channelsIn"].setValue(args.channels_in)
cat_creator["channelsOut"].setValue(args.channels_out)
cat_creator["modelId"].setValue(args.model_id)
cat_creator["createCatFile"].execute()

# clear so we don't prompt to save and then close
nuke.scriptClear()
nuke.scriptExit()
