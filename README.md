# The Rongotai Model Train Club
RMTC is a VFX industry focussed system to track AI artifacts through ingestion, training & inference.

The primary purposes of RMTC is to to provide visibility of where our models and datasets come from when using AI in production pipelines. A secondary goal being to simplify the creation and use of AI models for TDs and artists.

RMTC can be used to ingest foundational models, refine them for specific show needs, publish them to a standard format, invoke them from DCCs and then track the resulting inferred assets back to the models, datasets and associated license information.

RMTC is itself a set of abstractions and minimal shared implementation, however the package provides a core implementation to support PyTorch, AGE and other subsystems. These are only an example - it is straightfoward to create Keras, OpenCue or other abstractions for most parts of the framework. The system has been designed for delegation and abstraction as well as for pick 'n mix applications, for example; if you simply want to instrument your own training pipeline with provenance information, you can with the tracking layer alone. This allows facilities to tailor it to their specific needs. 

Below is an example in the explorer showing the provenance of a fictional DeAge inference, tracing back up the weights, run and input models & datasets.

![RMTC Explorer](docs/images/rmtc_explorer.gif)

## The Name
Rongotai is a Te Reo Maori term meaning 'sound of the sea' but is also the name of a Wellington suburb in New Zealand. Weta FX maintains facilities in Rongotai near to where RMTC first came to be. It's a club, since the project was setup with collaboration in mind. No, it's not about model trains, but one of the core features of the framework is about training models.

## License
RMTC is licensed under [Apache-2.0](LICENSE)

RMTC dependencies are licensed under MIT, Modified BSD, BSD-3-Clause, BSD-2-Clause, PSF-2.0 and LGPL-3.0 licenses.

RMTC uses Qt & PySide which fall under a LGPL-v3.0 license with obligations: https://www.qt.io/licensing/open-source-lgpl-obligations.
To obtain PySide, clone https://github.com/pyside to obtain Qt: https://doc.qt.io/qt-6/get-and-install-qt.html

For more detail, see: [Thirdparty Software](THIRD_PARTY.md) & [LGPL-3.0]


## Target Audience
RMTC targets mid to large facilities that use CGI related assets in AI pipelines: VFX houses, videogame studios or synthetic data production. RMTC assumes it will be used in tandem with scaled infrastructure for staorage and compute.

## Project Status
It is possible to use the system for tracking, training and inference of Torch models, however expect significant changes as this is still under active development.

This project is in ASWF Sandbox prototyping stage and has yet to be tested through production. We are maintaining a dev branch and looking to migrate once a production test has been completed.

## Installation
RMTC targets facility level institutions with their own asset, package and renderwall infrastructures. We understand that you might have a complex package management setup and as a result - we defer the dependencies installation to the institution. 

The default RMTC Core System by default requires a Tensorboard service and an Apache AGE instance to operate - you'll need the url, port, credentials and name - these go into the config file discussed later.

For example to kick off AGE under docker it might look like the following:
```bash
docker run -it --rm \ 
    --name age  \ 
    -p 5432:5432 \ 
    -e POSTGRES_USER=postgres \ 
    -e POSTGRES_PASSWORD=postgres \ 
    -e POSTGRES_DB=postgresDB \ 
    apache/age 
```

To install, we have a very simple cmake arrangement, with a root CMakeLists.txt that defers to a cmake subfolder with it's own CMakeLists.txt. The root CMakeLists.txt file exists for convienience & expectations, but the intent is that we separate src & build information - since facilities may use entirely custom build setups we avoid interleaving a specific build paradigm.

Assuming you are in your development folder, you can run the following to get going:

```bash
git clone https://github.com/AcademySoftwareFoundation/rmtc.git
cd rmtc
cmake -DCMAKE_INSTALL_PREFIX=$HOME/.local -B cmake/build -S .
cd cmake/build
make install
source ./rmtc-setup.bash
```

_Note_: You can replace `$HOME/.local` in the cmake command above with your installation directory of choice.

This will clone the repo into your code folder, create build info in cmake/build, then make and install into a given path. The final shell script source sets up the envvars required to execute. 

However, before running, you will need to create a config file for your age installation derived from the [template](/res/config/rmtc_config.yaml), the RMTC_CONFIG environment variable points RMTC to the config path, which you can override as follows:

```bash
setenv RMTC_CONFIG=<config path>/<config_name>.yaml
```

To test simply call `rmtc-gui` which should bring up the ingestion, train, track & trace UI. This will be empty at first.

