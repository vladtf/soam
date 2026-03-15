# TODO - List

Below is a list of tasks that need to be completed for the project. This list will be updated as new tasks are identified and completed tasks are checked off.

## 1. Requirements and Specifications

- **Functional Requirements:**
  - **Data Ingestion:** Define how the platform will ingest data from various heterogeneous sources.
  - **Data Aggregation:** Specify the operations needed to combine data streams, including real-time processing.
  - **Self-Onboarding:** Design mechanisms for new data providers to register and map their data without extensive manual configuration.
  - **Data Visualization:** Outline user-facing components such as dashboards and interactive charts for decision support.
  
- **Non-Functional Requirements:**
  - **Scalability:** Ensure the Big Data engine and middleware can handle high volumes, velocity, and variety.
  - **Performance:** Set expectations for real-time data processing and low-latency responses.
  - **Maintainability:** Consider modular design, documentation standards, and support for future updates.
  - **Usability:** Define user experience goals for both data providers and end users.

- **Security & Data Privacy:**
  - **Authentication & Authorization:** Decide on protocols (e.g., OAuth, JWT) for ensuring that only authorized users can access or modify data.
  - **Data Encryption:** Specify mechanisms for data-in-transit and data-at-rest encryption.
  - **Anonymization and Privacy:** Plan for handling sensitive data (especially in public smart city data) using anonymization techniques.

---

## 2. Architecture and System Design

- **System Architecture:**
  - **Microservices:** Plan a microservices-based architecture to enable modularity, independent scaling, and fault tolerance.
  - **Big Data Engine Integration:** Define how the middleware integrates with a Big Data processing framework (e.g., Apache Kafka, Spark) for stream processing.
  - **Ontology Integration:** Detail the selection (or creation) of an ontology, such as using the Smart City Ontology (SCO) or OWL, and how data mapping will be managed.

- **Interoperability:**
  - **Protocol Support:** Identify the various communication protocols (REST, MQTT, etc.) required to support different IoT devices.
  - **API Design:** Develop clear API contracts for both internal services and external data providers.
  
- **Data Flow and Integration:**
  - **ETL/ELT Pipelines:** Plan for extracting, cleaning, transforming, and loading data.
  - **Heuristics for Data Cleaning:** Consider algorithms that automatically detect and correct inconsistencies or errors (e.g., typos, duplicate entries).

---

## 3. Implementation Details

- **Core Modules:**
  - **Data Integration Module:** Handle ingestion, mapping, and transformation of heterogeneous data.
  - **Aggregation Engine:** Develop or adopt a solution capable of real-time processing and aggregation.
  - **Ontology Mapping Tools:** Implement utilities for mapping incoming data to the predefined ontology, possibly leveraging Natural Language Processing (NLP) for automation.
  
- **User Interface:**
  - **Dashboard Design:** Create intuitive, real-time dashboards for visualizing aggregated data.
  - **Self-Service Tools:** Build interfaces that allow data providers to perform self-onboarding and monitor data quality.

- **Security Implementation:**
  - **Authentication/Authorization:** Code and integrate secure authentication mechanisms.
  - **Audit Trails & Logging:** Implement logging for monitoring data access and detecting potential breaches.
  - **Data Validation:** Include routines for validating data integrity before processing.

---

## 4. Modularity, Maintainability, and Extensibility

- **Modular Design:**
  - **Service Isolation:** Break the platform into clearly defined modules (e.g., ingestion, processing, visualization) that can be independently updated.
  - **Plug-In Architecture:** Consider designing an extensible system that allows additional data sources or processing modules to be integrated seamlessly.
  
- **Maintainability:**
  - **Documentation:** Maintain comprehensive documentation for APIs, modules, and overall system architecture.
  - **Testing Strategy:** Develop unit, integration, and end-to-end tests to ensure each component works as expected.
  - **CI/CD Pipelines:** Set up continuous integration and deployment processes to streamline future updates and bug fixes.

---

## 5. Testing and Evaluation

- **Testing Approaches:**
  - **Unit Testing:** Ensure that each module (data ingestion, mapping, security, etc.) functions correctly in isolation.
  - **Integration Testing:** Verify that modules interact correctly and that data flows seamlessly through the entire system.
  - **Performance and Stress Testing:** Simulate high data volumes and fast data streams to validate the platform’s scalability and robustness.
  - **Security Testing:** Conduct penetration tests and vulnerability assessments to ensure robust security measures.

