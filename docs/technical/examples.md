# Examples 

To provide some guidance about how to use RMTC – there are a set of examples in the repo: 

* Basics - covers simple delete and add operations 
* Image2Mask – provides the skeleton for training an image-to-mask model (requires a pre-packaged image to image PyTorch package model and an EXR image dataset) 
* MNIST – a full example for categorising the public MNIST image dataset (requires download of the MNIST dataset) 
* Tracking – lower-level DB operations directly on the store 
* Pipeline – example of fictious asset manager build and publish 

## Example Usage 

The general style in the examples follows a vertical delimited format. 
```python
rmtc_sys            = System()

oss_license         = rmtc_sys.create_license(community_licenses.OSS,
    name            = "Apache-2.0", 
    uri             = URI("https://apache.org/licenses/LICENSE-2.0.html"),
    parties         = ["Mozilla Foundation"],
)

model               = rmtc_sys.create_model(entities.Model,
    name            = "Foundation Model",
    uri             = URI("https://github.com/foundation_model"),
    author          = "Big Tech",
    licenses        = [oss_license],
)  

dataset             = rmtc_sys.create_dataset(entities.Dataset,
    name            = "Test Data",
    uri             = URI("file://localhost/testdata"),
    licenses        = [oss_license],
)  

solution            = rmtc_sys.create_solution(
    name            = "Test Solution",
    uri             = URI("/proj/rmtc/solutions/test"),
    input_types     = [assets.Image],
    output_types    = [assets.Image],
    description     = "Example Solution",
)
solution            .add_models([model])
solution            .add_datasets([dataset])

run                 = rmtc_sys.create_run(
    solution        = solution,
    name            = "Test Run 1",
)

rmtc_sys            .push()
```

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
