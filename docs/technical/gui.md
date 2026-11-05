# GUI 

We have 3 main GUIs currently: a provenance tracker, an ingestion system and a training tracker – which are hosted in a central Qt applcation and look like the following: 

![Image of the RMTC GUI](../images/rmtc_gui.png)

The main edit window is a Qt wrapper that extends the NodeGraphQt graphing library to provide methods for ingesting external artifacts and tracing the resulting provenance.

The RMTC-GUI holds instances to several tools mentioned below, however these tools are prototypes at present and likely to be unified into a more holistic solution. There are additional UIs in development for training management – these portions are managed by the python API at present.

The DAG editor is only partially implemented – removing noodles is not fully operational. 

## Shared System 

The GUI sits and listens to the System object updates and reflects the changes that occur. This means all tools share the same backend – searching and fetching entities from the storage system will cause every tool instantiated to reflect the contents of the local System objects model. 

## Properties 

The common property widgets allow the Qt client to create a property editor for viewing Entity Properties – it listens to the sync state of the entities so shows what is available. For any member property it allows you to expand and collapse the properties as required. 

![Image of the RMTC entity property editor](../images/property_gui.png)

## Signal Box 

The Signal Box tool allows you to trace up and down the provenance tree via the IN/OUT properties on the object. A simple .md report can be generated from any selected item. 

This is a pure browser - no connections can be made/broken in this tool. 

![Image of the provenance tracing GUI](../images/signal_box_gui.png)

## Junction 

Junction is the junction between the outside world and RMTC – it allows you to ingest models, datasets & create solutions 

![Image of the junction ingestion tool GUI](../images/junction_gui.png)

## Conductor 

This is an upcoming tool to allow you to trigger training sessions under solutions and is likely to be merged with Train Track. 

![Image of the conductor training kick off GUI](../images/conductor_gui.png)

## Train Track 

Train Track is the third main tab in the RMTC GUI, allowing you to monitor training sessions and publish results. 

It queries the runs in the solution and provides visual feedback to the metric and status. It will additionally tie into the Tracker system (TensorBoard) to allow you view intermediate inferences. 

![Image of the train track reporter GUI](../images/train_track_gui.png)

Train Track will ultimately allow the client to restart and tweak jobs on the render farm. 

This is likely to be merged with Conductor.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