You can also run `pytest` from the root of the project to run the unit tests.

## Dependencies
See [pyproject](pyproject.toml) for a list of dependencies in machine readible format - these are not configured, found or installed as part of the build currently.

## Configuration
You will need an AGE instance running and alter the credentials in the CONFIG file. An important property is the name - which corresponds to the AGE graph name - you can have multiple names, we use `rmtc` for the 'prod' graph, `rmtc_test` for volatile test data and `rmtc_examples` for demo and example data. Tools can override the config via CLI arguments.

The below is the minimum config required for a AGE/Tensorboard setup:

```yaml
rmtc_store:
  type:         age
  name:         rmtc            #the graph name
  username:     <username>
  password:     <password>
  uri:          postgres:<uri>  #the age instance URI
  
rmtc_tracker:
  uri:          <tensorboard run path>
```

Any items added in here are accessible in Python via the internal Config class dict.

## Usage
To get going you can run the MNIST training example which will download the MNIST dataset, convert to EXRs and CSV data, run local training, then run an inference, all the while creating the database tracked objects. Once trained you can invoke the explorer and click through the provenance tree.

* python <repo>/examples/example_train_mnist.py
* rmtc-signalbox --store_name="rmtc_examples"

## Code Structure

The rmtc module provides abstractions and system objects, with rmtc_core providing the basic implementation. There is some functionality within rmtc, but without core it doesn't do a lot. We generally follow PEP8 style, with a lean towards verbosity for the sake of comprehension to an engineer less familiar with Python. We use abstract interfaces and injection with strong typing in the property system - but stopping short of true python type checking. Methods take arrays where possible - to provide allowance for batch optimisations later.

Regarding package names - we use the following structure:
`rmtc_<module>.<component>[.<technology>].<class>`
* module - the root module - core, weta, facilty, should be prefixed with `rmtc` as the type factory requires rmtc prefixes as a form of light whitelisting
* component - the main rmtc component seen in the root package - artifacts, system, io
* technology - the system or tech to satisfy the component, we skip 'python' as a tech type - oiio, aws, torch
* class - the kind of class to override - model, dataset

For example:
* `rmtc_core.artifacts.torch.datasets`
* `rmtc_core.io.oiio.image`
* `rmtc_core.system.log` - note that as Python implements the log, we omit python as it's an assumed technology

For further information see the [technical notes](docs/technical_notes.md) documentation.

## Support
As this is a Linux Foundation / ASWF project we benefit from the ASWF infrastructure. Please reach out on slack to talk through issues you might face.
* [Issues](https://github.com/AcademySoftwareFoundation/rmtc/issues)
* [Slack](https://academysoftwarefdn.slack.com/archives/C09FP5KUUP4)
* [Wiki](https://lf-aswf.atlassian.net/wiki)

## Roadmap
It is currently possible to track models & datasets through training to inferences and back. We are focussing on graduating the system to production, so our next set of features is about scaling.
* Production example
* Concurrent wall training to scale model production
* DCC plugin wrapper - specifically nuke
* Neo4j storage wrapper

## Contributing
Details for contributing can be found [here](CONTRIBUTING.md).

## Initial contributors and acknowledgments
* John McCarten
* Eric Hayes
* Stephen Revel
* Andy Wright
* Kimball Thurston
* Masahiro Teraoka
* Niall Lenihan
* John Mertic

## Dependencies

| Name | Version |
|------|---------|
| Python | 3.9.18 |
| Python Standard Library | 3.9.18 |
| Packaging | 25.0 |
| Yaml | 6.0.1 |
| Numpy | 1.23.0 |
| OpenImageIO | 2.2.16.0 |
| Flask | 3.1.0 |
| Requests | 2.28.0 |
| PyTorch | 2.1.0 |
| OpenCV | 4.8.0 | Apache-2.0 |
| TorchVision | 0.16.0 |
| Tensorboard | 2.19.0 |
| ONNX | 1.16.0 |
| ONNX Runtime | 1.19.2 |
| ONNX Script | 0.2.0 |
| Neo4j Driver | 4.4.10 |
| Apache AGE Driver | 0.0.7 |
| NodeGraphQt | 0.6.38 |
| PySide | 2.5.15.2 |
| Qt | 2.5.15.2 |

See: [Thirdparty Software](THIRD_PARTY.md)

---
<center>SPDX-License-Identifier: Apache-2.0 | Copyright Contributors to the RMTC Project</center>