#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc import System
from rmtc.system import URI
from rmtc.system import Config

from rmtc.core.track.filters.license import RightsFilter

import argparse
parser              = argparse.ArgumentParser(
    description     = "RMTC Rights Example."
)
args                = parser.parse_args()


###############################################################################

rmtc_sys            = System(
    config          = Config(name="demo"),   
)

# Usage rights
faceswap            = rmtc_sys.create_rights("Face Swap")
upscale             = rmtc_sys.create_rights("Upscale")
deage               = rmtc_sys.create_rights("De Age")

# Standard OSS rights
commercial          = rmtc_sys.create_rights("Commercial")
warranty            = rmtc_sys.create_rights("Warranty")
attribution         = rmtc_sys.create_rights("Attribution")

# Production related composite rights
test_show           = rmtc_sys.create_rights("TST") #show specific right
big_studio          = rmtc_sys.create_rights("Studio") #studio specific right

# create some licenses
academic_license    = rmtc_sys.create_license(
    name            = "Academic Non-Commercial License", 
    excludes        = [commercial],
)
faces_license       = rmtc_sys.create_license(
    name            = "Commercial Face Dataset License", 
    grants          = [faceswap],
    excludes        = [upscale, deage],
)
apache_license      = rmtc_sys.create_license(
    name            = "Apache-2.0", 
    requires        = [attribution],
    excludes        = [warranty],
)
test_show_license   = rmtc_sys.create_license(
    name            = "Test Show", 
    requires        = [test_show, big_studio],
)

# create some datasets
free_faces          = rmtc_sys.create_dataset(
    name            = "Free Faces Dataset",
    licenses        = [faces_license, academic_license],
)  
show_faces          = rmtc_sys.create_dataset(
    name            = "Show Faces Dataset",
    licenses        = [faces_license, test_show_license],
)  
commercial_faces    = rmtc_sys.create_dataset(
    name            = "Commercial Faces Dataset",
    licenses        = [faces_license],
)  
Images              = rmtc_sys.create_dataset(
    name            = "Generic Image Dataset",
    licenses        = [apache_license],
)  

# now create a new solution for face swapping that requires 
# the faceswap right
fs_solution         = rmtc_sys.create_solution(
    name            = "FaceSwap Solution",
    filters         = [
        RightsFilter(rights=[commercial, faceswap]),
    ]    
)
print("FaceSwap Solution")
print(f"Commercial faces: {fs_solution.is_compliant([commercial_faces])}")
print(f"Free faces: {fs_solution.is_compliant([free_faces])}")
print(f"Show faces: {fs_solution.is_compliant([show_faces])}")

fss_solution        = rmtc_sys.create_solution(
    name            = "FaceSwap Show Solution",
    filters         = [
        RightsFilter(rights=[test_show, commercial, faceswap, big_studio]),
    ], 
)
print("FaceSwap Show Solution")
print(f"Commercial faces: {fss_solution.is_compliant([commercial_faces])}")
print(f"Free faces: {fss_solution.is_compliant([free_faces])}")
print(f"Show faces: {fss_solution.is_compliant([show_faces])}")

# upscale should work also
us_solution         = rmtc_sys.create_solution(
    name            = "UpScale Solution",
    filters         = [
        RightsFilter(rights=[commercial, upscale, attribution]),
    ],
)
print("UpScale Solution")
print(f"Images: {us_solution.is_compliant([Images])}")



