# Architecture for Big Data - Vladislav Tiftilov

```plantuml
@startuml
!theme plain
skinparam defaultTextAlignment center
skinparam linetype ortho
skinparam nodesep 80
skinparam ranksep 60
skinparam rectangle {
    BackgroundColor #E3F2FD
    BorderColor Black
    FontSize 11
}
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
        rectangle "Sensors" as S #E3F2FD
        rectangle "Local Buffer" as LB #E3F2FD
        S -[hidden]right-> LB
        S -[hidden]right-> LB
    }

    cloud "Azure Cloud" {
        rectangle "Azure Service Bus" as ASB #E8F5E9
        
        package "Kubernetes Cluster" {
            package "Ingestion Layer" {
                rectangle "MQTT Server" as MQTT #E8F5E9
                rectangle "Ingestor\n1..N" as ING #E8F5E9
            }

            package "Processing Layer" {
                rectangle "Spark Master" as SM #FFF9C4
                rectangle "Spark Workers\n1..N" as SW #FFF9C4
            }

            package "Storage Layer" {
                rectangle "MinIO Cluster\n1..3" as MINIO #FFE0B2
            }

            ' Second Row - Application and Monitoring
            together {
                package "Application Layer" {
                    rectangle "Frontend" as FE #E1BEE7
                    rectangle "Backend" as BE #E1BEE7
                    BE -[hidden]right-> FE
                }
                
                package "Monitoring Stack" {
                    rectangle "Prometheus" as PROM #F3E5F5
                    rectangle "Grafana" as GRAF #F3E5F5
                    rectangle "cAdvisor" as CADV #F3E5F5
                    PROM -[hidden]right-> GRAF
                }
            }
        }
    }
}

' Data Flow
S -right-> LB : offline\nbuffer
S -down-> ASB
LB -right-> MQTT
MQTT -right-> ING
ASB -right-> ING
ING -right-> SM
SM -right-> SW
SW -right-> MINIO
FE -right-> BE
BE -right-> SW
BE -right-> MINIO

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

**Threats**: Packet loss/corruption, message duplication, out-of-order delivery, storage corruption

**Implementation**:
- SHA256 checksums for corruption detection
- Sequence numbers for duplicate/missing detection
- Acknowledgment-based retries
- Idempotent processing with deduplication