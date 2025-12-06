# Architecture for Big Data - Vladislav Tiftilov

```plantuml

@startuml
!theme plain
skinparam defaultTextAlignment center
skinparam linetype polyline
skinparam nodesep 80
skinparam ranksep 60
skinparam package {
    BackgroundColor White
    BorderColor Black
}
skinparam cloud {
    BackgroundColor #E1F5FE
    BorderColor #01579B
    BorderThickness 3
    FontSize 12
    FontStyle bold
}

' First Row - Application Layers
together {
    package "Edge Layer" {
        rectangle "Sensors" as S
        rectangle "(A1) Local Buffer" as LB #E3F2FD
        S -[hidden]right-> LB
    }

    cloud "Azure Cloud" {
     
   
        package "Kubernetes Cluster" {
            package "Ingestion Layer" {
                rectangle "MQTT Server" as MQTT
                rectangle "(A2) Ingestor\n1..N" as ING #E3F2FD
                MQTT -[hidden]right-> ING

            }

            package "Storage Layer" {
                rectangle "(A3,R2) MinIO Cluster\n1..3" as MINIO #E3F2FD\E8F5E9
            }

            package "Processing Layer" {
                rectangle "Spark Master" as SM
                rectangle "Spark Workers\n1..N" as SW
            }



            ' Second Row - Application and Monitoring
            together {
                package "Application Layer" {
                    rectangle "(R1,R3) Frontend" as FE #E8F5E9
                    rectangle "(R1,R3) Backend" as BE #E8F5E9
                    BE -[hidden]right-> FE
                }
                
                package "Monitoring Stack" {
                    rectangle "Prometheus" as PROM
                    rectangle "Grafana" as GRAF
                    rectangle "cAdvisor" as CADV
                    PROM -[hidden]right-> GRAF
                }
            }
        }
    }
}

' Data Flow
S -right-> LB : offline\nbuffer
S -down-> ING
LB --> MQTT
MQTT -right-> ING
ING -right-> MINIO
SM <-> SW
SW <-> MINIO
FE <-> BE
BE <-> SM


' Metrics Flow
MQTT -[#blue,dotted]down-> PROM
ING -[#blue,dotted]down-> PROM
SM -[#blue,dotted]down-> PROM : metrics
SW -[#blue,dotted]down-> PROM
MINIO -[#blue,dotted]down-> PROM
CADV -right-> PROM : container\nmetrics
PROM -right-> GRAF
@enduml
```

## Dependability Criteria

### 1. **Availability**
System remains operational and accessible despite failures.

**Threats**: MQTT/Service Bus disconnections, Spark/storage failures, network partitions

**Implementation**:
- Local buffer at edge for offline tolerance
- Auto-scaling ingestor instances for load handling
- Azure Service Bus with built-in high availability
- Spark workers auto-scaling (2-10 instances) based on load
- MinIO 3-node cluster for storage redundancy
- Health monitoring and auto-restart

### 2. **Reliability**
System delivers correct, uncorrupted data without loss.

**Threats**: Storage corruption, data loss during transmission

**Implementation**:
- User authentication and authorization
- Sensor authentication via MQTT client certificates
- User authentication through Azure AD integration
- Data labeling with source metadata and quality scores
- Automated backup policies with 30-day retention in MinIO
- Point-in-time recovery capability for critical data