- **Evaluation Metrics:**
  - **Performance Benchmarks:** Establish and track KPIs for latency, throughput, and real-time responsiveness.
  - **Data Quality:** Monitor and report on the success of data cleaning and error correction processes.
  - **User Feedback:** Incorporate testing sessions with potential end users and data providers to refine user interfaces and self-onboarding mechanisms.

---

## 6. Deployment and Operational Considerations

- **Deployment Strategy:**
  - **Cloud vs. On-Premise:** Decide on the deployment environment based on the scalability and resource requirements.
  - **Containerization:** Consider using Docker/Kubernetes for managing microservices and ensuring easy deployment and scalability.

- **Monitoring and Maintenance:**
  - **Real-Time Monitoring:** Implement dashboards for operational metrics and error logging.
  - **Backup and Recovery:** Plan for data backup routines and disaster recovery strategies.

- **Project Management:**
  - **Milestones and Timeline:** Create a roadmap with clear milestones for each development phase.
  - **Risk Assessment:** Identify potential risks (security breaches, data integration issues) and plan mitigation strategies.


## Other Ideas

- Develop a simulator for generating synthetic data to test the platform's scalability and performance under various conditions.
- Use Prometheus and Grafana as APIs for monitoring and visualizing system metrics.
- To validate whether the device is linked to the correct location, consider using geospatial data and algorithms.
- To start from MQTT, consider using the Mosquitto broker and Paho client libraries.
- Integrate WebVOWL for visualizing the ontology and its relationships. (https://service.tib.eu/webvowl/#file=m3-lite.owl)
- The values for building/address should be auto-completed based on already existing values in the system or to allow the user to select from a list of existing values.

## Tasks

- To handle the connection to the mqtt server before adding the new sensor (a device is a topic?)
- To add topic discovery mechanisms to identify available MQTT topics dynamically.
- To add some kind of learning guide to the frontend.
- To optimize the schema inference process.
- To integrate a module that supports multiple types of data sources.
- To store the inferred schema
- Schema inference should be coupled to the ingestion id and not used globally.
- To organize the data sources for the computations and to make all the computations dynamic. The average temperature should be registered when starting the application.
- Allow the user to enable streaming for the computations.
- To make a test with multiple temperature sensors.
- To make a test with another type of sensor.
- To use copilot for generation of computations.
- To create a feedback loop with the copilot from the user.
- To cleanup duplicated code.
- To configure copilot so it can easily access and utilize the logs and api responses.
- To profile the performance of the application to identify bottlenecks and optimize resource usage.

What would suggest to implement as an mobile app to complement the current platform?

What would you suggest to implement to satisfy at least 2 of dependability criteria?

Instead of using explicit threading, replace the thread pools with FastAPI's built-in async capabilities to handle concurrent requests more efficiently.

I want to allow the user to be able to enable streaming for their computation. Right now the user can only define the computation and run it once and the frontend has to refresh it. But I want the computation to becom a stream and store the result to a file and the frontend to fetch this result. Similar to have the average temperature works, I want to allow the user to define new such streams.

even after I have added a transformation for the templerature I do not see it reflected in the dashboard, as if the rule is ignored.

Can you please implement a mechanism to allow user to perform some basic data transformations (e.g., filtering, aggregation) on the incoming data before it is processed? Similar to key normalization but for values.

Can you please define a list of allowed unit measures and any new data should be validated against this list before being accepted?

Can you help me to build a copilot that will be aware of the frontend and backend context which will help the user to navigate and utilize the application more effectively? I want the copilot to provide clear guidance and suggestions based on the current state of the application, including available data sources, user actions, and system status.


The time until the computations began to be visible is too long. I need to investigate the cause and optimize the pipeline for faster results.

Can you help me to implement a log storage solution which allows for efficient querying and retrieval of logs based on various criteria (e.g., timestamp, sensor ID, log level)? I want that storage to be efficiently used by copilot when troubleshooting issues. Make sure to add more logging that will be stored in the log storage (for instance, debug logs are always stored but not displayed in the console). Update the copilot instructions file to reflect these changes.

Can you please help me to build a stream which will extract some metadata from the enriched fields and store it in sqlite? I want to be able to fetch this metadata faster than crawling through the entire dataset. For example I want to store the sensor id, ingestion id, and any other relevant metadata. Please use that table wherever the metadata is needed in the backend and replace the current crawling mechanism with efficient queries to the sqlite database.

Can you help me to make the frontend more smooth on changing pages, I want the requests to be cached and when the page loads to restore the previous state.

When sending a more resourceful request to the backend, all other requests are blocked until the resourceful request is completed. Is there a way to allow concurrent requests to be processed without waiting for the resourceful request to finish?

I want to force the user to register a normalization rule which will ensure that the registered device have a valid sensor ID. This means that the code should validate the raw data if it contains the sensorId field or that any rule referencing the sensor ID exists. If not, the user should be prompted to create a new normalization rule. This change should be reflected in the UI, guiding the user to create the necessary normalization rule before proceeding with the registration. This change should ensure that the registered device has a valid sensor ID.

I want to store the sensors that failed validation in a separate table in the SQLite database. This table should include the sensor ID, ingestion ID, and any error messages or reasons for the failure. This will allow for easier troubleshooting and reprocessing of failed sensors. Implement the necessary database schema and logic to support this feature. Also implement the feature in UI to display the failed sensors and allow for reprocessing. Include in this table also the devices that are missing the sensor ID or ingestion ID.

Can you help me to implement a feature wich will monitorin the healthiness of the all the applications in my cluster? Once an issue is detected, the monitoring app should check the logs of that app and send the logs to copilot to build a prompt the developer can use in copilot to troubleshoot and resolve the issue. The issues should be added to a markdown file to the local of the developer. The notification should be smart, to not duplicate issues and to not overwhelm the developer with too many notifications. Also, make sure to add the important logs to the notifications.

Can you help me to make the UI more friendly to the user? I want to have tooltips to help the user understand what he can do using a certain component.

  To log access to sensitive data, I want to implement an audit logging mechanism that records every access to sensitive data along with the user who accessed it, the timestamp, and the reason for access. This log should be stored securely and should be tamper-proof.

Use a lib to handle caching of the ingestor schema to avoid fetching it every time from backend.

there was a lot of metrics code added to backend and ingestor, can you help me to make it cleaner and easier to maintain?

Instead of calculating the latency while processing the data, I would like to calculate it in a separate thread directly from minio. Meaning that the enrichment latency is calculated by calculating the difference between the timestamp (from the data) and the enrichment time (from minio object metadata). Similar to aggregation latency, the average temperature data should have a field called timestamp (lowest timestamp from the data used to calculate the average) and the aggregation time (from minio object metadata). Using these two fields we can calculate the end-to-end latency from ingestion to enrichment/aggregation.

I want to understand why it takes 5 minutes for data to go from ingestion to gold layer, can you help me to profile this flow? the enrichment time is around 1m, meaning that 4min takes for data to reach gold

Can you help me to learn about the options to enable https for the services deployed in the AKS cluster? I want to understand the pros and cons of each option and how to implement them.
I'm looking for a solution that is easy to integrate, for instance using nginx ingress controller with cert-manager. I might also consider using Azure Application Gateway Ingress Controller if it provides a better integration with Azure services. An option is also using self-signed certificates, but I want to understand the implications of using self-signed certificates in terms of security and user experience. Also, I would like to know how create a single domain that will route to all the services in the cluster.


I would like to implement a feature that allows me to visualize the checkpoint status of each Spark streaming job in the frontend dashboard. This feature should provide insights into the last checkpoint time, the size of the checkpoint data, and any errors or warnings related to checkpointing. The goal is to help monitor the health and performance of the streaming jobs and ensure that they are functioning correctly with respect to checkpointing. This feature should allow me to track the files that were not yet processed based on the checkpoints.

There is a bug in the code related to authorization. Even when a user is not authenticated, he can register new devices. Can you help me to fix this issue?
Request URL
http://localhost:8000/api/devices
Request Method
POST
Status Code
401 Unauthorized
Remote Address
[::1]:8000
Referrer Policy
strict-origin-when-cross-origin
{
  "enabled": true,
  "sensitivity": "internal",
  "data_retention_days": 90,
  "ingestion_id": "c2b7904e_local_simulators_mqtt_mqtt_smartcity_sensors_temperature",
  "name": "c2b7904e_local_simulators_mqtt_mqtt_smartcity_sensors_temperature",
  "description": "",
  "created_by": "admin"
}

To replace the dsl used to build new computations with a more user-friendly interface in the frontend. It would be good to have something to check the syntax and to provide suggestions to the user while writing the computation.

I want to make sure that the files displayed in the data browser are always sorted by the creation time, with the most recent files appearing at the top. This will help users to easily find and access the latest data files without having to scroll through older files.

When a new field is being reported it is ignored because the enrichment stream is not restarted. I want to implement a mechanism to automatically detect when new fields are being reported and to restart the enrichment stream to take into account these new fields. This mechanism should be efficient and should not cause unnecessary restarts of the enrichment stream.


## Completed

[completed] I want to implement CI/CD pipelines for the entire infrastructure, including azure AKS deployment, using github actions. Can you help me to build the necessary scripts and workflows to automate the deployment process? I want it to include multiple stages such as image building, deployment to AKS, etc. Also it should allow me to easily rollback to previous versions in case of issues. The only concern is that the images caches won't be used properly in github actions, can you help me to optimize that?

[completed] To implement a mechanism that will allow me to switch between users with different roles easily for testing purposes. This mechanism should be available in the frontend, allowing me to select a user role from a dropdown menu and switch the current user context accordingly. This will help in testing the access control features of the application. Use predefined users that are created by the backend for testing purposes.

[completed] Can you please scan all the places in the backend and update the code to use type hints for better clarity and maintainability? 

[completed] Considering the dynamic schema, I want to get rid of get_comprehensive_raw_schema. 

[completed] When registering a new device the code should not yet care about the device sensor id, at this point it should only consider ingestion id because it's the only identifier needed for the initial registration process. The sensor id should become available only after the device has been successfully registered and the normalization rules allows the application to correctly identify the sensor id. 

[completed] Can you please build a mechanism to preview the normalized data before it is applied during the enrichment process? 

[completed] Can you please update the start_enrichment_stream to not assume that any field exists, there are various devices and different reported data, it should be agnostic of the device the data is coming from. it should only apply the normalization rules if the columns exists. 

[completed] Are the parquet files bound to only one schema and does not allow dynamic schema? I'm asking you this because I have multiple sensors and I want the code to be agnostic of the data source, I should allow the user to dinamically define some cleanup rules which he will use for creating new computations. 

[completed] Can you please add a smart normalization rule assistant which will suggest normalization rules based on the incoming data and its context? For context use the data itself and other data sources. Implement a feedback loop to improve the suggestions over time. Also implement this feature in the UI so that user can use the suggestions. 

[completed] I want to display in the Spark Applications & Cluster Status also the running streams, can you help me to implement it in both the frontend and backend?

[completed] Can you please make another spark stream in the backend which will continuosly infer the schema from the new bronze files and store the results to sqlite?

[completed] To improve the `Enrichment Status` tile, it can have more detailed information about the enrichment process, such as the number of records processed, the number of records failed, and the duration of the enrichment process.

[completed] Can you please help me to infer the schema of the sensor in the ingestor when the raw data is being stored? Do not use spark in the ingestor, do some basic type inference based on the raw data and store it in the minio. The backend should be able to access this schema information when processing the data.

[completed] Can you help me to diversify the data sources by integrating additional data connectors (e.g., REST APIs, databases) into the ingestor? Start with rest apis, but befor that I want you to build a plan for making the ingestor more modular and extensible for new data sources. Including updating the frontend to allow the user registering new data sources from the frontend.

[completed] The preview of a time series looks like a table chart, can you help me to fix this?

[completed] The ingestor is configured to scale out based on cpu usage, but in my tests I have seen that each ingestor pod is considered a subscripriber and because of the mqtt fan-out mechanism, each pod receives all the messages. This means that if I have 4 ingestor pods and I send 2000 msg/s, the "Total Messages Received" will show ~8000 msg/s (4 × 2000). I want to adjust the ingestor to read from mqtt in a way that each pod receives only a portion of the messages, so that the total messages received is equal to the messages sent. Can you help me to implement this?


[completed] Landing page in the frontend is too basic, can you help me to make it more appealing? Also, it should support navigating to other applications in the cluster even when the infrastructure is deployed to azure. Meaning that localhost links should be replaced with the actual service urls.

[completed] I want to understand how spark checkpoints work in the current implementation. Can you help me to explain how the checkpoints are created, stored, and used for recovery in case of failures? I want to ensure that the checkpointing mechanism is robust and can handle various failure scenarios effectively. I want to understand why there are no checkpoints for the enrichment stream. Also, I want to understand how to troubleshoot issues related to checkpointing and what best practices should be followed to optimize the checkpointing process. Also, I want to understand whether it's a good idea to implement a custom checkpointing mechanism for better control over the recovery process.

[completed] Can you help me to refactor the AuthContext.tx? It's too big and has too many responsibilities. I want to split it into smaller components with single responsibility.

[completed] Update the skafold to check if the tls setup is already done before starting the infrastructure, to avoid inbestigating issues related to tls every time the infrastructure is restarted. Also, add a command to the skaffold to setup tls, so that it can be easily done when needed.