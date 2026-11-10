# Objects 

Object module manages classes related to the base object property system which is shared amongst almost all RMTC items. 

## Object vs Entity vs Artifact 

There is a general 3 tier object hierarchy in RMTC. 

Objects own properties and can broadcast updates and changes, they each have a name and a unique UUID4 ID. 

Entities derive from Objects are replicated in the store and can be fetched, synced, updated, created and destroyed. These represent more abstract trackable ancillary items such as processors, IO and such. 

Artifacts are the high-level Entities that represent a resource with a URI, hold a License and can be read/written to and from the URI using an IO object. These are your core trackable items in RMTC – models, datasets, assets etc. 

## Object Properties 

Objects have an internal property system which allows you to define a property of the following types: 

* Bool 
* Number - floating point number
* Integer 
* String 
* Datetime – standard ISO UTC time zone string 
* Object – a reference to another RMTC object 
* URI – a fully qualified resource 
* Version – semantic version stored as a string 
* Type – a meta type name that works with Factory to resolve to a concrete type 
* Package – a versioned package name used for environments 
* Enum – a fixed list of values from a Python Enum 
* Dict – a JSON dictionary string 

Properties are currently defined on an object instance basis – via add property: 

```python
obj.add_property(“test”, int, 123) 
```

Altering a property is done via the actual name as if it was a standard Python e.g. a property of type: 

```python
obj.test = 456 
```

In addition, properties can be marked with a direction, deprecated status, required status and membership – detailed later. 

## Arrayed Properties 

The property type is defined as a python class type and supports arrays: 

```python
obj.add_property(“test”, [int], [123]) 
```

Properties can be interpreted as a value or array – a value accessed like an array will only operate on the first element, removal and append do nothing. There are specific accessor classes to manage array append and remove which correctly manage and notify any changes – avoid add or remove to array properties directly – this may be changed to tuples in the future to prevent this. 

## Property Types & Conversion 

Properties are strongly type – they cannot change type by assigning to a different value – they will attempt to run a conversion via the “_convert” method. If a conversion is not possible it will assign the property default. 

The _convert method is often a source of bugs – when something isn’t quite operating as expected it is likely due to a subtle type change occurring in the _convert. 

## Volatile Members vs Properties 

Properties are considered persistent – they are pushed up to the store. For temporary volatile data, objects should use standard python members – which require a "_” prefix so they are distinguished internally from properties. 

Artifacts need to store their concrete data as volatile Python data which is loaded, used and unloaded during training for memory purposes. For example, a PyTorch model or Image Tensor. 

RMTC uses a basic duplication system to copy property data rather than deep copy as may PyTorch classes cannot be easily copied in such a way. The properties are copied and the volatile data is reconstructed on read. 

## Members & The ‘DOM’ 

Any property can be marked as a member – by default they are.   

A member means that the property is considered inalienable and part of the object and determines the ownership of entities in the local system object structure. A member will appear in the property editor window directly; it will be pulled with the entity from the store. The Objects instance stores references to all Entities in the system. 

The system owns an Objects instance which is considered our ‘DOM’. It is a loose object model since we want to be able to store artifacts in multiple ways with many kinds of ownership – a model zoo, a structure solution with models etc. In general key entities like models and datasets exist in the store objects instance as a root object – it owns the child members and so on.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
