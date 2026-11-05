# Modules 

The following section provides notes on each of modules in the lib folder. 

The general pattern of usage is to create an instance of a System object – which takes in instances of various subsystems. System holds a local representation of objects in RMTC, and you use this instance to create or pull tracked artifacts, kick off training or inference then push the System instance to the remote store. 

For example, to create a simple model wrapper: 
```python
rmtc_sys = rmtc.System() 
rmtc_sys.create_model(entities.Model, name='Test Model')
rmtc_sys.push() 
```
For convenience, an RMTC Core System object instantiates common subsystems for you. 

## System (class) 

System is considered the ‘main’ for RMTC and holds the primary methods for interacting with the framework. System allows you to specify the following: 

* Store – the abstracted storage system that is pushed and pulled from 
* Config – a dict that is derived from a YAML file to define global settings 
* Objects – the local list of database entities 
* Log – the log abstraction 
* Tracker – the general tracking system for training 
* Asset manager – way to resolve asset manager URIs to concrete filesystem URIs as well as how to run the build and publish pipeline 
* Environment manager – how to resolve artifact environments for instantiating any external dependencies (not currently implemented) 
* Broadcaster – the internal event notification system 
* Factory – the system to resolve a type name to an actual class 

Core defines defaults for the above and each can be passed in during instantiation of the System class.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
