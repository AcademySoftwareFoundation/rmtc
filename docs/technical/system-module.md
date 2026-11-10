# System (module) 

System contains the basic shared elements for datatypes and configuration. 

## Factory, Type Names & Resolution 

Every Entity needs to have a Type Name which is exposed to RMTC via a YAML module definition.  

This Type Name follows the format: 

`<module>.<category>.<name>[.<version>]`

This type name has a mapping which connects it to the concrete Python class it will instantiate and acts like a whitelisting technique and way to identify implementations independently of their module import paths.  

Type Names can be deprecated and version-less – in which case the latest version is used. 

Factory takes these type names and resolves them to a concrete class path before importing and instantiating the class. 

## Modules

The factory populates the modules using YAML files that are found by searching the colon-separated paths in the ```RMTC_MODULES``` envvar.

To expose a new model type for example - you require a new module:

```yaml
_type:            module # module YAML type
_version:         1.0.0
_name:            rmtc # module name

Model: # category
  Model: # name
    version:      1.0.0
    display_name: "Tracked Model"
    class_path:   rmtc.track.entities.Model
```

Only classes that are exposed in module definitions are able to be serialised to and from the store.

## Configs 

System defines a config type which allows a client to specify the store, credentials and various systemic behaviours. 

These are contained in a YAML file that is found by searching the colon-separated paths in the ```RMTC_CONFIGS``` envvar. The ```RMTC_CONFIG_NAME``` envvar then selects which config to load - this is matched against the config's internal ```_name``` field, not the filename. This is useful to allow for testing by creating a config in a testing folder added to ```RMTC_CONFIGS```. 

For example to set up a store:

```yaml
_type:          config # required
_version:       1.0.0
_name:          rmtc

rmtc_store:
  type_name:    rmtc_core.Store.AGE-1.0.0
  uri:          postgres://apache-age.studio.com:1234
  name:         rmtc
```

`type_name` is required on any subsystem entry and is resolved to a concrete class via the Factory (see above). Store connection credentials are not part of the config - they are supplied separately via the RMTC_USER/RMTC_PW envvars (or passed to System directly).

You also can define the JIT sync operation, system mode (determines if the system is a test/dev/prod client) and log levels – consider these the RMTC settings. Anything set in this config is visible in the config dict - all of which can be overriden in the Config constructor.

## Complex base types 

System defines the basic property classes that are considered native to RMTC – URI, Datetime & Version – these are derived from associated Python base classes. 

* URI – is a fully qualified resource that has an interrogable param string. 
* Datetime – is the timestamp system that uses ISO UTC 
* Version – semantic versioning system 
* Package – a package and version reference 
* Type – type that works in conjunction with factory to instantiate classes, can define a default or abstract type 

## Logging 

Logging is supported via the Python Logger and the associated Tracker. Log levels can be defined in the YAML config file. Loggers can also broadcast log events. 

## Events & Broadcasting 

A simple broadcaster class in System allows any object to send events of a specific type. The types of messages are generally defined as an Enum. Broadcasters can be enabled and disabled for all messages. 

A listener registers to listen to a specific message by registering a callback. It is good practice to remove your callback on destroy. 

This class can be significantly improved upon and likely re-implemented with a standard lib.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
