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

- To handle the connection to the mqttt server before adding the new sensor (a device is a topic?)
- To make the data integration store raw data in the minio and spark to stream the cleaned data to the silver layer and then to the gold layer after the aggregation.